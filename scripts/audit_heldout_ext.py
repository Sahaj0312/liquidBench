"""Independent ambiguity audit of held-out extension tasks before they are frozen.

Container verification shows a task is self-consistent (the reference passes, wrong
solutions fail). It does not show the prompt determines the graded result. Each
task goes to Claude with exactly what the agent sees, plus the reference and the
expected results, and Claude judges whether the result follows uniquely from the
prompt. Tasks judged ambiguous, or whose audit did not complete, are moved out of
tasks/heldout-ext before freezing. Tasks are never edited. The first pass ran
without extended thinking; the second pass uses adaptive thinking, and a task stays
only if every pass judged it clear.
uv run python scripts/audit_heldout_ext.py submit --cap 50
uv run python scripts/audit_heldout_ext.py collect --batch-id msgbatch_... --cap 50
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time

from generate_training_tasks import BATCHES, pending_reservations
from liquidbench.claude_provider import PRICES, Ledger
from liquidbench.heldout import EXTENSION
from liquidbench.task import discover_tasks

MODEL = "claude-opus-5-5"
MAX_TOKENS = 32000
OUT = Path("runs/heldout-ext-audit")
REJECTED = Path("runs/heldout-ext-rejected")

GRADING = {
    "render-contract-v1": (
        "The grader renders the agent's file with each case's variables (strict core Liquid) "
        "and compares the HTML DOM with the expected HTML: element names, attributes and "
        "leaf text must match exactly; whitespace between elements, comments and attribute "
        "quote style are ignored."
    ),
    "schema-contract-v1": (
        "The grader parses the single top-level {% schema %} JSON and requires it to equal "
        "the expected schema exactly (same keys and values; key order ignored); markup "
        "outside the schema must be unchanged."
    ),
    "reference-contract-v1": (
        "The grader parses the agent's file and requires its Liquid syntax tree to equal the "
        "reference's, ignoring only whitespace and quote style; every literal (asset names, "
        "translation keys, snippet names) must match."
    ),
}

AUDIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "issues"],
    "properties": {
        "verdict": {"type": "string", "enum": ["clear", "ambiguous"]},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["where", "problem"],
                "properties": {"where": {"type": "string"}, "problem": {"type": "string"}},
            },
        },
    },
}

INSTRUCTIONS = """You are auditing one task in a benchmark for coding agents that edit Shopify
Liquid theme files. Do not solve the task. Decide whether a careful, competent developer who
reads ONLY the task prompt and the starting files would be forced to produce a file that
passes the grader, or whether the prompt leaves room for a reasonable reading that fails.

Mark "ambiguous" if any of these hold:
- a graded behavior (output text, element, attribute, ordering, case handling, null/empty
  handling, escaping, rounding, separators, schema field or value, literal name) is not stated
  or inferable with certainty from the prompt and files;
- the prompt contradicts itself, the files or an expected result;
- an expected result disagrees with what the prompt specifies;
- the grader demands something stricter than the prompt states.
Otherwise mark "clear". Do not flag issues the grader ignores, stylistic preferences, or
things that are standard Liquid semantics. List every concrete issue with where it occurs.

Grading: {grading}

--- TASK PROMPT (shown to the agent) ---
{prompt}

--- STARTING FILES (shown to the agent) ---
{files}

--- REFERENCE SOLUTION (hidden from the agent) ---
{reference}

