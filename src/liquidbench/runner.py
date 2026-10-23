"""Bounded agent loop and durable per-attempt artifacts."""

from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from .grading import grade
from .provider import ChatProvider, ProviderError
from .sandbox import InfrastructureError, Sandbox, ToolError, image_id
from .task import fingerprint, safe_name

SYSTEM = """You are a coding agent operating on an isolated Liquid task workspace.
Reply with exactly one JSON object per turn. No markdown or prose outside JSON.
Format: {"tool":"TOOL_NAME","args":{...}}
Available tools:
list_files: args {}
read_file: args {"path":"relative/path"}
write_file: args {"path":"relative/path","content":"complete file content"}
search: args {"text":"literal substring"}
render: args {"path":"relative/path.liquid","variables":{...},"strip_schema":false}
  For section bodies, set strip_schema:true to remove one top-level schema block.
analyze: args {"path":"relative/path.liquid"} (static AST and schema extraction)
check: args {} (runs Shopify Theme Check)
finish: args {} (submit final files)
Paths must remain within the workspace. No network or package installation.
Only the task's declared files may change. Hidden grading is unavailable.
Tool errors consume the same budget as successful calls. Finish explicitly when done."""
TOOLS = {"list_files", "read_file", "write_file", "search", "render", "analyze", "check", "finish"}


def parse_action(content):
    # Normalize a single Markdown wrapper, never repair the JSON or tool arguments.
    fenced = re.fullmatch(r"\s*```(?:json)?\s*\n(.*?)\n```\s*", content, re.DOTALL)
    if fenced:
        content = fenced.group(1)
    action = json.loads(content)
    if (
        not isinstance(action, dict)
        or set(action) != {"tool", "args"}
        or action["tool"] not in TOOLS
        or not isinstance(action["args"], dict)
    ):
        raise ValueError('Expected exactly {"tool": an available tool, "args": an object}')
    return action


