"""Supervised fine-tuning data: one kept teacher trajectory per task, family-grouped split.

Examples are the exact student conversations (Qwen system prompt, task, JSON actions,
tool results). Loss is on assistant actions only: each action's tokens plus the
<|im_end|> that ends it, so the student learns when an action stops.
"""

import json
import random
import re
from pathlib import Path

from .heldout import assert_not_heldout

TEACHER_ORDER = ("claude-sonnet-5-5", "claude-opus-5-5")
IGNORE = -100


def family_root(task_id):
    """Renamed duplicates (`age-gate-2`) share a root and must land in the same split."""
    return re.sub(r"-\d+$", "", task_id)


def load_examples(trajectories, train_tasks):
    """One trajectory per training task, preferring teachers in TEACHER_ORDER."""
    chosen = {}
    for teacher in TEACHER_ORDER:
        path = Path(trajectories) / teacher / "sft.jsonl"
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            example = json.loads(line)
            if example["task"] in train_tasks and example["task"] not in chosen:
                assert_not_heldout(json.dumps(example["messages"]))
                chosen[example["task"]] = example
    return [chosen[t] for t in sorted(chosen)]


def split(examples, val_fraction=0.1, seed=42):
    roots = sorted({family_root(e["task"]) for e in examples})
    random.Random(seed).shuffle(roots)
    target = max(1, round(len(examples) * val_fraction))
    val_roots = set()
    count = 0
    for root in roots:
        if count >= target:
            break
        val_roots.add(root)
        count += sum(family_root(e["task"]) == root for e in examples)
    train = [e for e in examples if family_root(e["task"]) not in val_roots]
    val = [e for e in examples if family_root(e["task"]) in val_roots]
    return train, val


def tokenize(messages, tokenizer):
    """Token ids and labels with every non-assistant token masked to IGNORE."""

    def encode(msgs, generation_prompt=False):
        text = tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=generation_prompt
        )
        return tokenizer.encode(text, add_special_tokens=False)

    ids = encode(messages)
    labels = [IGNORE] * len(ids)
    newline = tokenizer.encode("\n", add_special_tokens=False)
    for i, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        start = len(encode(messages[:i], generation_prompt=True))
        through = encode(messages[: i + 1])
        if ids[: len(through)] != through or len(through) <= start:
            raise ValueError("chat template is not prefix-stable; masking would be wrong")
        end = len(through)
        # The template follows <|im_end|> with a newline the student never generates.
        if through[end - len(newline) : end] == newline:
            end -= len(newline)
        labels[start:end] = ids[start:end]
    return ids, labels
