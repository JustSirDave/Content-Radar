"""Weight tuning from the owner's own post / maybe / no marks."""

from __future__ import annotations

import json
from pathlib import Path

MIN_PER_GROUP = 5  # fewer marks than this in either group says nothing reliable
SEPARATION = 0.05  # a part whose averages differ by less than this does not predict the marks


def find_in_latest_digest(out_dir: str | Path, topic_id: int) -> dict:
    """Return the topic as it was shown in the newest digest, with its score parts."""
    files = sorted(Path(out_dir).glob("*.json"))
    if not files:
        raise FileNotFoundError(f"no digest found in {out_dir}; run `python -m radar run` first")
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    for section in ("topics", "official_updates"):
        for t in data.get(section, []):
            if t.get("topic_id") == topic_id:
                return t
    raise KeyError(f"topic {topic_id} is not in the latest digest ({files[-1].name}); it can only be "
                   "rated while it is shown, because its score parts come from the digest")


def summarize(ratings: list[dict]) -> dict:
    """Average each score part for 'post' and 'no' marks. 'maybe' is counted but not compared."""
    groups = {r: [x for x in ratings if x["rating"] == r] for r in ("post", "maybe", "no")}
    counts = {k: len(v) for k, v in groups.items()}
    parts = sorted({p for x in ratings for p in x["components"]})
    rows = []
    for part in parts:
        means = {}
        for g in ("post", "no"):
            vals = [x["components"][part] for x in groups[g] if x["components"].get(part) is not None]
            means[g] = sum(vals) / len(vals) if vals else None
        gap = None if None in means.values() else means["post"] - means["no"]
        rows.append({"part": part, "post": means["post"], "no": means["no"], "gap": gap})
    enough = counts["post"] >= MIN_PER_GROUP and counts["no"] >= MIN_PER_GROUP
    return {"counts": counts, "enough": enough, "rows": rows}


def render(summary: dict) -> str:
    c = summary["counts"]
    lines = [f"marks: {c['post']} post, {c['maybe']} maybe, {c['no']} no"]
    if not summary["enough"]:
        lines.append(f"not enough yet: need at least {MIN_PER_GROUP} 'post' and {MIN_PER_GROUP} 'no' marks "
                     "before the averages mean anything. Keep rating topics from your digests.")
        return "\n".join(lines)
    lines.append(f"{'score part':14} {'post':>6} {'no':>6} {'gap':>7}  reading")
    for r in summary["rows"]:
        if r["gap"] is None:
            lines.append(f"{r['part']:14} {'n/a':>6} {'n/a':>6} {'':>7}  not measured for one group")
            continue
        reading = ("does not separate post from no" if abs(r["gap"]) < SEPARATION
                   else "higher for items you post" if r["gap"] > 0 else "higher for items you skip")
        lines.append(f"{r['part']:14} {r['post']:6.2f} {r['no']:6.2f} {r['gap']:+7.2f}  {reading}")
    lines.append("Raise the weight of parts that are higher for items you post; lower or drop parts "
                 "that do not separate. Weights live in radar/config.py (WEIGHTS).")
    return "\n".join(lines)
