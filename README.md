# LiquidBench

A Python harness for controlled experiments on offline Liquid coding tasks. The research design is in [brief.txt](brief.txt).

LiquidBench implements 20 **development** tasks, a modular grader, and an agent protocol with explicit context accounting. The runner gives an agent isolated tools, submits its final files to a separate grader, and saves the grade, trace, patch, token usage, latency, and estimated inference cost. No held-out benchmark or research results are claimed yet. The [7B pilot](docs/calibration/milestone-4-results.md) passed 2/5 tasks. The completed [Milestone 5 paired experiment](docs/calibration/milestone-5-results.md) scored **2/5 baseline versus 0/5 with full pinned skills**, using 9.07× as many treatment tokens. All ten attempts and cleanup evidence are preserved; post-training has not begun.

The original five tasks are below; the [Milestone 6 catalog and frozen loading study](docs/calibration/milestone-6-plan.md) lists all 20, exact token feasibility, repetitions and compute scenarios. [All 240 Milestone 6 attempts are complete](docs/calibration/milestone-6-results.md), with verified GPU/storage cleanup. Further paid execution requires fresh approval.

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

`validate-task` defaults to product-card; select another fixture with `--task tasks/dev/shipping-message`. `validate-suite` checks every task under `tasks/dev` and writes `runs/validation-suite.json`. The expanded suite contains 236 candidate submissions: 20 failing starters, 20 passing references, 19 alternative valid implementations, and 177 deliberately incorrect solutions. All 236 verdicts must match their expectations; the original 71 remain unchanged. Expected failures are successful grader validation, not benchmark scores.

## Run a real model

The provider speaks the chat-completions HTTP protocol used by Qwen servers. Credentials are read only on the host, through the optional `api_key_env` configuration field. Never put a key into a configuration file or URL.

For a free local smoke test on Apple Silicon:

