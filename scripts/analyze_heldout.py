"""Pre-registered held-out analysis (docs/heldout/analysis-plan.md).

Reads the two phase summaries, scores repetition 1, checks repetition agreement, and
runs exact two-sided McNemar tests. The interval for a paired pass-rate difference
is conditional on the discordant count: a Clopper-Pearson interval for b/(b+c),
mapped to (b+c)/n * (2p - 1).
uv run python scripts/analyze_heldout.py --base runs/heldout/base --tuned runs/heldout/tuned
"""

import argparse
from collections import defaultdict
import json
from math import comb
from pathlib import Path

COMPARISONS = [
    ("tuned", "base", "primary"),
    ("base_skills", "base", "exploratory"),
    ("tuned_skills", "tuned", "exploratory"),
    ("tuned_skills", "base", "exploratory"),
]


def binom_cdf(k, n):
    return sum(comb(n, i) for i in range(k + 1)) / 2**n


def mcnemar_p(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * binom_cdf(min(b, c), n))


def beta_quantile(q, a, b):
    """Quantile of Beta(a, b) by bisection on the binomial identity (integer a, b)."""
    lo, hi = 0.0, 1.0
    for _ in range(100):
        x = (lo + hi) / 2
        # P(Beta(a,b) <= x) = P(Binomial(a+b-1, x) >= a)
        n = a + b - 1
        cdf = sum(comb(n, i) * x**i * (1 - x) ** (n - i) for i in range(a, n + 1))
        lo, hi = (x, hi) if cdf < q else (lo, x)
    return (lo + hi) / 2


def clopper_pearson(k, n, alpha=0.05):
    lower = 0.0 if k == 0 else beta_quantile(alpha / 2, k, n - k + 1)
    upper = 1.0 if k == n else beta_quantile(1 - alpha / 2, k + 1, n - k)
    return lower, upper


def compare(outcomes, treated, control, tasks):
    b = sum(outcomes[treated][t] and not outcomes[control][t] for t in tasks)
    c = sum(outcomes[control][t] and not outcomes[treated][t] for t in tasks)
    n = len(tasks)
    if b + c:
        lo, hi = clopper_pearson(b, b + c)
        interval = [(b + c) / n * (2 * lo - 1), (b + c) / n * (2 * hi - 1)]
    else:
        interval = [0.0, 0.0]
    return {
        "treated_passes": sum(outcomes[treated][t] for t in tasks),
        "control_passes": sum(outcomes[control][t] for t in tasks),
        "tasks": n,
        "treated_only": b,
        "control_only": c,
        "difference": (b - c) / n,
        "interval95": interval,
        "p": mcnemar_p(b, c),
    }


def load(directories):
    runs = []
    for directory in directories:
        summary = json.loads((Path(directory) / "summary.json").read_text())
        if not summary["complete"]:
            raise SystemExit(f"Incomplete phase: {directory}")
        for run in summary["runs"]:
            run["root"] = Path(directory) / run["artifacts"]
            runs.append(run)
    return runs


def actions(root):
    return [
        json.loads(line)["tool"]
        for line in (root / "trace.jsonl").read_text().splitlines()
        if '"event": "action"' in line
    ]


def behavior(runs, evaluators):
    rows = defaultdict(lambda: defaultdict(int))
    for run in runs:
        if run["repetition"] != 1:
            continue
        row = rows[run["arm"]]
        tools = actions(run["root"])
        first_write = tools.index("write_file") if "write_file" in tools else len(tools)
        last_write = max((i for i, t in enumerate(tools) if t == "write_file"), default=-1)
        result = json.loads((run["root"] / "result.json").read_text())
        row["attempts"] += 1
        row["read_before_first_write"] += "read_file" in tools[:first_write]
        row["validated"] += any(t in {"check", "render", "analyze"} for t in tools)
        row["turn_budget"] += run["termination"] == "turn_budget"
        row["protocol_errors"] += result.get("protocol_errors", 0)
        if evaluators[run["task_id"]] == "render-contract-v1":
            row["rendered_tasks"] += 1
            row["final_render"] += "render" in tools[last_write + 1 :]
    return {arm: dict(row) for arm, row in rows.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--tuned", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("docs/heldout/results.json"))
    args = parser.parse_args()
    runs = load([args.base, args.tuned])
    if any(r["status"] == "infrastructure_error" for r in runs):
        raise SystemExit("Infrastructure errors present; report them, do not score")
    passed = defaultdict(dict)
    meta = {}
    for run in runs:
        passed[(run["arm"], run["repetition"])][run["task_id"]] = run["status"] == "passed"
        meta[run["task_id"]] = run["suite"]
    categories, evaluators = {}, {}
    for run in runs:
        manifest = json.loads((run["root"] / "task.json").read_text())
        categories[run["task_id"]] = manifest["category"]
        evaluators[run["task_id"]] = manifest["evaluator"]
    arms = sorted({a for a, _ in passed})
    tasks = sorted(meta)
    rep1 = {arm: passed[(arm, 1)] for arm in arms}
    both = {arm: {t: passed[(arm, 1)][t] and passed[(arm, 2)][t] for t in tasks} for arm in arms}
    disagreements = sorted(
        (arm, t) for arm in arms for t in tasks if passed[(arm, 1)][t] != passed[(arm, 2)][t]
    )
    groups = {"all": tasks}
    for suite in sorted(set(meta.values())):
        groups[f"suite:{suite}"] = [t for t in tasks if meta[t] == suite]
    for category in sorted(set(categories.values())):
        groups[f"category:{category}"] = [t for t in tasks if categories[t] == category]
    report = {
        "plan": "docs/heldout/analysis-plan.md",
        "scored_repetition": 1,
        "repetition_disagreements": disagreements,
        "pass_counts": {arm: sum(rep1[arm].values()) for arm in arms},
        "comparisons": [
            {
                "treated": treated,
                "control": control,
                "status": status,
                "group": group,
                **compare(rep1, treated, control, members),
            }
            for treated, control, status in COMPARISONS
            for group, members in groups.items()
        ],
        "primary_both_repetitions": compare(both, "tuned", "base", tasks),
        "behavior_rep1": behavior(runs, evaluators),
        "per_task": {
            t: {
                "suite": meta[t],
                "category": categories[t],
                **{arm: [passed[(arm, 1)][t], passed[(arm, 2)][t]] for arm in arms},
            }
            for t in tasks
        },
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    primary = next(
        c for c in report["comparisons"] if c["status"] == "primary" and c["group"] == "all"
    )
    print(json.dumps({"pass_counts": report["pass_counts"], "primary": primary}, indent=2))


if __name__ == "__main__":
    main()
