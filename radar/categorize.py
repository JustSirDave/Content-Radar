"""Rule-based grouping of ranked topics into digest categories. Rules live in radar/config.py."""

from __future__ import annotations

from typing import Callable

from . import config
from .rank import Cluster


def main_category(cluster: Cluster) -> str:
    """Category with the most matched niche-term weight; earlier category wins a tie."""
    best, best_weight = config.UNCATEGORISED, 0
    for name, terms in config.CATEGORIES:
        weight = sum(config.NICHE_TERMS[t] for t in cluster.niche_hits if t in terms)
        if weight > best_weight:
            best, best_weight = name, weight
    return best


def vendor_group(cluster: Cluster) -> str:
    for item in cluster.items:
        for label, prefixes in config.VENDOR_GROUPS:
            if item["source"].startswith(prefixes):
                return label
    return config.OTHER_UPDATES


def group_by(clusters: list[Cluster], key: Callable[[Cluster], str],
             order: list[str]) -> list[tuple[str, list[Cluster]]]:
    """Groups in `order`, then any other label last. Score order is kept inside a group."""
    buckets: dict[str, list[Cluster]] = {}
    for c in clusters:
        buckets.setdefault(key(c), []).append(c)
    labels = [o for o in order if o in buckets] + [k for k in buckets if k not in order]
    return [(label, buckets[label]) for label in labels]


MAIN_ORDER = [name for name, _ in config.CATEGORIES] + [config.UNCATEGORISED]
VENDOR_ORDER = [label for label, _ in config.VENDOR_GROUPS] + [config.OTHER_UPDATES]
