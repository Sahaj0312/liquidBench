"""Batch-API task authoring (50% price): submit, then collect and verify.

Worst-case cost of every submitted request is reserved against the ledger before
submission, so the cap holds even if each response uses its full max_tokens.
uv run python scripts/batch_training_tasks.py submit --requests 60 --cap 50
uv run python scripts/batch_training_tasks.py collect --batch-id msgbatch_...
"""

import argparse
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import random
import time

from generate_training_tasks import BATCHES, INSTRUCTIONS, THEMES, pending_reservations
from heldout_themes import HELDOUT_THEMES
from liquidbench.claude_provider import PRICES, Ledger
from liquidbench.heldout import verify_frozen
from liquidbench.sandbox import Sandbox, image_id
from liquidbench.sft import family_root
from liquidbench.task import discover_tasks
from liquidbench.training_tasks import SPEC_SCHEMA, Rejected, build, known_families, unique_family

ANGLES = [
    "null and empty-string inputs",
    "loops with limits or skipped items",
    "integer arithmetic and rounding",
    "escaping text and attributes",
    "priority between overlapping rules",
    "exact case-sensitive matching",
    "pluralization and counts",
    "joining lists with separators",
    "boundary values",
    "first/last item handling",
    "default values",
    "trimming whitespace",
    "state carried across loop iterations",
    "optional wrapper elements",
]
MAX_TOKENS = 48000
# Training tasks may be renamed on a family clash; held-out extension tasks are rejected
# instead, and must also be dissimilar to every training and development prompt.
SUITES = {
    "train": {"themes": THEMES, "out": Path("tasks/train"), "split": "train"},
    "heldout-ext": {"themes": HELDOUT_THEMES, "out": Path("tasks/heldout-ext"), "split": "heldout"},
}


def worst_case_usd(model, requests):
    price = PRICES[model]
    per = (4000 * price["input"] + MAX_TOKENS * price["output"]) / 1_000_000 / 2
    return per * requests


