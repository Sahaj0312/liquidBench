"""Exploratory Sonnet reference against the scored arms (analysis-plan.md, Addition 4).

Uses the same scoring, tests and groups as analyze_heldout.py; writes a separate report.
uv run python scripts/analyze_heldout_claude.py --base runs/heldout/base-s2 \
  --tuned runs/heldout/tuned-s2 --claude runs/heldout/claude
"""

import argparse
from collections import defaultdict
import json
from pathlib import Path

from analyze_heldout import behavior, compare, load, primary_tasks

COMPARISONS = [("claude_skills", "claude"), ("claude", "tuned"), ("claude", "base")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--tuned", type=Path, required=True)
    parser.add_argument("--claude", type=Path, required=True)
    parser.add_argument("--clusters", type=Path, default=Path("docs/heldout/theme-clusters.json"))
    parser.add_argument("--out", type=Path, default=Path("docs/heldout/reference-claude.json"))
    args = parser.parse_args()
    runs = load([args.base, args.tuned, args.claude])
    if any(r["status"] == "infrastructure_error" for r in runs):
        raise SystemExit("Infrastructure errors present; report them, do not score")
    passed, suites, evaluators = defaultdict(dict), {}, {}
    reads = defaultdict(lambda: [0, 0])
    served = defaultdict(int)
    for run in runs:
        passed[(run["arm"], run["repetition"])][run["task_id"]] = run["status"] == "passed"
        suites[run["task_id"]] = run["suite"]
        evaluators[run["task_id"]] = json.loads((run["root"] / "task.json").read_text())[
            "evaluator"
        ]
        result = json.loads((run["root"] / "result.json").read_text())
        reads[run["arm"]][0] += 1
        reads[run["arm"]][1] += bool(result["skill_accesses"])
        if run["arm"].startswith("claude"):
            for line in (run["root"] / "trace.jsonl").read_text().splitlines():
                model = (json.loads(line).get("metadata") or {}).get("served_model")
                if model:
                    served[model] += 1
    arms = sorted({a for a, _ in passed})
    tasks = sorted(suites)
    rep1 = {arm: passed[(arm, 1)] for arm in arms}
    primary = primary_tasks(tasks, suites, json.loads(args.clusters.read_text()))
    groups = {"primary": primary, "all": tasks}
    for suite in sorted(set(suites.values())):
        groups[f"suite:{suite}"] = [t for t in tasks if suites[t] == suite]
    report = {
        "plan": "docs/heldout/analysis-plan.md Addition 4 (exploratory)",
        "scored_repetition": 1,
        "pass_counts": {arm: sum(rep1[arm].values()) for arm in arms},
        "comparisons": [
            {"treated": t, "control": c, "group": g, **compare(rep1, t, c, members)}
            for t, c in COMPARISONS
            for g, members in groups.items()
        ],
        "repetition_disagreements": sorted(
            (arm, t)
            for arm in ("claude", "claude_skills")
            for t in tasks
            if passed[(arm, 1)][t] != passed[(arm, 2)][t]
        ),
        "attempts_with_skill_reads": {
            arm: {"attempts": n, "with_reads": k} for arm, (n, k) in reads.items()
        },
        "served_models": dict(served),
        "behavior_rep1": {
            arm: row for arm, row in behavior(runs, evaluators).items() if arm.startswith("claude")
        },
        "claude_failures_rep1": {
            arm: sorted(t for t in tasks if not rep1[arm][t]) for arm in ("claude", "claude_skills")
        },
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("pass_counts", "attempts_with_skill_reads")}))


if __name__ == "__main__":
    main()
