import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from liquidbench.preflight import (
    CHECK_NAMES,
    GENERATION_TARGETS,
    preflight,
    representative_messages,
    strict_object,
    synthetic_document,
    validate_report,
)
from liquidbench.runner import load_config

ROOT = Path(__file__).resolve().parents[1]


def config():
    return load_config(ROOT / "configs/qwen-ab-base.json")


def mock_endpoint(monkeypatch, failure=None, stage="short_action"):
    calls = []
    counts_seen = {}

    def post(self, url, *, headers, json):
        calls.append((url, json))
        messages = json["messages"]
        count = 200 + sum(len(m["content"]) for m in messages) // 4
        if count > 30000:
            name = "near_window_accounting"
        elif count > 16000:
            name = "representative_17k"
        elif count > 10000:
            name = "representative_10k"
        elif len(messages) == 1:
            name = "json_enforcement"
        elif len(messages) > 2:
            name = "tool_feedback_roles"
        else:
            name = "short_action"
        fail = failure if name == stage else None
        if url.endswith("/tokenize"):
            assert json["add_generation_prompt"] is True
            assert json["add_special_tokens"] is False
            key = repr(messages)
            counts_seen[key] = counts_seen.get(key, 0) + 1
            if fail == "unstable" and counts_seen[key] > 1:
                count += 1
            if fail == "invalid_count":
                count = -1
            return httpx.Response(200, json={"count": count})
        assert url.endswith("/v1/chat/completions")
        assert json["response_format"] == {"type": "json_object"}
        assert json["max_tokens"] == 1024
        assert (json["temperature"], json["top_p"], json["seed"]) == (0, 1, 42)
        assert "tools" not in json
        content = (
            '{"tool":"read_file","args":{"path":"snippets/probe.liquid"}}'
            if name == "short_action"
            else '{"tool":"finish","args":{}}'
        )
        if fail == "http":
            return httpx.Response(503, text="secret diagnostic")
        if fail == "prose":
            content = "READY"
        if fail == "action":
            content = '{"tool":"shell","args":{}}'
        if fail == "length":
            content = '{"tool":"unfinished'
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": content},
                        "finish_reason": (
                            "length"
                            if fail == "length"
                            else "other"
                            if fail == "finish"
                            else "stop"
                        ),
                    }
                ],
                "model": "wrong-model" if fail == "model" else json["model"],
                "usage": {
                    "prompt_tokens": count + (fail == "count"),
                    "completion_tokens": (
                        0 if fail == "zero" else 1025 if fail == "excess" else 10
                    ),
                },
            },
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    return calls


def test_preflight_generation_and_tokenizer_stress_are_separate(monkeypatch, tmp_path):
    calls = mock_endpoint(monkeypatch)
    directory = tmp_path / "preflight"
    report = preflight(config(), directory)
    assert report["passed"]
    assert report["failure_kind"] is None
    assert report["model_failures"] == []
    assert report["gpu_precision_revision_verified"] is False
    assert report["research_result"] is False
    assert [c["name"] for c in report["checks"]] == CHECK_NAMES
    assert len([url for url, _ in calls if url.endswith("completions")]) == 5
    assert len(calls) <= 92  # Four bounded sizing searches, five completions/counts, repeats.
    near = report["checks"][3]
    assert 31712 - 128 <= near["prompt_count"] <= 31712
    assert 32736 - 128 <= near["over_prompt_count"] <= 32736
    assert near["stable_counts"] and near["near_admitted"] and near["over_rejected"]
    assert near["generation_performed"] is False
    for check in report["checks"][4:]:
        target = GENERATION_TARGETS[check["name"]]
        assert target - 128 <= check["prompt_count"] <= target
    assert json.loads((directory / "report.json").read_text()) == report
    events = [json.loads(line) for line in (directory / "trace.jsonl").read_text().splitlines()]
    responses = [e for e in events if e["event"] == "model_response"]
    assert len(responses) == 5
    assert all(e["elapsed_seconds"] >= 0 and e["metadata"]["usage"] for e in responses)
    requests = [e for e in events if e["event"] == "model_request"]
    assert max(e["prompt_token_count"] for e in requests) <= 17000
    assert all(c["count_delta"] == 0 for c in report["checks"] if "count_delta" in c)
    assert len(requests[-2]["messages"]) == 3
    assert [m["role"] for m in requests[-1]["messages"]] == [
        "system",
        "user",
        "user",
        "assistant",
        "user",
    ]
    validate_report(report, config())
    with pytest.raises(FileExistsError):
        preflight(config(), directory)


@pytest.mark.parametrize(
    "failure,kind",
    [
        ("http", "infrastructure"),
        ("prose", "infrastructure"),
        ("model", "infrastructure"),
        ("count", "infrastructure"),
        ("finish", "infrastructure"),
        ("zero", "infrastructure"),
        ("excess", "infrastructure"),
        ("invalid_count", "infrastructure"),
        ("action", "model_protocol"),
        ("length", "model_protocol"),
    ],
)
def test_short_failures_block_with_separate_categories(monkeypatch, tmp_path, failure, kind):
    calls = mock_endpoint(monkeypatch, failure)
    directory = tmp_path / "preflight"
    report = preflight(config(), directory)
    assert not report["passed"]
    assert report["failure_kind"] == kind
    assert report["error"]
    assert len(calls) <= 2  # No retries or unconstrained-output fallback.
    assert "secret diagnostic" not in (directory / "trace.jsonl").read_text()
    if kind == "model_protocol":
        assert report["checks"][0]["infrastructure_passed"]
        assert report["model_failures"]
    with pytest.raises(ValueError):
        validate_report(report, config())


