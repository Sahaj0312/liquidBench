"""Probe an already authorized endpoint; never provision compute or load tasks.

This is a serving diagnostic, not a benchmark attempt or GPU/precision attestation.
Run explicitly with --config and a new --output directory. CI uses HTTP mocks only.
"""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from liquidbench.provider import ChatProvider, ProviderError
from liquidbench.runner import SYSTEM, load_config, parse_action


def messages_for(action, padding=""):
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": padding
            + "\nSynthetic protocol probe, not a coding task. Return exactly this action: "
            + json.dumps(action),
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


def preflight(config, directory):
    if config["token_counting"] != "vllm" or config["response_format"] != "json_object":
        raise ValueError("Preflight requires explicit vllm counting and json_object output")
    provider = ChatProvider(config)
    directory.mkdir(parents=True, exist_ok=False)
    report = {
        "kind": "synthetic_endpoint_preflight",
        "research_result": False,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "checks": [],
        "passed": False,
        "gpu_precision_revision_verified": False,
        "note": "Host evidence and actual sandbox tool execution require separate verification.",
    }
    timeout = config["request_timeout"]
    limit = config["max_context_tokens"] - config["max_output_tokens"] - 32
    finish = {"tool": "finish", "args": {}}

    with (directory / "trace.jsonl").open("x") as trace:

        def record(event, **fields):
            trace.write(json.dumps({"event": event, **fields}) + "\n")
            trace.flush()

        def count(messages):
            start = time.monotonic()
            record("count_request", messages=messages)
            result = provider.count_prompt(messages, timeout)
            record("count_response", count=result, elapsed_seconds=time.monotonic() - start)
            return result

        def probe(name, messages, expected=None):
            predicted = count(messages)
            if predicted > limit:
                raise ValueError("Probe would exceed the configured context reservation")
            record("model_request", name=name, messages=messages, prompt_token_count=predicted)
            start = time.monotonic()
            reply = provider.complete(messages, config["max_output_tokens"], timeout)
            record(
                "model_response",
                name=name,
                **asdict(reply),
                elapsed_seconds=time.monotonic() - start,
            )
            checks = {
                "name": name,
                "prompt_count": predicted,
                "count_delta": reply.input_tokens - predicted,
                "count_agrees": reply.input_tokens == predicted,
                "normal_stop": reply.metadata["finish_reason"] == "stop",
                "served_model_agrees": reply.metadata["served_model"] == config["model"],
                "within_output_limit": 0 < reply.output_tokens <= config["max_output_tokens"],
            }
            try:
                strict_object(reply.content)
                checks["json_object"] = True
            except ValueError:
                checks["json_object"] = False
            if expected is not None:
                try:
                    checks["expected_action"] = parse_action(reply.content) == expected
                except (ValueError, TypeError):
                    checks["expected_action"] = False
            checks["passed"] = all(value for value in checks.values() if type(value) is bool)
            report["checks"].append(checks)
            if not checks["passed"]:
                raise ValueError(f"Failed {name}; inspect trace before running development tasks")

        try:
            read = {"tool": "read_file", "args": {"path": "snippets/probe.liquid"}}
            short = messages_for(read)
            probe("short_action", short, read)
            # Match the harness's assistant-action / user-feedback message roles.
            history = short + [
                {"role": "assistant", "content": json.dumps(read)},
                {
                    "role": "user",
                    "content": json.dumps({"ok": True, "result": "<p>Hello</p>"}),
                },
                {"role": "assistant", "content": '{"tool":"check","args":{}}'},
                {
                    "role": "user",
                    "content": json.dumps({"ok": True, "result": []})
                    + '\nSynthetic probe complete. Return {"tool":"finish","args":{}}.',
                },
            ]
            probe("tool_feedback_roles", history, finish)
            probe(
                "json_enforcement",
                [
                    {
                        "role": "user",
                        "content": "Reply with only the bare word READY. Do not use JSON.",
                    }
                ],
            )
            # Bound tokenizer calls; find a synthetic prompt within 128 tokens of
            # the admission ceiling, leaving the full configured output allowance.
            low, high = 0, config["max_context_tokens"] * 2
            best = None
            for _ in range(16):
                if low > high:
                    break
                middle = (low + high) // 2
                messages = messages_for(finish, " filler" * middle)
                predicted = count(messages)
                if predicted <= limit:
                    best = (messages, predicted)
                    low = middle + 1
                else:
                    high = middle - 1
            if best is None or best[1] < limit - 128:
                raise ValueError("Could not construct a near-window prompt")
            probe("near_window", best[0], finish)
            report["passed"] = True
        except (ProviderError, ValueError) as exc:
            report["error"] = str(exc)
            record("error", message=str(exc))
        finally:
            (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = preflight(load_config(args.config), args.output)
    print(json.dumps({"passed": report["passed"], "artifacts": str(args.output)}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
