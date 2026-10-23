# LiquidBench

A Python harness for controlled experiments on offline Liquid coding tasks. The research design is in [brief.txt](brief.txt).

Milestone 2 implements five **development** tasks and a modular grader. The runner gives an agent isolated tools, submits its final files to a separate grader, and saves the grade, trace, patch, token usage, latency, and estimated inference cost. No held-out benchmark or research results are claimed yet.

| Task | Required repair | Grading evidence |
| --- | --- | --- |
| `product-card` | Product title/vendor fallbacks, availability, escaping | Strict core Liquid renders and DOM checks |
| `shipping-message` | Conditional priority, threshold boundaries, false/null values, message fallback | Strict core Liquid renders and DOM checks |
| `section-schema` | Settings IDs/types/defaults, range limits, preset values | Parsed schema, strict JSON, declared contract, unchanged surrounding markup |
| `asset-references` | Stylesheet filename and two translation keys | Live Liquid AST, protected asset/locale resolution, preserved structure |
| `announcement-subtitle` | Add an optional subtitle while preserving existing section behavior | Unchanged schema, rendered DOM, enabled/show-body controls, escaping |

## Quick start

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), and a running Docker-compatible Linux container engine. Ruby and Node run inside the pinned image; host installations are unnecessary.

```sh
uv sync --frozen
uv run liquidbench build-image
uv run liquidbench doctor
uv run liquidbench validate-task
uv run liquidbench validate-suite
```

On macOS, a small dedicated Colima VM works:

```sh
brew install colima docker
colima start --profile liquidbench --cpu 2 --memory 2 --disk 10 --vm-type vz
```

`validate-task` defaults to product-card; select another fixture with `--task tasks/dev/shipping-message`. `validate-suite` checks every task under `tasks/dev` and writes `runs/validation-suite.json`. The suite contains 71 candidate submissions: five failing starters, five passing references, four alternative valid implementations, and 57 deliberately incorrect solutions. All 71 verdicts must match their expectations. Expected failures are successful grader validation, not benchmark scores.

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
# A single new task:
uv run liquidbench run --task tasks/dev/shipping-message --config configs/local-smoke.json
# One attempt on each development task:
uv run liquidbench run-suite --config configs/local-smoke.json
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
         │     read / write / search / analyze / render / Theme Check
         │
         └── fresh evaluator container (network disabled)
               final file snapshot + host-supplied hidden cases
               core Ruby Liquid + Shopify Theme Check
