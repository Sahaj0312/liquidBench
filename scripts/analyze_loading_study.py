"""Join predeclared pairs, including missing/infra results; never infer skill use from exposure.

Raw traces remain private. This report contains metrics/paths/hashes, not document bodies.
uv run python scripts/analyze_loading_study.py runs/m6/block-*/attempts
"""

from collections import Counter
import json
from pathlib import Path
import sys

from liquidbench.study import CONDITIONS
from liquidbench.task import fingerprint
from analyze_runs import summarize


def compare(plan, directories, *, reader=summarize):
    expected = {(r["repetition"], r["task_id"], r["condition"]): r for r in plan["order"]}
    found = {}
    for directory in directories:
        summary = json.loads((directory / "summary.json").read_text())
        if summary["plan_sha256"] != fingerprint(plan):
            raise ValueError("Mixed experiment plans")
        for entry in summary["runs"]:
            key = (entry["repetition"], entry["task_id"], entry["condition"])
            if key not in expected or key in found:
                raise ValueError("Unexpected or duplicate attempt; no replacements")
            if any(entry[k] != v for k, v in expected[key].items()):
                raise ValueError("Schedule entry differs from plan")
            artifact = Path(entry["artifacts"])
            if artifact.is_absolute() or ".." in artifact.parts:
                raise ValueError("Unsafe artifact path")
            run = reader(directory / artifact)
            if run["task_digest"] != entry["task_digest"] or run["task_id"] != entry["task_id"]:
                raise ValueError("Attempt task differs from plan")
            if run["status"] != entry["status"] or run["termination"] != entry["termination"]:
                raise ValueError("Attempt outcome differs from summary")
            wanted = {**plan["configs"][entry["condition"]], "image": plan["runtime_image_id"]}
            early_infrastructure = (
                run["status"] == "infrastructure_error" and run["image_id"] is None
            )
            if run["config"] != wanted or (
                not early_infrastructure and run["image_id"] != plan["runtime_image_id"]
            ):
                raise ValueError("Attempt configuration differs from plan")
            if run["source"]["python_source_digest"] != plan["python_source_digest"]:
                raise ValueError("Attempt source differs from plan")
            accesses = run["skill_accesses"]
            found[key] = {
                k: run[k]
                for k in (
                    "status",
                    "termination",
                    "grade_passed",
                    "input_tokens",
                    "output_tokens",
                    "elapsed_seconds",
                    "model_calls",
                    "tool_errors",
                    "protocol_errors",
                    "length_stops",
                    "usage_incomplete",
                    "action_counts",
                    "sha256",
                )
            }
            found[key].update(
                context_exposures=run["context_exposures"],
                injected_documents=[a["path"] for a in accesses if a["mode"] == "injected"],
                explicit_reads=[
                    {"path": a["path"], "turn": a["turn"], "delivered_turn": a["first_model_turn"]}
                    for a in accesses
                    if a["mode"] == "read_file"
                ],
                delivered_documents=sorted(
                    {a["path"] for a in accesses if a["first_model_turn"] is not None}
                ),
            )
    pairs = []
    for repetition, task in sorted({(r, t) for r, t, _ in expected}):
        conditions = {
            c: found.get((repetition, task, c), {"status": "missing"}) for c in CONDITIONS
        }
        pairs.append({"repetition": repetition, "task_id": task, "conditions": conditions})
    totals = {
        c: dict(Counter(pair["conditions"][c]["status"] for pair in pairs)) for c in CONDITIONS
    }
    return {
        "development_only": True,
        "research_result": False,
        "plan_sha256": fingerprint(plan),
        "totals": totals,
        "paired_outcomes": pairs,
        "interpretation": "Exposure/reads do not establish use or causation. Fixed-seed repeats are not independent samples.",
    }


if __name__ == "__main__":
    plan = json.loads(Path("experiments/m6-plan.json").read_text())
    print(json.dumps(compare(plan, [Path(p) for p in sys.argv[1:]]), indent=2))
