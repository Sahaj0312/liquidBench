# Milestone 4: Qwen 7B development pilot preparation

**Status: prepared, not run. Actual spending: $0.** Checked October 22, 2026
(Toronto; October 23 UTC). The user confirmed that no GPU host or endpoint is
available and requested preparation and a cost estimate only. No compute was
rented, no inference purchased, and no 7B model response was generated.

The 8 GiB Apple M1 cannot host the requested BF16 deployment. No NVIDIA/vLLM
runtime or local serving endpoint was available. A read-only attempt to inspect
an existing cloud account failed with expired/invalid authorization; it did not
establish an available GPU. No cloud services or billing were enabled.

## What is ready

- [Deployment manifest](qwen-7b-pilot.json): immutable model and tokenizer
  revisions, linux/amd64 container digest, candidate serving arguments, frozen
  task/config/source trees, hardware requirements and cost assumptions. Observed
  GPU, serving configuration, preflight and suite fields remain `null`.
- [Execution runbook](qwen-7b-pilot.md): host evidence, endpoint preflight, one
  sequential five-task attempt, artifact retention, analysis and shutdown.
- [Endpoint preflight](../../scripts/preflight_endpoint.py): uses the existing
  provider and action parser on synthetic messages. Checks strict JSON objects,
  action envelopes, tool-feedback message roles, model ID, termination and exact
  token-count agreement on short and near-window prompts. It saves request/reply
  evidence and stops on a failure. HTTP-mocked tests incur no inference charges.

Nothing in `src/`, `runtime/`, `tasks/` or `configs/` changed. Protocol
`json-actions-v4`, all grading criteria and the calibrated budgets remain frozen.
The new script is optional serving preparation; it does not run inside a
benchmark attempt or access task/evaluator files.

## Deployment and cost proposal

