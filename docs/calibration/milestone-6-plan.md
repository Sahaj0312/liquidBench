# Milestone 6: expanded development coverage and loading study

Status: **all 240 predeclared attempts completed; GPU/storage cleanup verified**.
See the [complete comparison](milestone-6-results.md), retaining the original
[Block 0 report](milestone-6-block-0-results.md). Blocks 1–14 ran in their frozen
order in one separately approved session. The preparation and experimental rules
below are preserved; no further paid execution or post-training is authorized.
The four-condition plan is frozen in [m6-plan.json](../../experiments/m6-plan.json).
The [exact tokenizer report](milestone-6-feasibility.json) binds that plan, including
all task digests, Python source, system instructions, configs, and document hashes.
This does not establish a skills benefit or a research benchmark result.

The previous [development comparison](milestone-5-results.md) remains 2/5 baseline
versus 0/5 full skills, with 9.07× treatment tokens. It motivates these hypotheses;
it is not a control arm for this new experiment. The original five fixtures,
evaluators, system instructions, preflight v2 policy, skill pin/content, inference
settings and per-attempt budgets are unchanged. The historical M5 runner now
explicitly selects its original five IDs instead of discovering the expanded suite.

## Development coverage and acceptance contracts

There are 20 tasks: nine labeled easy, six medium, five hard. Difficulty labels
are author estimates, not calibrated difficulty scores. All fixtures are original
synthetic development data. Nothing is held out; nothing is a training dataset.
The eventual held-out benchmark must use separately authored families, content
and cases. Repository readers can inspect these development oracles; benchmark
agents cannot access them through their workspace or tools.

| Task | Difficulty | Domain and objective | Candidate verdicts |
| --- | --- | --- | ---: |
| product-card (original) | easy | Title/vendor fallback, availability and escaping | 8 |
| shipping-message (original) | easy | Conditional priority, threshold and boolean/null fallback | 13 |
| section-schema (original) | easy | Settings and preset consistency | 19 |
| asset-references (original) | easy | Stylesheet and locale references | 16 |
| announcement-subtitle (original) | easy | Optional content and existing behavior | 15 |
| status-priority | easy | Archived/stock/sale priority with overlapping predicates | 10 |
| tag-membership | medium | Exact array membership, priority, case and substring distinctions | 10 |
| eligibility-branch | hard | Enabled/stock guards and nested AND/OR logic | 10 |
| customer-name | easy | Independently trimmed null/string name parts and joining | 10 |
| option-list | medium | Ordered filtering, selection, duplicate values and label fallback | 10 |
| cart-arithmetic | medium | Integer accumulation, quantities, discount and zero clamp | 10 |
| select-schema | medium | Select option values/order, default and preset | 12 |
| range-schema | easy | Numeric range, fractional step, default and preset | 12 |
| blocks-schema | hard | Block definition/limit and ordered preset blocks | 12 |
| icon-reference | easy | Literal SVG asset reference with preserved image markup | 12 |
| locale-references | medium | Two distinct translation keys resolving in two locales | 12 |
| stylesheet-pair | hard | Two ordered stylesheets plus a translated heading | 12 |
| optional-caption | medium | Conditional trimmed caption preserving heading/footer/schema | 11 |
| notice-link | hard | Conditional relative link, label fallback and preserved content | 11 |
| visible-list-limit | hard | First N visible rows, duplicates, empty state and preservation | 11 |

The **236 expected verdicts** comprise 20 failing starters, 20 passing references,
19 passing alternatives and 177 deliberately incorrect submissions. The original
71 expectations remain unchanged. Each new task has a reference and a valid
alternative (formatting, JSON key order, quote style or translation alias), plus
several task-specific semantic mistakes and adversarial candidates. Negatives
include wrong branch priority, substring matching, boolean default coercion,
missing escaping, wrong numeric types, duplicate JSON keys, dead/commented outputs,
changed preserved structure/schema, hardcoded first-case output, unauthorized
files, suppression directives and deletion. A correct verdict on these candidates
is a grader check, not model task performance.

