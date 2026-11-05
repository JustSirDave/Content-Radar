import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar import config, pipeline
from radar.models import CollectResult, Signal
from radar.store import Store

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def signal(item_id="1", engagement=10.0, title="Claude Code ships MCP agent update", source="hackernews",
           hours_ago=1.0):
    return Signal(source=source, kind="community", item_id=item_id, title=title, text="",
                  link=f"https://x.test/{item_id}", published=NOW - timedelta(hours=hours_ago),
                  engagement=engagement, query="q")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def test_snapshots_give_velocity(self):
        self.store.record_signals([signal(engagement=10)], NOW - timedelta(hours=4))
        self.store.record_signals([signal(engagement=50)], NOW)
        [row] = self.store.load_window(NOW - timedelta(days=1))
        self.assertEqual(row["engagement"], 50)
        self.assertAlmostEqual(row["velocity"], 10.0)

    def test_unknown_engagement_stays_none(self):
        self.store.record_signals([signal(engagement=None)], NOW)
        [row] = self.store.load_window(NOW - timedelta(days=1))
        self.assertIsNone(row["engagement"])

    def test_record_counts_only_new_signals(self):
        self.assertEqual(self.store.record_signals([signal("1"), signal("2")], NOW), 2)
        self.assertEqual(self.store.record_signals([signal("1"), signal("3")], NOW), 1)

    def test_times_surfaced_counts_days_not_runs(self):
        tid = self.store.add_topic("topic", NOW)
        self.store.touch_topic(tid, NOW)
        self.store.touch_topic(tid, NOW + timedelta(hours=4))
        self.assertEqual(self.store.get_topic(tid)["times_surfaced"], 1)
        self.store.touch_topic(tid, NOW + timedelta(days=1))
        self.assertEqual(self.store.get_topic(tid)["times_surfaced"], 2)

    def test_invalid_status_raises(self):
        tid = self.store.add_topic("topic", NOW)
        with self.assertRaises(ValueError):
            self.store.set_status(tid, "archived", NOW)

    def test_unknown_topic_raises(self):
        with self.assertRaises(KeyError):
            self.store.set_status(999, "covered", NOW)


class PipelineTests(unittest.TestCase):
    def test_one_failing_source_does_not_stop_the_others(self):
        def boom(since):
            raise RuntimeError("blocked")

        tasks = [pipeline.Task("bad", boom),
                 pipeline.Task("good", lambda since: CollectResult([signal()]))]
        store = Store(":memory:")
        health = pipeline.collect_all(store, tasks, NOW, None)
        self.assertEqual([h["status"] for h in health], ["failed", "ok"])
        self.assertIn("blocked", health[0]["error"])
        self.assertIsNone(store.last_ok("bad"))  # a failure never advances catch-up state
        self.assertEqual(store.last_ok("good"), NOW)

    def test_catch_up_reads_from_last_success_within_limits(self):
        store = Store(":memory:")
        self.assertEqual(pipeline.since_for(store, "s", NOW, None),
                         NOW - timedelta(hours=config.DEFAULT_LOOKBACK_HOURS_BY_KIND["community"]))
        self.assertEqual(pipeline.since_for(store, "v", NOW, None, kind="vendor"),
                         NOW - timedelta(hours=config.DEFAULT_LOOKBACK_HOURS_BY_KIND["vendor"]))
        store.mark_ok("s", NOW - timedelta(hours=10))
        self.assertEqual(pipeline.since_for(store, "s", NOW, None),
                         NOW - timedelta(hours=10 + config.OVERLAP_HOURS))
        store.mark_ok("s", NOW - timedelta(days=30))
        self.assertEqual(pipeline.since_for(store, "s", NOW, None),
                         NOW - timedelta(hours=config.MAX_LOOKBACK_HOURS))
        self.assertEqual(pipeline.since_for(store, "s", NOW, 5), NOW - timedelta(hours=5))

    def test_full_run_writes_digest_and_hides_covered_topics(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, out = str(Path(tmp) / "r.db"), str(Path(tmp) / "out")
            tasks = [pipeline.Task("t", lambda since: CollectResult([signal(engagement=900)]))]
            self.assertEqual(pipeline.run(db, out, tasks=tasks, now=NOW), 0)
            digest = (Path(out) / "2026-11-04.md").read_text(encoding="utf-8")
            self.assertIn("Topic #1", digest)

            store = Store(db)
            store.set_status(1, "covered", NOW + timedelta(minutes=1))
            store.close()
            later = NOW + timedelta(hours=4)
            self.assertEqual(pipeline.run(db, out, tasks=tasks, now=later), 0)
            digest = (Path(out) / "2026-11-04.md").read_text(encoding="utf-8")
            self.assertIn("Nothing worth posting today", digest)  # covered, no new evidence

    def test_vendor_only_items_go_to_the_official_section_not_the_main_list(self):
        vendor = Signal(source="rss:claude_code_releases", kind="vendor", item_id="v1",
                        title="Claude Code release: adds MCP agent hooks", text="",
                        link="https://x.test/v1", published=NOW - timedelta(hours=1),
                        engagement=None, query="q")
        news = Signal(source="rss:techcabal", kind="news", item_id="n1",
                      title="Nigerian fintech startup raises seed funding", text="",
                      link="https://x.test/n1", published=NOW - timedelta(hours=1),
                      engagement=None, query="q")
        with tempfile.TemporaryDirectory() as tmp:
            tasks = [pipeline.Task("t", lambda since: CollectResult([vendor, news]))]
            self.assertEqual(pipeline.run(str(Path(tmp) / "r.db"), str(Path(tmp) / "o"), tasks=tasks,
                                          now=NOW), 0)
            text = (Path(tmp) / "o" / "2026-11-04.md").read_text(encoding="utf-8")
        main, official = text.split("## Vendor and regulator updates")
        self.assertIn("Nigerian fintech startup raises seed funding", main)
        self.assertNotIn("Claude Code release", main)
        self.assertIn("Claude Code release", official)

    def test_all_sources_failing_returns_exit_code_2(self):
        def boom(since):
            raise RuntimeError("down")

        with tempfile.TemporaryDirectory() as tmp:
            code = pipeline.run(str(Path(tmp) / "r.db"), str(Path(tmp) / "o"),
                                tasks=[pipeline.Task("t", boom)], now=NOW)
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
