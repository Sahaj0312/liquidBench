import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
summarize = runpy.run_path(str(ROOT / "scripts/analyze_runs.py"))["summarize"]


def test_analysis_counts_legacy_nested_errors_and_revised_protocol_errors(tmp_path):
    result = {
        "task_id": "test",
        "run_id": "test",
        "task_digest": "digest",
        "image_id": "image",
        "source": {},
        "config": {},
        "status": "failed",
        "termination": "turn_budget",
        "input_tokens": 20,
        "output_tokens": 10,
        "model_calls": 2,
        "elapsed_seconds": 1.0,
        "provider_errors": [],
    }
    (tmp_path / "result.json").write_text(json.dumps(result))
    (tmp_path / "changes.patch").write_text("")
    events = [
        {"event": "model_request", "prompt_token_count": 10},
        {
            "event": "model_response",
            "content": '```json\n{"tool":"render","args":{"path":"a"}}\n```',
            "input_tokens": 10,
            "output_tokens": 5,
            "metadata": {"finish_reason": "stop"},
        },
        {"event": "tool_result", "ok": True, "result": {"ok": False, "error": "render failure"}},
        {"event": "model_response", "content": "bad JSON", "input_tokens": 10, "output_tokens": 5},
        {
            "event": "tool_result",
            "ok": False,
            "error_type": "protocol_errors",
            "error": "invalid JSON",
        },
    ]
    (tmp_path / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    report = summarize(tmp_path)
    assert report["tool_errors"] == 1
    assert report["protocol_errors"] == 1
    assert report["malformed_envelopes"] == 1
    assert report["action_counts"] == {"render": 1}
    assert report["changed_files"] == []
    assert report["count_deltas"] == [0]
    assert report["errors"][0]["line"] == 3
