"""Offline exact-token preparation; no model weights, endpoint calls or inference.

uv run --with transformers==5.19.0 --with tokenizers==0.23.3 --with jinja2==3.1.6 python scripts/prepare_loading_study.py
Use --freeze only during preparation, before any study inference. By default verify.
"""

import argparse
import importlib.metadata
import json
from pathlib import Path

from liquidbench.preflight import synthetic_document
from liquidbench.runner import load_config
from liquidbench.skills import SkillBundle, sha256
from liquidbench.study import CONDITIONS, build_plan, measure_plan
from liquidbench.task import discover_tasks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    from transformers import AutoTokenizer

    packages = {
        name: importlib.metadata.version(name) for name in ("transformers", "tokenizers", "jinja2")
    }
    if packages != {"transformers": "5.19.0", "tokenizers": "0.23.3", "jinja2": "3.1.6"}:
        raise ValueError("Use pinned tokenizer packages")
    observed = json.loads(Path("docs/calibration/qwen-7b-observed.json").read_text())
    root = Path(".cache/qwen-7b-tokenizer")
    hashes = {
        name: sha256((root / name).read_bytes())
        for name in ("tokenizer.json", "tokenizer_config.json", "config.json")
    }
    if any(digest != observed["model"]["files"][name]["sha256"] for name, digest in hashes.items()):
        raise ValueError("Tokenizer files do not match pinned checkpoint")
    tokenizer = AutoTokenizer.from_pretrained(root, local_files_only=True)

    def encode(text):
        return tokenizer.encode(text, add_special_tokens=False)

    def count(messages):
        return len(
            encode(
                tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            )
        )

    bundle = SkillBundle.load(load_config("configs/qwen-ab-skills.json")["skills"])
    target = len(encode(bundle.entry_message()))
    # One deterministic corpus, token-only prefix sizing; never inspect a completion.
    corpus = "Reference notes:\n" + synthetic_document()
    neutral = tokenizer.decode(encode(corpus)[:target], skip_special_tokens=False)
    if len(encode(neutral)) != target:
        raise ValueError(
            "Neutral token prefix does not round-trip exactly; do not tune with model output"
        )
    neutral_path = Path("controls/neutral-v1.txt")
    if args.freeze and not neutral_path.exists():
        neutral_path.parent.mkdir(exist_ok=True)
        neutral_path.write_text(neutral)
    if neutral_path.read_text() != neutral:
        raise ValueError("Neutral control changed from deterministic prefix")
    configs = {c: load_config(f"configs/m6-{c}.json") for c in CONDITIONS}
    if configs["neutral"]["neutral_context"]["sha256"] != sha256(neutral.encode()):
        raise ValueError("Neutral config hash does not match measured control")
    tasks = discover_tasks(Path("tasks/dev"))
    plan = build_plan(configs, tasks)
    report = measure_plan(plan, tasks, count)
    report.update(
        packages=packages,
        tokenizer_files_sha256=hashes,
        tokenizer_revision="c03e6d358207e414f1eca0bb1891e29f1db0e242",
        neutral_corpus_sha256=sha256(corpus.encode()),
        neutral_sha256=sha256(neutral.encode()),
        full_message_tokens=target,
        neutral_message_tokens=len(encode(neutral)),
        index_message_tokens=len(encode(bundle.index_message())),
    )
    for path, data in [
        (Path("experiments/m6-plan.json"), plan),
        (Path("docs/calibration/milestone-6-feasibility.json"), report),
    ]:
        if args.freeze:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n")
        elif json.loads(path.read_text()) != data:
            raise ValueError(f"Frozen preparation differs: {path}")
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("full_message_tokens", "neutral_message_tokens", "index_message_tokens")
            }
        )
    )


if __name__ == "__main__":
    main()
