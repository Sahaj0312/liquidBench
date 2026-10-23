import json
from pathlib import Path

import httpx
import pytest

from liquidbench.provider import ChatProvider, Completion, ProviderError
from liquidbench.runner import load_config, parse_action, run
from liquidbench.task import Task
from test_runner import MemorySandbox, ScriptedProvider, run_fixture

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "action",
    [
        {"tool": [], "args": {}},
        {"tool": "finish", "args": {"content": "not saved"}},
        {"tool": "write_file", "args": {"path": "a"}},
        {"tool": "write_file", "args": {"path": "a", "content": {}}},
        {"tool": "render", "args": {"path": "a", "variables": {}, "strip_schema": "false"}},
    ],
)
def test_arguments_rejected_before_execution(action):
    with pytest.raises(ValueError):
        parse_action(json.dumps(action))


def test_context_limit_is_separate_from_cumulative_budget(tmp_path):
    _, provider, _, result = run_fixture(
        tmp_path, [], max_context_tokens=1100, max_total_tokens=24000
    )
    assert result["termination"] == "context_budget"
    assert provider.contexts == []
    assert result["input_tokens"] == 0


def test_total_budget_counts_repeated_prompt_usage(tmp_path):
    _, provider, _, result = run_fixture(
        tmp_path,
        ['{"tool":"list_files","args":{}}'],
        max_total_tokens=240,
        max_context_tokens=8192,
    )
    assert len(provider.contexts) == 1
    assert result["termination"] == "token_budget"


def test_counting_failure_is_infrastructure_not_a_model_error(tmp_path, monkeypatch):
    def fail(*args):
        raise ProviderError("Count endpoint unavailable")

    monkeypatch.setattr(ScriptedProvider, "count_prompt", fail)
    _, provider, _, result = run_fixture(tmp_path, [])
    assert result["status"] == "infrastructure_error"
    assert not provider.contexts
    assert not result["usage_incomplete"]  # Counting never performs paid inference.


def test_underestimated_prompt_cannot_execute_action(tmp_path):
    _, _, _, result = run_fixture(
        tmp_path, [Completion('{"tool":"finish","args":{}}', 200, 20, {})]
    )
    assert result["status"] == "infrastructure_error"
    assert "accounting mismatch" in result["error"]
    assert result["tool_calls"] == 0


def test_length_stop_never_executes_even_valid_json(tmp_path):
    _, _, _, result = run_fixture(
        tmp_path,
        [Completion('{"tool":"finish","args":{}}', 100, 20, {"finish_reason": "length"})],
        max_turns=1,
    )
    assert result["termination"] == "turn_budget"
    assert result["output_truncations"] == 1
    assert result["protocol_errors"] == 1


def test_nested_render_error_is_visible_and_repeated_errors_get_feedback(tmp_path):
    class BrokenRender(MemorySandbox):
        def call(self, tool, args):
            return {"ok": False, "error": "Liquid::UndefinedVariable: heading"}

    action = '{"tool":"render","args":{"path":"snippets/product-card.liquid","variables":{}}}'
    provider = ScriptedProvider([action, action, '{"tool":"finish","args":{}}'])
    destination, result = run(
        Task.load(ROOT / "tasks/dev/product-card"),
        load_config(ROOT / "configs/local-smoke.json"),
        tmp_path,
        provider=provider,
        sandbox_factory=BrokenRender,
        resolve_image=lambda _: "test-image",
        grader=lambda *a: {"passed": False},
    )
    assert result["tool_errors"] == 2
    assert result["protocol_errors"] == 0
    events = [json.loads(line) for line in (destination / "trace.jsonl").read_text().splitlines()]
    errors = [e for e in events if e["event"] == "tool_result"]
    assert all(e["ok"] is False for e in errors)
    assert "same action" in errors[1]["hint"]
    assert "same action" in provider.contexts[2]
    assert "Liquid::UndefinedVariable" in provider.contexts[1]


@pytest.mark.parametrize("backend", ["llama_cpp", "vllm"])
def test_counts_template_with_server_without_inference(monkeypatch, backend):
    config = load_config(ROOT / "configs/local-smoke.json")
    config["token_counting"] = backend
    calls = []

    def post(self, url, *, headers, json):
        calls.append((url, json))
        if url.endswith("/apply-template"):
            return httpx.Response(200, json={"prompt": "templated conversation"})
        assert url.endswith("/tokenize")
        return httpx.Response(200, json={"tokens": [1, 2, 3], "count": 3})

    monkeypatch.setattr(httpx.Client, "post", post)
    messages = [{"role": "user", "content": "hello"}]
    assert ChatProvider(config).count_prompt(messages, 5) == 3
    assert all("/v1/" not in url for url, _ in calls)
    if backend == "vllm":
        assert calls[0][1]["messages"] == messages
        assert calls[0][1]["add_generation_prompt"] is True
        assert calls[0][1]["add_special_tokens"] is False
    else:
        assert calls[0][1]["messages"] == messages
        assert calls[1][1] == {
            "content": "templated conversation",
            "add_special": True,
            "parse_special": True,
        }


@pytest.mark.parametrize("count", [0, -1, True, "100"])
def test_invalid_server_count_fails_closed(monkeypatch, count):
    config = load_config(ROOT / "configs/qwen-base.json")
    monkeypatch.setattr(ChatProvider, "post", lambda *a, **k: {"count": count})
    with pytest.raises(ProviderError, match="prompt token count"):
        ChatProvider(config).count_prompt([], 5)


def test_7b_config_matches_supported_chat_protocol(monkeypatch):
    config = load_config(ROOT / "configs/qwen-base.json")
    assert config["model"] == "Qwen/Qwen2.5-Coder-7B-Instruct"
    assert "c03e6d358207e414f1eca0bb1891e29f1db0e242" in config["model_revision"]
    assert config["max_context_tokens"] == 8192
    assert config["token_counting"] == "vllm"

    def post(self, url, *, headers, json):
        assert url.endswith("/v1/chat/completions")
        assert json["model"] == config["model"]
        assert json["max_tokens"] == 1024
        assert json["response_format"] == {"type": "json_object"}
        assert "tools" not in json  # Portable JSON-in-content, not native tool calling.
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"tool":"finish","args":{}}'}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 9},
            },
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    reply = ChatProvider(config).complete([{"role": "user", "content": "hello"}], 1024, 5)
    assert parse_action(reply.content)["tool"] == "finish"
