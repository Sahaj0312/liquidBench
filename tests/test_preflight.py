import json
import hashlib
from pathlib import Path
import runpy

import httpx
import pytest

from liquidbench.runner import load_config

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = runpy.run_path(str(ROOT / "scripts/preflight_endpoint.py"))
preflight = SCRIPT["preflight"]


def mock_endpoint(monkeypatch, failure=None):
    calls = []

    def post(self, url, *, headers, json):
        calls.append((url, json))
        messages = json["messages"]
        count = 600 + sum(m["content"].count(" filler") for m in messages)
        if url.endswith("/tokenize"):
            assert json["add_generation_prompt"] is True
            assert json["add_special_tokens"] is False
            return httpx.Response(200, json={"count": count})
        assert url.endswith("/v1/chat/completions")
        assert json["response_format"] == {"type": "json_object"}
        assert json["max_tokens"] == 1024
        assert (json["temperature"], json["top_p"], json["seed"]) == (0, 1, 42)
        assert "tools" not in json
        content = (
            '{"tool":"read_file","args":{"path":"snippets/probe.liquid"}}'
            if len(messages) == 2 and not messages[-1]["content"].count(" filler")
            else '{"tool":"finish","args":{}}'
        )
        if failure == "http":
            return httpx.Response(503, text="secret diagnostic")
        if failure == "prose":
            content = "READY"
        if failure == "action":
            content = '{"tool":"shell","args":{}}'
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": content},
                        "finish_reason": "length" if failure == "length" else "stop",
                    }
                ],
                "model": "wrong-model" if failure == "model" else json["model"],
                "usage": {
                    "prompt_tokens": count + (failure == "count"),
                    "completion_tokens": 10,
                },
            },
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    return calls


def test_preflight_exercises_json_counting_and_feedback_without_attesting_gpu(
    monkeypatch, tmp_path
):
    calls = mock_endpoint(monkeypatch)
    config = load_config(ROOT / "configs/qwen-base.json")
    directory = tmp_path / "preflight"
    report = preflight(config, directory)
    assert report["passed"]
    assert report["gpu_precision_revision_verified"] is False
    assert report["research_result"] is False
    assert len(report["checks"]) == 4
    assert len([url for url, _ in calls if url.endswith("completions")]) == 4
    assert len(calls) <= 24
    near = report["checks"][-1]
    assert 8192 - 1024 - 32 - 128 <= near["prompt_count"] <= 8192 - 1024 - 32
    assert json.loads((directory / "report.json").read_text()) == report
    events = [json.loads(line) for line in (directory / "trace.jsonl").read_text().splitlines()]
    responses = [e for e in events if e["event"] == "model_response"]
    assert len(responses) == 4
    assert all(e["elapsed_seconds"] >= 0 and e["metadata"]["usage"] for e in responses)
    assert all(e["count_delta"] == 0 for e in report["checks"])
    with pytest.raises(FileExistsError):
        preflight(config, directory)


@pytest.mark.parametrize("failure", ["http", "prose", "action", "length", "model", "count"])
def test_preflight_stops_and_preserves_failure_evidence(monkeypatch, tmp_path, failure):
    calls = mock_endpoint(monkeypatch, failure)
    directory = tmp_path / "preflight"
    report = preflight(load_config(ROOT / "configs/qwen-base.json"), directory)
    assert not report["passed"]
    assert report["error"]
    assert len(calls) == 2  # No retries or unconstrained-output fallback.
    assert "secret diagnostic" not in (directory / "trace.jsonl").read_text()
    assert not json.loads((directory / "report.json").read_text())["passed"]


@pytest.mark.parametrize("content", ["```json\n{}\n```", "[]", '{"a":1,"a":2}', '{"a":NaN}'])
def test_json_enforcement_is_stricter_than_action_fence_normalization(content):
    with pytest.raises(ValueError):
        SCRIPT["strict_object"](content)


def test_unconstrained_preflight_never_contacts_provider(monkeypatch, tmp_path):
    calls = mock_endpoint(monkeypatch)
    config = load_config(ROOT / "configs/qwen-base.json")
    config["response_format"] = "text"
    with pytest.raises(ValueError, match="json_object"):
        preflight(config, tmp_path / "preflight")
    assert not calls


def test_deployment_plan_preserves_calibrated_config_and_has_no_observed_result():
    plan = json.loads((ROOT / "docs/calibration/qwen-7b-pilot.json").read_text())
    path = ROOT / plan["config_path"]
    config = load_config(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == plan["config_sha256"]
    serving = plan["planned_serving"]
    args = serving["arguments"]
    assert args[0] == config["model"] == serving["model"]
    flags = dict(zip(args[1::2], args[2::2], strict=True))
    assert flags["--max-model-len"] == str(config["max_context_tokens"])
    assert flags["--seed"] == str(config["seed"])
    assert flags["--dtype"] == "bfloat16"
    assert flags["--revision"] == flags["--tokenizer-revision"] == serving["revision"]
    assert serving["revision"] in config["model_revision"]
    assert serving["image"].startswith("vllm/vllm-openai@sha256:")
    assert plan["observed_serving"] is plan["endpoint_preflight"] is plan["suite"] is None
