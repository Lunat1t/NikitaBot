"""Data models for scraped Instagram media and reels."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import datetime as dt
from typing import Any


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass
class ScrapedReel:
    shortcode: str
    url: str
    author: str
    caption: str
    timestamp: str
    video_url: str | None = None
    thumbnail_url: str | None = None
    likes_count: int = 0
    comments_count: int = 0
    views_count: int = 0
    duration_seconds: float | None = None
    is_video: bool = True
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScraperResult:
    status: str  # "success", "partial", "error", "rate_limited"
    target_username: str
    reels: list[ScrapedReel] = field(default_factory=list)
    count: int = 0
    error_message: str | None = None
    scraped_at: str = field(default_factory=utcnow)
    source: str = "instaloader"

    def __post_init__(self):
        if not self.count:
            self.count = len(self.reels)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "target_username": self.target_username,
            "count": self.count,
            "error_message": self.error_message,
            "scraped_at": self.scraped_at,
            "reels": [r.to_dict() for r in self.reels]
        }
