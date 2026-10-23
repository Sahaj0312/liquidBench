"""Dry plan by default. Execution needs fresh approval, serving evidence and v2 preflight.

Runs one predefined 16-attempt block. No provisioning, resumes or replacements.
"""

import argparse
import json
from pathlib import Path

from liquidbench.preflight import validate_report
from liquidbench.provider import ChatProvider
from liquidbench.runner import load_config
from liquidbench.skills import sha256
from liquidbench.study import CONDITIONS, build_plan, execute_block, verify_counts
from liquidbench.task import discover_tasks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--block", type=int, choices=range(15))
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--serving-evidence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    tasks = discover_tasks(Path("tasks/dev"))
    configs = {c: load_config(f"configs/m6-{c}.json") for c in CONDITIONS}
    plan = build_plan(configs, tasks)
    frozen = json.loads(Path("experiments/m6-plan.json").read_text())
    if frozen != plan:
        raise ValueError("Study differs from frozen plan; do not execute")
    if not args.execute:
        print(
            json.dumps(
                {
                    "attempts": len(plan["order"]),
                    "blocks": 15,
                    "plan": "experiments/m6-plan.json",
                    "inference_performed": False,
                },
                indent=2,
            )
        )
        return 0
    if any(
        value is None for value in (args.block, args.preflight, args.serving_evidence, args.output)
    ):
        raise ValueError("Execution needs block, preflight, serving-evidence and fresh output")
    if args.output.exists():
        raise ValueError("Output exists; no overwrite/resume/replacement")
    args.output.mkdir(parents=True)
    gate = {
        "preflight_sha256": sha256(args.preflight.read_bytes()),
        "serving_evidence_sha256": sha256(args.serving_evidence.read_bytes()),
        "passed": False,
    }
    try:
        validate_report(json.loads(args.preflight.read_text()), configs["base"])
        gate["counts"] = verify_counts(
            plan,
            tasks,
            json.loads(Path("docs/calibration/milestone-6-feasibility.json").read_text()),
            ChatProvider(configs["base"]),
        )
        gate["passed"] = True
    except Exception as exc:
        gate["error"] = str(exc)
        raise
    finally:
        (args.output / "gate.json").write_text(json.dumps(gate, indent=2) + "\n")
    return execute_block(plan, tasks, args.block, args.output / "attempts")


if __name__ == "__main__":
    raise SystemExit(main())
