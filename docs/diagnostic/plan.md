# Diagnostic v1 plan (frozen, not run)

**Status:** prepared and frozen. No GPU rented. No paid inference. No fine-tuning.
Milestone 6 evidence is unchanged. Execution requires new explicit approval.

Diagnostic v1 asks why full skills loading scored worse than baseline in Milestone 6. It
separates three possible causes:

1. The model's underlying Liquid ability
2. The tool instructions and renderer limitations
3. How skill content is loaded

Frozen artifacts:

| Artifact | Digest / location |
| --- | --- |
| Plan | `experiments/diagnostic-v1-plan.json`, fingerprint `3e889c605178bc21…` |
| Neutral controls | `controls/diagnostic-v1/<task>.txt`, SHA-256 in the plan |
| Clarification text | `CLARIFICATION` in `src/liquidbench/diagnostic.py`, `efae0340b471e5ce…` |
| Base system prompt | `SYSTEM` (unchanged from Milestone 6), `130d38c607cce4a0…` |
| Python source digest | `2ffe52e933298721…` |
| Skills | upstream revision `483f969bed623c87c9e26ac34324d8d7d8fe68c3`, unmodified |
| Serving pin | `experiments/diagnostic-v1-serving.json` (copied from Milestone 6 session 02) |
| Benchmark audit | [benchmark-audit.md](benchmark-audit.md) |

Verify without changing anything:
`uv run --with transformers==5.19.0 --with tokenizers==0.23.3 --with jinja2==3.1.6 python scripts/prepare_diagnostic.py`.
This command rebuilds the plan from the inputs and fails on any difference.

## Conditions

| Condition | System prompt | Extra context message (before the task) |
| --- | --- | --- |
| `original` | Milestone 6 `SYSTEM` | none |
| `clarified` | `SYSTEM` + clarification | none |
| `reference` | `SYSTEM` + clarification | One selected upstream reference document, full and unmodified |
| `neutral` | `SYSTEM` + clarification | Token-matched neutral records |

The clarification is generic tool-protocol text. It covers what `render` cannot emulate,
what `check` severities mean, why `analyze` output is not replacement source, and what
preservation requires. It contains no task IDs, solutions or task-specific hints.

`reference` and `neutral` use the same wrapper header, message role and position. Their
initial prompts are **exactly equal in tokens** for every task. No condition enables a
skill-read tool, so "exposure" equals "delivery" in every arm.

Shared across all arms: the same Qwen2.5-Coder-7B-Instruct checkpoint
(`c03e6d35…`), the pinned A40/BF16/vLLM serving setup, the tools, the graders, the task
prompts and the budgets. Budgets are 12 turns, 393,216 total tokens, 1,024 output tokens
per turn, 300 s, 32K context, temperature 0 and seed 42 (`configs/diagnostic-v1.json`).

## Task selection (public inputs only)

The rule picks one task per domain, with 2 easy, 2 medium and 1 hard. Among all eligible
combinations, it takes the one with the lexicographically smallest
`SHA256("diagnostic-v1:" + sorted ids)`. Inputs are the public `id`, `category` and
`difficulty` only. Audited exclusions: optional-caption, notice-link and
visible-list-limit (see audit §3).

| Task | Domain | Difficulty |
| --- | --- | --- |
| announcement-subtitle | modification | easy |
| customer-name | rendering | easy |
| locale-references | references | medium |
| select-schema | schema | medium |
| eligibility-branch | syntax | hard |

## Reference-loading policy

The policy reads only the public task prompt and a heading index of the pinned upstream
`references/` documents. Headings inside code fences are ignored. Routes are checked in
order, and the first match wins:

1. `schema`/`preset` in the first sentence → heading "Schema & Settings Reference"
2. `reference(s)` in the first sentence → "Localization" if `t`/`translate` is
   mentioned, else "Hosted file" if `asset_url` is mentioned, else **block**
3. trim/join wording → "String"
4. conditional wording (if/when/otherwise/boolean/priority) → "Conditional"
5. anything else → **block** (no fallback, no per-task override)

The heading must resolve to exactly one document. The full file is delivered.

| Task | Route | Document | Message tokens |
| --- | --- | --- | --- |
| announcement-subtitle | string-processing | `shopify-liquid-themes/references/filters-language.md` | 5,298 |
| customer-name | string-processing | `shopify-liquid-themes/references/filters-language.md` | 5,298 |
| eligibility-branch | conditional-control | `shopify-liquid-themes/references/tags.md` | 4,569 |
| locale-references | translation-reference | `shopify-liquid-themes/references/filters-commerce.md` | 2,549 |
| select-schema | schema-repair | `shopify-liquid-themes/references/schema-and-settings.md` | 2,353 |

## Initial prompt tokens (local tokenizer, pinned)

| Task | original | clarified | reference | neutral |
| --- | ---: | ---: | ---: | ---: |
| announcement-subtitle | 712 | 1,000 | 6,303 | 6,303 |
| customer-name | 584 | 872 | 6,175 | 6,175 |
| eligibility-branch | 611 | 899 | 5,473 | 5,473 |
| locale-references | 588 | 876 | 3,430 | 3,430 |
| select-schema | 604 | 892 | 3,250 | 3,250 |

