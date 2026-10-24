"""Freeze the SFT dataset: one kept trajectory per train task, family-grouped validation split.

Writes runs/training/sft/{train,val}.jsonl and a manifest (counts, Qwen token
statistics, file digests) that is also copied to docs/training/sft-manifest.json.
uv run --with transformers==5.19.0 --with tokenizers==0.23.3 --with jinja2==3.1.6 \
  python scripts/prepare_sft.py
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from liquidbench.claude_provider import qwen_tokenizer
from liquidbench.sft import IGNORE, family_root, final_render, load_examples, split, tokenize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trajectories",
        nargs="+",
        default=["runs/training/trajectories"],
        help="trajectory directories in priority order",
    )
    parser.add_argument(
        "--require-final-render",
        action="store_true",
        help="drop rendered-task trajectories that do not render after their last write",
    )
    parser.add_argument("--val-from", type=Path, help="manifest whose validation tasks to reuse")
    parser.add_argument("--manifest-copy", default="docs/training/sft-manifest.json")
    parser.add_argument("--out", default="runs/training/sft")
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    tasks = {}
    for path in Path("tasks/train").glob("*/task.json"):
        manifest = json.loads(path.read_text())
        tasks[manifest["id"]] = manifest

    def keep(example):
        rendered = tasks[example["task"]]["evaluator"] == "render-contract-v1"
        return not (args.require_final_render and rendered) or final_render(example["messages"])

    examples = load_examples(args.trajectories, set(tasks), keep)
    val_tasks = (
        json.loads(args.val_from.read_text())["splits"]["val"]["tasks"] if args.val_from else None
    )
    train, val = split(examples, args.val_fraction, args.seed, val_tasks)
    assert not {family_root(e["task"]) for e in train} & {family_root(e["task"]) for e in val}
    tokenizer = qwen_tokenizer()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "seed": args.seed,
        "val_fraction": args.val_fraction,
        "trajectories": args.trajectories,
        "require_final_render": args.require_final_render,
        "val_from": str(args.val_from) if args.val_from else None,
        "splits": {},
    }
    for name, rows in (("train", train), ("val", val)):
        lengths, trained = [], 0
        for row in rows:
            ids, labels = tokenize(row["messages"], tokenizer)
            lengths.append(len(ids))
            trained += sum(label != IGNORE for label in labels)
        path = out / f"{name}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
        manifest["splits"][name] = {
            "examples": len(rows),
            "tasks": [row["task"] for row in rows],
            "teachers": dict(Counter(row["teacher"] for row in rows)),
            "categories": dict(Counter(tasks[row["task"]]["category"] for row in rows)),
            "difficulties": dict(Counter(tasks[row["task"]]["difficulty"] for row in rows)),
            "tokens": sum(lengths),
            "assistant_tokens": trained,
            "max_tokens": max(lengths),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    manifest["without_trajectory"] = sorted(set(tasks) - {e["task"] for e in examples})
    text = json.dumps(manifest, indent=2) + "\n"
    (out / "manifest.json").write_text(text)
    Path(args.manifest_copy).write_text(text)
    for name, info in manifest["splits"].items():
        print(name, {k: v for k, v in info.items() if k != "tasks"})


if __name__ == "__main__":
    main()