def load_config(path):
    config = json.loads(Path(path).read_text())
    required = {
        "endpoint",
        "model",
        "model_revision",
        "image",
        "temperature",
        "top_p",
        "seed",
        "max_turns",
        "max_total_tokens",
        "max_output_tokens",
        "max_seconds",
        "request_timeout",
        "provider_retries",
        "input_usd_per_million",
        "output_usd_per_million",
        "purpose",
    }
    if required - config.keys():
        raise ValueError(f"Missing config fields: {sorted(required - config.keys())}")
    if set(config) - (required | {"api_key_env"}):
        raise ValueError("Unknown config fields; credentials belong in environment variables")
    for key in ("max_turns", "max_total_tokens", "max_output_tokens"):
        if type(config[key]) is not int or config[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    if (
        type(config["provider_retries"]) is not int
        or config["provider_retries"] < 0
        or config["max_seconds"] <= 0
        or config["request_timeout"] <= 0
    ):
        raise ValueError("Invalid time or retry limits")
    if not 0 <= config["temperature"] <= 2 or not 0 < config["top_p"] <= 1:
        raise ValueError("Invalid decoding settings")
    for key in ("input_usd_per_million", "output_usd_per_million"):
        if config[key] is not None and config[key] < 0:
            raise ValueError("Prices must be nonnegative or null")
    ChatProvider(config)  # Validate endpoint before creating any resources.
    return config


def prompt_reservation(messages):
    # Conservative estimate for byte-level tokenizers, not an exact token count.
    # A measured overrun fails the attempt and is explicitly reported.
    return 512 + sum(len(m["content"].encode()) + 128 for m in messages)


def source_version():
    def git(*args):
        result = subprocess.run(["git", *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    source_root = Path(__file__).parent
    sources = {
        str(path.relative_to(source_root)): path.read_text() for path in source_root.rglob("*.py")
    }
    return {
        "git_commit": git("rev-parse", "HEAD"),
        "git_status": git("status", "--porcelain"),
        "python_source_digest": fingerprint(sources),
        "python_version": sys.version,
    }


def patch(initial, final):
    output = []
    for path in sorted(set(initial) | set(final)):
        if initial.get(path) == final.get(path):
            continue
        output.extend(
            difflib.unified_diff(
                initial.get(path, "").splitlines(keepends=True),
                final.get(path, "").splitlines(keepends=True),
                fromfile="a/" + path if path in initial else "/dev/null",
                tofile="b/" + path if path in final else "/dev/null",
            )
        )
    return "".join(output)


def run(
    task,
    config,
    output_root,
    *,
    provider=None,
    sandbox_factory=Sandbox,
    grader=grade,
    resolve_image=image_id,
):
    provider = provider or ChatProvider(config)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    destination = Path(output_root).resolve() / run_id
    destination.mkdir(parents=True, exist_ok=False)
    result = {
        "schema_version": 1,
        "run_id": run_id,
        "task_id": task.manifest["id"],
        "task_version": task.manifest["version"],
        "task_digest": task.digest,
        "split": task.manifest["split"],
        "config": config,
        "config_digest": fingerprint(config),
        "source": source_version(),
        "status": "infrastructure_error",
        "termination": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "model_calls": 0,
        "tool_calls": 0,
        "provider_errors": [],
        "usage_incomplete": False,
        "estimated_cost_usd": None,
        "snapshot_captured": False,
    }
    start = time.monotonic()
    files = dict(task.initial)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": task.manifest["prompt"]},
    ]
    (destination / "task.json").write_text(json.dumps(task.manifest, indent=2) + "\n")
    with (destination / "trace.jsonl").open("w") as trace:

        def event(kind, **fields):
            trace.write(
                json.dumps(
                    {"event": kind, "elapsed_seconds": time.monotonic() - start, **fields},
                    ensure_ascii=False,
                )
                + "\n"
            )
            trace.flush()

        event("initial_context", messages=messages)
        try:
            image = resolve_image(config["image"])
            result["image_id"] = image
            with sandbox_factory(image, task.initial) as sandbox:
                snapshot_failure = None
                try:
                    reason = "turn_budget"
                    for turn in range(config["max_turns"]):
                        remaining_time = config["max_seconds"] - (time.monotonic() - start)
                        if remaining_time <= 0:
                            reason = "time_budget"
                            break
                        used = result["input_tokens"] + result["output_tokens"]
                        reserved_input = prompt_reservation(messages)
                        allowance = min(
                            config["max_output_tokens"],
                            config["max_total_tokens"] - used - reserved_input,
                        )
                        if allowance <= 0:
                            reason = "token_budget"
                            break
                        for retry in range(config["provider_retries"] + 1):
                            timeout = min(
                                config["request_timeout"],
                                config["max_seconds"] - (time.monotonic() - start),
                            )
                            if timeout <= 0:
                                raise ProviderError(
                                    "Attempt deadline reached during provider retries"
                                )
                            event(
                                "model_request",
                                turn=turn,
                                retry=retry,
                                max_tokens=allowance,
                                input_reservation=reserved_input,
                            )
                            result["model_calls"] += 1
                            try:
                                reply = provider.complete(messages, allowance, timeout)
                                break
                            except ProviderError as exc:
                                result["provider_errors"].append(str(exc))
                                result["usage_incomplete"] = True
                                event("provider_error", error=str(exc), retryable=exc.retryable)
                                if not exc.retryable or retry == config["provider_retries"]:
                                    raise
                        result["input_tokens"] += reply.input_tokens
                        result["output_tokens"] += reply.output_tokens
                        event(
                            "model_response",
                            content=reply.content,
                            input_tokens=reply.input_tokens,
                            output_tokens=reply.output_tokens,
                            metadata=reply.metadata,
                        )
                        messages.append({"role": "assistant", "content": reply.content})
                        if (
                            result["input_tokens"] + result["output_tokens"]
                            > config["max_total_tokens"]
                        ):
                            reason = "token_budget_overrun"
                            break
                        if time.monotonic() - start >= config["max_seconds"]:
                            reason = "time_budget"
                            break
                        result["tool_calls"] += 1
                        try:
                            action = parse_action(reply.content)
                            if action["tool"] == "finish":
                                reason = "finished"
                                event("finish")
                                break
                            response = sandbox.call(action["tool"], action["args"])
                            tool_result = {"ok": True, "result": response}
                        except (ValueError, KeyError, TypeError, ToolError) as exc:
                            tool_result = {"ok": False, "error": str(exc)[:1000]}
                        # Bound context growth without losing the full result in the trace.
                        event("tool_result", **tool_result)
                        text = json.dumps(tool_result, ensure_ascii=False)
                        if len(text) > 16000:
                            text = json.dumps({"truncated": True, "preview": text[:16000]})
                        messages.append({"role": "user", "content": "Tool result: " + text})
                finally:
                    try:
                        files = sandbox.snapshot()
                        result["snapshot_captured"] = True
                    except (ToolError, InfrastructureError) as exc:
                        snapshot_failure = exc
                        event("snapshot_error", error=str(exc))
            if snapshot_failure:
                raise snapshot_failure
            result["termination"] = reason
            result["grade"] = grader(task, files, image)
            result["status"] = (
                "passed" if reason == "finished" and result["grade"]["passed"] else "failed"
            )
        except ToolError as exc:
            result["status"] = "failed"
            result["termination"] = "invalid_workspace"
            result["error"] = str(exc)
            event("invalid_workspace", error=str(exc))
        except InfrastructureError as exc:
            result["termination"] = "infrastructure_error"
            result["error"] = str(exc)
            event("infrastructure_error", error=str(exc))
        finally:
            result["elapsed_seconds"] = time.monotonic() - start
            rates = (config["input_usd_per_million"], config["output_usd_per_million"])
            if all(rate is not None for rate in rates):
                result["known_usage_cost_usd"] = (
                    result["input_tokens"] * rates[0] + result["output_tokens"] * rates[1]
                ) / 1_000_000
                if not result["usage_incomplete"]:
                    result["estimated_cost_usd"] = result["known_usage_cost_usd"]
            if result["snapshot_captured"]:
                for name, content in files.items():
                    if not safe_name(name):
                        raise ValueError("Unsafe snapshot path")
                    target = destination / "final" / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content)
                (destination / "changes.patch").write_text(patch(task.initial, files))
            (destination / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            event("completed", status=result["status"], termination=result["termination"])
    return destination, result
