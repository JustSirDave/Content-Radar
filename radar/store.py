from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Signal

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    key TEXT PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL, item_id TEXT NOT NULL,
    title TEXT NOT NULL, text TEXT NOT NULL, link TEXT NOT NULL, published TEXT NOT NULL,
    query TEXT NOT NULL, first_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    key TEXT NOT NULL, taken_at TEXT NOT NULL, engagement REAL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_key ON snapshots(key, taken_at);
CREATE TABLE IF NOT EXISTS source_state (source TEXT PRIMARY KEY, last_ok TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL, times_surfaced INTEGER NOT NULL DEFAULT 0,
    last_surfaced_day TEXT, status TEXT NOT NULL DEFAULT 'open', status_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, started TEXT NOT NULL, finished TEXT,
    health TEXT NOT NULL
);
"""

VALID_STATUSES = ("open", "covered", "dismissed")


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def from_iso(raw: str) -> datetime:
    return datetime.fromisoformat(raw)


class Store:
    def __init__(self, path: str | Path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    # --- signals and snapshots -------------------------------------------------------

    def record_signals(self, signals: list[Signal], taken_at: datetime) -> int:
        """Insert new signals and add an engagement snapshot for every signal seen.

        Returns the number of signals not seen before.
        """
        new = 0
        with self.db:
            for s in signals:
                cur = self.db.execute(
                    "INSERT OR IGNORE INTO signals(key, source, kind, item_id, title, text, link,"
                    " published, query, first_seen) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (s.key, s.source, s.kind, s.item_id, s.title, s.text, s.link,
                     iso(s.published), s.query, iso(taken_at)),
                )
                new += cur.rowcount
                self.db.execute(
                    "INSERT INTO snapshots(key, taken_at, engagement) VALUES (?,?,?)",
                    (s.key, iso(taken_at), s.engagement),
                )
        return new

    def load_window(self, since: datetime) -> list[dict]:
        """Signals published since `since`, with latest engagement and growth between snapshots."""
        rows = self.db.execute(
            "SELECT * FROM signals WHERE published >= ? ORDER BY published DESC", (iso(since),)
        ).fetchall()
        out = []
        for row in rows:
            snaps = self.db.execute(
                "SELECT taken_at, engagement FROM snapshots WHERE key = ? ORDER BY taken_at",
                (row["key"],),
            ).fetchall()
            latest = snaps[-1]["engagement"] if snaps else None
            velocity = None
            known = [s for s in snaps if s["engagement"] is not None]
            if len(known) >= 2:
                hours = (from_iso(known[-1]["taken_at"]) - from_iso(known[0]["taken_at"])).total_seconds() / 3600
                if hours >= 1:
                    velocity = (known[-1]["engagement"] - known[0]["engagement"]) / hours
            out.append({**dict(row), "published": from_iso(row["published"]),
                        "first_seen": from_iso(row["first_seen"]),
                        "engagement": latest, "velocity": velocity})
        return out

    # --- per-source catch-up ---------------------------------------------------------

    def last_ok(self, source: str) -> datetime | None:
        row = self.db.execute("SELECT last_ok FROM source_state WHERE source = ?", (source,)).fetchone()
        return from_iso(row["last_ok"]) if row else None

    def mark_ok(self, source: str, when: datetime) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO source_state(source, last_ok) VALUES (?, ?) "
                "ON CONFLICT(source) DO UPDATE SET last_ok = excluded.last_ok",
                (source, iso(when)),
            )

    # --- topic memory ----------------------------------------------------------------

    def recent_topics(self, now: datetime, days: int) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM topics WHERE last_seen >= ?", (iso(now - timedelta(days=days)),)
        ).fetchall()

    def add_topic(self, title: str, now: datetime) -> int:
        with self.db:
            cur = self.db.execute(
                "INSERT INTO topics(title, first_seen, last_seen) VALUES (?,?,?)",
                (title, iso(now), iso(now)),
            )
        return int(cur.lastrowid)

    def touch_topic(self, topic_id: int, now: datetime) -> None:
        """Update last_seen, and count one surfacing per calendar day, not per run."""
        day = now.date().isoformat()
        with self.db:
            self.db.execute(
                "UPDATE topics SET last_seen = ?, "
                "times_surfaced = times_surfaced + CASE WHEN last_surfaced_day IS ? THEN 0 ELSE 1 END, "
                "last_surfaced_day = ? WHERE id = ?",
                (iso(now), day, day, topic_id),
            )

    def get_topic(self, topic_id: int) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if row is None:
            raise KeyError(f"no topic with id {topic_id}")
        return row

    def set_status(self, topic_id: int, status: str, now: datetime) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
        self.get_topic(topic_id)
        with self.db:
            self.db.execute("UPDATE topics SET status = ?, status_at = ? WHERE id = ?",
                            (status, iso(now), topic_id))

    def list_topics(self, status: str | None = None) -> list[sqlite3.Row]:
        if status is None:
            return self.db.execute("SELECT * FROM topics ORDER BY last_seen DESC").fetchall()
        return self.db.execute("SELECT * FROM topics WHERE status = ? ORDER BY last_seen DESC",
                               (status,)).fetchall()

    # --- runs ------------------------------------------------------------------------

    def record_run(self, started: datetime, finished: datetime, health: list[dict]) -> None:
        with self.db:
            self.db.execute("INSERT INTO runs(started, finished, health) VALUES (?,?,?)",
                            (iso(started), iso(finished), json.dumps(health)))
