"""RSS and Atom parsing, plus the collectors built on it (feeds, Google News, Anthropic sitemap)."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from .. import config
from ..http import FetchError, fetch
from ..models import CollectResult, Signal

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _local(c.tag) == name]


def _first_text(el: ET.Element, *names: str) -> str:
    for name in names:
        for child in _children(el, name):
            if child.text and child.text.strip():
                return child.text.strip()
    return ""


def clean_text(raw: str, limit: int = 600) -> str:
    text = html.unescape(_TAG_RE.sub(" ", raw or ""))
    return _SPACE_RE.sub(" ", text).strip()[:limit]


def parse_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_feed(data: bytes) -> list[dict]:
    """Return entries as dicts: title, link, summary, published (datetime|None), id.

    Raises ET.ParseError on malformed XML and ValueError on an unknown document type.
    """
    root = ET.fromstring(data)
    kind = _local(root.tag)
    if kind == "rss":
        channel = _children(root, "channel")
        items = _children(channel[0], "item") if channel else []
    elif kind == "feed":
        items = _children(root, "entry")
    else:
        raise ValueError(f"not an RSS or Atom document (root element: {kind})")

    entries = []
    for item in items:
        link = _first_text(item, "link")
        if not link:
            for link_el in _children(item, "link"):
                if link_el.get("rel", "alternate") == "alternate" and link_el.get("href"):
                    link = link_el.get("href", "").strip()
                    break
        entries.append(
            {
                "title": clean_text(_first_text(item, "title"), 300),
                "link": link,
                "summary": clean_text(_first_text(item, "description", "summary", "content")),
                "published": parse_date(_first_text(item, "pubDate", "published", "updated", "date")),
                "id": _first_text(item, "guid", "id") or link,
            }
        )
    return entries


def _to_signals(entries: list[dict], source: str, kind: str, prefix: str, query: str,
                since: datetime) -> CollectResult:
    signals: list[Signal] = []
    skipped = 0
    for entry in entries:
        if not (entry["title"] and entry["link"] and entry["published"]):
            skipped += 1
            continue
        if entry["published"] < since:
            continue
        signals.append(
            Signal(
                source=source, kind=kind, item_id=entry["id"], title=prefix + entry["title"],
                text=entry["summary"], link=entry["link"], published=entry["published"],
                engagement=None, query=query,
            )
        )
    return CollectResult(signals, skipped)


def collect_feed(name: str, url: str, kind: str, prefix: str, since: datetime) -> CollectResult:
    entries = parse_feed(fetch(url, accept="application/rss+xml, application/atom+xml, */*"))
    return _to_signals(entries, f"rss:{name}", kind, prefix, url, since)


def collect_google_news(name: str, query: str, kind: str, since: datetime) -> CollectResult:
    days = max(1, int((datetime.now(timezone.utc) - since).total_seconds() // 86400) + 1)
    url = (
        "https://news.google.com/rss/search?q="
        f"{quote_plus(query)}+when:{days}d&hl=en-US&gl=US&ceid=US:en"
    )
    entries = parse_feed(fetch(url, accept="application/rss+xml, */*"))
    return _to_signals(entries, f"gnews:{name}", kind, "", query, since)


def collect_anthropic_sitemap(since: datetime) -> CollectResult:
    """Anthropic has no news feed. Return every /news/ page in the sitemap.

    The sitemap's lastmod is a site maintenance date, not a publication date (old posts carry
    recent dates), so it is not used. The pipeline treats this source as new-only: it
    remembers which pages it has seen and reports a page the first time it appears.
    """
    root = ET.fromstring(fetch(config.ANTHROPIC_SITEMAP_URL, accept="application/xml, */*"))
    if _local(root.tag) != "urlset":
        raise ValueError(f"unexpected sitemap root element: {_local(root.tag)}")
    seen_at = datetime.now(timezone.utc)
    signals: list[Signal] = []
    for url_el in _children(root, "url"):
        loc = _first_text(url_el, "loc")
        if "/news/" not in loc:
            continue
        slug = loc.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
        signals.append(
            Signal(
                source="anthropic_sitemap", kind="vendor", item_id=loc,
                title=f"Anthropic news: {slug}", text="", link=loc, published=seen_at,
                engagement=None, query=config.ANTHROPIC_SITEMAP_URL,
            )
        )
    return CollectResult(signals, 0, "title comes from the page address; date is when first seen")


__all__ = ["FetchError", "parse_feed", "collect_feed", "collect_google_news",
           "collect_anthropic_sitemap"]
