from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .embeds import Embed
from .exceptions import UnsupportedOperation
from .guild import Guild

if TYPE_CHECKING:
    from .client import Bot


class Channel:
    """A subscribed text channel inside a Vizium guild."""

    def __init__(self, channel_id: str, client: "Bot", guild_id: str):
        self._channel_id = str(channel_id)
        self._client = client
        self._guild_id = str(guild_id)
        self._ws = None
        self._connected = False
        self._messages = {}

    @property
    def id(self) -> str:
        return self._channel_id

    @property
    def name(self) -> str:
        """Compatibility display name; it is the channel identifier."""
        return self._channel_id

    @property
    def guild_id(self) -> str:
        return self._guild_id

    @property
    def client(self) -> "Bot":
        return self._client

    @property
    def guild(self) -> Guild:
        return Guild(self.guild_id, self.client, self.id)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def history(self):
        return list(self._messages.values())

    async def send_msg(self, text: str, html: bool = False, reply: int = 0, delete_after: float = 0.0):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Message text is required")
        await self._send({"op": "message", "channel": self.id, "data": {"content": text}, "nonce": f"bot-{time.time_ns()}"})
        if delete_after:
            raise UnsupportedOperation("delete_after needs message acknowledgements and is not available yet")

    async def send_message(self, content: str = "", *, embed: Embed | None = None):
        """Send text and/or one embed to this exact channel."""
        if not content.strip() and not embed:
            raise ValueError("content or embed is required")
        return await self.client.send_message(self.guild_id, self.id, content, embed=embed)

    async def send_embed(self, embed: Embed):
        return await self.send_message(embed=embed)

    async def edit(self, *, name: str | None = None, topic: str | None = None, slow_mode_seconds: int | None = None):
        settings = {key: value for key, value in {"name": name, "topic": topic, "slow_mode_seconds": slow_mode_seconds}.items() if value is not None}
        if not settings:
            raise ValueError("Provide name, topic, or slow_mode_seconds")
        return await self.client.update_channel(self.id, **settings)

    async def delete(self):
        await self.client.delete_channel(self.id)

    async def typing(self):
        await self._send({"op": "typing", "channel": self.id})

    async def _send(self, payload: dict):
        if not self._ws or self._ws.closed:
            raise ConnectionError("Channel is not connected")
        await self._ws.send_json(payload)

    async def close(self):
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._connected = False

    async def delete_user(self, username: str):
        raise UnsupportedOperation("Use Vizium's guild moderation API and role permissions")

    async def clear_all(self):
        raise UnsupportedOperation("Bulk channel deletion is not available to bot tokens")

    async def ban(self, username: str):
        raise UnsupportedOperation("Use Vizium's guild moderation API and role permissions")
