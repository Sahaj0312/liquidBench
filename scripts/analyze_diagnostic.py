"""Predeclared diagnostic v1 analysis (docs/diagnostic/plan.md); no rescoring or replacement.

Missing and infrastructure attempts stay missing. Raw traces and reference bodies remain
private; this report contains metrics, paths and hashes only.
uv run python scripts/analyze_diagnostic.py runs/diagnostic-v1
"""

from collections import Counter
import json
from pathlib import Path
import re
import sys

from analyze_loading_study import paired_counts
from analyze_runs import summarize
from liquidbench.diagnostic import CONDITIONS, DOMAINS
from liquidbench.task import discover_tasks, fingerprint

ROOT = Path(__file__).resolve().parents[1]
COMPARISONS = (
    ("clarified", "original"),  # tool instructions
    ("neutral", "clarified"),  # added length alone
    ("reference", "neutral"),  # relevant content at equal tokens
    ("reference", "clarified"),  # total effect of loading the reference
)
UNDEFINED_FILTER = re.compile(r"Liquid::UndefinedFilter: Liquid error: undefined filter (\w+)")


def read_attempt(directory):
    run = summarize(directory)
    result = json.loads((directory / "result.json").read_text())
    filters = []
    for line in (directory / "trace.jsonl").read_text().splitlines():
        event = json.loads(line)
        if event["event"] != "tool_result":
            continue
        error = event.get("error") or event.get("result", {}).get("error") or ""
        filters += UNDEFINED_FILTER.findall(error)
    run["initial_context_sha256"] = result.get("initial_context_sha256")
    run["undefined_filter_renders"] = filters
    return run


def task_metadata(plan, root=ROOT / "tasks/dev"):
    expected = {r["task_id"]: r["task_digest"] for r in plan["order"]}
    metadata = {}
    for task in discover_tasks(root):
        name = task.manifest["id"]
        if name not in expected:
            continue
        if task.digest != expected[name]:
            raise ValueError("Task metadata differs from frozen task digest")
        metadata[name] = {
            "category": task.manifest["category"],
            "difficulty": task.manifest["difficulty"],
            "domain": DOMAINS[task.manifest["category"]],
            "editable_files": task.manifest["editable_files"],
        }
    if set(metadata) != set(expected):
        raise ValueError("Missing task metadata")
    return metadata


def check_delivery(plan, entry, run):
    """The attempt received exactly the frozen treatment, or it is not analyzable."""
    task_id, condition = entry["task_id"], entry["condition"]
    if run["status"] == "infrastructure_error" and run["initial_context_sha256"] is None:
        return
    if run["initial_context_sha256"] != plan["measurements"][task_id][condition]["messages_sha256"]:
        raise ValueError("Delivered initial context differs from frozen plan")
    accesses, exposures = run["skill_accesses"], run["context_exposures"]
    if condition == "reference":
        wanted = plan["references"][task_id]
        if [(a["path"], a["mode"], a["sha256"]) for a in accesses] != [
            (wanted["path"], "injected", wanted["sha256"])
        ]:
            raise ValueError("Reference delivery differs from frozen plan")
    elif accesses:
        raise ValueError("Skill content reached a non-reference condition")
    neutral = [e["message_sha256"] for e in exposures]
    if neutral != ([plan["controls"][task_id]["sha256"]] if condition == "neutral" else []):
        raise ValueError("Neutral delivery differs from frozen plan")


def compare(plan, root, *, reader=read_attempt):
    expected = {(r["repetition"], r["task_id"], r["condition"]): r for r in plan["order"]}
    metadata = task_metadata(plan)
    wanted_config = {**plan["config"], "image": plan["runtime_image_id"]}
    found, gates = {}, []
    for block in sorted(Path(root).glob("block-*")):
        gate_path = block / "gate.json"
        gate = json.loads(gate_path.read_text()) if gate_path.exists() else None
        gates.append({"block": block.name, "gate_passed": bool(gate and gate["passed"])})
        summary_path = block / "attempts/summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text())
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
            run = reader(block / "attempts" / artifact)
            if run["task_digest"] != entry["task_digest"] or run["task_id"] != entry["task_id"]:
                raise ValueError("Attempt task differs from plan")
            if run["status"] != entry["status"] or run["termination"] != entry["termination"]:
                raise ValueError("Attempt outcome differs from summary")
            early_infrastructure = (
                run["status"] == "infrastructure_error" and run["image_id"] is None
            )
            if run["config"] != wanted_config or (
                not early_infrastructure and run["image_id"] != plan["runtime_image_id"]
            ):
                raise ValueError("Attempt configuration differs from plan")
            if run["source"]["python_source_digest"] != plan["python_source_digest"]:
                raise ValueError("Attempt source differs from plan")
            check_delivery(plan, entry, run)
            editable = set(metadata[entry["task_id"]]["editable_files"])
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
                    "action_counts",
                    "undefined_filter_renders",
                    "initial_context_sha256",
                    "sha256",
                )
            }
            found[key].update(
                position=entry["position"],
                out_of_scope_edits=sorted(set(run["changed_files"]) - editable),
                delivered_context=[
                    {k: x.get(k) for k in ("kind", "path", "message_sha256", "message_bytes")}
                    for x in run["skill_accesses"] + run["context_exposures"]
                ],
            )
    pairs = []
    for repetition, task in sorted({(r, t) for r, t, _ in expected}):
        conditions = {
            c: found.get((repetition, task, c), {"status": "missing"}) for c in CONDITIONS
        }
        info = {k: v for k, v in metadata[task].items() if k != "editable_files"}
        pairs.append({"repetition": repetition, "task_id": task, **info, "conditions": conditions})
    passes = {
        task: {
            c: sum(p["conditions"][c]["status"] == "passed" for p in pairs if p["task_id"] == task)
            for c in CONDITIONS
        }
        for task in sorted(metadata)
    }
    totals = {
        c: dict(Counter(pair["conditions"][c]["status"] for pair in pairs)) for c in CONDITIONS
    }
    # Pooled view sums the per-repetition pairs; repeats are not independent samples.
    pooled = paired_counts([{**p, "repetition": "pooled"} for p in pairs], COMPARISONS)
    return {
        "study": "diagnostic-v1",
        "development_only": True,
        "research_result": False,
        "plan_sha256": fingerprint(plan),
        "gates": gates,
        "totals": totals,
        "passes_per_task": passes,
        "paired_outcomes": pairs,
        "paired_win_tie_loss": paired_counts(pairs, COMPARISONS),
        "paired_win_tie_loss_pooled": pooled,
        "pairing_rule": "Left versus right per task and repetition on unchanged attempt status. Missing pairs precede infrastructure pairs; neither counts as a tie.",
        "interpretation": "Five tasks, temperature 0 and one seed: diagnostic and directional only. No significance tests. Disagreement between identical-seed repeats is reported as nondeterminism.",
    }


if __name__ == "__main__":
    plan = json.loads((ROOT / "experiments/diagnostic-v1-plan.json").read_text())
    print(json.dumps(compare(plan, Path(sys.argv[1])), indent=2))
