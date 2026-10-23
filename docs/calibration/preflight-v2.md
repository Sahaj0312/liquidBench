# Milestone 5: revised endpoint gate and next deployment

**Predeclared policy: `liquidbench-preflight-v2`. No new GPU session or model
inference has run under this policy.** It replaces the preflight gate, not the
experiment. Deployment still needs fresh approval. The prior single-session
approval was consumed by the aborted session.

## Why change the gate

The [original failed preflight](milestone-5-preflight.md) tested generation after
31,712 tokens dominated by the same word. The model repeated that word until
its output allowance expired. Token counts agreed; the response arrived within
the timeout, with no demonstrated transport or memory failure. That is useful
model-behavior evidence, but a poor prerequisite for measuring the effect of
skills on real coding tasks. The measured treatment starts at 10,466–10,532
tokens and reaches 16,755–16,821 after one largest-reference read.

V2 tests generation at those representative sizes and reserves the near-window
case for tokenizer/accounting checks. It still requires basic protocol competence
on short prompts. Long-context model behavior becomes recorded diagnostic evidence,
not a criterion that selects whether a model may enter the experiment.

The original trace, report, archive hashes and failed verdict remain unchanged.
They are not reclassified as a v2 pass. The old implementation is retained in Git
at `85b99ba` (and earlier). No task, grader, skill, benchmark system/task prompt,
model configuration, decoding setting or execution budget changes in this revision.

## Fixed pass/fail criteria

The ordered checks below live in `src/liquidbench/preflight.py`. Each completion
is requested **once**, with the existing JSON mode, 1,024 output tokens,
temperature 0, top_p 1, seed 42 and 90-second timeout. Preflight does not retry,
switch output modes, or rewrite a prompt based on a completion. Tokenizer calls
alone choose a prefix length from one fixed synthetic corpus.

| Check | Mandatory evidence | Model behavior treatment |
| --- | --- | --- |
| `short_action` | Successful HTTP response, exact usage/count agreement, configured served-model identity, valid JSON object, expected `read_file` action | Wrong action or truncation blocks basic protocol readiness; labeled `model_protocol` |
| `tool_feedback_roles` | Same contract after assistant actions and user tool feedback; expected `finish` action | Wrong action or truncation blocks basic protocol readiness; labeled `model_protocol` |
| `json_enforcement` | A complete, normally stopped strict JSON object despite a request for bare text | Truncation leaves enforcement unproven and blocks as `model_protocol`; normally stopped non-JSON violates the serving contract |
| `near_window_accounting` | Stable repeated tokenizer counts near both 31,712 and 32,736; first fits output reservation, second is rejected by admission arithmetic | **No generation**, no instruction-following requirement |
| `representative_10k` | Generation at 10,500 tokens (within 128 below target), with identity, usage/count and output-contract checks | Expected `finish` is measured; wrong action or length truncation is a nonblocking model diagnostic |
| `representative_17k` | Same at 17,000 tokens, including synthetic document context plus assistant read/user tool-result history | Same nonblocking behavior criterion; retained even when the 10K diagnostic failed instruction following |

Every generation probe must agree exactly between `/tokenize` and returned
`usage.prompt_tokens`; output usage must be a positive integer no greater than
the requested maximum. The only supported finish reasons are `stop` and `length`.
HTTP/transport errors, malformed response metadata, identity mismatch, invalid or
unstable tokenizer counts, usage disagreement, excess/zero output usage, and
unsupported finish reasons **block at every prompt length**.

Strict JSON rejects prose, fences, arrays, duplicate keys and non-JSON numeric
constants. A response ending with `stop` must satisfy that contract, including
at representative lengths. A response ending with `length` can be an incomplete
JSON prefix and is recorded as model output truncation; it does not alone prove
that JSON enforcement is broken. This category describes an observed serving
contract violation, not a claim about whether a backend bug or a model caused it.
If usage/identity is wrong as well as the action, the infrastructure failure still
blocks. We never exempt long probes from accounting or serving-contract checks.

Failure classes in `report.json`:

- `infrastructure`: an observed transport, response-contract, identity or accounting failure.
- `model_protocol`: infrastructure checks passed but a mandatory short behavior check failed.
- `diagnostic_setup`: the fixed corpus cannot be sized safely for the declared probe; stop without blaming model reasoning.
- `failure_kind: null`, `passed: true`, possibly nonempty `model_failures`: the gate passed with recorded representative-length model failures. This is **not** a model task success or a clean bill of long-context health.

Each check records separate `infrastructure_passed` and, for generations,
`model_passed` fields. `passed` means that check's **gate criterion** was met.
Representative model failures remain in the full trace and summary and must be
included in the later analysis. No retry or selective replacement is authorized.

## Prompt construction and limits of the evidence

The corpus consists of 1,200 deterministic, distinct neutral records mixing
prose, quantities and JSON fields. It contains no Liquid advice, upstream skills,
benchmark examples or hidden cases. The 10.5K shape uses a system message, document
message and synthetic action request. The 17K shape divides the corpus between
initial document context and JSON-encoded tool feedback (60/40 by characters),
using the runner's assistant-action/user-feedback roles.

Each sizing search makes at most 20 tokenizer calls and accepts only a count
in `[target - 128, target]`. It never reads completion results. Generation prompt
counts are rechecked for stability before sending; the near-window counts are
also repeated. With 32,768 context, the original reservation rule remains
`input + 1,024 + 32 <= 32,768`. Both near-window examples are tokenizer-only,
even the admissible one. Intermediate sizing candidates may exceed the context;
they are never submitted to generation. The full successful diagnostic contains
five completions and at most 87 tokenizer requests, separate from task budgets.

