"""Hacker News, Stack Overflow, GitHub, DEV and Reddit collectors."""

from __future__ import annotations

import html
import json
import time
from datetime import datetime, timezone

from ..http import FetchError, fetch
from ..models import CollectResult, Signal


def _json(data: bytes):
    return json.loads(data.decode("utf-8"))


def _utc(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def collect_hackernews(queries: list[str], since: datetime) -> CollectResult:
    signals: dict[str, Signal] = {}
    skipped = 0
    for query in queries:
        payload = _json(fetch(
            "https://hn.algolia.com/api/v1/search_by_date",
            {"query": query, "tags": "story", "hitsPerPage": 30,
             "numericFilters": f"created_at_i>{int(since.timestamp())}"},
        ))
        for hit in payload["hits"]:
            title = hit.get("title")
            object_id = hit.get("objectID")
            created = hit.get("created_at_i")
            if not (title and object_id and created):
                skipped += 1
                continue
            link = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
            signals[object_id] = Signal(
                source="hackernews", kind="community", item_id=object_id, title=title,
                text="", link=link, published=_utc(created),
                engagement=float((hit.get("points") or 0) + (hit.get("num_comments") or 0)),
                query=query,
            )
        time.sleep(0.2)
    return CollectResult(list(signals.values()), skipped)


def collect_stackoverflow(tags: list[str], since: datetime) -> CollectResult:
    signals: dict[str, Signal] = {}
    skipped = 0
    for tag in tags:
        payload = _json(fetch(
            "https://api.stackexchange.com/2.3/questions",
            {"order": "desc", "sort": "votes", "tagged": tag, "site": "stackoverflow",
             "fromdate": int(since.timestamp()), "pagesize": 30},
        ))
        for q in payload["items"]:
            qid, title, link, created = q.get("question_id"), q.get("title"), q.get("link"), q.get("creation_date")
            if not (qid and title and link and created):
                skipped += 1
                continue
            signals[str(qid)] = Signal(
                source="stackoverflow", kind="community", item_id=str(qid),
                title=html.unescape(title), text="", link=link, published=_utc(created),
                engagement=float((q.get("score") or 0) + (q.get("answer_count") or 0)),
                query=tag,
            )
    return CollectResult(list(signals.values()), skipped)


def collect_github(topics: list[str], since: datetime) -> CollectResult:
    signals: dict[str, Signal] = {}
    skipped = 0
    for topic in topics:
        payload = _json(fetch(
            "https://api.github.com/search/repositories",
            {"q": f"topic:{topic} created:>{since.date().isoformat()}", "sort": "stars",
             "order": "desc", "per_page": 20},
            accept="application/vnd.github+json",
        ))
        for repo in payload["items"]:
            full_name, url, created = repo.get("full_name"), repo.get("html_url"), repo.get("created_at")
            published = datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None
            if not (full_name and url and published):
                skipped += 1
                continue
            signals[full_name] = Signal(
                source="github", kind="community", item_id=full_name,
                title=f"{full_name}: {repo.get('description') or ''}".strip(": "),
                text="", link=url, published=published,
                engagement=float(repo.get("stargazers_count") or 0), query=f"topic:{topic}",
            )
        time.sleep(1.0)  # unauthenticated search allows 10 requests a minute
    return CollectResult(list(signals.values()), skipped)


def collect_devto(tags: list[str], since: datetime) -> CollectResult:
    signals: dict[str, Signal] = {}
    skipped = 0
    for tag in tags:
        articles = _json(fetch("https://dev.to/api/articles", {"tag": tag, "per_page": 30, "top": 7}))
        for art in articles:
            aid, title, url, published = art.get("id"), art.get("title"), art.get("url"), art.get("published_at")
            if not (aid and title and url and published):
                skipped += 1
                continue
            when = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if when < since:
                continue
            signals[str(aid)] = Signal(
                source="devto", kind="community", item_id=str(aid), title=title,
                text=art.get("description") or "", link=url, published=when,
                engagement=float((art.get("public_reactions_count") or 0) + (art.get("comments_count") or 0)),
                query=tag,
            )
    return CollectResult(list(signals.values()), skipped)


def collect_reddit(subreddit: str, since: datetime) -> CollectResult:
    """Reddit blocks unauthenticated requests from this machine (checked 2026-11-04).

    A 403 raises FetchError and shows as a failed source. It is never worked around.
    """
    payload = _json(fetch(f"https://www.reddit.com/r/{subreddit}/top/.json", {"t": "day", "limit": 25}))
    signals: list[Signal] = []
    skipped = 0
    for child in payload["data"]["children"]:
        post = child["data"]
        pid, title, permalink, created = post.get("id"), post.get("title"), post.get("permalink"), post.get("created_utc")
        if not (pid and title and permalink and created):
            skipped += 1
            continue
        when = _utc(created)
        if when < since:
            continue
        signals.append(Signal(
            source="reddit", kind="community", item_id=pid, title=title,
            text=(post.get("selftext") or "")[:600], link=f"https://www.reddit.com{permalink}",
            published=when,
            engagement=float((post.get("score") or 0) + (post.get("num_comments") or 0)),
            query=f"r/{subreddit}",
        ))
    return CollectResult(signals, skipped)


__all__ = ["FetchError", "collect_hackernews", "collect_stackoverflow", "collect_github",
           "collect_devto", "collect_reddit"]
