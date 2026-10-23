"""Exact local Qwen tokenization; no model weights, inference or evaluator data.

uv run --with transformers==5.19.0 --with tokenizers==0.23.3 --with jinja2==3.1.6 python scripts/measure_skills.py

Downloads only three hash-verified tokenizer/config files when absent. Uses the
same tokenizer packages as the GPU pilot. The future endpoint must independently
agree with these chat counts before paired inference is authorized to proceed.
"""

import argparse
import importlib.metadata
import json
from pathlib import Path

import httpx

from liquidbench.runner import SYSTEM, load_config
from liquidbench.skills import SkillBundle, initial_messages, sha256


REVISION = "c03e6d358207e414f1eca0bb1891e29f1db0e242"


def measure(tokenizer, bundle, prompts, base, treatment):
    def count(messages):
        rendered = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return len(tokenizer.encode(rendered, add_special_tokens=False))

    raw_counts = {
        name: len(tokenizer.encode(content, add_special_tokens=False))
        for name, content in bundle.documents.items()
    }
    tasks = {}
    for name, prompt in sorted(prompts.items()):
        plain = initial_messages(SYSTEM, prompt)
        loaded = initial_messages(SYSTEM, prompt, bundle)
        references = {}
        for path in bundle.documents.keys() - set(bundle.manifest["entries"]):
            action = {"tool": "read_file", "args": {"path": path}}
            response = {"ok": True, "tool": "read_file", "result": bundle.read(path)}
            history = loaded + [
                {"role": "assistant", "content": json.dumps(action)},
                {
                    "role": "user",
                    "content": "Tool result: " + json.dumps(response, ensure_ascii=False),
                },
            ]
            references[path] = count(history)
        tasks[name] = {
            "baseline_initial_prompt_tokens": count(plain),
            "skills_initial_prompt_tokens": count(loaded),
            "skills_initial_fits_8192": count(loaded) + 32 + base["max_output_tokens"] <= 8192,
            "skills_initial_fits_proposed_context": (
                count(loaded) + 32 + treatment["max_output_tokens"]
                <= treatment["max_context_tokens"]
            ),
            "prompt_after_each_single_reference": dict(sorted(references.items())),
            "optimistic_calls_under_24000": 24000 // count(loaded),
        }
    return {
        "kind": "local_exact_tokenizer_feasibility",
        "research_result": False,
        "inference_performed": False,
        "endpoint_agreement_verified": False,
        "skill_revision": bundle.manifest["revision"],
        "skill_manifest_sha256": bundle.manifest_sha256,
        "system_sha256": sha256(SYSTEM.encode()),
        "raw_document_tokens": raw_counts,
        "entry_tokens_sum": sum(raw_counts[name] for name in bundle.manifest["entries"]),
        "entry_message_tokens": len(
            tokenizer.encode(bundle.entry_message(), add_special_tokens=False)
        ),
        "tasks": tasks,
        "proposed_budgets": {
            key: treatment[key]
            for key in (
                "max_context_tokens",
                "max_total_tokens",
                "max_output_tokens",
                "max_turns",
                "max_seconds",
            )
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-dir", type=Path, default=Path(".cache/qwen-7b-tokenizer"))
    parser.add_argument(
        "--output", type=Path, default=Path("docs/calibration/skills-feasibility.json")
    )
    args = parser.parse_args()
    from transformers import AutoTokenizer

    versions = {
        name: importlib.metadata.version(name) for name in ("transformers", "tokenizers", "jinja2")
    }
    if versions != {"transformers": "5.19.0", "tokenizers": "0.23.3", "jinja2": "3.1.6"}:
        raise ValueError("Use the pinned tokenizer packages shown in this script's usage")
    observed = json.loads(Path("docs/calibration/qwen-7b-observed.json").read_text())
    hashes = {}
    args.tokenizer_dir.mkdir(parents=True, exist_ok=True)
    for name in ("tokenizer.json", "tokenizer_config.json", "config.json"):
        path = args.tokenizer_dir / name
        if not path.exists():
            url = f"https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct/resolve/{REVISION}/{name}"
            data = httpx.get(url, follow_redirects=True, timeout=60).raise_for_status().content
            if sha256(data) != observed["model"]["files"][name]["sha256"]:
                raise ValueError("Downloaded tokenizer hash mismatch")
            path.write_bytes(data)
        hashes[name] = sha256(path.read_bytes())
        if hashes[name] != observed["model"]["files"][name]["sha256"]:
            raise ValueError("Cached tokenizer hash mismatch")
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_dir, local_files_only=True)
    treatment = load_config("configs/qwen-ab-skills.json")
    bundle = SkillBundle.load(treatment["skills"])
    # Only public task manifests; never load evaluator/reference files.
    prompts = {
        p.parent.name: json.loads(p.read_text())["prompt"]
        for p in Path("tasks/dev").glob("*/task.json")
    }
    report = measure(
        tokenizer, bundle, prompts, load_config("configs/qwen-ab-base.json"), treatment
    )
    report.update(tokenizer_revision=REVISION, tokenizer_files_sha256=hashes, packages=versions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"entry_tokens_sum": report["entry_tokens_sum"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
