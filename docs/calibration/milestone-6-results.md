# Milestone 6: complete four-condition development study

**All 240 predeclared attempts completed in their original order.** Block 0 was
retained; blocks 1–14 ran consecutively in one approved A40 session. No attempt
was replaced, omitted or selectively retried. No model, task, prompt, grader,
skill content or execution budget changed. No fine-tuning was started.

[Per-attempt CSV](milestone-6-attempts.csv) · [Complete metadata and paired counts](milestone-6-results.json)

## Correctness

Cells below are passing attempts out of 20 in each repetition. Aggregate counts
are descriptive; the three seed-42 repetitions are not independent samples.

| Condition | Repetition 1 | Repetition 2 | Repetition 3 | Total | Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 8/20 | 8/20 | 8/20 | **24/60** | 40.0% |
| Full skills | 1/20 | 2/20 | 2/20 | **5/60** | 8.3% |
| On-demand | 7/20 | 8/20 | 8/20 | **23/60** | 38.3% |
| Neutral | 2/20 | 2/20 | 2/20 | **6/60** | 10.0% |

All passing grades also had an explicit finish. Final code correctness and
attempt success agree here; turn-exhausted attempts did not hide additional
passing patches. There were no missing attempts or infrastructure pairs.

Per-task cells show passes across the three repetitions, not best-of-three:

| Task | Category | Difficulty | Baseline | Full | On-demand | Neutral |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| announcement-subtitle | section-modification | easy | 0/3 | 0/3 | 0/3 | 0/3 |
| asset-references | theme-references | easy | 3/3 | 2/3 | 3/3 | 3/3 |
| blocks-schema | section-schema | hard | 3/3 | 0/3 | 3/3 | 0/3 |
| cart-arithmetic | rendering | medium | 0/3 | 0/3 | 0/3 | 0/3 |
| customer-name | rendering | easy | 0/3 | 0/3 | 0/3 | 0/3 |
| eligibility-branch | liquid-syntax | hard | 0/3 | 0/3 | 0/3 | 0/3 |
| icon-reference | theme-references | easy | 3/3 | 0/3 | 3/3 | 3/3 |
| locale-references | theme-references | medium | 3/3 | 0/3 | 2/3 | 0/3 |
| notice-link | theme-modification | hard | 0/3 | 0/3 | 0/3 | 0/3 |
| option-list | rendering | medium | 0/3 | 0/3 | 0/3 | 0/3 |
| optional-caption | theme-modification | medium | 0/3 | 0/3 | 0/3 | 0/3 |
| product-card | liquid-rendering | easy | 0/3 | 0/3 | 0/3 | 0/3 |
| range-schema | section-schema | easy | 3/3 | 0/3 | 3/3 | 0/3 |
| section-schema | section-schema | easy | 3/3 | 0/3 | 3/3 | 0/3 |
| select-schema | section-schema | medium | 3/3 | 0/3 | 3/3 | 0/3 |
| shipping-message | conditional-logic | easy | 0/3 | 0/3 | 0/3 | 0/3 |
| status-priority | liquid-syntax | easy | 0/3 | 3/3 | 0/3 | 0/3 |
| stylesheet-pair | theme-references | hard | 0/3 | 0/3 | 0/3 | 0/3 |
| tag-membership | liquid-syntax | medium | 3/3 | 0/3 | 3/3 | 0/3 |
| visible-list-limit | theme-modification | hard | 0/3 | 0/3 | 0/3 | 0/3 |

Only two task/condition cells changed binary outcomes: full/asset-references and
on-demand/locale-references both went fail → pass → pass. Their initial-context
hashes matched across repetitions. Other patch variation is retained in the
metadata. Identical seeds and prompts did not ensure bitwise replay; host/cache/
order/numerical effects are possible explanations, not established causes.

## Paired wins, ties and losses

Wins are for the left condition. Each triple is W/T/L; ties include both-pass
and both-fail pairs. The JSON preserves both tie types, missing/infra counts,
and all six contrasts by repetition, original category, broad domain, difficulty
and category × difficulty. No scoring or grouping labels were changed.