All `original` counts equal Milestone 6's endpoint-verified baseline counts. Before
each block, `run_diagnostic.py` asks the live vLLM endpoint to count all 20 prompts. It
refuses to run if any count differs. For comparison, the Milestone 6 full bundle took
about 10.4K initial tokens.

## Order and repetitions

There are 80 attempts in 20 blocks. A block is one task × all four conditions. There are
4 repetitions, and each task sees each condition in each within-block position exactly
once. Every attempt uses seed 42 and temperature 0. Repetitions are therefore
reproducibility and position checks, **not independent samples**. Blocks run in frozen
order. There is no resume, no retry and no stopping based on scores. An infrastructure
error ends the block and is recorded as missing data, not as a model failure.

## Predeclared scoring and analysis

- **Primary outcome:** grader pass/fail per attempt, with unchanged graders. Warnings
  never fail a task.
- **Per task × condition:** passes out of 4.
- **Paired contrasts** (matched by task and repetition; win/tie/loss counts overall, by
  domain and by difficulty):
  - `clarified` − `original`: effect of the tool instructions
  - `neutral` − `clarified`: effect of added length alone
  - `reference` − `neutral`: effect of relevant content at equal tokens
  - `reference` − `clarified`: total effect of loading the reference
- **Reported per attempt:** termination type, tool calls by tool, renders using
  unsupported platform filters, edits outside the editable scope, input/output tokens,
  delivered context SHA-256 and bytes, and infrastructure errors.
- **Interpretation:** with 5 tasks and deterministic decoding, results are diagnostic and
  directional only. No significance tests or research claims. If repetitions disagree
  under identical seeds, that is reported as nondeterminism.

## Compute estimate (not approved)

On 2026-10-23, Runpod listed the A40 48 GB on Secure Cloud at **$0.59/hour**, with high
stock in EU-SE-1. Container disk costs $0.10/GB/month. The live read later failed on an
expired token, so the price and stock must be checked again before any request.

| Scenario | Basis | Session time | Estimated cost |
| --- | --- | ---: | ---: |
| Expected | Milestone 6 runner throughput 159 attempts/h; shorter prompts here | ~50 min, including about 11 min boot/preflight and 5 min export/cleanup | **~$0.50** |
| Worst case | every attempt hits the 300 s limit: 20 blocks × 20 min + 30 min overhead | ~7.2 h | ~$4.35 |

**Proposed approval request:** one A40 48 GB Secure Cloud session, capped at **2.5 hours
and $2.00** all-in, using existing credits. A block may start only if at least 35 minutes
remain (20 min worst-case block plus 15 min export/cleanup). Preflight is refreshed
whenever the evidence is older than 60 minutes. If a cap is reached, the session stops
at a block boundary, exports evidence and terminates. Blocks that did not run are
reported as missing. Nothing is retried.

## Remaining validity concerns

1. **Tiny sample.** 5 tasks, one per domain. Each domain contrast rests on a single task.
2. **No sampling variance.** Temperature 0 with one seed means the 4 repetitions mostly
   test determinism and position, not distributional robustness.
3. **The clarification was written after seeing Milestone 6.** It is generic and contains
   no task-specific hints. However, it was informed by the audit and by knowledge of
   Milestone 6 behavior, so `clarified` − `original` may overstate a "blind" effect.
4. **Reference relevance is rule-based.** announcement-subtitle (a section modification)
   routes to the string-filters document because its prompt mentions trimming. Whether
   that document helps the actual modification is untested. Two tasks share the same
   document.
5. **The neutral control matches length, not form.** The neutral text is synthetic
   records, while the reference is structured Markdown with Liquid code. The control
   isolates token count, not "any well-formatted documentation."
6. **The clarification adds 288 tokens.** The `clarified` − `original` contrast mixes
   content with this small length increase.
7. **Modification coverage is thin.** The three ambiguous theme-modification tasks are
   excluded, so only one easy modification task remains.
8. **These are development tasks, not held out.** All five were in Milestone 6, and their
   earlier outcomes are known. Selection used a fixed hash rule and public metadata only,
   but the salt `diagnostic-v1` was chosen by the experimenter.
9. **The analysis is fixed before inference.** `scripts/analyze_diagnostic.py` implements
   exactly the analysis above. It rejects any attempt whose delivered context, config,
   source or schedule differs from the frozen plan. It reports undefined-filter render
   names as the renderer gives them, without classifying them. Usage:
   `uv run python scripts/analyze_diagnostic.py runs/diagnostic-v1`.
10. **A preparation bug was caught.** The first freeze counted chat-template tokens
    incorrectly (transformers 5 returns a mapping), which made every prompt count 2 and
    the reference/neutral match trivially true. It was fixed before commit, the plan was
    frozen again, and a regression test now checks the counts against Milestone 6.
