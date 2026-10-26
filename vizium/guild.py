from __future__ import annotations

from typing import TYPE_CHECKING

from .embeds import Embed

if TYPE_CHECKING:
    from .client import Bot


class Guild:
    """A Vizium guild, optionally bound to the channel that raised an event."""

    def __init__(self, guild_id: str, client: "Bot", channel_id: str | None = None, name: str | None = None,
                 instance: str | None = None):
        self.id = str(guild_id)
        self.client = client
        self.channel_id = str(channel_id) if channel_id is not None else None
        self.name = name
        # Domain of the self-hosted instance serving this guild (None: the Hub)
        self.instance = instance

    async def channels(self) -> list[dict]:
        return await self.client._api_request("GET", f"/api/v1/chat/servers/{self.id}/channels", guild_id=self.id)

    async def members(self) -> list[dict]:
        return await self.client._api_request("GET", f"/api/v1/chat/servers/{self.id}/members", guild_id=self.id)

    async def roles(self) -> list[dict]:
        return await self.client._api_request("GET", f"/api/v1/chat/servers/{self.id}/roles", guild_id=self.id)

    async def create_channel(self, name: str, channel_type: str = "text", *, topic: str = "", slow_mode_seconds: int = 0):
        return await self.client._api_request("POST", f"/api/v1/chat/servers/{self.id}/channels", {
            "name": name, "channel_type": channel_type, "topic": topic, "slow_mode_seconds": slow_mode_seconds,
        }, guild_id=self.id)

    async def reorder_channels(self, channels: list[dict]):
        await self.client.reorder_channels(self.id, channels)

    async def send_message(self, content: str = "", *, embed: Embed | None = None, channel_id: str | None = None):
        target = channel_id or self.channel_id
        if not target:
            raise ValueError("Provide channel_id or use message.guild inside on_message")
        return await self.client.send_message(self.id, target, content, embed=embed)