| Comparison | Rep 1 | Rep 2 | Rep 3 | Descriptive total |
| --- | ---: | ---: | ---: | ---: |
| Full skills / Baseline | 1/11/8 | 1/12/7 | 1/12/7 | 3/35/22 |
| On-demand / Baseline | 0/19/1 | 0/20/0 | 0/20/0 | 0/59/1 |
| Neutral / Baseline | 0/14/6 | 0/14/6 | 0/14/6 | 0/42/18 |
| Full skills / Neutral | 1/17/2 | 1/18/1 | 1/18/1 | 3/53/4 |
| On-demand / Full skills | 7/12/1 | 7/12/1 | 7/12/1 | 21/36/3 |
| On-demand / Neutral | 5/15/0 | 6/14/0 | 6/14/0 | 17/43/0 |

Baseline solved all four schema tasks and three of four reference tasks in
every repetition, plus tag-membership. Full solved status-priority in every
repetition; no baseline or on-demand attempt solved it. All four conditions
scored zero in the rendering and theme-modification broad domains. Difficulty
labels are author-assigned development metadata, not calibrated ability levels.

## Tokens, latency and behavior

| Condition | Input tokens | Output tokens | Total tokens | vs baseline | Calls | Summed attempt seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 510,910 | 27,372 | 538,282 | 1.00× | 375 | 1352.85 |
| Full skills | 2,451,441 | 17,502 | 2,468,943 | 4.59× | 226 | 966.75 |
| On-demand | 544,855 | 25,848 | 570,703 | 1.06× | 392 | 1326.34 |
| Neutral | 3,076,219 | 19,142 | 3,095,361 | 5.75× | 280 | 1112.61 |

| Condition | Read before first write | Any validation call | Finished | Turn limit | Tool errors | Peak prompt |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 60/60 | 48/60 | 45 | 15 | 15 | 4,458 |
| Full skills | 6/60 | 17/60 | 53 | 7 | 30 | 12,438 |
| On-demand | 60/60 | 54/60 | 47 | 13 | 6 | 4,408 |
| Neutral | 18/60 | 26/60 | 53 | 7 | 7 | 13,017 |

Validation means at least one `check`, `analyze` or `render` call, not successful
validation or acting correctly on feedback. No attempt hit the time, context or
cumulative-token ceiling; no output was truncated. All 1,273 model calls had
zero input-count discrepancy, with zero provider or action-protocol errors.
Tool errors were recorded model actions such as missing reads or unsupported
renders, not transport failures. Total usage: 6,583,425 input + 89,864 output
= **6,673,289 tokens**. Cached input still counts fully against the shared budget.

Full received all three unmodified entry documents in each attempt: **180 entry
deliveries**. Neither full nor on-demand explicitly read any skill document.
On-demand saw only the fixed index; baseline and neutral had no skill access.
The entries were `shopify-liquid-themes/SKILL.md`, `liquid-theme-standards/SKILL.md`
and `liquid-theme-a11y/SKILL.md`, under the pinned upstream `skills/` directory.
Exposure is not evidence of attention or use. The raw full/neutral overhead
remained matched at 9,815 tokens (9,820 in the chat prompt); on-demand added
85 raw / 90 chat tokens. No content was summarized or truncated.

Full/neutral consumed more input tokens but often wrote and finished sooner,
without reading or validating. Their lower elapsed time is not an efficiency
win at equivalent correctness. Latency includes local grading; session reuse,
prefix caching, network and different action sequences confound direct causal
speed comparisons. Per-attempt and per-block measurements remain available.

## What failed, and what the skills changed

These are observations from saved patches, binary grader checks and trace actions,
not new scoring rules. The JSON report links every observation to an artifact path,
trace/result/patch hashes, action line numbers and validation feedback. Representative
manual audits cover all 20 tasks and the outcome-changing repetitions; aggregates
cover every attempt. The original [Block 0 analysis](milestone-6-block-0-results.md)
remains unchanged as historical evidence.

