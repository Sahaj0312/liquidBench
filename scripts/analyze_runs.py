"""Summarize saved development traces; never call models or read evaluator data.

Usage: uv run python scripts/analyze_runs.py before=runs/suite-... after=runs/suite-...
Output is JSON on stdout. Raw traces and patches remain local, with hashes for audit.
"""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(directory):
    result_path = directory / "result.json"
    trace_path = directory / "trace.jsonl"
    patch_path = directory / "changes.patch"
    result = json.loads(result_path.read_text())
    events = [json.loads(line) for line in trace_path.read_text().splitlines()]
    actions, errors, counts, responses = [], [], [], []
    malformed = 0
    last_action = None
    last_request = None
    for line, event in enumerate(events, 1):
        if event["event"] == "model_request":
            last_request = event
        elif event["event"] == "model_response":
            responses.append(event)
            if last_request and last_request.get("prompt_token_count") is not None:
                counts.append(event["input_tokens"] - last_request["prompt_token_count"])
            content = event["content"]
            fence = re.fullmatch(r"\s*```(?:json)?\s*\n(.*?)\n```\s*", content, re.DOTALL)
            try:
                action = json.loads(fence.group(1) if fence else content)
                if not isinstance(action, dict) or set(action) != {"tool", "args"}:
                    raise ValueError("Not an action envelope")
                last_action = action["tool"]
                actions.append(
                    {"line": line, "tool": last_action, "path": action["args"].get("path")}
                )
            except (ValueError, KeyError, TypeError, AttributeError):
                malformed += 1
                last_action = None
        elif event["event"] == "tool_result":
            # v1 wrapped render failures in outer ok:true; normalize both versions.
            nested = event.get("result", {})
            if event.get("ok") is False or nested.get("ok") is False:
                errors.append(
                    {
                        "line": line,
                        "tool": last_action,
                        "type": event.get(
                            "error_type", "tool_errors" if last_action else "protocol_errors"
                        ),
                        "error": event.get("error", nested.get("error")),
                    }
                )
    return {
        "task_id": result["task_id"],
        "run_id": result["run_id"],
        "artifacts": str(directory),
        "sha256": {
            "trace": sha(trace_path),
            "result": sha(result_path),
            "patch": sha(patch_path) if patch_path.exists() else None,
        },
        "task_digest": result["task_digest"],
        "image_id": result.get("image_id"),
        "source": result["source"],
        "config": result["config"],
        "skills": result.get("skills"),
        "skill_accesses": result.get("skill_accesses", []),
        "context_exposures": result.get("context_exposures", []),
        "grade_passed": result.get("grade", {}).get("passed"),
        "usage_incomplete": result.get("usage_incomplete", False),
        "status": result["status"],
        "termination": result["termination"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "model_calls": result["model_calls"],
        "elapsed_seconds": result["elapsed_seconds"],
        "max_prompt_tokens": max((r["input_tokens"] for r in responses), default=0),
        "max_output_tokens": max((r["output_tokens"] for r in responses), default=0),
        "length_stops": sum(
            r.get("metadata", {}).get("finish_reason") == "length" for r in responses
        ),
        "count_deltas": sorted(set(counts)),
        "malformed_envelopes": malformed,
        "protocol_errors": sum(e["type"] == "protocol_errors" for e in errors),
        "tool_errors": sum(e["type"] == "tool_errors" for e in errors),
        "provider_errors": result["provider_errors"],
        "action_counts": dict(Counter(a["tool"] for a in actions)),
        "changed_files": [
            line[6:]
            for line in (patch_path.read_text().splitlines() if patch_path.exists() else [])
            if line.startswith("+++ b/")
        ],
        "actions": actions,
        "errors": errors,
    }


def suite(path):
    manifest = json.loads((path / "summary.json").read_text())
    runs = [summarize(path / entry["artifacts"]) for entry in manifest["runs"]]
    return {
        "runs": runs,
        "totals": {
            "attempts": len(runs),
            "statuses": dict(Counter(r["status"] for r in runs)),
            "terminations": dict(Counter(r["termination"] for r in runs)),
            **{
                key: sum(r[key] for r in runs)
                for key in [
                    "input_tokens",
                    "output_tokens",
                    "model_calls",
                    "protocol_errors",
                    "tool_errors",
                    "length_stops",
                    "elapsed_seconds",
                ]
            },
        },
    }


if __name__ == "__main__":
    comparison = {
        label: suite(Path(path)) for label, path in (arg.split("=", 1) for arg in sys.argv[1:])
    }
    print(json.dumps({"development_only": True, "suites": comparison}, indent=2))