Use the pinned Qwen checkpoint with BF16 weights, one sequence and an 8,192-token
context. The candidate server is **vLLM 0.32.0**, pinned by its linux/amd64 image
manifest, with CUDA **13.0.2** from that image's configuration. Registry metadata
was inspected without pulling its approximately 9.21 GB of compressed layers.
The runtime has **not** been exercised on a GPU. Choose an Ampere-or-newer GPU
and a driver from branch 580 or newer, then verify actual startup and BF16 support.
[vLLM release](https://github.com/vllm-project/vllm/releases/tag/v0.32.0),
[GPU installation](https://docs.vllm.ai/en/v0.32.0/getting_started/installation/gpu/),
[NVIDIA driver compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html).

Weights alone need approximately 15.23 GB; one 8K BF16 KV cache needs 0.47 GB.
Runtime allocations, graph capture and compilation are additional. A 24 GB GPU
is a planning minimum, not a tested fit. Prefer one **A40 48 GB**, about 48 GB
host RAM and **100 GB disk** for image extraction, weights, caches and logs.
Actual RAM/disk consumption and throughput must be measured.

Published Runpod Pod rates, checked October 23 UTC:

| Candidate | VRAM | Compute/hour | Two hours compute |
| --- | --- | --- | --- |
| RTX A5000 | 24 GB | $0.27 | $0.54 |
| A40 (preferred) | 48 GB | $0.59 | $1.18 |
| RTX 4090 | 24 GB | $0.89 | $1.78 |

These are advertised rates, not reserved capacity or a verified checkout quote.
Region, host driver, image compatibility and availability remain unverified.
[Runpod pricing](https://www.runpod.io/pricing).

At $0.10/GB/month, 100 GB temporary container storage for two hours is about
$0.028 using a 720-hour month. **A40 estimate: $1.21 before tax**. Retained volume
storage can continue billing after a Pod stops; copy artifacts out and terminate
the rental and unwanted storage. Verify any egress fees, minimum top-up and taxes
at checkout; a deposit is cash committed, even if it is not consumed compute.
[Runpod storage and billing](https://docs.runpod.io/pods/pricing).

A concrete future approval would cover **one two-hour A40 session, at most $3
all-in**, conditional on a checkout quote fitting that cap and the hardware
requirements. No approval has been requested or granted for this purchase. If a
deposit or required configuration exceeds the cap, present the revised total
before buying. The $50 GPU allocation and $100 experimental planning ceiling
are ceilings, not permission to spend. Do not extend the rental automatically.

Two hours is a planning window for downloads, loading, compilation, preflight,
the five attempts and artifact export. Five 300-second agent budgets alone allow
25 minutes; initialization, final grading and in-flight requests add overhead.
No 7B throughput or completion-time guarantee is available yet. Hourly rental
must be costed from billed wall time; the harness's unknown token prices remain
`null`, and must not be relabeled as zero-dollar inference.

## Comparison and failure evidence

The prior final JSON-mode suites are retained in [metrics.json](metrics.json),
including per-task trace/patch hashes and action line numbers. They are Q4_K_M
llama.cpp runs, so a future BF16 vLLM comparison changes model size, precision and
backend together. It is a development diagnostic, not a controlled size effect.

| Final configuration | Attempts | Passes | Protocol/tool errors | Input/output tokens | Calls | Summed attempt time | Termination |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen 1.5B Q4_K_M | 5 | 0/5 | 0 / 0 | 8,140 / 996 | 11 | 38.99 s | finished ×5 |
| Qwen 3B Q4_K_M | 5 | 0/5 | 0 / 0 | 10,593 / 1,185 | 13 | 80.09 s | finished ×5 |
| Qwen 7B BF16 | **0** | **not measured** | not measured | not measured | 0 | not measured | not run: no compute |

Both prior suites had zero infrastructure errors. The 7B row is missing data,
not a 0/5 score. No 7B patches, latency, usage or failure explanations exist.

| Task | Prior 1.5B failure | Prior 3B failure | 7B |
| --- | --- | --- | --- |
| product-card | Rendered, then saved hardcoded output | Invented Liquid filters/ternary syntax | Not run |
| shipping-message | Replaced logic with English instructions in HTML | Added strip/escape but left broken conditions | Not run |
| section-schema | Invalid schema and removed surrounding markup | Repaired schema but deleted required markup | Not run |
| asset-references | Wrote JSON into the Liquid file | Repaired only one translation reference | Not run |
| announcement-subtitle | Used Handlebars and removed schema | Wrong placement and nonexistent `strip_whitespace` | Not run |

These diagnoses and supporting trace lines are in the
[Milestone 3 report](milestone-3.md). Neither final local model used `check`;
1.5B read no files, and 3B read only three tasks. This leaves instruction following,
incomplete repairs and Liquid knowledge as useful hypotheses for the 7B pilot.
It does not establish that 7B will share those failures.

For each future 7B attempt, report the exact read/write/analyze/render/check/finish
sequence, whether tool diagnostics were acted on, changed files, first decisive
error, final grader verdict and trace/patch line evidence. Separate unsupported
syntax/filters (knowledge), incomplete conditional fixes (reasoning), ignored
preservation constraints (instruction following), malformed actions (protocol),
and server/counting/sandbox faults (infrastructure). Budget termination alone
does not prove a budget is too small. A failed hidden check is analyzed by the
host after the attempt; never feed hidden cases back to the agent.

## Research gate and proposed next milestone

**Ready for an approved 7B development deployment; not ready to start the
four-configuration research comparison.** Live JSON enforcement, token counts,
BF16 operation, model revision and full tool use remain unverified. A successful
synthetic preflight is necessary evidence, not certification of coding ability
or proof that the advertised GPU loaded the pinned checkpoint.

First collect one attempt per task after deployment checks pass. Keep model
failures and infrastructure failures visible; do not selectively rerun failures
or silently substitute a cheaper model/precision. A corrected infrastructure
run must be separately labeled and retain the original attempted suite.

- If 7B has both successes and failures with reliable tool use, investigate the
  failures and assess whether skills plausibly address them before integrating
  Ben's skills. Freeze the future comparison only after this gate is reviewed.
- If 7B is 0/5, inspect file reads, saved edits, public checks, unsupported syntax,
  preservation failures and terminations first. Fix demonstrated harness defects
  and rerun all comparison conditions if the harness changes. Do not enlarge
  budgets just to obtain passing scores.
- If 7B is 5/5, these five fixtures may have a ceiling. At 0/5 they may have a
  floor. The fixtures cover five repair families but all currently carry an
  `easy` difficulty label; variety alone does not establish difficulty variation.
  One attempt per task also cannot establish variance or reliability. Propose a
  larger **development** difficulty ladder and repeated, predeclared seeds only
  after examining the pilot. Keep binary grading; diagnostic check failures are
  explanations, not a new partial-credit score.

Before the eventual four conditions, freeze tasks/evaluators/runtime, model and
tokenizer revisions, serving image/hardware/precision, JSON backend, system
instructions, retries, seed schedule and budgets. Skill context must consume the
same allowances. This milestone introduces no skills, training, held-out tasks
or leaderboard, and makes no research performance claim.

## Verification

Local validation: **174 tests passed** (89 unit, 85 container integration),
including all **71 unchanged grader verdicts**, tool execution and isolation
checks. Lint and formatting passed. Endpoint tests use mocked HTTP, not a model.
The [GitHub checks workflow](https://github.com/Sahaj0312/liquidBench/actions/workflows/ci.yml)
runs lint, unit tests, a runtime image build and container integration tests on
the pushed commit. No model credentials or inference are used in CI.
