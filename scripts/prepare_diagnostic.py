"""Offline tokenizer-only preparation; --freeze creates a NEW diagnostic plan.

uv run --with transformers==5.19.0 --with tokenizers==0.23.3 --with jinja2==3.1.6 python scripts/prepare_diagnostic.py --freeze
Never overwrite existing frozen files: use default verification after freezing.
"""

import argparse
import importlib.metadata
import json
from pathlib import Path

from liquidbench.diagnostic import (
    CONDITIONS,
    build_plan,
    context_message,
    messages,
    reference_index,
    select_reference,
    select_tasks,
)
from liquidbench.preflight import synthetic_document
from liquidbench.runner import load_config
from liquidbench.skills import SkillBundle, sha256
from liquidbench.task import discover_tasks, fingerprint


def tokenizer_tools():
    from transformers import AutoTokenizer

    packages = {k: importlib.metadata.version(k) for k in ("transformers", "tokenizers", "jinja2")}
    if packages != {"transformers": "5.19.0", "tokenizers": "0.23.3", "jinja2": "3.1.6"}:
        raise ValueError("Use pinned tokenizer package versions")
    observed = json.loads(Path("docs/calibration/qwen-7b-observed.json").read_text())
    root = Path(".cache/qwen-7b-tokenizer")
    hashes = {
        name: sha256((root / name).read_bytes())
        for name in ("tokenizer.json", "tokenizer_config.json", "config.json")
    }
    if any(value != observed["model"]["files"][name]["sha256"] for name, value in hashes.items()):
        raise ValueError("Tokenizer checkpoint mismatch")
    tokenizer = AutoTokenizer.from_pretrained(root, local_files_only=True)

    def count(history):
        # Same text-render-then-encode method as the Milestone 6 preparation.
        rendered = tokenizer.apply_chat_template(
            history, tokenize=False, add_generation_prompt=True
        )
        return len(tokenizer.encode(rendered, add_special_tokens=False))

    return tokenizer, count, {"packages": packages, "files_sha256": hashes}


def prepare(tokenizer, count, *, freeze=False):
    tasks = discover_tasks(Path("tasks/dev"))
    config = load_config("configs/diagnostic-v1.json")
    bundle = SkillBundle.load(load_config("configs/m6-full.json")["skills"])
    index = reference_index(bundle)
    selected = select_tasks([t.manifest for t in tasks])
    selections, measures, controls = {}, {}, {}
    corpus = synthetic_document()
    tokens = tokenizer.encode(corpus, add_special_tokens=False)
    for task in tasks:
        task_id, prompt = task.manifest["id"], task.manifest["prompt"]
        if task_id not in selected:
            continue
        selection = select_reference(prompt, index)
        body = bundle.documents[selection["path"]]
        reference = context_message(body)
        raw = len(tokenizer.encode(reference, add_special_tokens=False))
        initial = count(messages(prompt, "reference", reference))
        # Tokenizer-only sizing, fixed bounded search, no generation or outcome input.
        guess = len(tokenizer.encode(body, add_special_tokens=False))
        neutral = None
        for length in range(max(1, guess - 32), guess + 33):
            candidate = context_message(
                tokenizer.decode(tokens[:length], skip_special_tokens=False)
            )
            if (
                len(tokenizer.encode(candidate, add_special_tokens=False)) == raw
                and count(messages(prompt, "neutral", candidate)) == initial
            ):
                neutral = candidate
                break
        if neutral is None:
            raise ValueError("No exact neutral match in frozen sizing policy")
        path = Path(f"controls/diagnostic-v1/{task_id}.txt")
        if freeze and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(neutral)
        if path.read_text() != neutral:
            raise ValueError("Neutral context differs from deterministic prefix")
        controls[task_id] = {
            "path": str(path),
            "sha256": sha256(neutral.encode()),
            "message_tokens": raw,
        }
        selections[task_id] = {
            **selection,
            **bundle.manifest["files"][selection["path"]],
            "body_tokens": len(tokenizer.encode(body, add_special_tokens=False)),
            "message_tokens": raw,
        }
        measures[task_id] = {}
        for condition in CONDITIONS:
            content = (
                reference
                if condition == "reference"
                else neutral
                if condition == "neutral"
                else None
            )
            history = messages(prompt, condition, content)
            n = count(history)
            if n <= len(tokenizer.encode(prompt, add_special_tokens=False)):
                raise ValueError("Prompt count below task text; tokenizer output misread")
            if n + config["max_output_tokens"] + 32 > config["max_context_tokens"]:
                raise ValueError("Diagnostic context does not fit; no truncation")
            measures[task_id][condition] = {
                "initial_tokens": n,
                "messages_sha256": fingerprint(history),
            }
        if (
            measures[task_id]["reference"]["initial_tokens"]
            != measures[task_id]["neutral"]["initial_tokens"]
        ):
            raise ValueError("Unmatched reference/neutral prompts")
    plan = build_plan(tasks, config, bundle, selections, measures, controls)
    plan["neutral_corpus_sha256"] = sha256(corpus.encode())
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    path = Path("experiments/diagnostic-v1-plan.json")
    if args.freeze and path.exists():
        raise ValueError("Frozen plan already exists; do not overwrite")
    tokenizer, count, metadata = tokenizer_tools()
    plan = prepare(tokenizer, count, freeze=args.freeze)
    plan["tokenizer"] = metadata
    if args.freeze:
        path.write_text(json.dumps(plan, indent=2) + "\n")
    elif json.loads(path.read_text()) != plan:
        raise ValueError("Frozen plan mismatch")
    print(
        json.dumps(
            {
                "attempts": len(plan["order"]),
                "tasks": plan["selected_tasks"],
                "references": plan["references"],
                "measurements": plan["measurements"],
                "inference_performed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
