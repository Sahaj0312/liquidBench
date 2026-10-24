"""Dry by default. One frozen four-attempt block; no provision, retry or resume.

Use the same pinned tokenizer extras as prepare_diagnostic.py. Paid execution
requires explicit user approval outside this CLI; --execute is not authorization.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from liquidbench.diagnostic import CONDITIONS, execute_block, messages, treatment
from liquidbench.preflight import validate_report
from liquidbench.provider import ChatProvider
from liquidbench.runner import load_config, run, source_version
from liquidbench.sandbox import image_id
from liquidbench.skills import SkillBundle, sha256
from liquidbench.task import discover_tasks, fingerprint
from prepare_diagnostic import prepare, tokenizer_tools


def validate_serving(observed, expected, now=None):
    if any(observed.get(k) != value for k, value in expected.items()):
        raise ValueError("Serving evidence differs from pinned A40/BF16 environment")
    if observed.get("all_pinned_model_files_verified") is not True:
        raise ValueError("Model files not verified")
    verified = datetime.fromisoformat(observed["verified_utc"])
    if verified.tzinfo is None:
        raise ValueError("Serving time must include timezone")
    age = ((now or datetime.now(timezone.utc)) - verified).total_seconds()
    if age < 0 or age >= 3600:
        raise ValueError("Serving identity evidence is stale")


def check_order(plan, root, block):
    if block == 0:
        if root.exists():
            raise ValueError("Fresh study output required")
        return
    if json.loads((root / "plan.json").read_text()) != plan:
        raise ValueError("Study output plan mismatch")
    for previous in range(block):
        summary = json.loads((root / f"block-{previous:02d}" / "attempts/summary.json").read_text())
        expected = [x for x in plan["order"] if x["block"] == previous]
        if (
            not summary["complete"]
            or summary["plan_sha256"] != fingerprint(plan)
            or summary["planned"] != expected
            or len(summary["runs"]) != 4
        ):
            raise ValueError("Previous block incomplete; preserve missingness, no retry")
        for actual, wanted in zip(summary["runs"], expected):
            if any(actual.get(k) != v for k, v in wanted.items()) or actual["status"] not in {
                "passed",
                "failed",
            }:
                raise ValueError("Previous block sequence/termination mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--block", type=int, choices=range(20))
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--serving-evidence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    tokenizer, count, metadata = tokenizer_tools()
    plan = prepare(tokenizer, count)
    plan["tokenizer"] = metadata
    if plan != json.loads(Path("experiments/diagnostic-v1-plan.json").read_text()):
        raise ValueError("Frozen diagnostic plan changed")
    if not args.execute:
        print(
            json.dumps(
                {
                    "attempts": 80,
                    "blocks": 20,
                    "tasks": plan["selected_tasks"],
                    "inference_performed": False,
                },
                indent=2,
            )
        )
        return 0
    if any(x is None for x in (args.block, args.preflight, args.serving_evidence, args.output)):
        raise ValueError("Execution needs block, preflight, serving-evidence and output")
    if source_version()["git_status"]:
        raise ValueError("Execution requires a clean committed source tree")
    check_order(plan, args.output, args.block)
    destination = args.output / f"block-{args.block:02d}"
    destination.mkdir(parents=True, exist_ok=False)
    if args.block == 0:
        (args.output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    gate = {
        "passed": False,
        "plan_sha256": fingerprint(plan),
        "preflight_sha256": sha256(args.preflight.read_bytes()),
        "serving_evidence_sha256": sha256(args.serving_evidence.read_bytes()),
    }
    tasks = discover_tasks(Path("tasks/dev"))
    bundle = SkillBundle.load(load_config("configs/m6-full.json")["skills"])
    try:
        validate_report(json.loads(args.preflight.read_text()), plan["config"])
        validate_serving(
            json.loads(args.serving_evidence.read_text()),
            json.loads(Path("experiments/diagnostic-v1-serving.json").read_text()),
        )
        provider = ChatProvider(plan["config"])
        checks = []
        gate["counts"] = checks
        for task in tasks:
            if task.manifest["id"] not in plan["selected_tasks"]:
                continue
            for condition in CONDITIONS:
                ctx = treatment(plan, task, condition, bundle)["injected_context"]
                history = messages(
                    task.manifest["prompt"], condition, ctx["content"] if ctx else None
                )
                expected = plan["measurements"][task.manifest["id"]][condition]["initial_tokens"]
                actual = provider.count_prompt(history, plan["config"]["request_timeout"])
                checks.append(
                    {
                        "task": task.manifest["id"],
                        "condition": condition,
                        "local": expected,
                        "endpoint": actual,
                    }
                )
                if actual != expected:
                    raise ValueError("Local/server diagnostic prompt count mismatch")
        gate["passed"] = True
    except Exception as exc:
        gate["error"] = str(exc)
        raise
    finally:
        (destination / "gate.json").write_text(json.dumps(gate, indent=2) + "\n")
    return execute_block(
        plan,
        tasks,
        args.block,
        destination / "attempts",
        runner=run,
        resolve_image=image_id,
        bundle=bundle,
    )


if __name__ == "__main__":
    raise SystemExit(main())
