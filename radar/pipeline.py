from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from typing import Callable

from . import config, digest, rank
from .models import CollectResult
from .sources import community, feeds
from .store import Store, from_iso


@dataclass
class Task:
    name: str
    run: Callable[[datetime], CollectResult]
    kind: str = "community"  # decides the first-read lookback
    new_only: bool = False  # page lists without usable dates: report pages the first time seen


def build_tasks() -> list[Task]:
    tasks: list[Task] = []
    for name, url, kind, prefix in config.FEEDS:
        tasks.append(Task(f"rss:{name}", partial(feeds.collect_feed, name, url, kind, prefix), kind))
    tasks.append(Task("anthropic_sitemap", feeds.collect_anthropic_sitemap, "vendor", new_only=True))
    for name, query, kind, enabled in config.GOOGLE_NEWS_QUERIES:
        if enabled:
            tasks.append(Task(f"gnews:{name}", partial(feeds.collect_google_news, name, query, kind), kind))
    tasks.append(Task("hackernews", partial(community.collect_hackernews, config.HACKERNEWS_QUERIES)))
    tasks.append(Task("stackoverflow", partial(community.collect_stackoverflow, config.STACKOVERFLOW_TAGS)))
    tasks.append(Task("github", partial(community.collect_github, config.GITHUB_TOPICS)))
    tasks.append(Task("devto", partial(community.collect_devto, config.DEVTO_TAGS)))
    for sub in config.SUBREDDITS:
        tasks.append(Task(f"reddit:{sub}", partial(community.collect_reddit, sub)))
    return tasks


def since_for(store: Store, source: str, now: datetime, override_hours: float | None,
              kind: str = "community") -> datetime:
    """Per-source catch-up: read from just before this source's last success, within limits."""
    if override_hours is not None:
        return now - timedelta(hours=override_hours)
    last_ok = store.last_ok(source)
    if last_ok is None:
        return now - timedelta(hours=config.DEFAULT_LOOKBACK_HOURS_BY_KIND[kind])
    since = last_ok - timedelta(hours=config.OVERLAP_HOURS)
    return max(since, now - timedelta(hours=config.MAX_LOOKBACK_HOURS))


def _new_only(store: Store, task: Task, result: CollectResult, now: datetime,
              note: str) -> tuple[CollectResult, str]:
    """Keep only pages not seen before. The very first read is a baseline: every existing page
    is remembered but none is reported, since nothing tells us which of them are recent."""
    keys = [s.key for s in result.signals]
    fresh = store.unseen_keys(keys)
    store.mark_seen(keys, now)
    if store.last_ok(task.name) is None:
        return CollectResult([], result.skipped), f"baseline: remembered {len(keys)} existing pages, reported none"
    kept = [s for s in result.signals if s.key in fresh]
    return CollectResult(kept, result.skipped), f"{note}; {len(kept)} new of {len(keys)} pages"


def collect_all(store: Store, tasks: list[Task], now: datetime,
                override_hours: float | None) -> list[dict]:
    """Run every collector on its own. One failure never stops the others."""
    health: list[dict] = []
    for task in tasks:
        since = since_for(store, task.name, now, override_hours, task.kind)
        entry = {"source": task.name, "since": since.isoformat()}
        try:
            result = task.run(since)
        except Exception as err:  # noqa: BLE001  isolation is the point; the error is reported
            entry.update(status="failed", error=f"{type(err).__name__}: {err}", items=0, new=0)
        else:
            note = result.note
            if task.new_only:
                result, note = _new_only(store, task, result, now, note)
            new = store.record_signals(result.signals, now)
            store.mark_ok(task.name, now)
            entry.update(status="ok", items=len(result.signals), new=new,
                         skipped=result.skipped, note=note)
        health.append(entry)
    return health


def apply_topic_memory(store: Store, passing: list[rank.Cluster], now: datetime) -> list[rank.Cluster]:
    """Attach a topic id to each cluster, hide dismissed topics, and hide covered ones
    unless there is new evidence since they were marked."""
    known = list(store.recent_topics(now, config.TOPIC_MEMORY_DAYS))
    known_tokens = {row["id"]: rank.tokens(row["title"]) for row in known}
    rows = {row["id"]: row for row in known}
    visible: list[rank.Cluster] = []
    for c in passing:
        best_id, best_sim = None, 0.0
        for tid, toks in known_tokens.items():
            sim = rank.jaccard(rank.tokens(c.lead["title"]), toks)
            if sim >= config.TOPIC_MATCH_JACCARD and sim > best_sim:
                best_id, best_sim = tid, sim
        if best_id is None:
            best_id = store.add_topic(c.lead["title"], now)
            rows[best_id] = store.get_topic(best_id)
            known_tokens[best_id] = rank.tokens(c.lead["title"])
        row = rows[best_id]
        c.topic_id = best_id  # type: ignore[attr-defined]
        status = row["status"]
        if status == "dismissed":
            continue
        if status == "covered":
            marked_at = from_iso(row["status_at"])
            if not any(i["first_seen"] > marked_at for i in c.items):
                continue
            c.flags.append("new_evidence_since_covered")
        visible.append(c)
    return visible


def mark_surfaced(store: Store, shown: list[rank.Cluster], now: datetime) -> None:
    """Count a topic as surfaced only if it is actually in the digest."""
    for c in shown:
        store.touch_topic(c.topic_id, now)  # type: ignore[attr-defined]
        c.times_surfaced = store.get_topic(c.topic_id)["times_surfaced"]  # type: ignore[attr-defined]


def run(db_path: str, out_dir: str, override_hours: float | None = None,
        tasks: list[Task] | None = None, now: datetime | None = None) -> int:
    """One full run. Returns a process exit code: 0 ok, 2 if every source failed."""
    started = now or datetime.now(timezone.utc)
    store = Store(db_path)
    try:
        health = collect_all(store, tasks if tasks is not None else build_tasks(), started, override_hours)
        widest = started - timedelta(hours=max(config.RANK_WINDOW_HOURS_BY_KIND.values()))
        items = [
            i for i in store.load_window(widest)
            if i["published"] >= started - timedelta(hours=config.RANK_WINDOW_HOURS_BY_KIND[i["kind"]])
        ]
        passing, below = rank.rank(items, started)
        visible = apply_topic_memory(store, passing, started)
        shown = rank.diversify(visible, config.TOP_N)
        official = rank.pick_official(
            [c for c in visible if c not in shown],
            config.OFFICIAL_SECTION_LIMIT, config.OFFICIAL_PER_SOURCE,
        )
        mark_surfaced(store, shown + official, started)
        finished = datetime.now(timezone.utc)
        store.record_run(started, finished, health)
        paths = digest.write(Path(out_dir), started, health, shown, official, len(below), len(items))
    finally:
        store.close()
    print(f"digest: {paths[0]}")
    ok = sum(1 for h in health if h["status"] == "ok")
    print(f"sources ok: {ok}/{len(health)}  topics shown: {len(shown)}")
    return 2 if ok == 0 else 0
