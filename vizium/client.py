from __future__ import annotations

import asyncio
import logging
from typing import Iterable, Optional

import aiohttp

from . import constants
from .exceptions import AlreadyConnected, InvalidChannel, InvalidToken
from .handler import MessageHandler
from .message import Message
from .channel import Channel
from .guild import Guild
from .user import User
from .utils import websocket_base


class Bot(MessageHandler):
    """Async Vizium bot client authenticated by a generated bot token."""

    def __init__(self, forever: bool = True, guild_id: Optional[str] = None, api_base_url: str = constants.API_URL, websocket_base_url: Optional[str] = None):
        super().__init__()
        self._forever = forever
        self._guild_id = guild_id
        self._api_base_url = api_base_url.rstrip("/")
        self._websocket_base_url = websocket_base_url.rstrip("/") if websocket_base_url else None
        self._token = None
        self._access_token = None
        self._channels: dict[str, Channel] = {}
        self._dm_channels: dict[str, Channel] = {}
        self._global_ws = None
        self._guilds: dict[str, Guild] = {}
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._guild_sync_interval = 15.0
        self._guilds_loaded = False

    @property
    def channels(self):
        return list(self._channels.keys())

    @property
    def guilds(self) -> list[Guild]:
        """Guilds where this bot is currently installed.

        The collection is populated automatically by :meth:`start` and kept in
        sync while the client is running. Call :meth:`sync_guilds` to refresh
        it immediately after an out-of-band installation.
        """
        return list(self._guilds.values())

    def login(self, token: str, password=None, loop=None):
        """Set the opaque `vzb_` token. Passwords are intentionally unused."""
        if not isinstance(token, str) or not token.startswith("vzb_"):
            raise InvalidToken("Expected a generated Vizium bot token (vzb_...)")
        self._token = token

    def add_task(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task

    async def _get_new_session(self):
        if not self._token:
            raise InvalidToken("Call login(bot_token) before start()")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._api_base_url}{constants.BOT_TOKEN_EXCHANGE_PATH}",
                json={"token": self._token},
            ) as response:
                if response.status != 200:
                    raise InvalidToken("Vizium rejected the bot token")
                self._access_token = (await response.json())["access_token"]

    async def start(
        self,
        *,
        channels: Iterable = (),
        forever: bool = True,
        pm: bool = True,
        auto_discover: bool = True,
        guild_sync_interval: float = 15.0,
    ):
        """Start the client and, by default, discover every installed guild.

        ``channels`` remains available for a deliberately narrow/manual
        connection. With ``auto_discover=True`` (the default), the library
        queries the Hub for the bot's guilds, subscribes to their visible text
        channels, and keeps polling for newly authorized guilds.
        """
        await self._call_event("init")
        await self._get_new_session()
        self._running = True
        self._guild_sync_interval = max(float(guild_sync_interval), 1.0)
        self._message_task = asyncio.create_task(self._handle_messages())
        for channel in channels:
            if isinstance(channel, tuple) and len(channel) == 2:
                self.join_channel(channel[1], guild_id=channel[0])
            else:
                self.join_channel(channel)
        if auto_discover:
            await self.sync_guilds()
            self.add_task(self._watch_guilds())
        if pm:
            self.add_task(self._watch_direct_messages())
            self.add_task(self._watch_dm_subscriptions())
        await self._call_event("start")
        if forever:
            await asyncio.gather(*self._tasks)

    async def stop_all(self):
        self._running = False
        for channel in list(self._channels.values()):
            await channel.close()
        if self._global_ws and not self._global_ws.closed:
            await self._global_ws.close()
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._message_task:
            self._message_task.cancel()

    def join_channel(self, channel_id, guild_id: Optional[str] = None):
        target_guild = guild_id or self._guild_id
        if not target_guild:
            raise InvalidChannel("Provide Bot(guild_id=...) or join_channel(channel_id, guild_id=...)")
        channel_id = str(channel_id)
        if channel_id in self._channels:
            raise AlreadyConnected(f"Already connected to channel {channel_id}")
        channel = Channel(channel_id, self, str(target_guild))
        self._channels[channel_id] = channel
        self.add_task(self._watch_channel(channel))
        return channel

    def leave_channel(self, channel_id):
        channel = self._channels.pop(str(channel_id), None)
        if channel:
            self.add_task(channel.close())

    def get_channel(self, channel_id):
        return self._channels.get(str(channel_id))

    def get_guild(self, guild_id: str, channel_id: str | None = None) -> Guild:
        guild = self._guilds.get(str(guild_id))
        if guild and channel_id is None:
            return guild
        return Guild(guild_id, self, channel_id, name=guild.name if guild else None)

    async def fetch_guilds(self) -> list[Guild]:
        """Fetch the bot's installed guilds from the authenticated Hub API."""
        servers = await self._api_request("GET", "/api/v1/chat/servers")
        guilds = []
        for server in servers:
            guild_id = str(server.get("server_id") or server.get("id") or "")
            if not guild_id:
                continue
            guilds.append(
                Guild(
                    guild_id,
                    self,
                    name=server.get("server_name") or server.get("name"),
                )
            )
        return guilds

    async def sync_guilds(self) -> list[Guild]:
        """Synchronize installed guilds and their text-channel subscriptions.

        ``on_guild_available(guild)`` is emitted for guilds found on the first
        sync; ``on_guild_join(guild)`` is emitted when an installation appears
        later. ``on_guild_remove(guild)`` is emitted when it disappears.
        """
        fetched = {guild.id: guild for guild in await self.fetch_guilds()}
        previous = dict(self._guilds)
        is_initial_sync = not self._guilds_loaded
        self._guilds = fetched

        for guild_id, guild in fetched.items():
            is_new = guild_id not in previous
            try:
                channels = await guild.channels()
                for item in channels:
                    if item.get("channel_type") != "text":
                        continue
                    channel_id = str(item.get("channel_id") or item.get("id") or "")
                    if channel_id and channel_id not in self._channels:
                        self.join_channel(channel_id, guild_id=guild.id)
            except Exception as exc:
                await self._call_event("error", guild, exc)

            if is_new:
                await self._call_event("guild_available" if is_initial_sync else "guild_join", guild)

        for guild_id, guild in previous.items():
            if guild_id in fetched:
                continue
            for channel_id, channel in list(self._channels.items()):
                if channel.guild_id == guild_id:
                    self.leave_channel(channel_id)
            await self._call_event("guild_remove", guild)

        self._guilds_loaded = True
        return self.guilds

    async def _watch_guilds(self):
        while self._running:
            await asyncio.sleep(self._guild_sync_interval)
            if not self._running:
                break
            try:
                await self.sync_guilds()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                await self._call_event("error", None, exc)
                logging.getLogger(__name__).warning("Guild synchronization failed: %s", exc)

    async def _sync_direct_messages(self):
        """Discover DMs and subscribe to them on the authenticated global WS."""
        for item in await self._api_request("GET", "/api/v1/chat/dm"):
            channel_id = str(item.get("channel_id") or "")
            if not channel_id:
                continue
            channel = self._dm_channels.setdefault(
                channel_id, Channel(channel_id, self, "__dm__")
            )
            if self._global_ws and not self._global_ws.closed:
                await self._global_ws.send_json({"op": "subscribe", "channel": channel.id})

    async def _watch_dm_subscriptions(self):
        while self._running:
            try:
                if self._global_ws and not self._global_ws.closed:
                    await self._sync_direct_messages()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                await self._call_event("error", None, exc)
            await asyncio.sleep(self._guild_sync_interval)

    async def _watch_direct_messages(self):
        reconnecting = False
        while self._running:
            try:
                await self._get_new_session()
                base = await self._resolve_websocket_base()
                url = f"{websocket_base(base)}/ws/user"
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, heartbeat=30) as ws:
                        self._global_ws = ws
                        await ws.send_json({"op": "auth", "token": self._access_token})
                        async for incoming in ws:
                            if incoming.type != aiohttp.WSMsgType.TEXT:
                                break
                            event = incoming.json()
                            if event.get("op") == "hello":
                                await self._sync_direct_messages()
                                await self._call_event("dm_connect" if not reconnecting else "dm_reconnect")
                                continue
                            channel_id = str(event.get("channel") or "")
                            if event.get("op") == "message" and channel_id:
                                channel = self._dm_channels.setdefault(
                                    channel_id, Channel(channel_id, self, "__dm__")
                                )
                                await self._handle_ws_event(channel, event)
                            elif event.get("op") == "typing":
                                await self._call_event("typing", self._dm_channels.get(channel_id), event.get("data") or {})
                        self._global_ws = None
            except asyncio.CancelledError:
                break
            except Exception as exc:
                await self._call_event("error", None, exc)
                logging.getLogger(__name__).warning("Direct-message socket disconnected: %s", exc)
            if self._running:
                reconnecting = True
                await asyncio.sleep(3)

    async def send_message(self, guild_id: str, channel_id: str, content: str = "", *, embed=None):
        """Send through the REST API; works before a WebSocket is connected."""
        payload = {"content": content or (embed.to_content() if embed else ""), "embeds": [embed.to_payload()] if embed else []}
        return await self._api_request("POST", f"/api/v1/chat/channels/{channel_id}/messages", payload)

    async def get_permissions(self, guild_id: str):
        if not self._access_token:
            await self._get_new_session()
        payload = self._access_token.split(".")[1]
        import base64, json
        payload += "=" * (-len(payload) % 4)
        bot_id = json.loads(base64.urlsafe_b64decode(payload))["sub"]
        return await self._api_request("GET", f"/api/v1/chat/servers/{guild_id}/members/{bot_id}/permissions")

    async def delete_message(self, channel_id: str, message_id: str):
        await self._api_request("DELETE", f"/api/v1/chat/channels/{channel_id}/messages/{message_id}")

    async def edit_message(self, channel_id: str, message_id: str, content: str):
        """Edit one of this bot's own messages."""
        return await self._api_request(
            "PATCH", f"/api/v1/chat/channels/{channel_id}/messages/{message_id}",
            {"content": content},
        )

    async def update_channel(self, channel_id: str, **settings):
        return await self._api_request("PATCH", f"/api/v1/chat/channels/{channel_id}", settings)

    async def delete_channel(self, channel_id: str):
        await self._api_request("DELETE", f"/api/v1/chat/channels/{channel_id}")

    async def reorder_channels(self, guild_id: str, channels: list[dict]):
        await self._api_request("PUT", f"/api/v1/chat/servers/{guild_id}/channels/reorder", {"channels": channels})

    async def _api_request(self, method: str, path: str, body=None):
        if not self._access_token:
            await self._get_new_session()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.request(method, f"{self._api_base_url}{path}", json=body) as response:
                if response.status == 401:
                    await self._get_new_session()
                    return await self._api_request(method, path, body)
                if response.status >= 400:
                    raise RuntimeError(f"Vizium API error {response.status}: {await response.text()}")
                if response.status == 204:
                    return None
                return await response.json()

    async def _resolve_websocket_base(self) -> str:
        """Use the Hub-advertised WebSocket origin, with a same-origin fallback."""
        if self._websocket_base_url:
            return self._websocket_base_url
        try:
            config = await self._api_request("GET", "/api/v1/chat/websocket-config")
            if config.get("url"):
                return str(config["url"]).rstrip("/")
        except Exception:
            pass
        return self._api_base_url

    async def _watch_channel(self, channel: Channel):
        reconnecting = False
        while self._running:
            try:
                # A bot access JWT is deliberately short-lived. Re-exchange the
                # opaque token for every new WebSocket connection/reconnect.
                await self._get_new_session()
                base = await self._resolve_websocket_base()
                url = f"{websocket_base(base)}/server/{channel.guild_id}/ws"
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, heartbeat=30) as ws:
                        channel._ws = ws
                        await ws.send_json({"op": "auth", "token": self._access_token})
                        await ws.send_json({"op": "subscribe", "channel": channel.id})
                        async for incoming in ws:
                            if incoming.type != aiohttp.WSMsgType.TEXT:
                                break
                            await self._handle_ws_event(channel, incoming.json())
                            if not channel.connected:
                                channel._connected = True
                                await self._call_event("reconnect" if reconnecting else "connect", channel)
                        channel._connected = False
            except asyncio.CancelledError:
                break
            except Exception as exc:
                await self._call_event("error", channel, exc)
                logging.getLogger(__name__).warning("Channel %s disconnected: %s", channel.name, exc)
            if self._running:
                reconnecting = True
                await asyncio.sleep(3)
        channel._connected = False
        await self._call_event("disconnect", channel)

    async def _handle_ws_event(self, channel: Channel, event: dict):
        op = event.get("op")
        data = event.get("data") or {}
        if op == "message":
            message = Message(
                id=str(data.get("message_id", "")),
                channel=channel,
                user=User(id=str(data.get("author_id", ""))),
                body=str(data.get("content", "")),
                time=str(data.get("timestamp", "")),
                raw=event,
            )
            channel._messages[message.id] = message
            await self._add_message(message)
        elif op == "typing":
            await self._call_event("typing", channel, data)
        elif op == "presence":
            await self._call_event("presence", channel, data)
        elif op == "voice_state_update":
            await self._call_event("voice_state_update", channel, data)
        elif op == "error":
            await self._call_event("error", channel, RuntimeError(data.get("message", "Unknown WebSocket error")))
