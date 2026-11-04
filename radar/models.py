from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Signal:
    """One collected item. Author handles and names are deliberately not stored."""

    source: str  # e.g. "hackernews", "rss:techcabal"
    kind: str  # community | news | vendor | regulator
    item_id: str
    title: str
    text: str
    link: str
    published: datetime  # timezone-aware, UTC
    engagement: float | None  # None means unknown, never zero
    query: str

    @property
    def key(self) -> str:
        return f"{self.source}:{self.item_id}"


@dataclass
class CollectResult:
    signals: list[Signal]
    skipped: int = 0  # items dropped because a required field was missing
    note: str = ""
