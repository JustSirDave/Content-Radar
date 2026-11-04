"""Clustering, scoring, the confidence floor and the diversity cap.

The score belongs to a cluster of items about the same story, not to a single link.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime

from . import config

_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with", "is", "are",
    "was", "were", "be", "been", "it", "its", "this", "that", "how", "why", "what", "new",
    "now", "you", "your", "we", "our", "they", "from", "at", "by", "as", "has", "have",
    "will", "can", "not", "just", "about", "after", "over", "into", "than", "more", "most",
    "says", "said", "show", "hn", "ask", "release", "x",
}


# Whole-word match, plural allowed. Plain substring matching let "rag" fire inside "storage".
_TERM_PATTERNS = {
    term: re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"s?(?![a-z0-9])")
    for term in config.NICHE_TERMS
}


def niche_hits(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(term for term, pattern in _TERM_PATTERNS.items() if pattern.search(lowered))


def tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 2 and w.lower() not in _STOPWORDS}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Cluster:
    items: list[dict]
    lead: dict = field(init=False)
    tokens: set[str] = field(init=False)
    score: float = 0.0
    components: dict[str, float | None] = field(default_factory=dict)
    bonuses: dict[str, float] = field(default_factory=dict)
    niche_hits: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    confidence: str = "low"
    passes_floor: bool = False
    floor_reason: str = ""

    def __post_init__(self) -> None:
        self.lead = self.items[0]
        self.tokens = tokens(self.lead["title"])

    @property
    def sources(self) -> set[str]:
        return {i["source"] for i in self.items}

    @property
    def kinds(self) -> set[str]:
        return {i["kind"] for i in self.items}

    @property
    def engagement_total(self) -> float | None:
        known = [i["engagement"] for i in self.items if i["engagement"] is not None]
        return sum(known) if known else None


def cluster_items(items: list[dict]) -> list[Cluster]:
    """Greedy single pass over items, newest first. Same link, or enough shared words, merges."""
    clusters: list[Cluster] = []
    by_link: dict[str, Cluster] = {}
    for item in items:
        if item["link"] in by_link:
            by_link[item["link"]].items.append(item)
            continue
        item_tokens = tokens(item["title"])
        best, best_sim = None, 0.0
        for c in clusters:
            shared = len(item_tokens & c.tokens)
            sim = jaccard(item_tokens, c.tokens)
            if shared >= config.CLUSTER_MIN_SHARED_TOKENS and sim >= config.CLUSTER_JACCARD and sim > best_sim:
                best, best_sim = c, sim
        if best is None:
            best = Cluster([item])
            clusters.append(best)
        else:
            best.items.append(item)
        by_link[item["link"]] = best
    for c in clusters:  # lead = most engaged item, newest on ties
        c.items.sort(key=lambda i: (i["engagement"] if i["engagement"] is not None else -1, i["published"]),
                     reverse=True)
        c.lead = c.items[0]
        c.tokens = tokens(c.lead["title"])
    return clusters


def engagement_percentiles(items: list[dict]) -> dict[str, float]:
    """Percentile of each item's engagement within its own source. Unknown engagement is skipped."""
    by_source: dict[str, list[float]] = {}
    for i in items:
        if i["engagement"] is not None:
            by_source.setdefault(i["source"].split(":")[0], []).append(i["engagement"])
    out = {}
    for i in items:
        if i["engagement"] is None:
            continue
        values = by_source[i["source"].split(":")[0]]
        out[i["key"]] = sum(1 for v in values if v <= i["engagement"]) / len(values)
    return out


def _half_life(source: str) -> float:
    return config.HALF_LIFE_HOURS[source.split(":")[0]]


