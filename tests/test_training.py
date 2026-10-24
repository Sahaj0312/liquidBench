import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from liquidbench.claude_provider import ClaudeProvider, Ledger, usage_cost
from liquidbench.provider import ProviderError

ROOT = Path(__file__).resolve().parents[1]


def test_usage_cost_and_batch_discount():
    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read_input_tokens": 0}
    assert usage_cost("claude-opus-5-5", usage) == pytest.approx(6.0)
    assert usage_cost("claude-sonnet-5-5", usage, batch=True) == pytest.approx(1.5)


def test_ledger_refuses_calls_past_cap(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl", 0.05)
    ledger.require(0.01)
    ledger.record("x", "claude-sonnet-5-5", {"input_tokens": 0, "output_tokens": 5000})
    assert ledger.spent() == pytest.approx(0.05)
    with pytest.raises(ProviderError, match="cap"):
        ledger.require(0.001)


class FakeTokenizer:
    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        return "".join(m["content"] for m in messages)

    def encode(self, text, add_special_tokens):
        return text.split()


class FakeClient:
    def __init__(self, text, stop_reason="end_turn"):
        self.calls = []
        self.reply = SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text=text),
            ],
            stop_reason=stop_reason,
            model="claude-sonnet-5-5",
            usage=SimpleNamespace(
                model_dump=lambda **_: {"input_tokens": 100, "output_tokens": 50}
            ),
        )
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.reply


def provider(tmp_path, text, **kw):
    client = FakeClient(text, **kw)
    ledger = Ledger(tmp_path / "ledger.jsonl", 1.0)
    return ClaudeProvider(
        "claude-sonnet-5-5", ledger, client=client, tokenizer=FakeTokenizer()
    ), client


def test_provider_maps_harness_messages_and_counts_with_student_tokenizer(tmp_path):
    p, client = provider(tmp_path, '{"tool":"finish","args":{}}')
    messages = [{"role": "system", "content": "sys a b"}, {"role": "user", "content": "task c"}]
    reply = p.complete(messages, 1024, 30)
    call = client.calls[0]
    assert call["system"][0]["text"] == "sys a b"
    assert call["messages"] == [{"role": "user", "content": "task c"}]
    assert call["max_tokens"] > 1024 and call["fallbacks"] == "default"
    assert reply.input_tokens == 4 and reply.output_tokens == 1
    assert reply.metadata["finish_reason"] == "stop" and reply.metadata["usd"] > 0
    assert p.transcript[-1] == {"role": "assistant", "content": '{"tool":"finish","args":{}}'}


def test_provider_flags_actions_longer_than_student_limit(tmp_path):
    p, _ = provider(tmp_path, "word " * 50)
    reply = p.complete(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}], 10, 30
    )
    assert reply.metadata["finish_reason"] == "length"


def test_provider_refusal_is_not_a_trajectory(tmp_path):
    p, _ = provider(tmp_path, "", stop_reason="refusal")
    with pytest.raises(ProviderError, match="declined"):
        p.complete([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}], 10, 30)


integration = pytest.mark.skipif(
    os.environ.get("LIQUIDBENCH_INTEGRATION") != "1", reason="Set LIQUIDBENCH_INTEGRATION=1"
)

RENDER = {
    "family": "loyalty-tier-label",
    "category": "liquid-syntax",
    "difficulty": "easy",
    "path": "snippets/loyalty-tier-label.liquid",
    "prompt": "Repair snippets/loyalty-tier-label.liquid. customer.points is a nonnegative "
    "integer. Output one p class=tier: Gold when points is at least 1000, Silver when "
    "at least 250, otherwise Bronze.",
    "starter": '<p class="tier">{% if customer.points > 1000 %}Gold{% else %}Bronze{% endif %}</p>',
    "reference": '<p class="tier">{% if customer.points >= 1000 %}Gold{% elsif customer.points '
    ">= 250 %}Silver{% else %}Bronze{% endif %}</p>",
    "extra_files": [],
    "tags": ["p"],
    "expected_schema_json": "",
    "cases": [
        {
            "variables_json": json.dumps({"customer": {"points": p}}),
            "expected_html": f'<p class="tier">{t}</p>',
        }
        for p, t in [
            (0, "Bronze"),
            (249, "Bronze"),
            (250, "Silver"),
            (999, "Silver"),
            (1000, "Gold"),
            (5000, "Gold"),
        ]
    ],
    "wrong_solutions": [
        {
            "name": "boundary",
            "content": '<p class="tier">{% if customer.points > 1000 %}Gold'
            "{% elsif customer.points >= 250 %}Silver{% else %}"
            "Bronze{% endif %}</p>",
        },
        {
            "name": "no silver",
            "content": '<p class="tier">{% if customer.points >= 1000 %}Gold'
            "{% else %}Bronze{% endif %}</p>",
        },
    ],
}


def build_spec(tmp_path, spec, **changes):
    from liquidbench.heldout import verify_frozen
    from liquidbench.sandbox import Sandbox, image_id
    from liquidbench.training_tasks import build

    return build(
        {**spec, **changes},
        tmp_path,
        sandbox_factory=Sandbox,
        image=image_id("liquidbench-runtime:0.1"),
        heldout_tasks=verify_frozen(),
        known_families=set(),
        provenance="test",
    )


@integration
def test_verified_render_spec_becomes_a_train_task(tmp_path):
    from liquidbench.task import Task

    task = Task.load(build_spec(tmp_path, RENDER))
    assert task.manifest["split"] == "train" and len(task.cases) == 7


