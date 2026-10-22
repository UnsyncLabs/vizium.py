from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .exceptions import UnsupportedOperation
from .user import User

if TYPE_CHECKING:
    from .channel import Channel


@dataclass
class Message:
    id: str
    channel: "Channel"
    user: User
    body: str
    time: str
    raw: dict

    @property
    def tid(self) -> str:
        return self.id

    @property
    def guild(self):
        return self.channel.guild

    @property
    def channel_id(self) -> str:
        return self.channel.id

    def is_dm(self) -> bool:
        """Return ``True`` when this message arrived through a direct message."""
        return self.channel.guild_id == "__dm__"

    async def reply(self, content: str = "", *, embed=None):
        """Reply in the same channel that delivered this message."""
        return await self.channel.send_message(content, embed=embed)

    async def delete(self) -> None:
        await self.channel.client.delete_message(self.channel.id, self.id)

    async def edit(self, text: str):
        """Edit this bot's own message in its original channel."""
        return await self.channel.client.edit_message(self.channel.id, self.id, text)
