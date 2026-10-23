# Milestone 5: Ben Sehl Liquid skills paired development experiment

**Baseline: 2/5. Full pinned skills: 0/5.** The new session passed preflight,
completed all ten planned attempts, retained every failure, exported evidence,
and terminated the Pod. There were no provider, protocol or infrastructure
failures. The treatment lost both baseline passes and gained none. This is a
negative result for this particular full-entry integration on five development
fixtures, not evidence that skills generally harm coding models.

Recommendation: **expand and replicate the development benchmark before
post-training**. The harness can support controlled experiments; this treatment
has not shown a task-level benefit. Do not train on these outcomes or weaken the
graders to turn the observed failures into passes.

## Frozen execution and preflight

The source tree was clean at `2c3ff9355e5aed222fdbcf63ff6acf44e6597df4` for all ten
attempts. The two configurations differed only in skills availability. Each task
received one baseline and one treatment attempt in the predeclared alternating
order. There were no retries of whole tasks or replacements of failures.

- Model/tokenizer: `Qwen/Qwen2.5-Coder-7B-Instruct` at
  `c03e6d358207e414f1eca0bb1891e29f1db0e242`; all 14 files, including four weight
  shards, matched the previous verified raw hashes.
- Image: `vllm/vllm-openai@sha256:6ee133356d49ed24cee03dd0cda3d3980279a11c107ce3e752c89e76540f41c9`.
- A40 48 GB, Secure Cloud CA-MTL-1; driver 595.91.07, CUDA host 13.2,
  PyTorch 2.13.0+cu130, vLLM 0.32.0, Transformers 5.19.0, tokenizers 0.23.3,
  xgrammar 0.2.8, Python 3.12.3. Endpoint fingerprint: `vllm-0.32.0-9da1cd72`.
- BF16 weights and KV cache, no quantization, TP 1, one sequence, 32,768 context,
  GPU memory utilization 0.9, generation config `vllm`, xgrammar JSON mode.
  Prefix caching stayed enabled. Engine logs showed 24.53 GiB available KV memory.
- Both arms: 393,216 cumulative tokens, 12 turns, 1,024 output tokens, 300 seconds
  per attempt, 90-second request timeout, two transient provider retries,
  temperature 0, top_p 1, seed 42. No transient retries were needed.
- Runtime image remained
  `sha256:ffd88aa28203d5582a880a59727f5e4700f1bf225387a381b60cb60bbadc9638`.
- Skills revision remained `483f969bed623c87c9e26ac34324d8d7d8fe68c3`.
  All three entries were loaded unchanged and references remained read-only/on demand.

The [v2 preflight](preflight-v2.md) ran **once**. Every mandatory check passed;
both representative-length model diagnostics also passed, with no warnings.
All ten actual initial prompts independently matched local tokenizer measurements.

| Generation probe | Input / output tokens | Result | Trace line |
| --- | ---: | --- | ---: |
| Short read action | 522 / 18 | Expected action, complete JSON | 4 |
| Tool-feedback roles | 613 / 10 | Expected finish | 8 |
| JSON enforcement | 42 / 9 | JSON despite bare-text request | 12 |
| Representative 10.5K | 10,500 / 12 | Expected finish | 128 |
| Representative 17K | 17,000 / 12 | Expected finish | 168 |

All usage/count deltas were zero. Tokenizer-only stress counts were 31,712 and
32,736, stable on repetition, with correct admission/rejection for the output
reservation. No near-window generation ran. Preflight used 28,677 input and 61
output tokens, excluded from attempt totals. The original repetitive-probe
failure remains unchanged and is not retroactively marked passed.

## Paired outcomes and resource use

