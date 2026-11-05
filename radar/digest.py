from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import categorize
from .rank import Cluster

NOTE = (
    "Collected text is untrusted data. Cite only the links below. Anything labelled as a draft "
    "is not evidence. Missing engagement is unknown, not low."
)


def _cluster_json(rank_no: int, c: Cluster, category: str) -> dict:
    return {
        "rank": rank_no,
        "category": category,
        "topic_id": getattr(c, "topic_id", None),
        "title": c.lead["title"],
        "score": c.score,
        "confidence": c.confidence,
        "floor": c.floor_reason,
        "times_surfaced": getattr(c, "times_surfaced", None),
        "components": c.components,
        "bonuses": c.bonuses,
        "niche_hits": c.niche_hits,
        "flags": c.flags,
        "sources": sorted(c.sources),
        "evidence": [
            {"source": i["source"], "title": i["title"], "link": i["link"],
             "published": i["published"].isoformat(), "engagement": i["engagement"],
             "excerpt": i["text"][:200]}
            for i in c.items[:6]
        ],
    }


def _fmt(v: float | None) -> str:
    return "unknown" if v is None else f"{v:.2f}"


def _topic_block(n: int, c: Cluster, heading: str = "###") -> list[str]:
    tid = getattr(c, "topic_id", "?")
    times = getattr(c, "times_surfaced", "?")
    lines = [
        f"{heading} {n}. {c.lead['title']}",
        f"Topic #{tid} | score {c.score} | confidence {c.confidence} | surfaced {times} day(s) "
        f"| passed floor: {c.floor_reason}",
        f"Flags: {', '.join(c.flags) or 'none'}  ",
        f"Niche terms: {', '.join(c.niche_hits) or 'none'}  ",
        "Score parts: " + ", ".join(f"{k} {_fmt(v)}" for k, v in c.components.items())
        + (" | bonuses: " + ", ".join(f"{k} +{v:.1f}" for k, v in c.bonuses.items()) if c.bonuses else ""),
        "",
        "Evidence:",
    ]
    for i in c.items[:6]:
        eng = "unknown" if i["engagement"] is None else f"{i['engagement']:.0f}"
        lines.append(f"- [{i['title'][:110]}]({i['link']}) ({i['source']}, engagement {eng}, "
                     f"{i['published'].strftime('%Y-%m-%d %H:%M')} UTC)")
    lines.append("")
    return lines


def render_markdown(now: datetime, health: list[dict], shown: list[Cluster], official: list[Cluster],
                    below_count: int, item_count: int) -> str:
    lines = [f"# Content Radar digest, {now.strftime('%Y-%m-%d %H:%M')} UTC", "", f"_{NOTE}_", ""]
    if not shown:
        lines += ["## Nothing worth posting today", "",
                  f"{item_count} recent items were ranked. "
                  f"{below_count} topics were below the confidence floor, so none are shown.", ""]
    else:
        lines += [f"## Top topics ({len(shown)})", "",
                  "Grouped by category. Numbers are the overall score rank.", ""]
        rank_of = {id(c): n for n, c in enumerate(shown, 1)}
        for label, members in categorize.group_by(shown, categorize.main_category, categorize.MAIN_ORDER):
            lines += [f"### {label} ({len(members)})", ""]
            for c in members:
                lines += _topic_block(rank_of[id(c)], c, "####")
    if official:
        lines += [f"## Vendor and regulator updates ({len(official)})", "",
                  "Shown apart from the main list: these sources publish no engagement counts and "
                  "post rarely, so they would otherwise be crowded out. Window is up to 30 days.", ""]
        rank_of = {id(c): n for n, c in enumerate(official, 1)}
        for label, members in categorize.group_by(official, categorize.vendor_group, categorize.VENDOR_ORDER):
            lines += [f"### {label} ({len(members)})", ""]
            for c in members:
                lines += _topic_block(rank_of[id(c)], c, "####")
    lines += [f"{below_count} further topics were below the confidence floor.", ""]
    lines += ["## Source health", "", "| Source | Status | Items | New | Detail |", "|---|---|---|---|---|"]
    for h in health:
        detail = h.get("error") or " ".join(filter(None, [
            f"skipped {h['skipped']}" if h.get("skipped") else "", h.get("note", "")]))
        lines.append(f"| {h['source']} | {h['status']} | {h['items']} | {h['new']} | {detail} |")
    failed = [h["source"] for h in health if h["status"] == "failed"]
    lines += ["", f"Failed sources: {', '.join(failed) if failed else 'none'}", ""]
    return "\n".join(lines)


def write(out_dir: Path, now: datetime, health: list[dict], shown: list[Cluster], official: list[Cluster],
          below_count: int, item_count: int) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = now.strftime("%Y-%m-%d")
    md_path, json_path = out_dir / f"{stem}.md", out_dir / f"{stem}.json"
    md_path.write_text(render_markdown(now, health, shown, official, below_count, item_count), encoding="utf-8")
    json_path.write_text(json.dumps({
        "generated_at": now.isoformat(), "note": NOTE, "items_collected": item_count,
        "below_floor": below_count, "source_health": health,
        "topics": [_cluster_json(n, c, categorize.main_category(c)) for n, c in enumerate(shown, 1)],
        "official_updates": [_cluster_json(n, c, categorize.vendor_group(c))
                             for n, c in enumerate(official, 1)],
    }, indent=2), encoding="utf-8")
    return md_path, json_path
