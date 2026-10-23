# Milestone 4: Qwen 7B development pilot results

**Qwen2.5-Coder-7B-Instruct passed 2 of 5 development tasks.** All five attempts
completed through the calibrated harness with zero protocol or infrastructure
errors. The passing tasks were asset references and section schema. The other
three failed on Liquid syntax, normalization or boolean fallback behavior.
The GPU was terminated after evidence export; fresh Runpod reads confirmed that
the Pod was gone and no Pods or network volumes remained.

This is one attempt per **development** task, not held-out research evidence.
No prompts, graders, budgets, model settings or harness code changed. No failed
task was rerun. Skills and fine-tuning were not introduced.

## Deployment and verification

The user authorized one A40 session, at most two hours and $3 from an existing
$10 balance. The live Secure Cloud catalog quoted $0.59/hour and low A40 stock
in Montréal. Pod `vxk35bw5h56smi` was created in `CA-MTL-1` at
2026-10-23 17:49:53.980 UTC. It allocated one NVIDIA A40, 50 GB host RAM, nine
vCPUs and 100 GB ephemeral container disk, with no persistent or network mount.
Only SSH was exposed; inference used a tunnel to local port 8000. The SSH host
fingerprint was verified against authenticated provider boot logs.

| Serving property | Observed value |
| --- | --- |
| Checkpoint and tokenizer revision | `c03e6d358207e414f1eca0bb1891e29f1db0e242` |
| Model architecture / precision | Qwen2ForCausalLM / BF16, no quantization |
| GPU / driver | NVIDIA A40 / 595.91.07 |
| Container | `vllm/vllm-openai@sha256:6ee133356d49ed24cee03dd0cda3d3980279a11c107ce3e752c89e76540f41c9` |
| vLLM / response fingerprint | 0.32.0 / `vllm-0.32.0-e87799ff` |
| PyTorch / compiled CUDA | 2.13.0+cu130 / 13.0 |
| Python / Transformers / tokenizers | 3.12.3 / 5.19.0 / 0.23.3 |
| xgrammar | 0.2.8; explicitly selected JSON backend |
| Context / concurrency / tensor parallel | 8192 / 1 / 1 |
| KV cache | `auto`, which resolves to the model's BF16 dtype; implementation captured |
| Decoding | temperature 0, top_p 1, seed 42, 1024 maximum output tokens |
| Other settings | generation config `vllm`, GPU memory utilization 0.9; prefix caching and chunked prefill enabled |

The image's CUDA environment is 13.0.2, the PyTorch build reports 13.0, and the
provider's host CUDA compatibility field reports 13.2. These are different
version fields, not an inferred change of inference precision. The bootstrap
installed OpenSSH server to enable access; it did not replace Python serving
packages. Package versions, complete effective engine configuration, startup
logs, model config and raw-file hashes are preserved in the evidence bundle.

All four downloaded weight shards matched their SHA-256 values in the official
Hugging Face metadata for the pinned revision. The tokenizer's chat-template
SHA-256 matched `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`.
The server logged BF16 weights and no quantization; model loading consumed
14.29 GiB. GPU allocation after initialization was 40,529 MiB, which includes
runtime/cache reservations and is not a measured minimum requirement.

The four synthetic preflight probes passed: short read action, assistant-action/
user-tool-feedback history, JSON output despite a plain-text request, and a
near-window finish action. Prompt counts were **462, 553, 42 and 7136**; every
`/tokenize` count exactly matched completion usage. All replies were strict JSON
objects with normal stops. The startup configuration confirms xgrammar was active.
Preflight consumed 8,193 input and 49 output tokens, separately from task runs.
The HTTP report deliberately does not attest GPU/revision; the separate host
evidence supplies that verification.