| Task | Baseline | Skills | Main difference |
| --- | --- | --- | --- |
| announcement-subtitle | Fail, finished | Fail, finished | Both put filters in `if`; skills also rewrote protected schema and omitted section-ID escaping |
| asset-references | **Pass**, finished | Fail, turn budget | Skills used an `assets/` prefix in `asset_url`, ignored repeated MissingAsset feedback, and edited protected CSS |
| product-card | Fail, turn budget | Fail, turn budget | Both repeated identical invalid Liquid after five syntax-error checks; skills also omitted title fallback |
| section-schema | **Pass**, finished | Fail, finished | Skills repaired JSON values but replaced preserved markup with a render of a nonexistent snippet |
| shipping-message | Fail, finished | Fail, finished | Skills respected explicit false, but replaced null-threshold defaulting with unconditional free shipping |

| Task | Baseline input / output | Skills input / output | Calls, base / skills | Seconds, base / skills |
| --- | ---: | ---: | ---: | ---: |
| announcement-subtitle | 3,360 / 446 | 21,527 / 446 | 3 / 2 | 22.98 / 16.77 |
| asset-references | 3,340 / 154 | 134,522 / 489 | 4 / 12 | 8.74 / 22.05 |
| product-card | 19,993 / 885 | 136,711 / 680 | 12 / 12 | 34.20 / 32.08 |
| section-schema | 4,507 / 377 | 21,311 / 292 | 4 / 2 | 13.27 / 10.53 |
| shipping-message | 3,868 / 267 | 21,190 / 141 | 4 / 2 | 11.83 / 8.15 |
| **Total** | **35,068 / 2,129** | **335,261 / 2,048** | **27 / 30** | **91.03 / 89.58** |

Total token usage was **37,197 versus 337,309: 9.07×** for treatment. Input usage
alone was 9.56×. Every repeated entry/history token counted, regardless of server
prefix caching. These are measured token costs, not token-priced invoices:
Runpod billed rented GPU/storage time, and no per-token dollar rate was invented.

There were no context-budget, cumulative-token-budget, time-budget or output-length
stops. Maximum observed prompts were 2,760 baseline and 12,398 treatment tokens.
One baseline and two treatment attempts exhausted the **turn** budget. The other
seven emitted `finish`, which does not imply grader success.

Elapsed attempt time includes tool execution and grading. Similar aggregate
latency does not establish treatment efficiency: three treatment attempts skipped
reading/validation and finished wrong after two calls; cached prefixes and fixed
execution order also affect timing. No statistical or speed claim is made.

## Failure analysis with trace evidence

Trace paths are listed below; `L` refers to a JSONL line. Full model messages,
tool feedback, patches, final files and grading checks are retained locally.

### Announcement: syntax failure plus preservation regression

Baseline `base/20261023T190933Z-3ba4b449/trace.jsonl`: L3 reads the existing section;
L7 adds an `if` containing `section.settings.subtitle | strip != ''`; L11 finishes
without any validation. The strict Liquid parser rejects a filter inside the
condition. The schema-preservation check passes, but the syntax/render checks fail.

Treatment `skills/20261023T190956Z-30d96758/trace.jsonl`: L9 writes a replacement
without reading the file; L13 finishes without checking. Its condition still
contains `section.settings.subtitle | strip`. It also changes schema defaults,
labels and field types, removes presets, adds unresolved schema translation keys,
and removes escaping from the section ID. Grading rejects syntax, missing
translations and schema preservation. The behavioral render checks are not run
after preservation fails; do not interpret absent checks as passes.

### Assets: explicit validation feedback did not guide repair

Baseline `base/20261023T191035Z-2310ec70/trace.jsonl`: L3 reads, L7 writes the three
correct literal operands, L11 checks, and L15 finishes. All grader checks pass.

Treatment `skills/20261023T191013Z-51b802d3/trace.jsonl`: L13 writes
`'assets/promo-banner.css' | asset_url`; L19 explicitly reports
`'assets/assets/promo-banner.css' does not exist`. L21 and L25 request absent
settings files, generating the experiment's only two tool errors. It reads an
existing locale file at L29 but rewrites the same incorrect snippet at L33.
L41 and L49 change protected CSS instead of removing the redundant asset prefix.
Checks at L39, L47 and L55 repeat the unresolved-path error. The run reaches
12 turns without finishing; grading rejects edit scope before later checks.
This is valid tool use with incorrect repairs and scope violations, not a tool
transport failure. Both translation keys were corrected, but the task still fails.

