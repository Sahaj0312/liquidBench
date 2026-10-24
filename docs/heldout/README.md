# Held-out benchmark (frozen)

`tasks/heldout/` holds **24 original tasks** for the final comparison of the base, skills,
fine-tuned and fine-tuned + skills models. They are frozen by digest in
[`manifest.json`](manifest.json), suite digest `00d89c7dd96b0d26…`.
`liquidbench.heldout.verify_frozen()` refuses to load a changed suite, and a unit test
enforces this.

| Domain | Easy | Medium | Hard |
| --- | --- | --- | --- |
| Liquid syntax | stock-badge, size-label | discount-label, store-hours | gift-wrap-eligibility |
| Rendering | initials-avatar | price-format, breadcrumb-trail, rating-stars | pagination-window |
| Section schema | color-scheme-schema, footer-schema | collection-grid-schema, testimonials-schema | slideshow-blocks-schema |
| Theme references | logo-asset | cart-assets, cart-labels | price-render |
| Theme modification | hero-cta | card-sale-badge, grid-columns | faq-details, sale-countdown |

## Construction

- Written with the dev task machinery and the same graders (render, schema and reference
  contracts), by `scripts/author_heldout.py`. The script regenerates the suite
  byte-for-byte.
- Expected outputs come from independent Python oracles, not from rendering the
  reference solution.
- Every task has a realistic buggy starter, at least three plausible-wrong solutions and
  standard adversarial submissions (hardcoded output, suppressed checks, extra file,
  deleted target). **All 270 verdicts are correct**: every reference and alternative
  solution passes, and every starter, wrong and adversarial submission fails.
- Every prompt states the full input structure, including which inputs are top-level and
  which sit under `section.settings`, so the Milestone 6 audit's ambiguity cannot recur.
- No family overlaps with the 20 development tasks.

## Isolation rules

1. Final-model evaluation only. Never use these tasks for prompt development, model
   selection or debugging.
2. Never show held-out families, prompts, cases or solutions to a training-data
   generator. Training material must pass `liquidbench.heldout.assert_not_heldout()`.
3. No task is changed after freezing. A correction means a new versioned suite, with the
   old results kept.
4. Run each model condition once under the same frozen configuration, and report all
   outcomes, including failures and missing attempts.

## Extension (76 Claude-authored tasks)

`tasks/heldout-ext/` adds 76 tasks, frozen in [`extension-manifest.json`](extension-manifest.json) with suite digest `9be3e37bf3db8d21…`. Together with the original 24, the held-out set is 100 tasks.

**How the tasks were made**
- **Authoring:** Opus 5.5 wrote them in two batches (`msgbatch_011GuAnNWgWbYBxKtCbR8jSd`, `msgbatch_01Mz3BgK22rvg7gF6vTB5ngb`). Themes come from [`scripts/heldout_themes.py`](../../scripts/heldout_themes.py) and do not overlap the training themes.
- **Verification:** every task passed container verification, using the same checks as the training tasks.
- **Leak checks:** a family-root check plus a prompt-similarity check against all training, development and original held-out tasks. 156 tasks were authored; 78 were rejected, mostly for reusing a family root.
- **Ambiguity audit:** two Opus 5.5 passes; the first without extended thinking, the second with adaptive thinking. Two tasks were removed for contradicting their own files: `cookie-banner-labels` and `size-guide-labels`. Verdicts and reasons are in [`audit.json`](audit.json). No task was edited.

**Category mix:**

| Domain | Tasks |
| --- | --- |
| Section schema | 22 |
| Theme modification | 16 |
| Liquid syntax | 14 |
| Rendering | 13 |
| Theme references | 11 |

**Theme clusters.** Authoring reused themes, so some extension tasks are near-duplicates of each other. [`theme-clusters.json`](theme-clusters.json) groups the 76 tasks into 34 theme clusters and marks one primary task per cluster. The primary test uses the original 24 plus these 34, 58 tasks in all. Every task still runs in every arm; see Addition 1 in [`analysis-plan.md`](analysis-plan.md).

**Run plan.** [`experiments/heldout-plan.json`](../../experiments/heldout-plan.json) fixes 800 attempts: 100 tasks × 4 arms × 2 repetitions. Initial prompt token counts are in [`initial-counts.json`](initial-counts.json).
