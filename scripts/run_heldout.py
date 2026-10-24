"""Held-out four-arm evaluation: freeze the plan locally, then execute one phase per server.

  freeze-extension  write docs/heldout/extension-manifest.json from tasks/heldout-ext
  plan              build and freeze experiments/heldout-plan.json and its initial counts
  execute           run one phase (base | tuned) against the live endpoint

Execution re-derives the plan and refuses to run if it differs from the frozen
file, if either held-out manifest fails to verify, if the endpoint preflight
failed, or if the live server counts any initial prompt differently.
uv run --with transformers==5.19.0 --with tokenizers==0.23.3 --with jinja2==3.1.6 \
  python scripts/run_heldout.py plan
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from liquidbench.heldout import EXTENSION, EXTENSION_MANIFEST, verify_frozen
from liquidbench.heldout_study import (
    ARMS,
    build_plan,
    execute_phase,
    initial_counts,
    verify_counts,
)
from liquidbench.preflight import validate_report
from liquidbench.provider import ChatProvider
from liquidbench.runner import load_config
from liquidbench.task import discover_tasks, fingerprint

PLAN = Path("experiments/heldout-plan.json")
COUNTS = Path("docs/heldout/initial-counts.json")
REPETITIONS = 2


def suites():
    return {
        "original": verify_frozen(),
        "extension": verify_frozen(EXTENSION, EXTENSION_MANIFEST),
    }


def configs():
    return {arm: load_config(f"configs/heldout-{arm.replace('_', '-')}.json") for arm in ARMS}


def freeze_extension(_):
    if EXTENSION_MANIFEST.exists():
        raise SystemExit("Extension already frozen; a change needs a new versioned suite")
    tasks = discover_tasks(EXTENSION)
    entries = {
        t.manifest["id"]: {
            "family": t.manifest["family"],
            "category": t.manifest["category"],
            "difficulty": t.manifest["difficulty"],
            "digest": t.digest,
        }
        for t in tasks
    }
    if any(t.manifest["split"] != "heldout" for t in tasks):
        raise SystemExit("Every extension task must be split heldout")
    manifest = {
        "schema_version": 1,
        "split": "heldout",
        "suite": "extension",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Final-model evaluation only. Never shown to training-data generation, "
        "prompt development or model selection.",
        "categories": dict(Counter(e["category"] for e in entries.values())),
        "difficulties": dict(Counter(e["difficulty"] for e in entries.values())),
        "tasks": entries,
        "suite_digest": fingerprint(entries),
    }
    EXTENSION_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"tasks": len(entries), "suite_digest": manifest["suite_digest"]}))


def plan(_):
    from liquidbench.claude_provider import qwen_tokenizer

    tokenizer = qwen_tokenizer()

    def count(messages):
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return len(tokenizer.encode(text, add_special_tokens=False))

    loaded = suites()
    frozen = build_plan(configs(), loaded, REPETITIONS)
    tasks = [t for ts in loaded.values() for t in ts]
    PLAN.write_text(json.dumps(frozen, indent=2) + "\n")
    COUNTS.write_text(json.dumps(initial_counts(frozen, tasks, count), indent=2) + "\n")
    print(json.dumps({"attempts": len(frozen["order"]), "suites": frozen["suites"]}))


def execute(args):
    loaded = suites()
    rebuilt = build_plan(configs(), loaded, REPETITIONS)
    frozen = json.loads(PLAN.read_text())
    if rebuilt != frozen:
        raise SystemExit("Plan differs from the frozen plan; do not execute")
    phase_config = frozen["configs"][args.phase]
    validate_report(json.loads(args.preflight.read_text()), phase_config)
    tasks = [t for ts in loaded.values() for t in ts]
    verify_counts(
        frozen, tasks, json.loads(COUNTS.read_text()), args.phase, ChatProvider(phase_config)
    )
    return execute_phase(frozen, tasks, args.phase, args.output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze-extension")
    sub.add_parser("plan")
    e = sub.add_parser("execute")
    e.add_argument("--phase", choices=["base", "tuned"], required=True)
    e.add_argument("--preflight", type=Path, required=True)
    e.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return {"freeze-extension": freeze_extension, "plan": plan, "execute": execute}[args.command](
        args
    )


if __name__ == "__main__":
    raise SystemExit(main())