### Product card: identical rewrites after repeated syntax errors

Baseline `base/20261023T191044Z-8b3e2cf2/trace.jsonl` writes at L7, L15, L23, L31,
L39 and L47. **All six file contents have the same SHA-256.** Checks at L13, L21,
L29, L37 and L45 report the invalid `if` containing `product.vendor | strip != ''`.
The model never changes that condition, reaches 12 turns and does not finish.

Treatment `skills/20261023T191118Z-11a898bc/trace.jsonl` writes at L13, L21, L29,
L37, L45 and L53; again **all six contents are identical within the run**. Checks
at L19, L27, L35, L43 and L51 identify the same class of syntax error, this time
`product.vendor | strip` inside `if`. It also omits the required title fallback
and does not trim the rendered vendor. Those additional omissions are visible in
the patch; syntax failure prevents the render checks from isolating their effects.

Both conditions call validation but fail to use its actionable feedback. The
harness returns findings inside a successfully executed `check` result (`ok:true`);
that means the tool ran, not that the file passed. No feedback was hidden or
truncated. The traces demonstrate repeated actions, not the model's internal
reasoning or why it ignored the findings.

### Schema: correct values do not excuse replacing protected markup

Baseline `base/20261023T191201Z-5337e77c/trace.jsonl`: L3 reads, L7 repairs duplicate
setting IDs, boolean/numeric defaults and preset values, L13 returns no offenses,
and L15 finishes. All grader checks pass.

Treatment `skills/20261023T191150Z-f75f9574/trace.jsonl`: L9 writes without reading;
L13 finishes without validation. The schema values in its patch match the requested
repair, but it deletes all original markup and inserts
`{% render 'feature-panel-content' %}`. That snippet does not exist. Grading rejects
`preserved_markup` and Theme Check's MissingTemplate finding. The evaluator stops
at that point, so this is not recorded as a schema-validation pass. General
component refactoring is incompatible with this task's explicit preservation rule.

### Shipping: false handling improved, null-threshold behavior regressed

Baseline `base/20261023T191214Z-d8b87f56/trace.jsonl`: L7 fixes empty-cart priority,
the inclusive boundary, message trimming/fallback and escaping. It retains
`settings.enabled | default: true`, which converts explicit false to the fallback.
The three disabled cases fail; the other fourteen semantic cases pass. Its L13
check has only an orphaned-snippet warning. Static syntax checks cannot establish
that the boolean behavior is correct; no render cases were exercised by the agent.

Treatment `skills/20261023T191226Z-b458c314/trace.jsonl`: L9 directly writes and L13
finishes, without reading or validation. `if settings.enabled` correctly preserves
false, and all three disabled cases now pass. However,
`cart.total >= settings.threshold or settings.threshold == null` makes every
nonempty cart with a null threshold qualify for free shipping. The contract
requires a threshold of 5000 in that situation. Nine below-threshold/message cases
fail; eight semantic cases pass. This is a **partial boolean fix**, accompanied by
a larger threshold regression, not a task success. The traces cannot establish
that a particular skill document caused either change.

## Document access and agent behavior

Every treatment attempt received all three unmodified entries at model turn 0:

- `skills/shopify-liquid-themes/SKILL.md`
- `skills/liquid-theme-standards/SKILL.md`
- `skills/liquid-theme-a11y/SKILL.md`

There were **15 delivered entry exposures and zero on-demand reference reads**.
None of the fourteen reference files was accessed. Baseline had zero skill
accesses. Injection records prove exposure, not attention or application.