[Offline measurements](preflight-v2-tokenizer.json) used the existing hash-verified
Qwen tokenizer with Transformers 5.19.0, tokenizers 0.23.3 and Jinja2 3.1.6. All
four target sizes were reached exactly; corpus and prompt hashes are recorded.
No model weights, endpoint or inference were used. Those measurements are **not**
an endpoint gate. CI uses mocked HTTP only.

Repeated `/tokenize` calls near 32K test stability and local admission arithmetic;
they do not prove generation quality, memory capacity or full-window usage
agreement. Usage agreement is tested during actual short, 10.5K and 17K
completions. Host/engine evidence must separately establish the pinned revision,
BF16, max model length and GPU settings. The paired runner additionally requires
all ten original initial-prompt counts to match the independent local Qwen counts.

The gate is sufficient to begin measuring task behavior once these serving and
compatibility requirements pass; it does not guarantee the model can solve tasks,
use every reference, or behave reliably at every length up to 32K. Those are
observations to preserve, not preflight scores to optimize.

## Updated deployment instructions — approval still required

1. Obtain fresh approval for **one A40 48 GB**, with no GPU substitution. Keep
   the proposed session ceilings at **90 minutes and $2 USD all-in**; do not
   assume the previous approval applies. Before provisioning, recheck live
   Secure Cloud A40 price/capacity, CUDA compatibility >=13.0 and storage charges.
   Stop if no qualifying A40 is available or the quote cannot fit the cap. No
   paid resources are created by any local test or command in this change.
2. Reuse the prior pinned image, SSH bootstrap/tunnel pattern and ephemeral
   100 GB disk, without persistent/network volumes. Verify the SSH host key via
   authenticated provider evidence. Record the Pod ID, rate, creation time and
   approved deadline before inference. Keep active cost/deadline supervision.
3. Verify the deployment against [observed serving evidence](milestone-5-preflight.json):
   GPU/driver, model/tokenizer revision, all four weight-shard hashes, package
   versions, chat template, complete command, BF16 weights/KV, no quantization,
   32,768 context, one sequence, TP 1, seed 42, GPU utilization 0.9, generation
   config `vllm`, and xgrammar. A response's model name cannot attest these facts.

Pinned deployment (unchanged):

```text
image: vllm/vllm-openai@sha256:6ee133356d49ed24cee03dd0cda3d3980279a11c107ce3e752c89e76540f41c9
model/tokenizer revision: c03e6d358207e414f1eca0bb1891e29f1db0e242
```

```sh
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct \
  --revision c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --tokenizer-revision c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --dtype bfloat16 --kv-cache-dtype auto --max-model-len 32768 \
  --max-num-seqs 1 --tensor-parallel-size 1 --gpu-memory-utilization 0.9 \
  --generation-config vllm --structured-outputs-config '{"backend":"xgrammar"}' \
  --seed 42 --host 0.0.0.0 --port 8000
```

4. From a clean committed checkout, run the new diagnostic once, after endpoint
   readiness and host verification. Use a fresh output directory so the original
   failed preflight cannot be overwritten. Inspect all reported model warnings;
   the predeclared criteria above decide admission, not a desire for a clean
   diagnostic score. If a mandatory check fails, export evidence and terminate;
   do not adjust settings or retry within the experiment.

```sh
uv run python scripts/preflight_endpoint.py \
  --config configs/qwen-ab-base.json \
  --output runs/m5-endpoint-preflight-v2-01
```

5. Only after the gate passes, execute the unchanged ten attempts. The runner
   rejects reports from a different policy/source/system, incomplete checks,
   configuration mismatches, or timestamps outside the last hour. It then checks
   all ten initial counts before any task completion. No changes are made to
   `configs/qwen-ab-base.json` or `configs/qwen-ab-skills.json`: both retain
   393,216 cumulative tokens, 12 turns, 1,024 output tokens, 300 seconds per task,
   90-second request timeout, two transient retries, and identical decoding.

```sh
uv run python scripts/run_skills_ab.py --execute \
  --preflight runs/m5-endpoint-preflight-v2-01/report.json \
  --output runs/skills-ab-01
uv run python scripts/analyze_runs.py \
  base=runs/skills-ab-01/base skills=runs/skills-ab-01/skills \
  > runs/skills-ab-01/comparison.json
```

Order remains announcement base/skills; assets skills/base; product base/skills;
schema skills/base; shipping base/skills. Use a fresh sandbox/history each time,
the same server/runtime, and one attempt per task/condition. Task failures continue;
infrastructure failures stop and leave explicit missing pairs. Do not replace
failed attempts. Include diagnostic warnings in the paired failure analysis.

6. Export all traces, patches, final files, grades, skill-access records, usage,
   latency, host/preflight records and billing evidence; hash the archive. Stop
   starting work at 80 minutes and delete the Pod and any session storage by the
   approved deadline, or earlier on completion/failure. Verify cleanup with
   independent get/list reads. Keep upstream skill bodies in local evidence;
   permission to redistribute them has not been established.

The last session's $0.59/hour GPU plus 100 GB at $0.10/GB/month implies about
$0.906 for 90 minutes before tax/adjustments (720-hour month). This is historical
planning arithmetic, **not a new live quote or authorization**. Recheck before
spending and keep the approved all-in cap. No fine-tuning, new tasks, or training
data are included.

## Local validation

Tests cover mandatory failures at short and representative lengths, nonblocking
model errors/truncation, tokenizer instability, exact request settings, absence
of near-window generation, complete evidence, and rejection of old/incomplete or
stale reports. Local validation passed **230 tests: 144 unit tests and 86 container integration
tests**, including all **71 expected grader verdicts**. Ruff lint and formatting
also passed. GitHub CI checks this commit before handoff. No live model generation
was performed while designing or testing these probes.
