# LiquidBench

A Python harness for controlled experiments on offline Liquid coding tasks. The research design is in [brief.txt](brief.txt).

The first milestone implements one **development** task: repairing a product-card snippet. The runner gives an agent isolated tools, submits its final files to a separate grader, and saves the grade, trace, patch, token usage, latency, and estimated inference cost. No held-out benchmark or research results are claimed yet.

## Quick start

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), and a running Docker-compatible Linux container engine. Ruby and Node run inside the pinned image; host installations are unnecessary.

```sh
uv sync --frozen
uv run liquidbench build-image
uv run liquidbench doctor
uv run liquidbench validate-task
```

On macOS, a small dedicated Colima VM works:

```sh
brew install colima docker
colima start --profile liquidbench --cpu 2 --memory 2 --disk 10 --vm-type vz
```

The validation command must accept the reference solution and reject the starter plus six intentionally wrong submissions. Its detailed report is saved in `runs/grader-validation.json`. Expected failures are successful grader validation, not benchmark scores.

## Run a real model

The provider speaks the chat-completions HTTP protocol used by Qwen servers. Credentials are read only on the host, through the optional `api_key_env` configuration field. Never put a key into a configuration file or URL.

For a free local smoke test on Apple Silicon:

```sh
brew install llama.cpp
llama-server -hf Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q4_K_M \
  --host 127.0.0.1 --port 8087 --alias liquidbench-smoke \
  --ctx-size 8192 --parallel 1 --threads 4
```

In another terminal:

```sh
uv run liquidbench run --config configs/local-smoke.json
```

This small quantized model is a development smoke test, **not the planned 7B research baseline**. The model download is approximately 1 GB. Stop the server with Ctrl-C when finished. Stop the dedicated VM with `colima stop --profile liquidbench` when it is no longer needed.

For a separately provisioned Qwen 7B endpoint, edit a copy of `configs/qwen-base.json`, then run it with `--config`. That configuration is deliberately marked provisional. Set its checkpoint revision, endpoint, prices, and serving settings before research use. This repository does not provision or purchase GPU instances.

CLI exit codes: `0` passed, `1` model/task failure or failed grader validation, `2` infrastructure/configuration error. A real model failure is a valid captured attempt.

## What runs where

```text
Host Python orchestrator ──HTTP──> model server
         │
         ├── disposable agent container (network disabled)
         │     initial task files + public tool helpers
         │     read / write / search / render / Theme Check
         │
         └── fresh evaluator container (network disabled)
               final file snapshot + host-supplied hidden cases
               core Ruby Liquid + Shopify Theme Check
```

Containers have a read-only root filesystem, an unprivileged user, no Linux capabilities, resource limits, and bounded temporary workspace storage. No host directory, credentials, Docker socket, reference solution, or hidden cases are mounted into the agent container. File paths are constrained; symlinks and non-regular files are rejected. Snapshot data is copied as text, never executed on the host.

The initial command interface deliberately exposes only `render` and `check`, alongside file tools. General shell execution is not implemented. Hidden grading uses a new container and protected lint configuration. Out-of-scope edits and check suppressions fail.

## Task and grading contract

`tasks/dev/product-card/task.json` declares the prompt, editable files, category, difficulty, family, provenance, and supported runtime subset. `initial/` contains the starting files. `evaluator/` contains host-only fixtures and the reference solution; these files are excluded from the runtime image.

The grader requires:

- Only the declared snippet changes; the expected file set is preserved.
- No Theme Check suppression directives or static errors. Warnings remain diagnostic.
- Correct DOM structure and text for 12 cases covering null/empty fields, trimming, availability, escaping, entities, Unicode, and novel values.

HTML quote style and whitespace between elements are unrestricted. Alternative implementations can pass. Grader validation includes unescaped output, missing fallback, always-in-stock output, hardcoded markup, suppressions, and evaluator-configuration edits.

The supported runtime is **Ruby Liquid core**, using strict parsing, variables, and filters, with render resource limits. The product is a supplied hash with nullable title/vendor and boolean availability, not a Shopify object. Shopify-specific semantics such as its `blank` handling are not emulated; the reference uses core `empty` comparison. Theme Check is static evidence, not proof of real storefront behavior.

## Agent protocol and budgets

The same system instruction and loop apply to every model. Each assistant turn returns one JSON action:

```json
{"tool":"read_file","args":{"path":"snippets/product-card.liquid"}}
```

Tools are `list_files`, `read_file`, `write_file`, `search`, `render`, `check`, and `finish`. One surrounding Markdown JSON fence is normalized; extra prose, malformed JSON, and unknown tools are errors. Tool errors consume turns and remain in the trace. The agent must explicitly finish.

Development defaults: 12 turns, 24,000 cumulative reported tokens, 1,024 output tokens per request, 300 seconds, and up to two retries for transient provider failures. Input context is conservatively reserved using UTF-8 byte length plus message overhead before requests; actual input/output usage comes from the provider. A measured token overrun fails before executing its action. This is a development admission estimate, not an exact tokenizer guarantee; calibrate or replace it before controlled research runs. Cached prompt tokens are still counted toward the common allowance. Request and tool output limits bound context growth.

Provider authentication errors are not retried. Transient errors and every retry are logged. Failed requests with unknown usage make total estimated cost unknown; observed usage cost is retained separately. Docker/evaluator faults are infrastructure errors, with zero automatic runtime retries. Budget exhaustion, invalid tool actions, and incorrect code are model failures. Research aggregation must report missing infrastructure runs explicitly.

## Artifacts

Each attempt creates an ignored `runs/<timestamp-id>/` directory containing:

- `result.json`: status, termination, individual checks, task/config fingerprints, Git revision/status, runtime image ID, usage, latency, and cost.
- `trace.jsonl`: initial context, raw model replies, tool results, provider metadata/errors, and completion status.
- `changes.patch` and `final/`: the submitted text changes and final workspace snapshot.
- `task.json`: the visible task manifest.

Unknown pricing yields `null`, not a fabricated zero. Local smoke configuration explicitly uses zero API cost; that excludes electricity and hardware. Do not automatically publish traces: review them for credentials or restricted material first. Run artifacts are ignored by Git.

## Development

```sh
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q -m 'not integration'
LIQUIDBENCH_INTEGRATION=1 uv run pytest -q -m integration
```

CI runs both unit and container integration tests, without model API calls or credentials. Python dependencies are locked by `uv.lock`; Node by `runtime/package-lock.json`; Ruby by `runtime/Gemfile.lock`. Base images are pinned by digest, and each attempt records the exact built image ID. OS packages are resolved when building, so preserve the built image for exact reruns.

```text
src/liquidbench/    runner, provider, sandbox, task contract, grader, CLI
runtime/           pinned container, trusted file/render/lint helpers
tasks/dev/         development fixtures and isolated evaluator assets
configs/           explicit development experiment settings
tests/             grading, accounting, failure, and isolation checks
```

Next milestones: expand to five development tasks, integrate the pinned skill bundle, measure costs, and build a separate held-out set. Skills, fine-tuning, multiple-task aggregation, storefront tests, and a leaderboard are not implemented in this milestone.

## Sources

- [Shopify Liquid engine](https://github.com/Shopify/liquid)
- [Shopify Liquid variations](https://shopify.dev/docs/api/liquid#variations-of-liquid)
- [Theme Check library](https://github.com/Shopify/theme-tools/tree/main/packages/theme-check-common)
- [Qwen serving](https://qwen.readthedocs.io/en/latest/deployment/vllm.html)
- [Qwen local smoke model](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF)