def score_cluster(c: Cluster, now: datetime, percentiles: dict[str, float]) -> None:
    freshest = max(c.items, key=lambda i: i["published"])
    age_hours = max(0.0, (now - freshest["published"]).total_seconds() / 3600)
    recency = 0.5 ** (age_hours / _half_life(freshest["source"]))

    top = sorted((percentiles[i["key"]] for i in c.items if i["key"] in percentiles), reverse=True)[:3]
    engagement = sum(top) / len(top) if top else None

    corroboration = min(1.0, (len(c.sources) - 1) / 3)

    text = " ".join(i["title"] + " " + i["text"] for i in c.items).lower()
    hits = niche_hits(text)
    c.niche_hits = hits
    relevance = min(1.0, sum(config.NICHE_TERMS[t] for t in hits) / config.NICHE_SATURATION)

    diversity = min(1.0, len(c.kinds) / 3)

    c.components = {"recency": recency, "engagement": engagement, "corroboration": corroboration,
                    "relevance": relevance, "diversity": diversity}
    available = {k: v for k, v in c.components.items() if v is not None}
    weight_sum = sum(config.WEIGHTS[k] for k in available)
    base = 100 * sum(config.WEIGHTS[k] * v for k, v in available.items()) / weight_sum

    c.bonuses = {}
    velocities = [i["velocity"] for i in c.items if i.get("velocity") is not None]
    if velocities:
        c.bonuses["velocity"] = config.VELOCITY_MAX_BONUS * min(
            1.0, max(0.0, max(velocities)) / config.VELOCITY_SATURATION_PER_HOUR)
    quiet = any(t in text for t in config.QUIET_IMPORTANT_TERMS) and bool(c.kinds & config.OFFICIAL_KINDS)
    if quiet:
        c.bonuses["quiet_important"] = config.QUIET_IMPORTANT_BONUS
    c.score = round(min(100.0, base + sum(c.bonuses.values())), 1)

    c.flags = []
    if engagement is None:
        c.flags.append("engagement_unknown")
    if len(c.sources) == 1:
        c.flags.append("single_source")
    if "quiet_important" in c.bonuses:
        c.flags.append("quiet_important")

    total = c.engagement_total
    if len(c.sources) >= 3 and total is not None:
        c.confidence = "high"
    elif len(c.sources) >= 2 or (total is not None and total >= config.FLOOR_MIN_ENGAGEMENT):
        c.confidence = "medium"
    else:
        c.confidence = "low"

    apply_floor(c)


def apply_floor(c: Cluster) -> None:
    """Absolute evidence bar. A relative ranker alone would show noise on a quiet day.

    Every path first requires at least one niche term, so popular but off-niche items
    (hardware news, unrelated launches) never reach the digest on engagement alone.
    """
    total = c.engagement_total
    if not c.niche_hits:
        c.passes_floor, c.floor_reason = False, "no niche term matched"
    elif total is not None and total >= config.FLOOR_SINGLE_SOURCE_ENGAGEMENT:
        c.passes_floor, c.floor_reason = True, f"engagement {total:.0f} >= {config.FLOOR_SINGLE_SOURCE_ENGAGEMENT:.0f}"
    elif len(c.sources) >= config.FLOOR_MIN_SOURCES and (total is None or total >= config.FLOOR_MIN_ENGAGEMENT):
        c.passes_floor, c.floor_reason = True, f"{len(c.sources)} independent sources"
    elif "quiet_important" in c.bonuses:
        c.passes_floor, c.floor_reason = True, "official source, quiet-important, on topic"
    else:
        c.passes_floor, c.floor_reason = False, "below the confidence floor"


def rank(items: list[dict], now: datetime) -> tuple[list[Cluster], list[Cluster]]:
    """Return (passing_floor, below_floor), both sorted by score. Capping comes later."""
    clusters = cluster_items(items)
    percentiles = engagement_percentiles(items)
    for c in clusters:
        score_cluster(c, now, percentiles)
    clusters.sort(key=lambda c: c.score, reverse=True)
    passing = [c for c in clusters if c.passes_floor]
    below = [c for c in clusters if not c.passes_floor]
    return passing, below


def diversify(clusters: list[Cluster], top_n: int) -> list[Cluster]:
    cap = max(2, math.ceil(top_n * config.MAX_SOURCE_SHARE))
    shown: list[Cluster] = []
    used: dict[str, int] = {}
    for c in clusters:
        lead_source = c.lead["source"]
        if used.get(lead_source, 0) >= cap:
            continue
        shown.append(c)
        used[lead_source] = used.get(lead_source, 0) + 1
        if len(shown) >= top_n:
            break
    return shown
