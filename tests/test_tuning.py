import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from radar import cli, tuning
from radar.store import Store

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def rating(topic_id, label, recency, engagement=None, relevance=0.5):
    return {"topic_id": topic_id, "rating": label, "score": 50.0,
            "components": {"recency": recency, "engagement": engagement, "relevance": relevance}}


class SummarizeTests(unittest.TestCase):
    def test_not_enough_marks_says_so_and_shows_no_averages(self):
        out = tuning.render(tuning.summarize([rating(1, "post", 0.9), rating(2, "no", 0.1)]))
        self.assertIn("not enough yet", out)
        self.assertNotIn("gap", out)

    def test_gap_and_reading_per_part(self):
        marks = [rating(i, "post", 0.9) for i in range(5)] + [rating(10 + i, "no", 0.2) for i in range(5)]
        summary = tuning.summarize(marks)
        self.assertTrue(summary["enough"])
        rows = {r["part"]: r for r in summary["rows"]}
        self.assertAlmostEqual(rows["recency"]["gap"], 0.7)
        self.assertAlmostEqual(rows["relevance"]["gap"], 0.0)
        text = tuning.render(summary)
        self.assertIn("higher for items you post", text)
        self.assertIn("does not separate post from no", text)

    def test_unknown_values_are_skipped_not_counted_as_zero(self):
        marks = [rating(i, "post", 0.5, engagement=None) for i in range(5)]
        marks += [rating(10 + i, "no", 0.5, engagement=None) for i in range(5)]
        rows = {r["part"]: r for r in tuning.summarize(marks)["rows"]}
        self.assertIsNone(rows["engagement"]["gap"])  # never measured, so no comparison

    def test_maybe_is_counted_but_not_compared(self):
        marks = [rating(1, "maybe", 0.5)]
        self.assertEqual(tuning.summarize(marks)["counts"]["maybe"], 1)


class DigestLookupTests(unittest.TestCase):
    def _write(self, tmp, name="2026-11-04.json"):
        data = {"topics": [{"topic_id": 1, "title": "Main", "score": 60.0, "components": {"recency": 0.9}}],
                "official_updates": [{"topic_id": 2, "title": "Official", "score": 40.0,
                                      "components": {"recency": 0.4}}]}
        (Path(tmp) / name).write_text(json.dumps(data), encoding="utf-8")

    def test_finds_topics_in_either_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp)
            self.assertEqual(tuning.find_in_latest_digest(tmp, 1)["title"], "Main")
            self.assertEqual(tuning.find_in_latest_digest(tmp, 2)["title"], "Official")

    def test_topic_not_in_the_digest_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp)
            with self.assertRaises(KeyError):
                tuning.find_in_latest_digest(tmp, 99)

    def test_no_digest_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                tuning.find_in_latest_digest(tmp, 1)


class RatingStoreAndCliTests(unittest.TestCase):
    def test_rating_is_stored_and_replaced_not_duplicated(self):
        store = Store(":memory:")
        tid = store.add_topic("topic", NOW)
        store.set_rating(tid, "no", NOW, {"recency": 0.1}, 30.0)
        store.set_rating(tid, "post", NOW, {"recency": 0.9}, 60.0)
        [row] = store.list_ratings()
        self.assertEqual((row["rating"], row["score"], row["components"]), ("post", 60.0, {"recency": 0.9}))

    def test_invalid_rating_and_unknown_topic_raise(self):
        store = Store(":memory:")
        tid = store.add_topic("topic", NOW)
        with self.assertRaises(ValueError):
            store.set_rating(tid, "love", NOW, {}, 1.0)
        with self.assertRaises(KeyError):
            store.set_rating(999, "post", NOW, {}, 1.0)

    def test_rate_and_weights_commands_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, out = str(Path(tmp) / "r.db"), str(Path(tmp) / "digests")
            Path(out).mkdir()
            store = Store(db)
            tid = store.add_topic("Main", NOW)
            store.close()
            (Path(out) / "2026-11-04.json").write_text(json.dumps({"topics": [
                {"topic_id": tid, "title": "Main", "score": 60.0, "components": {"recency": 0.9}}],
                "official_updates": []}), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(cli.main(["--db", db, "rate", str(tid), "post", "--out", out]), 0)
                self.assertEqual(cli.main(["--db", db, "weights"]), 0)
            self.assertIn("rated post", buf.getvalue())
            self.assertIn("marks: 1 post", buf.getvalue())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["--db", db, "rate", "999", "post", "--out", out]), 1)


if __name__ == "__main__":
    unittest.main()