```sh
brew install llama.cpp
llama-server -hf Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q4_K_M \
  --host 127.0.0.1 --port 8087 --alias liquidbench-smoke \
  --ctx-size 8192 --parallel 1 --threads 4 --no-context-shift
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

For the next approved Qwen 7B deployment, follow the [Milestone 5 preflight/runbook](docs/calibration/preflight-v2.md), including host evidence, before the paired run. The [8K pilot runbook](docs/calibration/qwen-7b-pilot.md) is historical; current preflight v2 requires room for its fixed 17K generation probe plus output reservation. The completed [Milestone 4 pilot](docs/calibration/milestone-4-results.md) verified the pinned BF16/vLLM deployment on an A40 and passed **2/5 development tasks**, with exact token-count agreement and no protocol or infrastructure errors. The GPU was terminated after evidence export. The [preparation report](docs/calibration/milestone-4.md) remains a historical planning record. This repository does not automatically provision or purchase GPU instances.

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

The calibrated configurations set `response_format: "json_object"` for server-enforced JSON syntax. This is model-agnostic and contains no task-specific schema. Tool names, arguments, edits and grading remain strictly validated. Use explicit `"text"` only to reproduce unconstrained experiments; an unsupported JSON mode fails without silently falling back.

Development defaults: 12 turns, 24,000 cumulative reported tokens, 1,024 output tokens per request, 300 seconds, and up to two retries for transient provider failures. Each request must separately fit an 8,192-token context, including the output reservation. The cumulative budget counts all repeated/cached input across turns; it is not a context-window size.

Configurations require `max_context_tokens` and `token_counting`: `llama_cpp` counts the server's templated prompt via `/apply-template` and `/tokenize`; `vllm` uses chat `/tokenize`. Both reserve an additional 32 tokens and check reported usage before executing actions. Counting failures or count overruns are infrastructure failures. Overfull history stops with `context_budget`; history is never silently shortened. `conservative_bytes` is an explicit approximate fallback, unsuitable for exact controlled comparisons. The server's actual context must match configuration; disable automatic context shifting.

Argument names/types are validated. Render failures return `ok:false`, with public recovery guidance for schema-flag misuse and repeated failures. Output-length stops never execute truncated actions. Results record protocol errors, tool errors and output truncations separately; these errors consume the normal budget.

Provider authentication errors are not retried. Transient errors and every retry are logged. Failed requests with unknown usage make total estimated cost unknown; observed usage cost is retained separately. Docker/evaluator faults are infrastructure errors, with zero automatic runtime retries. Budget exhaustion, invalid tool actions, and incorrect code are model failures. Research aggregation must report missing infrastructure runs explicitly.

## Artifacts

Each attempt creates an ignored `runs/<timestamp-id>/` directory containing:

- `result.json`: status, termination, individual checks, task/config fingerprints, Git revision/status, runtime image ID, usage, latency, and cost.
- `trace.jsonl`: initial context, raw model replies, tool results, provider metadata/errors, and completion status.
- `changes.patch` and `final/`: the submitted text changes and final workspace snapshot.
- `task.json`: the visible task manifest.

Unknown pricing yields `null`, not a fabricated zero. Local smoke configuration explicitly uses zero API cost; that excludes electricity and hardware. Do not automatically publish traces: review them for credentials or restricted material first. Run artifacts are ignored by Git.

`run-suite` runs tasks sequentially against one immutable runtime image ID. Its `runs/suite-<timestamp-id>/summary.json` links individual attempts and counts passes, model failures, and infrastructure errors separately. It is marked `development` and `research_result: false`; this is pipeline bookkeeping, not a leaderboard.

## Optional skills and paired development experiment

The optional `skills` config field names a pinned manifest, local checkout and full Git revision; null or absent disables access. Ben Sehl's complete three entry instructions are injected unchanged, and fourteen references are available through existing `read_file` calls. The baseline cannot load or read them. Documents remain outside agent/evaluator containers and final task snapshots. `list_files` includes document paths in the treatment; search and development tools retain their task-file scope. Protocol v5 explains this identically to both conditions; task prompts and graders are unchanged.

There is no license/redistribution grant in the pinned upstream snapshot, so content is fetched into an ignored local checkout, not vendored. Full treatment traces also remain local. The loader verifies Git revision, inventory, file hashes and pinned Git object contents. `skill_accesses` records injected entries, explicit reads and the first completed model call that received each document. Reference text is never silently shortened; it counts against context and cumulative usage on every request.

```sh
uv run python scripts/prepare_skills.py
uv run --with transformers==5.19.0 --with tokenizers==0.23.3 --with jinja2==3.1.6 python scripts/measure_skills.py
uv run python scripts/run_skills_ab.py  # dry plan only
```

All three entries require **9,457 raw tokens**, exceeding the pilot's 8K context. Both paired conditions used the approved 32K context and 393,216-token cumulative ceiling, retaining 12 turns and all other execution/decoding limits. After an [aborted original preflight](docs/calibration/milestone-5-preflight.md), a separately approved session passed [preflight v2](docs/calibration/preflight-v2.md) and completed all ten attempts. See the [full comparison and evidence](docs/calibration/milestone-5-results.md): baseline 2/5, skills 0/5, no on-demand reference reads. The GPU was deleted. Further paid runs require approval. Milestone 6 adds 15 development tasks and two loading controls; no fine-tuning, training data or leaderboard is implemented.

## Milestone 6 loading study

`configs/m6-{base,full,on_demand,neutral}.json` share all model and execution settings. Full loading preserves the original bundle; on-demand exposes an 85-token index and charges complete document reads to normal budgets. Neutral context is a hash-pinned, unrelated 9,815-token message, exactly matching full-bundle initial overhead. Baseline and neutral cannot access skills. The upstream documents remain unchanged and unvendored.

The [predeclared study](docs/calibration/milestone-6-plan.md) completed 20 tasks × four conditions × three fixed-seed repetitions, preserving Block 0 and all later attempts. The [complete comparison](docs/calibration/milestone-6-results.md) reports baseline **24/60**, full **5/60**, on-demand **23/60**, neutral **6/60**, with paired counts by category/difficulty and complete token/behavior metadata. Full used 4.59× baseline tokens; on-demand made no skill-document reads. Repetitions are reproducibility checks, not independent research samples. All billable resources were deleted; no fine-tuning was started. `scripts/run_loading_study.py` still prints a dry plan by default; any future paid execution requires fresh approval. `scripts/analyze_loading_study.py` reproduces the core paired comparisons from private evidence.

## Diagnostic v1 (complete)

A frozen four-condition pilot (`original`, `clarified`, `reference`, `neutral`) tests whether Milestone 6's skills result reflects the model's Liquid ability, the tool instructions, or the loading strategy. It covers 5 balanced tasks, 4 position-balanced repetitions and 80 attempts. The relevant upstream reference is selected only from the public prompt and a heading index, then delivered in full. The neutral control matches it exactly in tokens. See the [plan, controls, cost and validity concerns](docs/diagnostic/plan.md) and the [benchmark audit](docs/diagnostic/benchmark-audit.md). All 80 attempts ran in one A40 session (about $0.49 estimated, resources deleted and verified). [Results](docs/diagnostic/results.md): original **8/20**, clarified 4/20, reference 4/20, neutral 0/20, deterministic across repetitions. Any context placed before the task cut read-before-write from 20/20 to 4–8/20. Relevant content beat equal-length noise (4–0) but not no context. Three tasks failed in every arm. Milestone 6 is unchanged. No fine-tuning started.

## Development

```sh
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
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

Milestone 3 adds trace-based failure reporting, backend prompt counting, clearer tool instructions/error feedback, and a reproducible comparison script. Run `uv run python scripts/analyze_runs.py before=runs/<suite> after=runs/<suite>` to summarize saved attempts without calling a model or loading hidden evaluator data. Full calibration results and remaining readiness gates are in the [failure report](docs/calibration/milestone-3.md). Skills integration, post-training, held-out tasks, real storefront tests, and a leaderboard remain outside this milestone.

The final local JSON-mode suites completed with zero protocol/tool/infrastructure errors for both Qwen 1.5B and 3B, but each passed 0/5 tasks due to incorrect code. The 1.5B token total fell from 45,640 to 9,136 as failure loops disappeared and submissions finished earlier. This supports a 7B development pilot, not research-readiness or a task-solving claim. All intermediate calibration attempts are reported; budgets and graders were unchanged.

Milestone 3 validation: **161 tests passed** (76 unit, 85 container integration), including all 71 unchanged grader verdicts. Lint and formatting also passed.

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