| Task | Observed failure or successful repair |
| --- | --- |
| announcement-subtitle | Baseline/on-demand put a filter inside an `if` condition. Full also replaced protected schema/defaults. Neutral used rendering feedback to fix syntax but still mishandled null/whitespace. |
| asset-references | Baseline/on-demand/neutral repaired literals. Full repetition 1 used a doubled `assets/` prefix and edited protected CSS despite MissingAsset feedback; repetitions 2–3 repaired the literals successfully. |
| blocks-schema | Baseline/on-demand preserved the section and repaired settings. Full/neutral wrote bare JSON, losing schema delimiters and surrounding markup. |
| cart-arithmetic | Baseline/on-demand retained unsupported filters after repeated diagnostics. Full/neutral used known filters but calculated `(total + price) × quantity`, used absolute value instead of a zero clamp, then added an unauthorized section. Their recorded verdict is scope failure; arithmetic is a separate inspection finding. |
| customer-name | Trimming, joining, fallback and escaping remained wrong. Baseline fixed `trim` to `strip` after feedback but removed internal spaces; on-demand substituted `strip_html`. A clean public check did not establish semantic correctness. |
| eligibility-branch | Parenthesized conditional expressions are invalid in this Liquid runtime. Full finished without validation; other conditions repeatedly retained the syntax despite feedback and exhausted turns. |
| icon-reference | Baseline/on-demand/neutral repaired the literal while preserving markup. Full repeatedly used core Liquid rendering with Shopify `asset_url`, which that public renderer does not support; its final attribute reordering also violated the declared preservation contract. This is not proof that the final markup is invalid Shopify HTML. |
| locale-references | Baseline repaired both keys. Full replaced required literals/markup with a parameterized LiquidDoc snippet; neutral retained a misspelled key. On-demand failed repetition 1 and passed repetitions 2–3. |
| notice-link | Baseline/on-demand placed the link inside the paragraph, omitted URL trimming and changed the supplied `body` variable after a static warning. Full/neutral replaced protected schema or markup. |
| option-list | All conditions lost the required unselected `option` class in representative patches. Full/neutral also suppressed the required empty list. Valid Liquid alone was insufficient. |
| optional-caption | Baseline/on-demand used a filtered condition and finished without checking. Full/neutral overwrote protected schema and surrounding section structure. |
| product-card | Every condition repeatedly emitted a filter inside an `if` despite syntax feedback and exhausted the 12-turn allowance. Full/neutral also had fallback defects. |
| range-schema | Baseline/on-demand made the narrow step repair. Full knew the step value but replaced required markup/other schema fields; neutral wrote bare, incorrectly nested JSON. |
| section-schema | Baseline/on-demand repaired settings/presets. Full corrected requested fields but replaced markup with a missing snippet render; neutral removed the section wrapper. |
| select-schema | Baseline/on-demand repaired the default while preserving structure. Full misplaced settings at the schema top level and introduced a missing render; neutral wrote bare/wrongly nested JSON. |
| shipping-message | Baseline/on-demand retained `enabled | default: true`, overriding explicit false. Full/neutral used a direct boolean test and passed disabled cases, but null threshold/fallback or message logic still failed. No condition passed the task. |
| status-priority | Full passed with explicit `if`/`elsif` priority. Baseline/on-demand invented unsupported boolean-to-string filters despite feedback. Neutral's final priority logic was plausible, but it added an unauthorized section after an orphaned-snippet warning, so failed scope. |
| stylesheet-pair | Baseline/on-demand repaired CSS references but changed protected locale resources to accommodate a wrong translation key. Full changed the required reference structure; neutral doubled the asset prefix and retained the locale typo. |
| tag-membership | Baseline/on-demand used ordered `contains` branches correctly. Full produced plausible snippet logic but added an unauthorized section after a warning; neutral emitted multiple matches without the required priority/default. |
| visible-list-limit | Baseline/on-demand reacted to a warning about supplied `rows` by changing its source and adding an unsupported schema type. Full/neutral replaced protected section/schema/empty-state structure. |

