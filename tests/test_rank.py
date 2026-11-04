import unittest
from datetime import datetime, timedelta, timezone

from radar import config, rank

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def item(key, title, source="hackernews", kind="community", engagement=10.0, hours_ago=2.0,
         text="", link=None, velocity=None):
    return {"key": key, "source": source, "kind": kind, "title": title, "text": text,
            "link": link or f"https://x.test/{key}", "published": NOW - timedelta(hours=hours_ago),
            "engagement": engagement, "velocity": velocity,
            "first_seen": NOW - timedelta(hours=1)}


class ClusterTests(unittest.TestCase):
    def test_same_story_from_two_sources_merges(self):
        items = [
            item("a", "OpenAI to acquire Pierre Computer Company", source="hackernews"),
            item("b", "OpenAI acquires Pierre Computer Company", source="rss:openai_news", kind="vendor",
                 engagement=None),
        ]
        clusters = rank.cluster_items(items)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].sources, {"hackernews", "rss:openai_news"})

    def test_unrelated_titles_stay_apart(self):
        items = [item("a", "Claude Code adds new MCP features"), item("b", "AMD outsells Intel in servers")]
        self.assertEqual(len(rank.cluster_items(items)), 2)

    def test_same_link_merges_even_with_different_titles(self):
        items = [item("a", "One title here", link="https://same.test"),
                 item("b", "Totally different words", link="https://same.test")]
        self.assertEqual(len(rank.cluster_items(items)), 1)


class ScoringTests(unittest.TestCase):
    def test_unknown_engagement_is_unknown_not_zero(self):
        items = [item("a", "CBN circular on data localisation", source="gnews:cbn", kind="regulator",
                      engagement=None)]
        [c] = rank.cluster_items(items)
        rank.score_cluster(c, NOW, rank.engagement_percentiles(items))
        self.assertIsNone(c.components["engagement"])
        self.assertIn("engagement_unknown", c.flags)

    def test_percentile_is_within_own_source(self):
        items = [item("a", "t1", engagement=1), item("b", "t2", engagement=5),
                 item("c", "t3", source="github", engagement=5000)]
        pct = rank.engagement_percentiles(items)
        self.assertEqual(pct["b"], 1.0)  # best on HN, even though GitHub numbers are far larger
        self.assertEqual(pct["c"], 1.0)

    def test_recency_decays_with_the_source_half_life(self):
        fresh = item("a", "Fresh story about agents", hours_ago=0)
        old = item("b", "Older story about agents", hours_ago=24)  # one HN half-life
        for it in (fresh, old):
            [c] = rank.cluster_items([it])
            rank.score_cluster(c, NOW, rank.engagement_percentiles([it]))
            it["_recency"] = c.components["recency"]
        self.assertAlmostEqual(fresh["_recency"], 1.0)
        self.assertAlmostEqual(old["_recency"], 0.5)

    def test_velocity_adds_a_bonus(self):
        slow = [item("a", "Some topic words here", velocity=None)]
        fast = [item("a", "Some topic words here", velocity=20.0)]
        scores = []
        for items in (slow, fast):
            [c] = rank.cluster_items(items)
            rank.score_cluster(c, NOW, rank.engagement_percentiles(items))
            scores.append(c.score)
        self.assertGreater(scores[1], scores[0])


class NicheTermTests(unittest.TestCase):
    def test_terms_match_whole_words_only(self):
        self.assertEqual(rank.niche_hits("Average storage in a garage"), [])
        self.assertEqual(rank.niche_hits("A new RAG pipeline"), ["rag"])

    def test_plurals_match(self):
        self.assertIn("ai agent", rank.niche_hits("Why AI agents fail"))

    def test_new_terms_match(self):
        self.assertEqual(rank.niche_hits("OpenAI to acquire Pierre"), ["openai"])
        self.assertIn("codex", rank.niche_hits("Codex chats and model training"))


class FloorTests(unittest.TestCase):
    def _floor(self, items):
        [c] = rank.cluster_items(items)
        rank.score_cluster(c, NOW, rank.engagement_percentiles(items))
        return c

    def test_weak_single_source_item_fails_the_floor(self):
        c = self._floor([item("a", "A tiny post about nothing", engagement=2)])
        self.assertFalse(c.passes_floor)

    def test_big_single_source_item_passes(self):
        c = self._floor([item("a", "Claude Code MCP agent goes viral", engagement=500)])
        self.assertTrue(c.passes_floor)

    def test_big_but_off_niche_item_fails_the_floor(self):
        c = self._floor([item("a", "AMD expects to outsell Intel in Q4", engagement=5000)])
        self.assertFalse(c.passes_floor)
        self.assertEqual(c.floor_reason, "no niche term matched")

    def test_multi_source_off_niche_item_also_fails(self):
        c = self._floor([item("a", "Flipper One Kickstarter opens pre-orders", source="hackernews"),
                         item("b", "Flipper One Kickstarter opens pre-orders today", source="devto",
                              link="https://x.test/b2")])
        self.assertFalse(c.passes_floor)

    def test_quiet_important_official_item_passes_without_engagement(self):
        c = self._floor([item("a", "CBN circular sets data localisation deadline", source="gnews:cbn",
                              kind="regulator", engagement=None)])
        self.assertTrue(c.passes_floor)
        self.assertIn("quiet_important", c.flags)

    def test_quiet_important_without_niche_terms_does_not_pass(self):
        c = self._floor([item("a", "Library will be removed in March", source="rss:x", kind="vendor",
                              engagement=None)])
        self.assertFalse(c.passes_floor)


class RankTests(unittest.TestCase):
    def test_quiet_day_yields_nothing_shown(self):
        passing, below = rank.rank([item("a", "Weak post one", engagement=1),
                                    item("b", "Another weak thing", engagement=2)], NOW)
        self.assertEqual(passing, [])
        self.assertEqual(len(below), 2)

    def test_diversity_cap_limits_one_source(self):
        items = [item(str(i), f"Distinct claude story number{i} alpha{i} beta{i} gamma{i}", engagement=1000 + i)
                 for i in range(20)]
        passing, _ = rank.rank(items, NOW)
        shown = rank.diversify(passing, config.TOP_N)
        self.assertLessEqual(len(shown), 5)  # ceil(12 * 0.4)


if __name__ == "__main__":
    unittest.main()