--- EXPECTED RESULTS (hidden from the agent) ---
{expected}"""


def specs_by_family():
    specs = {}
    log = Path("runs/training/authoring.jsonl")
    for line in log.read_text().splitlines():
        row = json.loads(line)
        if row["verdict"] == "kept" and row["reason"].startswith("tasks/heldout-ext/"):
            specs[row["family"]] = row["spec"]
    return specs


def audit_prompt(task, spec):
    root = task.root
    editable = task.manifest["editable_files"][0]
    files = "\n\n".join(
        f"== {p.relative_to(root / 'initial')} ==\n{p.read_text()}"
        for p in sorted((root / "initial").rglob("*"))
        if p.is_file()
    )
    evaluator = task.manifest["evaluator"]
    if evaluator == "render-contract-v1":
        expected = "\n".join(
            f"case {i}: variables={c['variables_json']}\n  expected_html={c['expected_html']!r}"
            for i, c in enumerate(spec["cases"])
        )
    elif evaluator == "schema-contract-v1":
        expected = spec["expected_schema_json"]
    else:
        expected = "The fixed file must have the reference's syntax tree (see reference)."
    return INSTRUCTIONS.format(
        grading=GRADING[evaluator],
        prompt=task.manifest["prompt"],
        files=files,
        reference=(root / "evaluator/reference" / editable).read_text(),
        expected=expected,
    )


def worst_case_usd(requests):
    price = PRICES[MODEL]
    return (12000 * price["input"] + MAX_TOKENS * price["output"]) / 1_000_000 / 2 * requests


def submit(args):
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    tasks = discover_tasks(EXTENSION)
    specs = specs_by_family()
    ledger = Ledger(args.ledger, args.cap)
    reserve = worst_case_usd(len(tasks))
    ledger.require(reserve + sum(pending_reservations()))
    requests = [
        Request(
            custom_id=t.manifest["id"],
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "high",
                    "format": {"type": "json_schema", "schema": AUDIT_SCHEMA},
                },
                messages=[{"role": "user", "content": audit_prompt(t, specs[t.manifest["id"]])}],
            ),
        )
        for t in tasks
    ]
    batch = anthropic.Anthropic().messages.batches.create(requests=requests)
    (BATCHES / f"{batch.id}.json").write_text(
        json.dumps(
            {
                "batch_id": batch.id,
                "purpose": "heldout-ext-audit",
                "model": MODEL,
                "thinking": "adaptive",
                "max_tokens": MAX_TOKENS,
                "submitted_utc": datetime.now(timezone.utc).isoformat(),
                "requests": [{"custom_id": t.manifest["id"]} for t in tasks],
                "worst_case_usd": reserve,
                "collected": False,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps({"batch_id": batch.id, "tasks": len(tasks), "worst_case_usd": round(reserve, 2)})
    )


def collect(args):
    import anthropic

    client = anthropic.Anthropic()
    path = BATCHES / f"{args.batch_id}.json"
    record = json.loads(path.read_text())
    if record["collected"]:
        raise SystemExit("Batch already collected")
    while (batch := client.messages.batches.retrieve(args.batch_id)).processing_status != "ended":
        print(f"{batch.processing_status}: {batch.request_counts}", flush=True)
        time.sleep(60)
    ledger = Ledger(args.ledger, args.cap)
    OUT.mkdir(parents=True, exist_ok=True)
    verdicts = {}
    with (OUT / f"{args.batch_id}.jsonl").open("w") as handle:
        for result in client.messages.batches.results(args.batch_id):
            row = {"task": result.custom_id, "verdict": "incomplete", "issues": []}
            if result.result.type == "succeeded":
                message = result.result.message
                ledger.record(
                    "heldout-ext-audit",
                    MODEL,
                    message.usage.model_dump(exclude_none=True),
                    batch=True,
                )
                if message.stop_reason == "end_turn":
                    text = "".join(b.text for b in message.content if b.type == "text")
                    row.update(json.loads(text))
            verdicts[row["task"]] = row["verdict"]
            handle.write(json.dumps(row) + "\n")
            print(f"{row['verdict']:10} {row['task']}", flush=True)
    REJECTED.mkdir(parents=True, exist_ok=True)
    for task, verdict in verdicts.items():
        if verdict != "clear":
            shutil.move(str(EXTENSION / task), str(REJECTED / task))
    record["collected"] = True
    record["verdicts"] = verdicts
    path.write_text(json.dumps(record, indent=2) + "\n")
    counts = {v: list(verdicts.values()).count(v) for v in set(verdicts.values())}
    print(json.dumps({**counts, "ledger_total": round(ledger.spent(), 4)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("submit")
    c = sub.add_parser("collect")
    c.add_argument("--batch-id", required=True)
    for p in sub.choices.values():
        p.add_argument("--cap", type=float, required=True)
        p.add_argument("--ledger", default="runs/training/ledger-full.jsonl")
    args = parser.parse_args()
    submit(args) if args.command == "submit" else collect(args)


if __name__ == "__main__":
    main()