@pytest.mark.parametrize("stage", ["tool_feedback_roles", "json_enforcement"])
def test_other_short_protocol_failures_also_block(monkeypatch, tmp_path, stage):
    mock_endpoint(monkeypatch, "length", stage)
    report = preflight(config(), tmp_path / "preflight")
    assert not report["passed"]
    assert report["failure_kind"] == "model_protocol"
    assert report["checks"][-1]["infrastructure_passed"]
    assert report["checks"][-1]["name"] == stage


@pytest.mark.parametrize("failure", ["action", "length"])
@pytest.mark.parametrize("stage", GENERATION_TARGETS)
def test_representative_model_failures_are_recorded_without_blocking(
    monkeypatch, tmp_path, failure, stage
):
    calls = mock_endpoint(monkeypatch, failure, stage)
    report = preflight(config(), tmp_path / "preflight")
    assert report["passed"]
    assert report["failure_kind"] is None
    assert len(report["checks"]) == 6
    assert report["model_failures"][0]["name"] == stage
    check = next(c for c in report["checks"] if c["name"] == stage)
    assert check["infrastructure_passed"]
    assert check["model_passed"] is False
    assert check["passed"] is True  # Passed gate, not passed instruction-following diagnostic.
    assert len([url for url, _ in calls if url.endswith("completions")]) == 5
    validate_report(report, config())


@pytest.mark.parametrize("failure", ["http", "prose", "model", "count", "excess", "finish"])
def test_representative_infrastructure_failures_still_block(monkeypatch, tmp_path, failure):
    mock_endpoint(monkeypatch, failure, "representative_10k")
    report = preflight(config(), tmp_path / "preflight")
    assert not report["passed"]
    assert report["failure_kind"] == "infrastructure"
    assert not any(c["name"] == "representative_17k" for c in report["checks"])
    with pytest.raises(ValueError):
        validate_report(report, config())


@pytest.mark.parametrize("failure", ["unstable", "invalid_count"])
def test_near_window_tokenizer_failure_blocks_without_generation(monkeypatch, tmp_path, failure):
    calls = mock_endpoint(monkeypatch, failure, "near_window_accounting")
    report = preflight(config(), tmp_path / "preflight")
    assert not report["passed"]
    assert report["failure_kind"] == "infrastructure"
    assert len([url for url, _ in calls if url.endswith("completions")]) == 3


def test_representative_count_instability_blocks_before_generation(monkeypatch, tmp_path):
    calls = mock_endpoint(monkeypatch, "unstable", "representative_10k")
    report = preflight(config(), tmp_path / "preflight")
    assert not report["passed"]
    assert report["failure_kind"] == "infrastructure"
    assert "Unstable tokenizer" in report["error"]
    assert len([url for url, _ in calls if url.endswith("completions")]) == 3


@pytest.mark.parametrize(
    "change",
    ["legacy", "source", "system", "config", "stale", "future", "missing", "infra", "protocol"],
)
def test_paired_gate_rejects_old_or_incomplete_reports(monkeypatch, tmp_path, change):
    mock_endpoint(monkeypatch)
    report = copy.deepcopy(preflight(config(), tmp_path / "preflight"))
    if change == "legacy":
        del report["policy"]
    elif change in {"source", "system"}:
        report[change + "_sha256"] = "stale"
    elif change == "config":
        report["config"]["max_turns"] += 1
    elif change in {"stale", "future"}:
        report["started_utc"] = (
            datetime.now(timezone.utc) + timedelta(hours=-2 if change == "stale" else 1)
        ).isoformat()
    elif change == "missing":
        report["checks"].pop()
    elif change == "infra":
        report["checks"][-1]["infrastructure_passed"] = False
    else:
        report["checks"][0]["model_passed"] = False
    with pytest.raises(ValueError, match="current-policy"):
        validate_report(report, config())


@pytest.mark.parametrize("content", ["```json\n{}\n```", "[]", '{"a":1,"a":2}', '{"a":NaN}'])
def test_json_enforcement_is_stricter_than_action_fence_normalization(content):
    with pytest.raises(ValueError):
        strict_object(content)


def test_invalid_config_never_contacts_provider(monkeypatch, tmp_path):
    calls = mock_endpoint(monkeypatch)
    unconstrained = {**config(), "response_format": "text"}
    with pytest.raises(ValueError, match="json_object"):
        preflight(unconstrained, tmp_path / "preflight")
    with pytest.raises(ValueError, match="17K"):
        preflight(load_config(ROOT / "configs/qwen-base.json"), tmp_path / "preflight")
    assert not calls


def test_synthetic_corpus_is_varied_deterministic_and_contains_no_task_guidance():
    document = synthetic_document()
    assert document == synthetic_document()
    assert len(document.splitlines()) == len(set(document.splitlines())) == 1200
    assert " filler" not in document
    assert "Liquid" not in document
    messages = representative_messages(document[:1000], feedback=True)
    assert document[:600] in messages[1]["content"]
    result = messages[-1]["content"].removeprefix("Tool result: ").split("\nSynthetic protocol")[0]
    assert document[600:1000] in json.loads(result)["result"]


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