Three small registry evaluators avoid new per-task branches:

- `render-contract-v1`: strict core Ruby Liquid renders against supplied variables,
  then exact allowed DOM structure, attributes and leaf text. Expected DOM values
  were authored independently in Python from each public specification, not copied
  from the reference's rendered output. Inter-element whitespace and comments are
  immaterial; unexpected markup/text fails. Modification cases also preserve the
  entire original top-level schema block byte for byte.
- `schema-contract-v1`: exactly one top-level schema, strict JSON with duplicate-key
  rejection, specified fields/types/array order and unchanged surrounding source.
  Object-key order and JSON formatting are immaterial. Schema contracts are
  intentionally explicit; they do not claim to accept every possible Shopify theme.
- `reference-contract-v1`: the live parsed AST preserves markup/output/filter
  structure while checking required literal operands. It ignores quote/formatting
  metadata and accepts `translate` as the alias of `t`. Protected assets/locales
  cannot change; Theme Check verifies static references. Matching text in a comment
  or dead branch cannot replace the required live expression. This is deliberately
  a literal-reference repair task, not arbitrary program equivalence.

Shared edit-scope, suppression and Theme Check gates still run. Grading stays
binary, in a fresh isolated container. No hidden case, reference solution, skill
checkout or host path is mounted into the agent container. Public tools retain
only their original workspace scope. Existing canary/isolation and full-pipeline
reference tests now cover all 20 tasks. Candidate failures caused by a runtime
fault are not counted as correct rejections.

