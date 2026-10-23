from pathlib import Path

import httpx
import pytest

from liquidbench.provider import ChatProvider, ProviderError
from liquidbench.runner import load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.com/v1",
        "https://secret@example.com/v1",
        "https://example.com/v1?api_key=secret",
        "file:///tmp",
    ],
)
def test_reject_unsafe_endpoints(endpoint):
    with pytest.raises(ValueError):
        ChatProvider({"endpoint": endpoint})


def test_adapter_keeps_credential_out_of_request_body(monkeypatch):
    config = load_config(ROOT / "configs/local-smoke.json")
    config["api_key_env"] = "LIQUIDBENCH_TEST_KEY"
    monkeypatch.setenv("LIQUIDBENCH_TEST_KEY", "test-only-secret")
    captured = {}

    def post(self, url, *, headers, json):
        captured.update(url=url, headers=headers, body=json)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"tool":"finish","args":{}}'}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "model": "test",
            },
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    reply = ChatProvider(config).complete([{"role": "user", "content": "hello"}], 100, 5)
    assert captured["headers"]["Authorization"] == "Bearer test-only-secret"
    assert "test-only-secret" not in str(captured["body"])
    assert reply.input_tokens == 10
    assert reply.output_tokens == 5


@pytest.mark.parametrize("status,retryable", [(401, False), (429, True), (503, True)])
def test_provider_error_classification(monkeypatch, status, retryable):
    monkeypatch.setattr(
        httpx.Client,
        "post",
        lambda *a, **k: httpx.Response(
            status, text="sensitive server response must not enter trace"
        ),
    )
    provider = ChatProvider(load_config(ROOT / "configs/local-smoke.json"))
    with pytest.raises(ProviderError) as caught:
        provider.complete([], 10, 5)
    assert caught.value.retryable is retryable
    assert "sensitive" not in str(caught.value)


def test_missing_usage_is_not_reported_as_zero(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "post",
        lambda *a, **k: httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]}),
    )
    with pytest.raises(ProviderError, match="token usage"):
        ChatProvider(load_config(ROOT / "configs/local-smoke.json")).complete([], 10, 5)


@pytest.mark.parametrize("mode", ["text", "json_object"])
def test_output_format_is_explicit_and_has_no_task_schema(monkeypatch, mode):
    config = load_config(ROOT / "configs/local-smoke.json")
    config["response_format"] = mode

    def post(self, route, payload, timeout):
        if mode == "json_object":
            assert payload["response_format"] == {"type": "json_object"}
        else:
            assert "response_format" not in payload
        assert "tools" not in payload
        assert "schema" not in payload
        return {
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }

    monkeypatch.setattr(ChatProvider, "post", post)
    assert ChatProvider(config).complete([], 10, 5).content == "{}"


def test_unsupported_json_mode_is_not_silently_retried_as_text(monkeypatch):
    calls = []

    def post(*args, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(400, text="unsupported response_format")

    monkeypatch.setattr(httpx.Client, "post", post)
    with pytest.raises(ProviderError) as caught:
        ChatProvider(load_config(ROOT / "configs/local-smoke.json")).complete([], 10, 5)
    assert not caught.value.retryable
    assert len(calls) == 1
