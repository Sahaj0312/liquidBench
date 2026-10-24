"""Group held-out extension tasks into theme clusters and pick one primary task per cluster.

Authoring sampled each held-out theme in several requests (with different angles), so
the extension holds several tasks about the same storefront feature. Such tasks are
not independent, and the paired McNemar test assumes they are. This step groups
themes into clusters (themes sharing a non-generic word stem, transitively), assigns
each task to the theme of its request that its family name and prompt match best,
and marks the earliest-authored task per cluster as primary. Every task still runs;
the primary test uses the primary tasks plus the original suite. Run after the
ambiguity audit and before freezing; no model has attempted any of these tasks.
uv run python scripts/cluster_heldout_ext.py [--dry-run]
"""

import argparse
import json
from pathlib import Path
import re

from heldout_themes import HELDOUT_THEMES
from liquidbench.heldout import EXTENSION

OUT = Path("docs/heldout/theme-clusters.json")
GENERIC = {
    "section", "labels", "label", "list", "script", "page", "block", "notice",
    "table", "items", "rows", "product", "prompt",
}  # fmt: skip
STOP = {"a", "an", "the", "to", "of", "and", "for", "in", "on", "with"}


def stem(word):
    return word[:-1] if word.endswith("s") and not word.endswith("ss") else word


def stems(text):
    words = set(re.findall(r"[a-z0-9]+", text.lower())) - STOP
    return {stem(w) for w in words} - {stem(g) for g in GENERIC}


def base_theme(theme):
    return theme.split(" (angle:")[0].strip()


def theme_clusters(themes):
    """Union-find over themes linked by a shared non-generic stem; returns theme -> cluster."""
    parent = {t: t for t in themes}

    def find(t):
        while parent[t] != t:
            t = parent[t]
        return t

    for a in themes:
        for b in themes:
            if a < b and stems(a) & stems(b):
                parent[find(b)] = find(a)
    groups = {}
    for t in themes:
        groups.setdefault(find(t), []).append(t)
    return {t: " | ".join(sorted(groups[find(t)])) for t in themes}


def assign_theme(family, prompt, candidates):
    """The candidate theme whose stems the family name (first) and prompt match best."""

    def score(theme):
        s = stems(theme)
        return (len(s & stems(family.replace("-", " "))), len(s & stems(prompt)))

    ranked = sorted(candidates, key=score, reverse=True)
    return ranked[0], score(ranked[0]) == score(ranked[-1])


def authored():
    """Kept held-out extension tasks in authoring order, with their request's themes."""
    rows = []
    for line in Path("runs/training/authoring.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row["verdict"] == "kept" and row["reason"].startswith("tasks/heldout-ext/"):
            rows.append(row)
    return rows


def select(rows, present, prompts, clusters):
    chosen, decisions = {}, []
    for row in rows:
        family = row["family"]
        if family not in present:
            continue
        theme, tie = assign_theme(
            family, prompts.get(family, ""), [base_theme(t) for t in row["themes"]]
        )
        cluster = clusters.get(theme, theme)
        primary = cluster not in chosen
        if primary:
            chosen[cluster] = family
        decisions.append(
            {
                "task": family,
                "theme": theme,
                "theme_tie": tie,
                "cluster": cluster,
                "primary": primary,
                "same_cluster_as": None if primary else chosen[cluster],
            }
        )
    return decisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    themes = sorted({t for ts in HELDOUT_THEMES.values() for t in ts})
    rows = authored()
    themes = sorted(set(themes) | {base_theme(t) for r in rows for t in r["themes"]})
    clusters = theme_clusters(themes)
    present = {p.name for p in EXTENSION.iterdir() if p.is_dir()}
    prompts = {
        name: json.loads((EXTENSION / name / "task.json").read_text())["prompt"] for name in present
    }
    decisions = select(rows, present, prompts, clusters)
    unlisted = present - {d["task"] for d in decisions}
    if unlisted:
        raise SystemExit(f"Tasks without an authoring record: {sorted(unlisted)}")
    primary = [d for d in decisions if d["primary"]]
    print(json.dumps({"tasks": len(decisions), "primary": len(primary)}, indent=2))
    for d in decisions:
        mark = "primary" if d["primary"] else f"(cluster of {d['same_cluster_as']})"
        print(f"{d['task']:30} {d['cluster'][:60]:60} {mark}{' TIE' if d['theme_tie'] else ''}")
    if args.dry_run:
        return
    OUT.write_text(
        json.dumps({"rule": __doc__.split("\n\n")[1], "decisions": decisions}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