Representative trace anchors (repetition 1 unless stated otherwise):

- Announcement baseline: read/write/finish at lines 3/7/11; neutral syntax feedback
  at 15 followed by rewrite 17 and render 21. This shows an actual correction that
  still did not meet all acceptance cases.
- Asset full: MissingAsset feedback at 19/39/47/55 and protected CSS writes at 41/49.
  Preserve this failed repetition alongside the later passes.
- Arithmetic baseline: repeated checker feedback at 13/21/29/37/45; full created
  the unauthorized section at 17, neutral at 13/21.
- Icon full: unsupported-render feedback at 15/23/31/39/47/55. Repeated validation
  calls consumed turns without establishing correctness.
- Customer baseline: unsupported-filter feedback at 13, rewrite at 15, finish 23.
  Removing that error did not fix the remaining semantic requirements.

The full treatment's status-priority wins and improved boolean-false handling are
real local observations, but they do not establish a general benefit. Neutral also
fixed the disabled boolean cases, and its status-priority loss was a scope violation
rather than incorrect branch priority. Full's LiquidDoc rewrite is consistent with
the injected upstream snippet guidance, but the trace does not establish causation
or attention to any particular document. No explicit skill retrieval occurred.

Transport, JSON action parsing and token accounting worked. Model mistakes include
invalid syntax, invented filters, missed edge cases, failure to preserve supplied
structure, and unproductive reactions to public validation feedback. There are also
important tool/task limitations: the public core renderer is not a complete Shopify
engine; static warnings about supplied variables or orphaned snippets can distract
the agent from a narrow repair; preservation checks can reject otherwise plausible
rewrites. These limits are documented without changing grades or retroactively
classifying model actions as infrastructure outages.

## Interpretation and next experiment

The full bundle substantially reduced correctness while consuming more tokens.
The neutral condition also regressed, which is compatible with context length,
distraction or message-format effects. This control does not isolate a pure causal
length effect: its synthetic content differs from skills, and trajectories use
different numbers of turns. Full's narrow task wins show content can matter too.

On-demand stayed close to baseline but never retrieved a document. That tests the
availability/index policy, not the value of reading relevant skills. A next study
should predeclare a task-independent selection/loading policy that reliably causes
document access, compare it with an appropriately matched neutral loading control,
and preserve unmodified upstream bodies. Select documents from the public task and
skill index, not from solutions or failure-specific hints. Budget any selector and
document reads explicitly; run a fresh controlled baseline if the protocol changes.

Before investing in post-training, separately test a general instruction/tool
clarification that distinguishes public validation warnings from task requirements
and makes renderer support explicit. Apply any such change equally to all arms in
a new frozen version; do not repair this study or silently change the existing one.
The current schema/reference tasks provide useful variation, while rendering and
theme-modification tasks remain at a floor. A larger development sample may help
after a loading policy actually exercises retrieval; merely repeating this inert
on-demand policy is unlikely to answer the intended question.

These 20 development tasks and three seed-42/temperature-zero repetitions are not
held-out research findings or 60 independent tasks per condition. Report repetitions
separately, with descriptive totals only: no significance claim, pass-at-k selection
or causal conclusion about Ben's skills in general. Runtime caching, order, host and
different action trajectories also limit latency comparisons. No training examples,
fine-tuning, new tasks or leaderboard were produced.

## Execution, spending and cleanup

Session 02 used one A40 48 GB Secure Cloud Pod, `sqk87w1rrz1oa2`, EU-SE-1,
at the rechecked $0.59/hour rate with 100 GB ephemeral disk and no persistent
or network volume. There was no substitution, extra rental, top-up or extension.
The approved 120-minute block-admission reserve and 15-minute final cleanup
reserve were used; neither constrained the completed schedule.

