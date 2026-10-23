# Milestone 5: skills A/B preparation

Historical preparation record. The user subsequently approved the shared budgets
and one 90-minute/$2 session. That session was terminated after the near-window
preflight failed; see the [preflight report and cleanup evidence](milestone-5-preflight.md).
The ten task attempts have not run. The [v2 preflight/runbook](preflight-v2.md)
supersedes the endpoint gate and deployment commands below for the next session;
the experiment configurations and paired design are unchanged.

Preparation is complete; **no paired model attempts or paid deployment have been
launched**. The full upstream entry instructions cannot fit the old 8K context.
The proposed experiment therefore requires approval of a shared budget adjustment
as well as the new GPU session. The old 2/5 pilot is historical context, not the
control arm of this comparison.

## Source and redistribution

Pinned upstream: [benjaminsehl/liquid-skills at
483f969bed623c87c9e26ac34324d8d7d8fe68c3](https://github.com/benjaminsehl/liquid-skills/tree/483f969bed623c87c9e26ac34324d8d7d8fe68c3).
The complete tracked inventory, README, plugin metadata and all skill documents
were inspected. No license file or redistribution grant was found. This report
does not infer permission from the repository being public.

Original content remains in an ignored local checkout at `.cache/liquid-skills`.
Only a [revision/file-hash manifest](../../skills/liquid-skills.lock.json) is
committed. No upstream prose, examples or modified skill versions are vendored.
The loader verifies the checkout's HEAD, complete tracked skills inventory,
per-file SHA-256/size, and equality to the pinned Git objects. Symlinks and
modified files are rejected. Updating a hash alone cannot relabel edited content
as the original revision. CI uses entirely synthetic skill documents.

The bundle contains all three entry files, including their YAML front matter,
and all fourteen reference documents. Entries load in upstream plugin order:
Liquid language, coding standards, accessibility. Content is not summarized,
truncated, rewritten or selected based on previous failures. Reference links
resolve relative to each entry's directory.

Treatment traces will contain upstream text. Keep them local and outside agent
workspaces; obtain appropriate permission before redistributing that content or
publishing full traces. Hashes, token counts, access paths and aggregate results
can be retained independently. No message requesting permission was sent to the
author as part of this work.

## Exact token feasibility

The pinned Qwen tokenizer/config files match the previous GPU pilot's raw-file
SHA-256 values. Measurement uses Transformers 5.19.0, tokenizers 0.23.3 and
Jinja2 3.1.6, with the checkpoint's original chat template and generation prompt.
No model weights or inference are required. Local counts also matched all
18 saved vLLM tokenizer responses from the prior preflight exactly. A new live
endpoint must still pass preflight and independently match the paired prompts.

| Entry | Tokens without chat wrapping |
| --- | ---: |
| shopify-liquid-themes/SKILL.md | 3,090 |
| liquid-theme-standards/SKILL.md | 3,069 |
| liquid-theme-a11y/SKILL.md | 3,298 |
| **Total** | **9,457** |

The complete entry message, including document paths and boundaries, is 9,815
tokens. It adds exactly 9,820 tokens to each initial chat prompt after template
overhead. Full initial prompt measurements:

| Task | Baseline | Skills | Skills after one largest-reference read |
| --- | ---: | ---: | ---: |
| announcement-subtitle | 712 | 10,532 | 16,821 |
| asset-references | 646 | 10,466 | 16,755 |
| product-card | 673 | 10,493 | 16,782 |
| section-schema | 681 | 10,501 | 16,790 |
| shipping-message | 696 | 10,516 | 16,805 |

The last column includes the read action and full JSON-encoded tool response,
not just raw Markdown tokens. Each request additionally reserves 1,024 output
tokens and a 32-token margin. Neither 8K nor 16K supports that reference-read
case. Under 24K cumulative accounting, even an optimistic history-free treatment
could make only two requests; reading, writing and explicitly finishing already
requires three. Real history and outputs cost more.

Proposed limits, **identical for both arms**:

| Setting | Pilot | Proposed paired comparison |
| --- | ---: | ---: |
| Context | 8,192 | **32,768** |
| Cumulative measured input + output | 24,000 | **393,216** |
| Turns | 12 | 12 |
| Output per response | 1,024 | 1,024 |
| Attempt seconds | 300 | 300 |
| Request timeout / transient retries | 90 seconds / 2 | unchanged |
| Temperature / top_p / seed | 0 / 1 / 42 | unchanged |

32K is the checkpoint's native context; no YaRN or quantization change is
proposed. 393,216 is `12 × 32,768`: the cumulative ceiling admits twelve legal
full-context requests, rather than penalizing the full-entry treatment after two
turns. It is a maximum, not expected consumption or a billing guarantee for
unknown-usage retries. Both arms pay for every repeated input token, including
cached prefixes. The old pilot configuration remains unchanged.

All seventeen documents total 49,586 raw tokens. Loading all references into one
conversation will not fit 32K. References are available individually on demand;
history is never evicted or compressed. An overfull history stops with
`context_budget` and remains an observed failure. This is an explicit limitation,
not a claim that every possible reference-reading trajectory fits.

Reproduce locally from the repository root:

```sh
uv run python scripts/prepare_skills.py
uv run --with transformers==5.19.0 --with tokenizers==0.23.3 --with jinja2==3.1.6 python scripts/measure_skills.py
uv run python scripts/run_skills_ab.py
```

The last command only prints the plan. Measurement downloads only pinned,
hash-verified tokenizer files if absent. See [complete measurements](skills-feasibility.json)
and [prior-server cross-check](skills-tokenizer-crosscheck.json).

## Integration and isolation

`skills` is an optional configuration field. The paired files differ **only**
in this field: [baseline](../../configs/qwen-ab-base.json) sets it to null;
[treatment](../../configs/qwen-ab-skills.json) names the manifest, checkout and
full revision. Existing configs without the field remain baseline configurations.

Protocol v5 adds a common, task-independent explanation of read-only document
paths and instruction precedence to the system message in **both** arms. Task
prompts are byte-for-byte unchanged. All three entry instructions form a separate
user message before the original task. The task's explicit scope/runtime and
the tool protocol take precedence over optional general guidance.

No tool names or argument schemas are added. `read_file` serves only exact
verified `skills/` document paths from an immutable in-memory snapshot;
`list_files` includes their paths. `search`, `analyze`, `render` and `check` retain
their task-workspace scope. Writes to skills and using other path-based tools on
them are rejected. Baseline requests for skills fail without opening the checkout.
The bundle is never mounted in a container, copied into the task snapshot, or
passed to the grader. Host reads accept only the operator's pinned manifest, never
an agent-selected filesystem path.

Full entry text and reference results go through normal prompt admission and
usage accounting. The existing 16,000-character task-tool preview rule is bypassed
for skill reads, preserving the complete reference. A subsequent context overflow
stops the run before another inference call. Skills do not grant shell, network,
package installation, hidden data or new Shopify runtime support.

`result.json` records the bundle identity and `skill_accesses`, with path,
content hash/size, mode (`injected` or `read_file`), request turn and
`first_model_turn`. The last field remains null if a document was prepared/read
but context/budget exhaustion prevented a subsequent successful model response.
Trace events distinguish document access from delivery to a completed model call.
These are evidence of exposure, not proof of internal attention or reasoning.
The analysis script includes access records and summed attempt latency.

The original bundle recommends general Shopify features and tools, including
translation patterns and shell-based JSON editing, that may be outside these
tasks' explicit contract. Those instructions are preserved. Any resulting scope,
runtime or unavailable-tool failure must be analyzed as a treatment failure; do
not quietly edit the bundle to prevent it.

## Exact GPU run plan for approval

1. Obtain approval for the shared limits above and **one A40 session, at most
   90 minutes and $1 in GPU/storage charges**. Recheck price and capacity before
   creating anything. The live October 23 catalog quotes Secure Cloud A40 48 GB
   at **$0.59/hour**, but currently returns **NONE** for CUDA >=13.0 Pod capacity.
   Do not substitute another GPU/cloud/image without revising the plan.
2. Use one Secure Cloud A40, CUDA host compatibility >=13.0, 100 GB ephemeral
   container disk, no persistent/network volume, only SSH exposed. Reuse the
   previously verified bootstrap and SSH tunnel pattern. Preserve the official
   vLLM image digest and all serving arguments recorded in
   [observed metadata](qwen-7b-observed.json), changing only `--max-model-len`
   from `8192` to `32768` for **both** arms. Keep BF16 weights/KV, no quantization,
   one sequence, tensor parallel 1, seed 42, GPU utilization 0.9, generation config
   `vllm`, and xgrammar JSON enforcement.
3. Record GPU/driver, full command, software versions, actual engine settings,
   model/tokenizer revision and all four weight-shard hashes. The model remains
   `Qwen/Qwen2.5-Coder-7B-Instruct@c03e6d358207e414f1eca0bb1891e29f1db0e242`;
   image remains `vllm/vllm-openai@sha256:6ee133356d49ed24cee03dd0cda3d3980279a11c107ce3e752c89e76540f41c9`.
   The A40 hosted the BF16 pilot; 32K startup/concurrency capacity still requires
   live verification. Model weights were 14.29 GiB; the BF16 KV estimate grows
   from about 0.44 to 1.75 GiB per sequence, before runtime reservations.
4. Run synthetic endpoint preflight at the new context, with JSON enforcement,
   tool-feedback roles and near-window count agreement. The paired runner also
   compares live `/tokenize` counts with all ten local initial prompt counts,
   before task inference. Stop on any mismatch; do not fall back to approximation.
5. Execute exactly one attempt per task/condition in this predeclared order:
   announcement base/skills; assets skills/base; product base/skills; schema
   skills/base; shipping base/skills. Every attempt gets a fresh sandbox/history;
   the same server and immutable runtime image serve all ten. Keep prefix caching
   unchanged and record the order; latency is descriptive, not a clean speed
   experiment. Task failures continue; infrastructure errors stop the experiment
   with explicit missing pairs. No automatic task reruns or selective replacements.
6. Export complete traces, patches, final files, grades, document-access records,
   tokens, latency, preflight, serving evidence and billing records locally. Hash
   the archive. Stop starting work at 80 minutes, export and delete the Pod by
   90 minutes; actively monitor the session rather than relying on unsupported
   provider auto-termination flags. Delete after completion or failure. Verify
   absence by independent get/list reads and that no pilot storage remains.

Approved-session commands (do not run inference during preparation):

```sh
uv run python scripts/preflight_endpoint.py --config configs/qwen-ab-base.json --output runs/m5-endpoint-preflight
uv run python scripts/run_skills_ab.py --execute --preflight runs/m5-endpoint-preflight/report.json --output runs/skills-ab-01
uv run python scripts/analyze_runs.py base=runs/skills-ab-01/base skills=runs/skills-ab-01/skills > runs/skills-ab-01/comparison.json
```

The paired runner rejects existing output directories, unequal configurations,
stale local feasibility metadata and missing/nonmatching endpoint preflight. A
preflight must be less than an hour old. The runner does not provision or delete
cloud resources; session supervision and cleanup remain required operator steps.

## Cost and interpretation

At the quoted $0.59/hour plus 100 GB container disk at $0.10/GB/month,
assuming 720 hours/month, total rental is approximately **$0.60389/hour**.
10–30 minutes would cost **$0.101–$0.302**; 90 minutes costs **$0.906** before tax
or billing adjustments. Ten maximum-duration attempts occupy 50 minutes, leaving
40 minutes within the proposed cap for setup, probes and export. This is planning
arithmetic, not a promise of throughput. Stop early if preparation stalls.
[Runpod storage and billing terms](https://docs.runpod.io/pods/pricing).

No top-up or resources were purchased during preparation. The previous session's
approval does not authorize this one. The [live quote](skills-runpod-quote.json)
is retained; capacity and price must be revalidated after approval.

There are **no A/B results yet**. The subsequent report must compare paired task
verdicts, gains and regressions, validation actions, repeated errors, all document
exposures/reads, cumulative input/output, latency, truncation and budget stops.
Distinguish successful tool execution from lint findings. Inspect failure traces
for the previous grammar, normalization and false/default problems, but do not
add targeted hints or task answers to the treatment. More tokens are not evidence
of better reasoning; fewer tokens from an early wrong finish are not efficiency.

Five tasks and one attempt per arm remain development diagnostics. A useful next
gate would be improved paired correctness without new systematic instruction or
runtime failures, with clearly reported extra context/cost. That would justify
considering a larger development benchmark, not a held-out research claim or
fine-tuning. No new tasks, training data, training or leaderboard are included.

## Local verification

**201 tests pass locally: 115 unit and 86 container integration tests.** The full
200-test suite passed in 129.91 seconds; after adding the infrastructure-summary
regression, the final 115-test unit suite passed again. Integration includes all
71 unchanged grader verdicts and a scripted skills-enabled success through real
agent/evaluator containers. This is synthetic harness evidence, not a model score.
Ruff lint and formatting pass.

Coverage includes original bytes/front matter, complete inventory, revision and
Git-object pinning, symlink/tamper rejection, baseline isolation, exact read-only
paths, full long-reference delivery, access-versus-delivery logging, context and
cumulative accounting, paired order/config equality, stale counts, and preserving
infrastructure failures without replacements. Task fixtures, graders, runtime
files and the original `qwen-base.json` are unchanged. The final preparation
commit is also checked by GitHub CI before handoff.
