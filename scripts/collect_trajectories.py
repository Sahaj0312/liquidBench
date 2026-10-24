"""Run a Claude teacher on training tasks in the unchanged Qwen harness; keep clean passes.

Kept examples are the exact student-format conversations (Qwen system prompt, task,
JSON actions, tool results) that passed the hidden grader, read the target before
the first write, had no protocol errors or truncated actions, and fit Qwen's 32K context. Spend is capped by the ledger.
uv run --with anthropic --with transformers==5.19.0 --with tokenizers==0.23.3 \
  --with jinja2==3.1.6 python scripts/collect_trajectories.py --model claude-sonnet-5-5 --cap 3
"""

import argparse
import json
from pathlib import Path

from liquidbench.claude_provider import ClaudeProvider, Ledger
from liquidbench.heldout import assert_not_heldout
from liquidbench.runner import load_config, run
from liquidbench.task import discover_tasks


def habits(transcript):
    actions = []
    for message in transcript:
        if message["role"] == "assistant":
            try:
                actions.append(json.loads(message["content"])["tool"])
            except (ValueError, KeyError, TypeError):
                actions.append("?")
    first_write = actions.index("write_file") if "write_file" in actions else len(actions)
    return {
        "actions": actions,
        "read_before_write": "read_file" in actions[:first_write],
        "validated": any(a in {"check", "render", "analyze"} for a in actions),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--cap", type=float, required=True, help="total USD cap for the ledger")
    parser.add_argument("--effort", default="low")
    parser.add_argument("--tasks", nargs="*", help="task ids (default: all tasks/train)")
    parser.add_argument("--ledger", default="runs/training/ledger.jsonl")
    parser.add_argument("--out", default="runs/training/trajectories")
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="skip tasks that already have a kept trajectory from any teacher",
    )
    args = parser.parse_args()
    ledger = Ledger(args.ledger, args.cap)
    config = load_config("configs/train-collect.json")
    provider = ClaudeProvider(args.model, ledger, effort=args.effort)
    tasks = discover_tasks(Path("tasks/train"))
    if args.tasks:
        tasks = [t for t in tasks if t.manifest["id"] in set(args.tasks)]
    if args.only_missing:
        done = {
            json.loads(line)["task"]
            for path in Path(args.out).glob("*/sft.jsonl")
            for line in path.read_text().splitlines()
        }
        tasks = [t for t in tasks if t.manifest["id"] not in done]
    out = Path(args.out) / args.model
    out.mkdir(parents=True, exist_ok=True)
    kept_path = out / "sft.jsonl"
    summary = []
    for task in tasks:
        before = ledger.spent()
        provider.transcript = None
        destination, result = run(task, config, out / task.manifest["id"], provider=provider)
        transcript = provider.transcript or []
        info = {
            "task": task.manifest["id"],
            "category": task.manifest["category"],
            "difficulty": task.manifest["difficulty"],
            "status": result["status"],
            "termination": result["termination"],
            "model_calls": result["model_calls"],
            "protocol_errors": result["protocol_errors"],
            "tool_errors": result["tool_errors"],
            "truncations": result.get("output_truncations", 0),
            "usd": round(ledger.spent() - before, 5),
            **habits(transcript),
        }
        prompt_tokens = provider.qwen_prompt_tokens(transcript[:-1]) if transcript else 0
        info["qwen_context_tokens"] = prompt_tokens
        # The habit Milestone 6 and the diagnostic showed missing: read before editing.
        keep = (
            result["status"] == "passed"
            and info["protocol_errors"] == 0
            and info["truncations"] == 0
            and info["read_before_write"]
            and prompt_tokens + config["max_output_tokens"] <= config["max_context_tokens"]
        )
        if keep:
            assert_not_heldout(json.dumps(transcript))
            with kept_path.open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "task": task.manifest["id"],
                            "teacher": args.model,
                            "messages": transcript,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        info["kept"] = keep
        summary.append(info)
        print(json.dumps(info), flush=True)
    kept = [s for s in summary if s["kept"]]
    print(
        json.dumps(
            {
                "model": args.model,
                "attempts": len(summary),
                "kept": len(kept),
                "usd": round(sum(s["usd"] for s in summary), 4),
                "usd_per_kept": round(sum(s["usd"] for s in summary) / max(1, len(kept)), 4),
                "ledger_total": round(ledger.spent(), 4),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
