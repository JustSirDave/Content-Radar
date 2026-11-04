from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from . import pipeline
from .store import VALID_STATUSES, Store

DEFAULT_DB = "data/radar.db"
DEFAULT_OUT = "digests"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar", description="Content Radar")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="collect, rank and write the digest")
    run_p.add_argument("--out", default=DEFAULT_OUT, help="digest output folder")
    run_p.add_argument("--since-hours", type=float, default=None,
                       help="ignore catch-up state and read this many hours back")

    mark_p = sub.add_parser("mark", help="set a topic's status")
    mark_p.add_argument("topic_id", type=int)
    mark_p.add_argument("status", choices=VALID_STATUSES)

    list_p = sub.add_parser("topics", help="list remembered topics")
    list_p.add_argument("--status", choices=VALID_STATUSES, default=None)

    args = parser.parse_args(argv)

    # Titles come from the whole world; a Windows console defaults to a codepage that cannot print them.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if args.command == "run":
        return pipeline.run(args.db, args.out, override_hours=args.since_hours)

    store = Store(args.db)
    try:
        if args.command == "mark":
            store.set_status(args.topic_id, args.status, datetime.now(timezone.utc))
            print(f"topic {args.topic_id} marked {args.status}")
        else:
            for t in store.list_topics(args.status):
                print(f"#{t['id']} [{t['status']}] surfaced {t['times_surfaced']}x  {t['title']}")
    except (KeyError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    finally:
        store.close()
    return 0