These tests exercise a documented subset, not a hosted storefront or theme-editor
integration. Core rendering does not emulate Shopify `asset_url`, `stylesheet_tag`
or translations; those tasks use static checks. Settings and blocks follow
[Shopify's section schema](https://shopify.dev/docs/storefronts/themes/architecture/sections/section-schema)
and [input settings](https://shopify.dev/docs/storefronts/themes/architecture/settings/input-settings).
Finite cases cannot prove universal correctness or defeat every case-hardcoding
attack. Additions were validated locally before freezing; no model outputs selected
these fixtures. The new icon reference initially lacked image dimensions: local
Theme Check caught it, and width/height were added to its initial/reference/contract
before freeze. No existing task or checker was relaxed.

## Four fixed exposure policies

All conditions receive the identical system instructions, task prompt, tools,
initial files, graders, JSON decoding and execution budgets. Only document
availability and the extra user-message content differ. Permissions on the
existing `read_file`/`list_files` namespace implement the treatment; no new tool,
search retrieval, automatic relevance routing or extra turn allowance is added.

| Condition/config suffix | Initial extra user message | Accessible skill documents |
| --- | --- | --- |
| `base` | None | None; guessed skills paths fail |
| `full` | The existing wrapper and all three original entry documents, unchanged | All 17 pinned documents through `read_file` |
| `on_demand` | Fixed index of all three entry paths and generic reading instructions | The same 17 documents; model chooses whether/what to read |
| `neutral` | Fixed unrelated prose/quantity/JSON records | None; guessed skills paths fail |

Ben Sehl's [upstream repository](https://github.com/benjaminsehl/liquid-skills/tree/483f969bed623c87c9e26ac34324d8d7d8fe68c3)
remains pinned at `483f969bed623c87c9e26ac34324d8d7d8fe68c3` in the inventory
(the authoritative full SHA is in `skills/liquid-skills.lock.json`). The original
content is verified against Git objects and file hashes, never summarized,
reordered internally, or edited. No redistribution grant was established for that
snapshot. Continue fetching locally into the ignored checkout; do not commit
upstream bodies, full treatment traces or training examples.

The on-demand index is the same for every task and contains paths, not descriptions,
solutions, prior-failure hints or recommendations. It does not force even an entry
read. `list_files` can reveal all available paths; relative links are resolved by
the model using exact paths. Each `read_file` consumes a normal turn and returns
complete original text, including front matter. Full and on-demand reads have the
same accounting and read-only restrictions. A document returned after the final
model turn is a read request, not observed model exposure.

The neutral control is one deterministic prefix of the existing varied synthetic
preflight corpus, preceded by `Reference notes:`. It mixes seven locations, seven
materials, five unrelated observations, quantities and JSON records. Prefix length
was selected **only by the pinned tokenizer**, once, without model generations or
success feedback. It has no Liquid guidance, skill text, task examples, tool-use
instructions or instruction-following test. Its committed bytes and hash are fixed.
This is a structured synthetic control, not representative natural prose. It tests
sensitivity to this particular unrelated context; it cannot identify a universal
causal effect of length or disentangle formatting, salience, relevance and wording.

## Exact feasibility and unchanged limits

Tokenizer files are hash-verified against the original pinned checkpoint.
Transformers 5.19.0, tokenizers 0.23.3 and Jinja2 3.1.6 render the same chat template.
No weights or inference are needed for these measurements.

| Condition | Extra message tokens (raw) | Added chat tokens | Initial task prompt range |
| --- | ---: | ---: | ---: |
| base | 0 | 0 | 584–712 |
| full | 9,815 | 9,820 | 10,404–10,532 |
| on_demand | 85 | 90 | 674–802 |
| neutral | 9,815 | 9,820 | 10,404–10,532 |

Full and neutral match **exactly on every one of the 20 initial conversations**.
After any one available-document read, full reaches at most 16,821 input tokens
and on-demand at most 7,091. Each fits input + 1,024 output + 32 margin <=32,768.
Repeated reads/edits can still exhaust context; histories are never truncated or
summarized. The feasibility report records every single-read count, not a guarantee
that all 12 turns can fit any arbitrary interaction.

Common limits remain 32,768 context; 393,216 cumulative reported input+output tokens;
12 turns; 1,024 output tokens per response; 300 seconds per attempt; 90-second request
timeout; two transient provider retries; temperature 0; top_p 1; seed 42; JSON object
mode. Repeated/cached context counts in full on every completion. Document reads
increase future prompt usage and consume turns; they are not a free side channel.
Neutral and full have equal initial overhead, not equal total tokens after their
trajectories diverge. Do not pad baseline, force reads, increase budgets or tune
prompts based on observed scores.

## Predeclared repetitions, pairing and stopping

The plan has **240 attempts: 20 tasks × four conditions × three repetitions**.
All repetitions retain seed 42 and temperature zero. They measure reproducibility
and backend nondeterminism; they are **not 60 independent task samples per arm**.
Use unique tasks as the unit of diversity; present repeats separately. No best-of-N,
pass@k or inferred statistical significance from repeated deterministic calls.

Tasks are sorted by ID, rotated by seven positions per repetition. Condition order
cycles through the four conditions with offset `(task_position + repetition_index)
mod 4`. Every condition appears five times in each ordinal position per repetition.
Each consecutive group of four tasks is a predefined block (0–14), containing
16 attempts and one appearance of every condition in each position. Every attempt
starts a fresh sandbox and history; the same model deployment and cache setting
serve all four conditions. Record block/session/host/order: cache warmth, driver
and time effects can still affect latency. Prefix caching remains enabled as in M5.

Run blocks in numeric order. Task/model failures continue; infrastructure failures
stop the session and leave explicit missing pairs. Preserve all failed/partial
attempts. Do not replace them, resume within a block, change selection or stop based
on a promising/disappointing score. A subsequent approved recovery must retain
missingness and be identified as a separate protocol amendment, not silently merged.
Deadline/budget termination is operational missingness, not a model failure.

The runner rejects a changed plan/source/task/config, stale/mismatched v2 preflight,
local/endpoint initial-count disagreement, or different built runtime image. It
records gate failures before task execution. Serving-evidence input is archived
by hash: an operator must actually verify its content; the CLI does not attest
remote BF16/checkpoint settings merely from a filename or endpoint model name.

## Evidence and predeclared analysis

Retain per-attempt task/config/source/image digests, complete trace, final files,
patch, hidden grader results, termination, provider usage/incomplete-usage flag,
latency and errors. Keep model bodies and skill content in private local evidence.
`skill_accesses` separates injection and explicit reads with requested/delivered
turns; `context_exposures` separately records index/neutral hash, bytes and first
completed model call. Exposure or reading does **not** prove that guidance was used.

Join on `(task_id, repetition, condition)`. The analysis script rejects duplicate
attempts, mixed plans/configs/source/digests, and prints missing/infra outcomes
rather than filtering them. Report each repeat's paired task table; totals by
category and proposed difficulty; task-level win/tie/loss for full/base,
on-demand/base, neutral/base, full/neutral, and on-demand/full. Also show original
five versus new fifteen descriptively. No post hoc subset replaces the full table.

For each pair compare raw grader correctness separately from successful explicit
submission, token totals/input/output, context and time exhaustion, validation tool
counts/order, read-before-edit behavior, and subsequent changes after feedback.
Manually audit trace line numbers and patches for these descriptive failure labels:
Liquid syntax/semantics (including boolean false/default behavior), schema/reference
contract violations, preservation/escaping errors, tool/protocol misuse, ignored
validation feedback, premature finish, output/turn/context/time exhaustion, and
infrastructure failure. Multiple labels are allowed; ambiguous causes stay unknown.
A `check` call alone is not proof of validation or responsiveness. Record what it
returned and whether the next saved code addressed it. Cite accessed document paths
and concrete patch changes before attributing an apparent skill-informed correction.

Interpretation rules: if neutral and full both degrade, length/distraction is
plausible but not proven. If full is worse than matched neutral, skill content or
instruction interaction is implicated, not isolated. If on-demand improves, inspect
whether it actually read relevant documents; a no-read gain is not evidence of
knowledge transfer. Any gains must be weighed against read turns, cumulative tokens,
latency and regressions. With 20 authored tasks and deterministic repeats, report
exploratory patterns, not held-out findings, causal identification or significance.

## Future deployment, approval and compute estimate

**No prior GPU approval carries into this milestone.** No rental/API purchase was
made for preparation. Obtain fresh approval with a concrete session deadline and
all-in dollar cap. Recheck live A40 price, capacity, CUDA/driver compatibility,
storage rate and remaining credit before spending. Do not substitute a GPU.

Use [preflight v2](preflight-v2.md) and its pinned deployment command unchanged:
Qwen2.5-Coder-7B-Instruct revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`;
BF16 weights/KV, no quantization, one sequence/TP1, GPU utilization 0.9;
vLLM image `sha256:6ee133356d49ed24cee03dd0cda3d3980279a11c107ce3e752c89e76540f41c9`;
vLLM 0.32.0, torch 2.13.0+cu130, transformers 5.19.0, tokenizers 0.23.3,
xgrammar 0.2.8; generation config `vllm`. Verify weight/tokenizer hashes, startup
command, BF16 and serving versions from host evidence. Model metadata alone cannot
prove those settings. Local runtime must be the original recorded image ID from
the frozen plan. A different platform build needs an explicit amendment, not bypass.

The last observed A40 rate was **$0.59/hour**; 100 GB ephemeral storage at
$0.10/GB/month adds ~$0.013889/hour (720-hour convention), or **$0.603889/hour**
combined. These are historical planning rates, not a live quote or an all-in bill.

| Scenario for 240 attempts | Attempt time | Plus assumed startup/preflight/export | Rental estimate before tax/adjustments |
| --- | ---: | ---: | ---: |
| 20 seconds average | 1.33 h | 1 h | $1.41 |
| 60 seconds average | 4 h | 1 h | $3.02 |
| 120 seconds average | 8 h | 1 h | $5.44 |
| Every attempt uses 300 seconds | 20 h | 7.5 h (15 separate blocks ×30 min) | $16.61 |

These are scenarios, not predicted durations. Startup, download, public tools,
grading outside the agent loop, exports and sessions must also be paid for. The
300-second limit is not a hard Pod deadline: an in-flight tool/final grading can
extend wall time. Reserve explicit headroom and monitor the external spend/deadline.
One 16-attempt block has 80 minutes of nominal agent budget; a conservative planning
envelope is 110 minutes including setup/export, ~$1.11 before tax at the historical
rate. This **would require new duration/cost approval**; it does not fit inside the
previous 90-minute authorization by assumption. Faster blocks may share a session
if its approved deadline/cap and fresh preflight permit. Do not start a block
without room for its worst-case completion/export; stop before the approved limit.
The maximum declared task-token allowance is 94,371,840 total tokens across 240
attempts, not an expected usage or a token-priced Runpod invoice.

Commands below prepare/verify locally. The cached tokenizer is initialized by the
historical measurement script if absent; do not overwrite the historical report:

```sh
uv run python scripts/prepare_skills.py
uv run --with transformers==5.19.0 --with tokenizers==0.23.3 --with jinja2==3.1.6 \
  python scripts/measure_skills.py --output .cache/tokenizer-bootstrap.json
uv run --with transformers==5.19.0 --with tokenizers==0.23.3 --with jinja2==3.1.6 \
  python scripts/prepare_loading_study.py
uv run python scripts/run_loading_study.py  # dry plan, no endpoint call
```

After fresh explicit approval and host verification, run preflight once for the
session. A mandatory failure stops deployment; diagnostic model failures remain
in evidence and do not trigger prompt tuning. Run a block only with a matching
report less than one hour old. All 80 initial prompts must agree with local counts
before any attempt. A new session uses a new output path and fresh gate.

```sh
uv run python scripts/preflight_endpoint.py --config configs/m6-base.json \
  --output runs/m6/session-01/preflight
uv run python scripts/run_loading_study.py --execute --block 0 \
  --preflight runs/m6/session-01/preflight/report.json \
  --serving-evidence runs/m6/session-01/serving.json --output runs/m6/block-00
uv run python scripts/analyze_loading_study.py runs/m6/block-*/attempts \
  > runs/m6/comparison.json
```

Export and hash all evidence before deleting the Pod and ephemeral storage. Verify
cleanup independently by get/list; include actual billing records when available.
Do not publish upstream content. Later blocks retain the same frozen plan and
follow numeric order; approval and current gate are operational requirements.

Recommendation: run this frozen four-condition development study before any
post-training. It can reveal whether smaller exposure helps, whether the neutral
control reproduces degradation, and whether new tasks produce useful difficulty
variation. If nearly all tasks are uniformly easy/hard or effects are inconsistent,
revise development coverage in a separately versioned study before designing a
held-out evaluation. Do not generate training data or optimize skills from this run.

## Preparation validation

Local checks passed **466 distinct tests: 184 unit and 282 container integration**.
The integration sweep passed 281 tests; the newly parameterized full/on-demand
container isolation check then passed both modes (one additional distinct test).
This includes all **236 expected grader verdicts**, all 20 reference-fixture
pipeline runs and all 20 initial-workspace isolation checks. Ruff lint, formatting,
exact-token feasibility, and the dry experiment plan also pass. Tests use scripted
providers and synthetic skill documents; these are not Qwen task scores.

[Validation metadata](milestone-6-validation.json) records the plan, runtime and
local log hashes. GitHub Actions runs the complete unit/container suite on the
pushed commit; its status is reported separately in the handoff. No model server,
paid GPU, training job or training-data export was created for this preparation.
