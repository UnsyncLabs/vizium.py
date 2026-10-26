from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class User:
    """Minimal Vizium chat identity delivered by message events."""

    id: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_bot: bool = False

    @property
    def showname(self) -> str:
        return self.name or self.id

    @property
    def mention(self) -> str:
        return f"@{self.showname}"