The suite ran from clean commit `fec13dd6d2f916d00ae2835bc9c5beb5b4751524` with
protocol `json-actions-v4` and runtime image
`sha256:ffd88aa28203d5582a880a59727f5e4700f1bf225387a381b60cb60bbadc9638`.
Source, runtime, task and configuration trees match the frozen preparation
manifest. Limits remained 12 turns, 24K cumulative tokens, 1024 output tokens,
300 seconds, 90-second request timeout and two transient retries.

## Results and comparison

| Task | Verdict | Calls | Input / output tokens | Attempt seconds | Termination |
| --- | --- | ---: | ---: | ---: | --- |
| announcement-subtitle | Fail | 6 | 9,180 / 1,050 | 35.34 | finished |
| asset-references | Pass | 4 | 3,100 / 154 | 6.56 | finished |
| product-card | Fail | 12 | 19,273 / 885 | 32.06 | turn_budget |
| section-schema | Pass | 4 | 4,267 / 377 | 12.91 | finished |
| shipping-message | Fail | 4 | 3,628 / 267 | 11.36 | finished |
| **Total** | **2/5** | **30** | **39,448 / 2,733** | **98.24** | finished ×4; turn_budget ×1 |

| Final development configuration | Passed | Calls | Input / output tokens | Summed attempt seconds | Protocol / tool / infrastructure errors |
| --- | --- | ---: | ---: | ---: | --- |
| Qwen 1.5B Q4_K_M, llama.cpp, M1 | 0/5 | 11 | 8,140 / 996 | 38.99 | 0 / 0 / 0 |
| Qwen 3B Q4_K_M, llama.cpp, M1 | 0/5 | 13 | 10,593 / 1,185 | 80.09 | 0 / 0 / 0 |
| Qwen 7B BF16, vLLM, A40 | 2/5 | 30 | 39,448 / 2,733 | 98.24 | 0 / 1 / 0 |

The 7B model read the target file on **all five tasks** and used public validation
on all five: Theme Check on four, rendering on announcement-subtitle. It made
five reads, eleven writes, eight checks, two renders and four finishes. Neither
final smaller-model suite used `check`; 1.5B read none and 3B read three files.
No 7B attempt used `analyze`, `search` or `list_files`; those tools were available,
but the traces do not show that they were needed for these fixes.

The single recorded tool error is a failed Liquid render. Theme Check successfully
returning syntax-error findings counts as a successful tool invocation, so the
five product-card syntax diagnostics are **not** five additional tool errors.
Zero protocol errors must not be mistaken for correct code or good recovery.

Every task request's count matched reported input usage exactly. No provider
errors/retries, context stops, cumulative-token stops, timeouts or output-length
stops occurred. The largest task prompt was 2,700 tokens, and the largest output
was 402. Product-card spent 20,158 cumulative tokens and about 32 seconds; its
turn limit was exhausted by repetition, not long output or useful unfinished work.
These traces do not justify increasing any budget.

Model size, precision, serving backend and hardware all differ from the earlier
local models. Consequently this is a descriptive comparison, not an isolated
model-size effect, a throughput comparison or a statistically reliable gain.
More tokens partly reflect useful validation and partly the product-card loop;
the smaller models' short unsuccessful submissions are not efficiency wins.

## Task-by-task trace evidence

Suite: `runs/suite-20261023T175220Z-4b832a5f`. Line references below are to each
attempt's `trace.jsonl`. Result and patch hashes, paths and action lines are
committed in [qwen-7b-results.json](qwen-7b-results.json). Full traces, patches,
final snapshots and grading output remain in the retained local run bundle.

### Announcement subtitle: incomplete semantic recovery

Attempt `20261023T175220Z-fcef422f`.

L3 reads the file. L7 saves a subtitle condition using
`section.settings.subtitle | strip != ''` directly inside an `if`. L11 renders
with correctly nested variables and `strip_schema:true`; L13 returns a precise
syntax error at the pipe. L15 removes `| strip` from the condition, leaving
`subtitle != ''`, and still outputs the original untrimmed subtitle. The schema
and pre-existing heading/body behavior are preserved.