@integration
@pytest.mark.parametrize(
    "change,match",
    [
        # Author's predicted output disagrees with the reference's real output.
        (
            {
                "cases": [
                    {**RENDER["cases"][0], "expected_html": '<p class="tier">Gold</p>'},
                    *RENDER["cases"][1:],
                ]
            },
            "verdict wrong for reference",
        ),
        # A wrong solution the cases cannot distinguish from the reference.
        (
            {
                "wrong_solutions": [
                    RENDER["wrong_solutions"][1],
                    {"name": "same", "content": RENDER["reference"]},
                ]
            },
            "verdict wrong",
        ),
        ({"family": "stock-badge", "path": "snippets/stock-badge.liquid"}, "leaked"),
        ({"path": "sections/loyalty-tier-label.liquid"}, "path must be"),
    ],
)
def test_unverifiable_specs_are_rejected_and_not_kept(tmp_path, change, match):
    from liquidbench.training_tasks import Rejected

    with pytest.raises(Rejected, match=match):
        build_spec(tmp_path, RENDER, **change)
    assert not any(tmp_path.iterdir())


@integration
def test_schema_and_reference_specs_verify(tmp_path):
    schema = {
        "name": "Video",
        "settings": [{"type": "checkbox", "id": "autoplay", "label": "Autoplay", "default": False}],
    }
    body = '<section class="video"></section>\n'
    wrap = lambda s: body + "{% schema %}\n" + json.dumps(s) + "\n{% endschema %}\n"  # noqa: E731
    spec = {
        **RENDER,
        "family": "video-schema-test",
        "category": "section-schema",
        "path": "sections/video-schema-test.liquid",
        "prompt": "Repair the schema.",
        "starter": wrap({**schema, "settings": [{**schema["settings"][0], "default": "no"}]}),
        "reference": wrap(schema),
        "tags": [],
        "cases": [],
        "expected_schema_json": json.dumps(schema),
        "wrong_solutions": [
            {"name": "string", "content": wrap({**schema, "name": "V"})},
            {"name": "markup", "content": wrap(schema).replace("video", "x")},
        ],
    }
    assert build_spec(tmp_path, spec).name == "video-schema-test"
    ref = "<span>{{ 'search.label' | t }}</span>"
    locales = [
        {"path": "locales/en.default.json", "content": '{"search": {"label": "Search"}}'},
        {"path": "locales/fr.json", "content": '{"search": {"label": "Chercher"}}'},
    ]
    spec = {
        **spec,
        "family": "search-label-test",
        "category": "theme-references",
        "path": "snippets/search-label-test.liquid",
        "prompt": "Fix the translation key.",
        "starter": ref.replace("search.label", "search.lable"),
        "reference": ref,
        "extra_files": locales,
        "expected_schema_json": "",
        "wrong_solutions": [
            {"name": "literal", "content": "<span>Search</span>"},
            {"name": "filter", "content": ref.replace(" | t", " | escape")},
        ],
    }
    assert build_spec(tmp_path, spec).name == "search-label-test"


def test_structured_reply_becomes_exact_student_action():
    from liquidbench.claude_provider import canonical_action

    reply = json.dumps(
        {
            "action": {
                "tool": "render",
                "args": {
                    "path": "snippets/a.liquid",
                    "variables_json": '{"x": {"y": null}}',
                    "strip_schema": False,
                },
            }
        }
    )
    assert json.loads(canonical_action(reply)) == {
        "tool": "render",
        "args": {
            "path": "snippets/a.liquid",
            "variables": {"x": {"y": None}},
            "strip_schema": False,
        },
    }
    assert canonical_action(json.dumps({"action": {"tool": "finish", "args": {}}})) == (
        '{"tool": "finish", "args": {}}'
    )
    assert canonical_action('<invoke name="read_file">') is None
    assert (
        canonical_action(
            json.dumps(
                {
                    "action": {
                        "tool": "render",
                        "args": {"path": "a", "variables_json": "[1]", "strip_schema": False},
                    }
                }
            )
        )
        is None
    )


def test_reused_family_is_renamed_with_its_path():
    from liquidbench.training_tasks import unique_family

    spec = {**RENDER, "prompt": "Repair snippets/loyalty-tier-label.liquid. " + RENDER["prompt"]}
    assert unique_family(spec, set()) is spec
    renamed = unique_family(spec, {"loyalty-tier-label", "loyalty-tier-label-2"})
    assert renamed["family"] == "loyalty-tier-label-3"
    assert renamed["path"] == "snippets/loyalty-tier-label-3.liquid"
    assert "snippets/loyalty-tier-label.liquid" not in json.dumps(renamed)
    assert renamed["cases"] == RENDER["cases"]


def test_teacher_note_reaches_claude_but_not_the_student_transcript(tmp_path):
    client = FakeClient('{"tool":"finish","args":{}}')
    p = ClaudeProvider(
        "claude-sonnet-5-5",
        Ledger(tmp_path / "ledger.jsonl", 1.0),
        client=client,
        tokenizer=FakeTokenizer(),
        teacher_note="render edge cases",
    )
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]
    p.complete(messages, 1024, 30)
    assert [b["text"] for b in client.calls[0]["system"]] == ["sys", "render edge cases"]
    assert "render edge cases" not in json.dumps(p.transcript)