| Behavior | Baseline | Skills |
| --- | ---: | ---: |
| Tasks reading a file before first write | 5/5 | 2/5 |
| Tasks invoking validation | 4/5 | 2/5 |
| `check` calls | 8 | 9 |
| `render` / `analyze` / `search` / `list_files` calls | 0 | 0 |
| Valid model action responses | 27 | 30 |
| Protocol errors / provider errors | 0 / 0 | 0 / 0 |
| Tool errors | 0 | 2 missing-file reads |

Extra checks in the treatment were concentrated in unsuccessful loops. More
validation calls did not mean better use of feedback. The missing-file errors
were model-selected paths rejected normally by the tool; all requests and
response accounting otherwise worked. No agent accessed evaluator data.

## Cost, cleanup and evidence

Runpod's live GPU catalog returned LOW A40 availability in CA-MTL-1 and EU-SE-1,
CUDA 13.2 capacity and **$0.59/hour**. The one Pod, **`4ye95u0h25wk0f`**, used
100 GB ephemeral disk and no persistent/network mounts. Creation was
**2026-10-23 19:07:12.345 UTC**; deletion was requested at **19:13:01 UTC**:
**348.655 seconds (5 minutes 48.655 seconds)**.

Estimated GPU cost: **$0.05714**. Estimated storage: **$0.00135** at
[$0.10/GB/month](https://docs.runpod.io/pods/pricing), using a 720-hour month.
**Estimated total: $0.05849**, before billing adjustments, well below the $2 cap.
The billing read had no posted records; settled cost is unknown, not zero.
No credits were purchased and no resource or session limit was increased.

Deletion returned 204. Independent verification at 19:13:08 UTC returned 404 for
the Pod, an empty Pod list and an empty network-volume list. The SSH tunnel closed
and the local test VM was stopped. No billable resource from this session remains.

The complete local archive is `runs/liquidbench-skills-ab-20261023.tar.gz`:
91 evidence files, each reread and SHA-256 verified after export.

```text
7dcdbc7f3c1af75c5dc564cbb156bd1a3c066942087862c6caf650f1e4de6aeb
```

It contains all ten traces, results, patches, final files and task manifests;
paired plan/analysis; preflight; serving/model hashes; price, approval and
cleanup records; and a per-file manifest. It includes upstream text in treatment
traces and **stays local**, since redistribution permission was not established.
No private SSH key or model weights are included. Committed
[machine-readable results](milestone-5-results.json) contain metadata, metrics,
trace references, check findings and hashes, without upstream skill bodies.

## Interpretation and next gate

There are two paired regressions, no gains and three unchanged task failures:
**40% versus 0%, a descriptive difference of −40 percentage points**. Five tasks
and one attempt per condition do not support a general effect-size or statistical
claim. The fresh baseline matches the prior pilot's 2/5 task pattern, but the old
8K pilot is historical context, not the control used here.

The main failures are Liquid grammar, semantic defaulting, preservation/scope,
and ineffective response to validation. JSON tool use and the serving/accounting
path were reliable. Longer context was admitted correctly; no reference-read or
context overflow occurred. We cannot separate the effect of guidance content,
its length, and instruction competition with this two-arm experiment.

For the next milestone, propose a **separately approved, preregistered development
expansion and replicated paired runs**, covering these failure families with
variation in difficulty and preservation constraints. Retain this pinned bundle
and this negative result. A separately declared length-matched neutral-context
control would help distinguish instruction content from context load; it must
not be improvised during a run or silently replace one of the future four
configurations. Review skill/task scope conflicts and validation-response behavior
before freezing that next design. Do not add targeted hints based on these answers.

Do **not** move to post-training on this evidence. Establish broader development
coverage, a defensible comparison protocol and eventual separation of training
and evaluation data first. No benchmark expansion, fine-tuning, training-data
generation, held-out tasks or leaderboard was implemented in this milestone.

The frozen preparation commit passed **230 tests**, including all **71 grader
verdicts**, and the real pipeline completed all ten graded attempts. This results
commit changes documentation/evidence only; GitHub CI is verified before handoff.