L19 renders only a nonempty, already-trimmed subtitle, which succeeds at L21.
L23 finishes. This example cannot expose null, whitespace-only or trimming
errors. The grader accepts scope, schema preservation and static lint, but
rejects seven behavioral cases. The prompt explicitly required null handling,
ASCII trimming, omission of empty normalized text, and escaped normalized output.

Attribution: a Liquid grammar gap followed by an incomplete repair and weak
test selection. The harness gave the right syntax feedback and executed the
successful second render. The remaining mismatch is not missing context or an
unsupported Shopify feature. We observe actions, not the model's private reasoning.

### Asset references: complete literal repair

Attempt `20261023T175256Z-e047de98`.

L3 reads the snippet. L7 repairs all three literal operands to the existing
stylesheet and two translation keys while retaining live markup and filter
order. L11 calls `check`; L13 reports only the nonblocking OrphanedSnippet warning.
L15 finishes. All eleven grading checks pass.

The prompt names the required references, so this demonstrates a bounded edit
and correct static-tool selection, not broad Shopify asset discovery. The model
correctly avoids the unsupported offline render path for Shopify-only filters.

### Product card: unchanged invalid code after repeated diagnostics

Attempt `20261023T175302Z-5e68d20a`.

L3 reads the file. L7 writes a title fallback, escaping and availability branches,
but inserts `{% if product.vendor | strip != '' %}`, which is invalid core Liquid.
L11 calls `check`; L13 reports `LiquidSyntaxError: Syntax error in 'if' tag` at
the relevant lines. It also reports a nonblocking orphaned-snippet warning.

L15, L23, L31, L39 and L47 write **exactly the same file content** as L7. Checks
at L19, L27, L35 and L43 return the same syntax finding at L21, L29, L37 and L45.
After six identical writes and five checks, all 12 turns are consumed without
`finish`. Final static and render grading reject the syntax. Even the attempted
vendor output uses the raw escaped vendor rather than the required trimmed value.

Attribution: Liquid syntax knowledge plus failure to act on tool feedback. The
system prompt already says repeating an erroneous action will not fix it. The
diagnostic is available and no protocol parsing failed. Theme Check's wording
is less specific than the renderer's pipe error, but it identifies the failing
tag and location. A future generic diagnostic presentation experiment could be
justified; it must be separate and applied to all conditions. No harness feedback
was changed during this pilot, and extra turns would only be speculation.

### Section schema: complete repair with markup preservation

Attempt `20261023T175335Z-0436938b`.

L3 reads the whole section. L7 fixes the checkbox ID/type of default, range
default, and preset key/values while preserving every byte outside the schema.
L11 calls `check`; L13 returns no offenses; L15 finishes. All twelve grading
checks pass, including schema contract and preserved markup. This fixes the
preservation failure seen in the earlier 3B run.

The acceptance values were explicit in the task. This is evidence of successful
JSON editing and constraint following, not real theme-editor validation.

### Shipping message: false overwritten by default

Attempt `20261023T175347Z-ad63fa6e`.

L3 reads the snippet. L7 correctly adds empty-cart priority, an inclusive
threshold boundary, message trimming/fallback and HTML escaping. It retains
`{% assign enabled = settings.enabled | default: true %}`. An explicit false
therefore becomes true, violating the prompt's disabled behavior.

L11 calls `check`; L13 returns only OrphanedSnippet; L15 finishes without a
behavioral render. All fourteen enabled-behavior cases pass; the three disabled
cases fail. The successful static check does not test boolean semantics.

Attribution: a false/default semantics gap or incomplete review of the original
logic, combined with insufficient behavioral validation. The trace cannot tell
which internal explanation dominates. Public rendering with `enabled:false`
could have exposed this without any hidden-case access. No context or budget
limit constrained the four-call attempt.

## Cost, retention and cleanup

