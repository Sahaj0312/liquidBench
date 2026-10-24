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
