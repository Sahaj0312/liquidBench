"""Exploratory frontier reference on the held-out suite (analysis-plan.md, Addition 4).

Runs claude-sonnet-5-5 with and without on-demand skills in the frozen base-phase order
(base -> claude, base_skills -> claude_skills). The frozen plan is re-derived and must
match first, so tasks, order and harness source are the scored study's. Spend goes to
its own capped ledger.
uv run --with anthropic --with transformers==5.19.0 --with tokenizers==0.23.3 \
  --with jinja2==3.1.6 python scripts/run_heldout_claude.py --output runs/heldout/claude
"""

import argparse
import json
from pathlib import Path

from run_heldout import PLAN, REPETITIONS, configs, suites

from liquidbench.claude_provider import ClaudeProvider, Ledger
from liquidbench.heldout_study import build_plan, execute_phase
from liquidbench.runner import load_config, run

ARMS = {"base": "claude", "base_skills": "claude_skills"}
MODEL = "claude-sonnet-5-5"


class ReferenceLedger(Ledger):
    def record(self, purpose, model, usage, *, batch=False):
        return super().record("heldout-claude-reference", model, usage, batch=batch)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cap", type=float, default=30.0)
    parser.add_argument("--ledger", default="runs/heldout-claude/ledger.jsonl")
    args = parser.parse_args()
    loaded = suites()
    frozen = json.loads(PLAN.read_text())
    if build_plan(configs(), loaded, REPETITIONS) != frozen:
        raise SystemExit("Plan differs from the frozen plan; do not execute")
    reference = {
        arm: load_config(f"configs/heldout-{arm.replace('_', '-')}.json") for arm in ARMS.values()
    }
    if any(c["model"] != MODEL for c in reference.values()):
        raise SystemExit(f"Reference arms must use {MODEL}")
    if reference["claude_skills"]["skills"] != frozen["configs"]["base_skills"]["skills"]:
        raise SystemExit("Skills must match the frozen skill arms")
    plan = {
        **frozen,
        "reference": "analysis-plan.md Addition 4",
        "configs": {**frozen["configs"], **reference},
        "order": [
            {**item, "phase": "claude", "arm": ARMS[item["arm"]]}
            for item in frozen["order"]
            if item["phase"] == "base"
        ],
    }
    provider = ClaudeProvider(MODEL, ReferenceLedger(args.ledger, args.cap), effort="low")
    tasks = [t for ts in loaded.values() for t in ts]
    return execute_phase(
        plan,
        tasks,
        "claude",
        args.output,
        runner=lambda task, config, out: run(task, config, out, provider=provider),
    )


if __name__ == "__main__":
    raise SystemExit(main())