Pinned Qwen revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, BF16, the pinned
vLLM image/package versions, all 14 model/tokenizer files and startup command
matched Block 0. vLLM 0.32.0, torch 2.13.0+cu130, transformers 5.19.0,
tokenizers 0.23.3 and xgrammar 0.2.8 were recorded. Context 32,768, cumulative
budget 393,216, 12 turns, 1,024 output tokens, 300 agent seconds, temperature
zero, seed 42, TP1/one sequence and prefix caching stayed unchanged.

Preflight v2 ran at 22:14:26 and refreshed at 23:10:35 UTC before block 10.
Both passed all six checks, with no diagnostic model failures or retries.
Every block entered with a report younger than one hour; refresh was scheduled
at 50 minutes between blocks. Across all 15 blocks, **1,200 initial token-count
checks** matched. The evidence audit verified exact chronological plan order,
source/config/runtime hashes, clean execution trees, file integrity and token sums.

| Session 02 measure | Observed |
| --- | ---: |
| Creation → verified cleanup | 95.198 minutes |
| Blocks 1–14, including count gates | 84.454 minutes |
| Preflights | 104.884 seconds |
| Summed 224 attempt durations | 73.867 minutes |
| Runner throughput | 159.14 attempts/hour |
| Full rental throughput | 141.18 attempts/hour |
| Execution end → verified cleanup | 19.712 seconds |
| Estimated GPU | $0.936114 |
| Estimated disk | $0.022037 |
| Estimated session total | **$0.958150** |
| Posted partial billing, through 23:00 UTC | $0.391978 |
| Settled full charge | Not yet available |

Created 2026-10-23 22:05:51.120 UTC; deletion requested 23:40:58; absence
verified 23:41:03. The 95m11.88s lifetime is below the eight-hour cap. The
estimate is below $6 and uses lifetime × live rate, including cold startup,
plus disk at $0.10/GB/month with a 720-hour month. It is conservative, before
unreported adjustments, and is not a settled invoice. The first posted hourly
bucket is partial; the unknown final charge is `null`, not zero. Including
Block 0, the whole study's lifetime-based estimate is **$1.131642**.

Host logs, traces, final snapshots, patches, grades and metadata were exported
and hashed before deletion. Runpod deletion returned 204; independent get
returned 404; Pod and network-volume lists were empty. Ephemeral storage
was deleted with the Pod. The SSH tunnel ended and the local runtime VM
was stopped. `caffeinate -is` kept the Mac awake through the supervised run.

## Evidence and validation

Execution commit: `5dac94a3e5596d31dc9d438cd2c581539ee5b1b5` (Block 0 used
`702d53896c65e74971e13afbefa33c81c3c60e9c`). Only operational documentation
differed; frozen Python source digest
`63be28169db8365064dc6dc8e7228a1ed3178dc2975828221dd7122ec5991828`
and plan file SHA-256
`5155fe8ce80adaafd0d6bd8c23da71f2aa9d99d7e1a345433811bff812bac2f0`
matched throughout. Every result recorded a clean tree.

[Execution CI passed](https://github.com/Sahaj0312/liquidBench/actions/runs/40031408313):
**186 unit + 282 integration tests**, including all **236 grader verdicts**,
plus lint/format checks. The final report commit also runs the same CI.
No benchmark implementation or tests were altered for these results.

Reproduce core comparisons from private evidence with:

```sh
uv run python scripts/analyze_loading_study.py runs/m6/block-*/attempts
```

The archive also retains the analysis/audit/export scripts used for additional
behavioral metrics and trace checks. Raw traces include upstream skill bodies;
redistribution permission remains unestablished, so only reviewed metadata is
committed. Complete evidence stays local. See the archive paths and hashes below.


- `runs/m6-complete-study-predelete-evidence.tar.gz` (5,090,455 bytes), SHA-256
  `3b4a9e976f6f8b4bd2bec6b5402f720d88e7ffcf50109d8d84bed0a7a5adc3fb`.

- `runs/m6-complete-study-final-evidence.tar.gz` (5,165,530 bytes), SHA-256
  `ccb1fd3d26a575d9b8dd23163be1ea987b4ce80b7fe7559bffd93d6fc2fb83a8`.
