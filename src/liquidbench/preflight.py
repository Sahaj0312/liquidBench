"""Versioned endpoint gate, separate from task execution and model scoring.

Synthetic documents and criteria are fixed before deployment. Tokenizer-only
searches size prompts; completion outcomes never select or revise a prompt.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from .provider import ChatProvider, ProviderError
from .runner import SYSTEM, parse_action

POLICY = "liquidbench-preflight-v2"
MANDATORY_MODEL_PROBES = {"short_action", "tool_feedback_roles", "json_enforcement"}
GENERATION_TARGETS = {"representative_10k": 10500, "representative_17k": 17000}
CHECK_NAMES = [
    "short_action",
    "tool_feedback_roles",
    "json_enforcement",
    "near_window_accounting",
    *GENERATION_TARGETS,
]
FINISH = {"tool": "finish", "args": {}}
READ = {"tool": "read_file", "args": {"path": "snippets/probe.liquid"}}


def source_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def messages_for(action):
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": "Synthetic protocol probe, not a coding task. Return exactly this action: "
            + json.dumps(action),
        },
    ]


def synthetic_document():
    """Neutral varied records: no Liquid guidance, upstream skills or task data."""
    subjects = ("orchard", "harbor", "museum", "garden", "station", "library", "trail")
    materials = ("copper", "linen", "birch", "glass", "stone", "paper", "clay")
    notes = (
        "The morning inventory was recorded beside the north entrance.",
        "A blue label marks the shelf reserved for the next inspection.",
        "Visitors followed the eastern path after the afternoon rain.",
        "The archive lists a date, a location, and a short observation.",
        "Each sample was measured twice before being placed in its box.",
    )
    return "\n".join(
        f"Record {i:04d}: {subjects[i % 7]} / {materials[(i // 7) % 7]}. "
        f"{notes[i % 5]} Quantity {(i * 37) % 997}; distance {(i * 13) % 431} metres. "
        + json.dumps({"index": i, "label": f"sample-{i * 19:05d}", "checked": i % 3 == 0})
        for i in range(1200)
    )


def representative_messages(document, *, feedback=False):
    header = "Synthetic reference data for an endpoint diagnostic; no coding task.\n"
    if not feedback:
        return [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": header + document},
            messages_for(FINISH)[-1],
        ]
    split = len(document) * 3 // 5
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": header + document[:split]},
        messages_for(READ)[-1],
        {"role": "assistant", "content": json.dumps(READ)},
        {
            "role": "user",
            "content": "Tool result: "
            + json.dumps({"ok": True, "tool": "read_file", "result": header + document[split:]})
            + "\n"
            + messages_for(FINISH)[-1]["content"],
        },
    ]


def strict_object(content):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Non-JSON numeric constant")

    value = json.loads(content, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object without prose or Markdown fences")
    return value


def check_passes(check):
    return check.get("infrastructure_passed") is True and (
        check["name"] not in MANDATORY_MODEL_PROBES or check.get("model_passed") is True
    )


def validate_report(report, config, *, now=None):
    """Reject old, incomplete, stale or mismatched gates before paired inference."""
    now = now or datetime.now(timezone.utc)
    try:
        age = (now - datetime.fromisoformat(report["started_utc"])).total_seconds()
        valid = (
            report["policy"] == POLICY
            and report["source_sha256"] == source_digest()
            and report["system_sha256"] == hashlib.sha256(SYSTEM.encode()).hexdigest()
            and report["passed"] is True
            and report["config"] == config
            and 0 <= age < 3600
            and [c["name"] for c in report["checks"]] == CHECK_NAMES
            and all(check_passes(c) for c in report["checks"])
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("Require a complete current-policy matching preflight from the last hour")


class ProbeFailure(ValueError):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def preflight(config, directory):
    if config["token_counting"] != "vllm" or config["response_format"] != "json_object":
        raise ValueError("Preflight requires explicit vllm counting and json_object output")
    limit = config["max_context_tokens"] - config["max_output_tokens"] - 32
    if limit < max(GENERATION_TARGETS.values()):
        raise ValueError(
            "Preflight v2 requires room for the fixed 17K probe plus output reservation"
        )
    provider = ChatProvider(config)
    directory.mkdir(parents=True, exist_ok=False)
    report = {
        "kind": "synthetic_endpoint_preflight",
        "policy": POLICY,
        "source_sha256": source_digest(),
        "system_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
        "research_result": False,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "checks": [],
        "passed": False,
        "failure_kind": None,
        "model_failures": [],
        "gpu_precision_revision_verified": False,
        "note": "Host evidence and actual sandbox tool execution require separate verification.",
    }
    timeout = config["request_timeout"]
    document = synthetic_document()

    with (directory / "trace.jsonl").open("x") as trace:

        def record(event, **fields):
            trace.write(json.dumps({"event": event, **fields}) + "\n")
            trace.flush()

        def count(name, messages):
            start = time.monotonic()
            record("count_request", name=name, messages=messages)
            result = provider.count_prompt(messages, timeout)
            record(
                "count_response", name=name, count=result, elapsed_seconds=time.monotonic() - start
            )
            return result

        def sized(name, target, *, feedback=False):
            # Only prefix length is searched, never a completion outcome. Same
            # fixed corpus, bounded tokenizer calls, no diagnostic prompt retries.
            low, high = 0, len(document)
            best = None
            for _ in range(20):
                if low > high:
                    break
                middle = (low + high) // 2
                messages = representative_messages(document[:middle], feedback=feedback)
                predicted = count(name, messages)
                if predicted <= target:
                    best = messages, predicted
                    low = middle + 1
                else:
                    high = middle - 1
            if best is None or not target - 128 <= best[1] <= target:
                raise ProbeFailure("diagnostic_setup", f"Could not size {name} within 128 tokens")
            return best

        def save(check):
            check["infrastructure_passed"] = not check["infrastructure_errors"]
            check["passed"] = check_passes(check)
            report["checks"].append(check)
            if check.get("model_passed") is False:
                report["model_failures"].append(
                    {"name": check["name"], "errors": check["model_errors"]}
                )
            if not check["passed"]:
                kind = "infrastructure" if check["infrastructure_errors"] else "model_protocol"
                raise ProbeFailure(kind, f"Failed {check['name']}; inspect trace before tasks")

        def probe(name, messages, expected=None, *, expected_count=None):
            predicted = count(name, messages)
            if expected_count is not None and predicted != expected_count:
                raise ProbeFailure("infrastructure", f"Unstable tokenizer count for {name}")
            if predicted > limit:
                raise ProbeFailure("diagnostic_setup", "Probe exceeds context reservation")
            record("model_request", name=name, messages=messages, prompt_token_count=predicted)
            start = time.monotonic()
            reply = provider.complete(messages, config["max_output_tokens"], timeout)
            record(
                "model_response",
                name=name,
                **asdict(reply),
                elapsed_seconds=time.monotonic() - start,
            )
            finish_reason = reply.metadata["finish_reason"]
            check = {
                "name": name,
                "prompt_count": predicted,
                "count_delta": reply.input_tokens - predicted,
                "count_agrees": reply.input_tokens == predicted,
                "finish_reason": finish_reason,
                "served_model_agrees": reply.metadata["served_model"] == config["model"],
                "within_output_limit": 0 < reply.output_tokens <= config["max_output_tokens"],
                "infrastructure_errors": [],
                "model_errors": [],
            }
            for field in ("count_agrees", "served_model_agrees", "within_output_limit"):
                if not check[field]:
                    check["infrastructure_errors"].append(field)
            if finish_reason not in {"stop", "length"}:
                check["infrastructure_errors"].append("unsupported_finish_reason")
            try:
                strict_object(reply.content)
                check["json_object"] = True
            except ValueError:
                check["json_object"] = False
            # A length-limited prefix need not be complete JSON. A normally
            # stopped non-object breaks the requested endpoint JSON contract.
            if finish_reason == "stop" and not check["json_object"]:
                check["infrastructure_errors"].append("json_contract")
            if finish_reason == "length":
                check["model_errors"].append("output_truncated")
            if expected is not None:
                try:
                    check["expected_action"] = parse_action(reply.content) == expected
                except (ValueError, TypeError):
                    check["expected_action"] = False
                if not check["expected_action"]:
                    check["model_errors"].append("unexpected_action")
            check["model_passed"] = not check["model_errors"]
            save(check)

        try:
            short = messages_for(READ)
            probe("short_action", short, READ)
            history = short + [
                {"role": "assistant", "content": json.dumps(READ)},
                {"role": "user", "content": json.dumps({"ok": True, "result": "<p>Hello</p>"})},
                {"role": "assistant", "content": '{"tool":"check","args":{}}'},
                {
                    "role": "user",
                    "content": json.dumps({"ok": True, "result": []})
                    + '\nSynthetic probe complete. Return {"tool":"finish","args":{}}.',
                },
            ]
            probe("tool_feedback_roles", history, FINISH)
            probe(
                "json_enforcement",
                [
                    {
                        "role": "user",
                        "content": "Reply with only the bare word READY. Do not use JSON.",
                    }
                ],
            )

            # No near-window generation. Exercise stable tokenizer counts on
            # both sides of admission, including a prompt near the full window.
            near, near_count = sized("near_window_accounting", limit)
            over, over_count = sized("near_window_accounting", config["max_context_tokens"] - 32)
            near_repeat = count("near_window_accounting", near)
            over_repeat = count("near_window_accounting", over)
            facts = {
                "stable_counts": near_count == near_repeat and over_count == over_repeat,
                "near_admitted": near_count + config["max_output_tokens"] + 32
                <= config["max_context_tokens"],
                "over_rejected": over_count + config["max_output_tokens"] + 32
                > config["max_context_tokens"],
            }
            save(
                {
                    "name": "near_window_accounting",
                    "prompt_count": near_count,
                    "over_prompt_count": over_count,
                    "generation_performed": False,
                    **facts,
                    "infrastructure_errors": [key for key, value in facts.items() if not value],
                }
            )
            for name, target in GENERATION_TARGETS.items():
                messages, predicted = sized(name, target, feedback=name == "representative_17k")
                probe(name, messages, FINISH, expected_count=predicted)
            report["passed"] = True
        except (ProviderError, ProbeFailure) as exc:
            report["failure_kind"] = exc.kind if isinstance(exc, ProbeFailure) else "infrastructure"
            report["error"] = str(exc)
            record("error", kind=report["failure_kind"], message=str(exc))
        finally:
            (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