def submit(args):
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    ledger = Ledger(args.ledger, args.cap)
    reserve = worst_case_usd(args.model, args.requests)
    ledger.require(reserve + sum(pending_reservations()))
    rng = random.Random(args.seed)
    themes_by_category = SUITES[args.suite]["themes"]
    cells = list(itertools.product(sorted(themes_by_category), ["easy", "medium", "hard"]))
    rng.shuffle(cells)
    plan = []
    for i, (category, difficulty) in enumerate(
        itertools.islice(itertools.cycle(cells), args.requests)
    ):
        themes = [
            f"{t} (angle: {rng.choice(ANGLES)})"
            for t in rng.sample(themes_by_category[category], args.per_call)
        ]
        plan.append(
            {
                "custom_id": f"req-{args.seed:03d}-{i:04d}",
                "category": category,
                "difficulty": difficulty,
                "themes": themes,
            }
        )
    requests = [
        Request(
            custom_id=p["custom_id"],
            params=MessageCreateParamsNonStreaming(
                model=args.model,
                max_tokens=MAX_TOKENS,
                output_config={
                    "effort": args.effort,
                    "format": {"type": "json_schema", "schema": SPEC_SCHEMA},
                },
                messages=[
                    {
                        "role": "user",
                        "content": INSTRUCTIONS.format(
                            count=args.per_call,
                            category=p["category"],
                            difficulty=p["difficulty"],
                            themes="; ".join(p["themes"]),
                        ),
                    }
                ],
            ),
        )
        for p in plan
    ]
    batch = anthropic.Anthropic().messages.batches.create(requests=requests)
    BATCHES.mkdir(parents=True, exist_ok=True)
    (BATCHES / f"{batch.id}.json").write_text(
        json.dumps(
            {
                "batch_id": batch.id,
                "model": args.model,
                "effort": args.effort,
                "suite": args.suite,
                "submitted_utc": datetime.now(timezone.utc).isoformat(),
                "requests": plan,
                "worst_case_usd": reserve,
                "collected": False,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {"batch_id": batch.id, "requests": len(plan), "worst_case_usd": round(reserve, 2)}
        )
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
    plan = {p["custom_id"]: p for p in record["requests"]}
    image = image_id("liquidbench-runtime:0.1")
    suite = SUITES[record.get("suite", "train")]
    heldout = verify_frozen()
    if suite["split"] == "heldout":
        # Extension tasks must not resemble anything a model was trained or tuned on.
        compare = [
            *heldout,
            *(t for d in ("tasks/train", "tasks/dev") for t in discover_tasks(Path(d))),
        ]
    else:
        compare = heldout
    log = Path("runs/training/authoring.jsonl")
    stamp = datetime.now(timezone.utc).date().isoformat()
    provenance = (
        f"Claude-authored training task ({record['model']}, batch {args.batch_id}, "
        f"{stamp}); kept only after container verification. Not development or "
        "held-out data."
        if suite["split"] == "train"
        else f"Claude-authored held-out extension task ({record['model']}, batch "
        f"{args.batch_id}, {stamp}); kept only after container verification. Themes "
        "disjoint from training; never shown to training-data generation."
    )
    counts = {"kept": 0, "rejected": 0, "unusable": 0}
    for result in client.messages.batches.results(args.batch_id):
        meta = plan[result.custom_id]
        if result.result.type != "succeeded":
            counts["unusable"] += 1
            print(f"{result.custom_id}: {result.result.type}", flush=True)
            continue
        message = result.result.message
        ledger.record(
            "task-authoring-batch",
            record["model"],
            message.usage.model_dump(exclude_none=True),
            batch=True,
        )
        text = "".join(b.text for b in message.content if b.type == "text")
        try:
            if message.stop_reason != "end_turn":
                raise ValueError(message.stop_reason)
            specs = json.loads(text)["tasks"]
        except (ValueError, KeyError, TypeError) as exc:
            counts["unusable"] += 1
            print(f"{result.custom_id}: unusable ({exc})", flush=True)
            continue
        for spec in specs:
            known = known_families()
            if suite["split"] == "train":
                spec = unique_family(spec, known)
            try:
                if suite["split"] == "heldout" and family_root(spec.get("family", "")) in {
                    family_root(f) for f in known
                }:
                    raise Rejected("family root matches an existing task")
                root = build(
                    spec,
                    suite["out"],
                    sandbox_factory=Sandbox,
                    image=image,
                    heldout_tasks=compare,
                    known_families=known,
                    provenance=provenance,
                    split=suite["split"],
                )
                verdict, reason = "kept", str(root)
            except Rejected as exc:
                verdict, reason = "rejected", str(exc)
            except Exception as exc:  # A malformed spec must not stop verification of the rest.
                verdict, reason = "rejected", f"builder error: {type(exc).__name__}: {exc}"
            counts[verdict] += 1
            with log.open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "batch_id": args.batch_id,
                            "custom_id": result.custom_id,
                            **meta,
                            "family": spec.get("family"),
                            "verdict": verdict,
                            "reason": reason,
                            "model": record["model"],
                            "spec": spec,
                        }
                    )
                    + "\n"
                )
            print(f"{verdict:8} {spec.get('family')}: {reason}", flush=True)
    record["collected"] = True
    record["counts"] = counts
    path.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({**counts, "ledger_total": round(ledger.spent(), 4)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--requests", type=int, required=True)
    s.add_argument("--per-call", type=int, default=2)
    s.add_argument("--model", default="claude-opus-5-5")
    s.add_argument("--effort", default="medium")
    s.add_argument("--seed", type=int, default=100)
    s.add_argument("--suite", choices=sorted(SUITES), default="train")
    c = sub.add_parser("collect")
    c.add_argument("--batch-id", required=True)
    for p in (s, c):
        p.add_argument("--cap", type=float, required=True)
        p.add_argument("--ledger", default="runs/training/ledger-full.jsonl")
    args = parser.parse_args()
    submit(args) if args.command == "submit" else collect(args)


if __name__ == "__main__":
    main()
