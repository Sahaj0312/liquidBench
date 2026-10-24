import json
from pathlib import Path

import pytest

from liquidbench.sft import IGNORE, family_root, load_examples, split, tokenize

ROOT = Path(__file__).resolve().parents[1]


def example(task, teacher="claude-sonnet-5-5"):
    return {
        "task": task,
        "teacher": teacher,
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": f"fix {task}"},
            {"role": "assistant", "content": '{"tool": "finish", "args": {}}'},
        ],
    }


def test_renamed_duplicates_share_a_family_root():
    assert family_root("age-gate-2") == family_root("age-gate") == "age-gate"
    assert family_root("icon-sprite-kit") == "icon-sprite-kit"


def test_split_never_puts_one_family_on_both_sides():
    tasks = [f"family{i}" for i in range(20)] + [f"family{i}-2" for i in range(20)]
    train, val = split([example(t) for t in tasks], 0.1, seed=0)
    assert val and len(train) + len(val) == 40
    assert not {family_root(e["task"]) for e in train} & {family_root(e["task"]) for e in val}


def test_one_trajectory_per_task_preferring_sonnet(tmp_path):
    for teacher, tasks in {
        "claude-opus-5-5": ["a", "b"],
        "claude-sonnet-5-5": ["b", "c"],
    }.items():
        (tmp_path / teacher).mkdir()
        (tmp_path / teacher / "sft.jsonl").write_text(
            "".join(json.dumps(example(t, teacher)) + "\n" for t in tasks)
        )
    chosen = load_examples(tmp_path, {"a", "b"})
    assert [(e["task"], e["teacher"]) for e in chosen] == [
        ("a", "claude-opus-5-5"),
        ("b", "claude-sonnet-5-5"),
    ]


@pytest.mark.skipif(
    not (ROOT / ".cache/qwen-7b-tokenizer").exists(), reason="pinned Qwen tokenizer not cached"
)
def test_loss_covers_exactly_each_action_and_its_end_token():
    pytest.importorskip("transformers")
    from liquidbench.claude_provider import qwen_tokenizer

    tokenizer = qwen_tokenizer()
    actions = ['{"tool": "read_file", "args": {"path": "a"}}', '{"tool": "finish", "args": {}}']
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": actions[0]},
        {"role": "user", "content": "Tool result: {}"},
        {"role": "assistant", "content": actions[1]},
    ]
    ids, labels = tokenize(messages, tokenizer)
    trained = tokenizer.decode([i for i, label in zip(ids, labels) if label != IGNORE])
    assert trained == "".join(a + "<|im_end|>" for a in actions)


def test_final_render_must_follow_the_last_write():
    from liquidbench.sft import final_render

    def actions(*tools):
        return [
            {"role": "assistant", "content": json.dumps({"tool": t, "args": {}})} for t in tools
        ]

    assert final_render(actions("read_file", "write_file", "check", "render", "finish"))
    assert not final_render(actions("read_file", "render", "write_file", "check", "finish"))
    assert not final_render(actions("read_file", "write_file", "check", "finish"))


def test_frozen_validation_tasks_keep_their_families_out_of_train():
    examples = [example(t) for t in ("a", "a-2", "b", "c")]
    train, val = split(examples, val_tasks=["a"])
    assert [e["task"] for e in val] == ["a", "a-2"]
    assert [e["task"] for e in train] == ["b", "c"]
