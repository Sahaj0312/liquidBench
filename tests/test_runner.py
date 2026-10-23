import json
from pathlib import Path

import pytest

from liquidbench.provider import Completion, ProviderError
from liquidbench.runner import load_config, parse_action, run
from liquidbench.task import Task, safe_name

ROOT = Path(__file__).resolve().parents[1]


class MemorySandbox:
    def __init__(self, image, files):
        self.files = dict(files)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def call(self, tool, args):
        if tool == "write_file":
            self.files[args["path"]] = args["content"]
        return {"ok": True}

    def snapshot(self):
        return self.files


class ScriptedProvider:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.contexts = []

    def count_prompt(self, messages, timeout):
        return 100

    def complete(self, messages, max_tokens, timeout):
        self.contexts.append(json.dumps(messages))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, Completion):
            return reply
        return Completion(reply, 100, 20, {"fixture": True})


def run_fixture(tmp_path, replies, **changes):
    config = load_config(ROOT / "configs/local-smoke.json")
    config.update(changes)
    task = Task.load(ROOT / "tasks/dev/product-card")
    provider = ScriptedProvider(replies)
    destination, result = run(
        task,
        config,
        tmp_path,
        provider=provider,
        sandbox_factory=MemorySandbox,
        resolve_image=lambda _: "sha256:test",
        grader=lambda task, files, image: {
            "passed": files["snippets/product-card.liquid"] == task.reference,
            "checks": [],
        },
    )
    return task, provider, destination, result


def test_success_captures_patch_usage_and_hides_reference(tmp_path):
    reference = Task.load(ROOT / "tasks/dev/product-card").reference
    replies = [
        json.dumps(
            {
                "tool": "write_file",
                "args": {"path": "snippets/product-card.liquid", "content": reference},
            }
        ),
        '{"tool":"finish","args":{}}',
    ]
    task, provider, destination, result = run_fixture(tmp_path, replies)
    assert result["status"] == "passed"
    assert result["input_tokens"] == 200
    assert result["output_tokens"] == 40
    assert "evaluator" not in provider.contexts[0]
    assert task.reference not in provider.contexts[0]
    assert "Larch-9f31" not in provider.contexts[0]
    assert "+  <h2>{{ card_title | escape }}</h2>" in (destination / "changes.patch").read_text()
    assert json.loads((destination / "result.json").read_text())["status"] == "passed"


def test_malformed_actions_consume_turns_and_fail(tmp_path):
    _, _, _, result = run_fixture(
        tmp_path, ["not JSON", '{"tool":"_snapshot","args":{}}'], max_turns=2
    )
    assert result["status"] == "failed"
    assert result["termination"] == "turn_budget"
    assert result["tool_calls"] == 2


def test_provider_retries_are_recorded_and_cost_not_fabricated(tmp_path):
    _, _, _, result = run_fixture(
        tmp_path, [ProviderError("HTTP 503", True), '{"tool":"finish","args":{}}']
    )
    assert result["model_calls"] == 2
    assert result["usage_incomplete"]
    assert result["estimated_cost_usd"] is None
    assert result["provider_errors"] == ["HTTP 503"]


def test_infrastructure_failure_is_missing_not_model_failure(tmp_path):
    _, _, destination, result = run_fixture(tmp_path, [ProviderError("HTTP 401")])
    assert result["status"] == "infrastructure_error"
    assert (destination / "trace.jsonl").exists()
    assert result["input_tokens"] == 0


def test_measured_token_overrun_prevents_tool_execution(tmp_path):
    huge = Completion('{"tool":"finish","args":{}}', 24000, 100, {})
    _, _, _, result = run_fixture(tmp_path, [huge])
    assert result["termination"] == "token_budget_overrun"
    assert result["tool_calls"] == 0


def test_budget_preflight_makes_no_unfunded_model_request(tmp_path):
    _, provider, _, result = run_fixture(tmp_path, [], max_total_tokens=1)
    assert not provider.contexts
    assert result["termination"] == "token_budget"
    assert result["status"] == "failed"


@pytest.mark.parametrize("value", ["../secret", "/etc/passwd", "a/../secret", "a//b", ""])
def test_unsafe_paths(value):
    assert not safe_name(value)


@pytest.mark.parametrize(
    "raw", ["[]", "{}", '{"tool":"_initialize","args":{}}', '{"tool":"read_file","args":[]}']
)
def test_protocol_rejects_internal_tools(raw):
    with pytest.raises(ValueError):
        parse_action(raw)


def test_normalizes_one_json_fence_without_repairing_json():
    assert parse_action('```json\n{"tool":"finish","args":{}}\n```')["tool"] == "finish"
    with pytest.raises(ValueError):
        parse_action('Some prose\n```json\n{"tool":"finish","args":{}}\n```')
    with pytest.raises(ValueError):
        parse_action('```json\n{"tool":"finish",}\n```')


def test_preserves_edits_when_provider_fails_after_write(tmp_path):
    replies = [
        json.dumps(
            {
                "tool": "write_file",
                "args": {"path": "snippets/product-card.liquid", "content": "partial work"},
            }
        ),
        ProviderError("HTTP 401"),
    ]
    _, _, destination, result = run_fixture(tmp_path, replies)
    assert result["status"] == "infrastructure_error"
    assert result["snapshot_captured"]
    assert (destination / "final/snippets/product-card.liquid").read_text() == "partial work"
