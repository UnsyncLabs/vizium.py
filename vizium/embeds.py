"""Embed helpers that produce content understood by the Vizium web client."""

from dataclasses import dataclass, field
import re
from typing import Optional


_YOUTUBE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([\w-]{11})"
)


@dataclass
class Embed:
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    color: Optional[str] = None
    fields: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def youtube(cls, url: str, title: Optional[str] = None) -> "Embed":
        """Create an embed whose URL triggers Vizium's sandboxed YouTube frame."""
        if not _YOUTUBE.search(url):
            raise ValueError("Expected a supported YouTube URL")
        return cls(title=title or "YouTube Video", url=url)

    def add_field(self, name: str, value: str) -> "Embed":
        self.fields.append((name, value))
        return self

    def to_content(self) -> str:
        """Render safe text/URLs; the web client detects YouTube URLs itself."""
        lines = [part for part in (self.title, self.description) if part]
        lines.extend(f"**{name}**\n{value}" for name, value in self.fields)
        if self.url:
            lines.append(self.url)
        return "\n".join(lines)

    def to_payload(self) -> dict:
        payload = {
            key: value
            for key, value in {
                "title": self.title,
                "description": self.description,
                "url": self.url,
                "color": self.color,
            }.items()
            if value
        }
        if self.fields:
            payload["fields"] = [{"name": name, "value": value} for name, value in self.fields]
        match = _YOUTUBE.search(self.url or "")
        if match:
            video_id = match.group(1)
            payload.update({
                "color": "#FF0000",
                "image": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                "video": {"url": f"https://www.youtube.com/embed/{video_id}?autoplay=1&modestbranding=1&rel=0", "platform": "youtube"},
            })
        return payload