```

Containers have a read-only root filesystem, an unprivileged user, no Linux capabilities, resource limits, and bounded temporary workspace storage. No host directory, credentials, Docker socket, reference solution, or hidden cases are mounted into the agent container. File paths are constrained; symlinks and non-regular files are rejected. Snapshot data is copied as text, never executed on the host.

The command interface exposes `analyze`, `render`, and `check`, alongside file tools. General shell execution is not implemented. Hidden grading uses a new container and protected lint configuration. Out-of-scope edits and check suppressions fail. The public analyzer reads only workspace files; it has no access to evaluator data.

## Task and grading contract

Each `tasks/dev/<task>/task.json` declares the prompt, editable files, category, difficulty, family, provenance, supported runtime subset, and versioned `evaluator`. `initial/` contains the starting files. `evaluator/` contains host-only cases, a `reference/` tree of replacement files, and declarative `validation.json` mutations; these files are excluded from the runtime image and model context. These are repository-visible development fixtures, not secret held-out data. Their isolation is from the benchmark agent, not from repository readers.

The manifest selects a versioned evaluator from the explicit registry in `src/liquidbench/evaluators/__init__.py`. An evaluator implements `evaluate(task, files, sandbox)` and returns nonempty, uniquely named boolean checks. Adding a task does not require new branches in `grading.py`. Task data cannot import or execute Python code. The shared grader requires:

- Only declared files change; the expected file set is preserved.
- No Theme Check suppression directives or static errors. Warnings remain diagnostic.
- Every task-specific check passes. Success remains binary; there is no partial-credit score.

HTML quote style and whitespace between elements are unrestricted for rendered tasks. Alternative implementations can pass. Validation covers null/empty values, boolean controls, threshold boundaries, escaping, entities, Unicode, and novel values. Adversarial submissions include hardcoding, comment/raw/dead-branch decoys, duplicate JSON keys and setting IDs, boolean-as-number defaults, incorrect presets, missing outputs, protected-file edits, and check suppressions. Accepted alternatives include reordered schema settings, the `translate` alias, and different Liquid branches.

The supported rendering runtime is **Ruby Liquid core**, using strict parsing, variables, and filters, with render resource limits. Inputs are supplied hashes, not Shopify objects. Shopify-specific semantics such as its `blank` handling are not emulated; references use core `empty` comparison. `render` with `strip_schema:true` removes exactly one AST-verified top-level schema block before rendering the section body. It does not simulate section lifecycle, schema defaults, or the theme editor.

Schema grading checks the task's explicit text/checkbox/range contract; it is not a general Shopify schema validator. Asset/translation grading checks literal references and preserved AST structure against protected fixtures; it does not emulate CDN URLs or translation filters. This task deliberately permits only three literal repairs, not arbitrary equivalent rewrites. Theme Check is static evidence, not proof of real storefront behavior.

To author another development task, add its manifest, initial files, hidden `cases.json`, reference replacement tree, and `validation.json`. Each validation entry has `name`, boolean `expected_pass`, and `changes` mapping paths to full replacement text (or `null` for deletion), applied to the reference snapshot. Starter/reference candidates are generated automatically. Supply at least two incorrect candidates, plus edge cases and valid alternatives; implement/register a trusted evaluator if needed, add integration coverage, and run `validate-suite`. The task fingerprint includes all fixture and validation data; the source fingerprint includes nested evaluator modules.

## Agent protocol and budgets

The same system instruction and loop apply to every model. Each assistant turn returns one JSON action:

```json
{"tool":"read_file","args":{"path":"snippets/product-card.liquid"}}
```

Tools are `list_files`, `read_file`, `write_file`, `search`, `analyze`, `render`, `check`, and `finish`. One surrounding Markdown JSON fence is normalized; extra prose, malformed JSON, and unknown tools are errors. Tool errors consume turns and remain in the trace. The agent must explicitly finish.

Development defaults: 12 turns, 24,000 cumulative reported tokens, 1,024 output tokens per request, 300 seconds, and up to two retries for transient provider failures. Input context is conservatively reserved using UTF-8 byte length plus message overhead before requests; actual input/output usage comes from the provider. A measured token overrun fails before executing its action. This is a development admission estimate, not an exact tokenizer guarantee; calibrate or replace it before controlled research runs. Cached prompt tokens are still counted toward the common allowance. Request and tool output limits bound context growth.

Provider authentication errors are not retried. Transient errors and every retry are logged. Failed requests with unknown usage make total estimated cost unknown; observed usage cost is retained separately. Docker/evaluator faults are infrastructure errors, with zero automatic runtime retries. Budget exhaustion, invalid tool actions, and incorrect code are model failures. Research aggregation must report missing infrastructure runs explicitly.

## Artifacts

Each attempt creates an ignored `runs/<timestamp-id>/` directory containing:

- `result.json`: status, termination, individual checks, task/config fingerprints, Git revision/status, runtime image ID, usage, latency, and cost.
- `trace.jsonl`: initial context, raw model replies, tool results, provider metadata/errors, and completion status.
- `changes.patch` and `final/`: the submitted text changes and final workspace snapshot.
- `task.json`: the visible task manifest.

Unknown pricing yields `null`, not a fabricated zero. Local smoke configuration explicitly uses zero API cost; that excludes electricity and hardware. Do not automatically publish traces: review them for credentials or restricted material first. Run artifacts are ignored by Git.

`run-suite` runs tasks sequentially against one immutable runtime image ID. Its `runs/suite-<timestamp-id>/summary.json` links individual attempts and counts passes, model failures, and infrastructure errors separately. It is marked `development` and `research_result: false`; this is pipeline bookkeeping, not a leaderboard.

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

Milestone 2 verification: 139 tests passed locally (54 unit and 85 container integration), including all 71 candidate verdicts, successful scripted-reference end-to-end runs for every task, and hidden-data isolation checks. A free Qwen2.5-Coder-1.5B Q4_K_M `run-suite` smoke completed all five real-model attempts: zero passed, five failed, zero infrastructure errors. Two attempts finished with invalid submissions and three exhausted the turn budget. These small-model development attempts are not research scores; successful scripted-reference runs are harness tests, not model results.

Recommended next step: audit the failed local traces and calibrate the action protocol and budgets, then freeze the development task/evaluator versions before controlled model comparisons. Skills integration, post-training, held-out tasks, real storefront tests, and a leaderboard remain outside this milestone.

## Sources

- [Shopify Liquid engine](https://github.com/Shopify/liquid)
- [Shopify Liquid variations](https://shopify.dev/docs/api/liquid#variations-of-liquid)
- [Theme Check library](https://github.com/Shopify/theme-tools/tree/main/packages/theme-check-common)
- [Shopify section schema](https://shopify.dev/docs/storefronts/themes/architecture/sections/section-schema)
- [Shopify input settings](https://shopify.dev/docs/storefronts/themes/architecture/settings/input-settings)
- [Shopify asset_url filter](https://shopify.dev/docs/api/liquid/filters/asset_url)
- [Shopify translate filter](https://shopify.dev/docs/api/liquid/filters/translate)
- [Qwen serving](https://qwen.readthedocs.io/en/latest/deployment/vllm.html)
- [Qwen local smoke model](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF)
