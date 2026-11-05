import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar import categorize, config, pipeline
from radar.models import CollectResult, Signal
from radar.rank import Cluster

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def cluster(hits, sources=("rss:techcabal",)):
    items = [{"source": s, "kind": "news", "title": "t", "link": "l", "text": "",
              "published": NOW, "engagement": None} for s in sources]
    c = Cluster(items)
    c.niche_hits = list(hits)
    return c


class MainCategoryTests(unittest.TestCase):
    def test_policy_terms_beat_a_shared_country_term(self):
        c = cluster(["cbn", "naira", "nigeria"])
        self.assertEqual(categorize.main_category(c), "Nigeria policy and economy")

    def test_business_terms_go_to_africa_tech_and_business(self):
        c = cluster(["nigeria", "nigerian", "startup"])
        self.assertEqual(categorize.main_category(c), "Africa tech and business")

    def test_claude_code_is_engineering_not_a_company_story(self):
        c = cluster(["claude", "claude code"])
        self.assertEqual(categorize.main_category(c), "AI engineering and agents")

    def test_company_names_alone_are_ai_companies(self):
        c = cluster(["openai", "codex"])
        self.assertEqual(categorize.main_category(c), "AI companies and models")

    def test_no_matching_term_is_labelled_uncategorised(self):
        self.assertEqual(categorize.main_category(cluster([])), config.UNCATEGORISED)

    def test_a_tie_goes_to_the_earlier_category(self):
        # naira and sme both weigh 1; policy is listed before africa tech.
        c = cluster(["naira", "sme"])
        self.assertEqual(categorize.main_category(c), "Nigeria policy and economy")


class VendorGroupTests(unittest.TestCase):
    def test_groups_by_source_even_when_a_community_item_leads(self):
        c = cluster([], sources=("hackernews", "rss:openai_news"))
        self.assertEqual(categorize.vendor_group(c), "OpenAI")

    def test_official_x_accounts_group_with_their_vendor(self):
        self.assertEqual(categorize.vendor_group(cluster([], ("gnews:x_official_claudedevs",))),
                         "Anthropic and Claude")
        self.assertEqual(categorize.vendor_group(cluster([], ("gnews:x_official_metafordevs",))), "Meta")

    def test_unknown_source_is_other_updates(self):
        self.assertEqual(categorize.vendor_group(cluster([], ("rss:somewhere_new",))),
                         config.OTHER_UPDATES)


class GroupByTests(unittest.TestCase):
    def test_config_order_then_unknown_labels_last(self):
        a, b, c = cluster(["cbn"]), cluster(["openai"]), cluster([])
        groups = categorize.group_by([c, b, a], categorize.main_category, categorize.MAIN_ORDER)
        self.assertEqual([g for g, _ in groups],
                         ["Nigeria policy and economy", "AI companies and models", config.UNCATEGORISED])

    def test_empty_groups_are_skipped(self):
        groups = categorize.group_by([cluster(["cbn"])], categorize.main_category, categorize.MAIN_ORDER)
        self.assertEqual(len(groups), 1)


class ConfigConsistencyTests(unittest.TestCase):
    def test_category_terms_exist_and_are_disjoint(self):
        seen = set()
        for name, terms in config.CATEGORIES:
            self.assertFalse(terms - set(config.NICHE_TERMS), f"{name} has terms not in NICHE_TERMS")
            self.assertFalse(terms & seen, f"{name} repeats a term from an earlier category")
            seen |= terms

    def test_every_niche_term_has_a_category(self):
        covered = set().union(*(t for _, t in config.CATEGORIES))
        self.assertEqual(set(config.NICHE_TERMS) - covered, set())

    def test_every_vendor_prefix_matches_a_configured_source(self):
        sources = ([f"rss:{f[0]}" for f in config.FEEDS] + [f"gnews:{q[0]}" for q in config.GOOGLE_NEWS_QUERIES]
                   + ["anthropic_sitemap"])
        for label, prefixes in config.VENDOR_GROUPS:
            for p in prefixes:
                self.assertTrue(any(s.startswith(p) for s in sources), f"{label}: {p} matches no source")

    def test_every_official_vendor_or_regulator_source_has_a_group(self):
        official = [f"rss:{n}" for n, _, kind, _ in config.FEEDS if kind in ("vendor", "regulator")]
        official += [f"gnews:{n}" for n, _, kind, on in config.GOOGLE_NEWS_QUERIES
                     if kind == "vendor" and on]
        for s in official:
            self.assertNotEqual(categorize.vendor_group(cluster([], (s,))), config.OTHER_UPDATES,
                                f"{s} has no vendor group")


class DigestOutputTests(unittest.TestCase):
    def test_markdown_groups_and_json_carry_the_category(self):
        def sig(item_id, source, kind, title):
            return Signal(source=source, kind=kind, item_id=item_id, title=title, text="",
                          link=f"https://x.test/{item_id}", published=NOW - timedelta(hours=1),
                          engagement=None, query="q")

        signals = [sig("n1", "rss:techcabal", "news", "Nigerian fintech startup raises seed funding"),
                   sig("n2", "rss:nairametrics", "news", "CBN circular on naira data localisation"),
                   sig("v1", "rss:claude_code_releases", "vendor", "Claude Code release: adds MCP agent hooks"),
                   sig("v2", "rss:openai_news", "vendor", "OpenAI Codex agent update")]
        with tempfile.TemporaryDirectory() as tmp:
            tasks = [pipeline.Task("t", lambda since: CollectResult(signals))]
            self.assertEqual(pipeline.run(str(Path(tmp) / "r.db"), str(Path(tmp) / "o"), tasks=tasks,
                                          now=NOW), 0)
            text = (Path(tmp) / "o" / "2026-11-04.md").read_text(encoding="utf-8")
            data = json.loads((Path(tmp) / "o" / "2026-11-04.json").read_text(encoding="utf-8"))
        self.assertIn("### Africa tech and business (1)", text)
        self.assertIn("### Nigeria policy and economy (1)", text)
        self.assertIn("### Anthropic and Claude (1)", text)
        self.assertIn("### OpenAI (1)", text)
        self.assertEqual({t["category"] for t in data["topics"]},
                         {"Africa tech and business", "Nigeria policy and economy"})
        self.assertEqual({t["category"] for t in data["official_updates"]}, {"Anthropic and Claude", "OpenAI"})


if __name__ == "__main__":
    unittest.main()