Deletion was requested at **17:54:19 UTC**, about **265 seconds (4m25s)** after
creation. At $0.59/hour plus 100 GB at $0.10/GB/month (720-hour-month estimate),
the estimated total is **$0.0445**, approximately **4.5 US cents**, before any
tax or billing adjustments. This includes setup, preflight, regression-test
waiting time, suite execution and export. No additional top-up was made.

The post-termination billing API returned no records. **The settled charge is
not available yet; the zero returned by an empty billing report is not a claim
of free GPU usage.** Token-price fields remain null because this was hourly
rental, not per-token inference. The elapsed estimate is comfortably below the
approved $3 session cap and $50 GPU planning allocation.

The delete returned 204; an independent get returned 404, and lists returned
zero Pods and zero network volumes. The Pod had no persistent/network mounts.
The SSH tunnel closed after deletion. No cloud GPU or storage created for this
pilot remains. Other user resources were not modified.

Complete evidence is retained in `runs/runpod-pilot-preparation/`,
`runs/7b-preflight-01/`, and the five-task suite directory. The exported archive
is `runs/liquidbench-qwen7b-pilot-20261023.tar.gz`, with a companion SHA-256 file.
It includes the complete 7B artifacts, serving logs/config/model hashes,
provider creation/deletion evidence, preflight and both earlier baseline suites. It
contains no SSH private key, account API key, reference solution or hidden cases.
Keep it outside agent workspaces. Committed observed serving metadata is in
[qwen-7b-observed.json](qwen-7b-observed.json).

The archive contains 117 evidence files plus a per-file SHA-256 manifest; every
archived evidence file was read back and checked against that manifest. Archive
SHA-256: `38b3bdef0758d232d556bf3b0f9ff97c79d6a31dcadc13a65ef914f99024b9e7`.

## Next research gate

**Proceed next to a controlled base-versus-base-plus-skills development ablation;
do not start fine-tuning or claim the four-configuration research experiment is
ready.** The 7B baseline now demonstrates valid tool use, real repair capability,
and both successes and failures under the frozen budget. Its observed 2/5 avoids
an immediate floor or ceiling and gives a plausible skills hypothesis around
Liquid grammar, normalization, false/default semantics and validation discipline.
It does not prove the skills bundle will improve those failures.

For the next milestone, first inspect and pin the complete, unmodified Ben Sehl
bundle described in the brief. Verify all three entry instructions and reference
reads fit and are counted under the same 8K context/24K cumulative allowance.
Do not add task answers or these failure traces to the skill treatment. Preserve
the same BF16 checkpoint, hardware class, serving image, JSON backend, system
prompt, tools, budgets and grading, changing only skill availability. Record
bundle visibility/access and loaded content. A fresh matched base run is useful
to verify reproducibility when that treatment is introduced; label all runs and
do not selectively replace this baseline's failures.

Five tasks, all labeled `easy`, are still too few to establish difficulty tiers,
variance or generalization. Before freezing research evaluation, propose a wider
development difficulty ladder and a predeclared repeat/seed policy, then separately
design uncontaminated evaluation and training partitions. Do not author those
partitions or begin training in this milestone. At temperature zero, repeating
the same request/seed is a reproducibility check, not independent stochastic
evidence. Any later harness change requires all compared conditions to be rerun.

Retain binary grading and the current budgets. The present failures offer no
evidence for weakening acceptance criteria or increasing output/context/turn
limits. Generic reporting of lint findings separately from tool-execution errors
would improve analysis without changing agent behavior, but is not needed to
make this pilot's verdicts interpretable.

## Validation

**174 tests passed** before the model suite, including all **71 unchanged grader
verdicts**, sandbox isolation and the full scripted pipeline. Ruff lint and format
checks passed. The results commit changes documentation and observed metadata
only; it leaves `src/`, `tasks/`, `runtime/`, `configs/`, scripts and tests unchanged.
GitHub CI runs the same checks and container build on the pushed results commit.
