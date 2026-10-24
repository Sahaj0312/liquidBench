# Held-out evaluation: analysis plan (pre-registered)

Written before the held-out extension was frozen and before any held-out attempt ran.
Later changes are allowed only as clearly marked additions, never as edits.

## Suites

- **Original:** 24 tasks, frozen in `docs/heldout/manifest.json`. Hand-written; expected outputs come from Python oracles.
- **Extension:** Claude-authored tasks, frozen in `docs/heldout/extension-manifest.json`.
  - Themes are disjoint from training (`scripts/heldout_themes.py`).
  - Each task passed container verification.
  - Each task passed a family-root check and a prompt-similarity check against all training, development and original held-out tasks.
  - Each task passed an independent ambiguity audit (`scripts/audit_heldout_ext.py`). Tasks the audit flagged, or whose audit did not complete, were removed before freezing and listed in the results. No task was edited.

## Arms

All four arms share the pinned vLLM serving command, temperature 0, seed 42 and the
Milestone 6 budgets. The arms are base, base + skills, tuned and tuned + skills; skills
are loaded on demand, at the pinned revision `483f969`. "Tuned" is LoRA v1 (merged
BF16), chosen over v2 on the development split before this plan was written. Every
task runs once per arm and repetition, with 2 repetitions, in the frozen order
`experiments/heldout-plan.json`. There are no retries, replacements or resumes; an
infrastructure error stops the phase and is reported.

## Outcome and tests

- **Task outcome:** pass or fail from the hidden grader, using repetition 1. Repetition 2 is a reproducibility check. Its agreement with repetition 1 is reported. Any task whose two repetitions disagree is listed, and the primary test is repeated counting such a task as a pass only if both repetitions passed.
- **Primary comparison:** tuned against base on all held-out tasks, original plus extension. The test is an exact two-sided McNemar test on the discordant pairs, at α = 0.05. The paired difference in pass rate is reported with an exact 95% interval.
- **Secondary comparisons** (reported with the same test and no multiplicity correction; labelled exploratory):
  1. base + skills against base;
  2. tuned + skills against tuned;
  3. tuned + skills against base;
  4. each comparison within each suite and within each category.
- **Behavior:**
  - read-before-first-write rate;
  - validation-call rate;
  - final-render rate on rendered tasks;
  - turn-budget exhaustion (looping);
  - protocol errors per arm.

## What will be reported regardless of outcome

- **All results:** every arm, every task, both repetitions, including null or negative results.
- **Exclusions:** the list of tasks removed by the audit, with the audit's reasons.
- **Cost:** API and GPU cost.

## Addition 1 (before the extension was frozen and before any held-out attempt)

**Observed problem.** Authoring sampled each held-out theme in several requests, each with a different angle. As a result, the 78 container-verified extension tasks contain several tasks about the same storefront feature; for example, seven are about the social feed or the lookbook. Such tasks are correlated, and the McNemar test assumes independent pairs.

**Theme clusters.** `scripts/cluster_heldout_ext.py` groups the tasks into theme clusters and writes the result to `docs/heldout/theme-clusters.json`. The rules:

- Two themes belong to the same cluster when they share any non-generic word stem, applied transitively. This errs toward merging.
- Each task is assigned to the theme of its own authoring request that best matches its family name.
- The earliest-authored task in each cluster that survives the audit is marked **primary**.

**Changes to the analysis.**

- **Primary comparison:** tuned against base on the **primary set**, meaning the original suite plus the primary extension tasks. The test (exact McNemar, α = 0.05) and the interval are unchanged.
- **All held-out tasks:** the same comparison on every held-out task is reported, labelled exploratory.
- **What runs:** every audited-clear extension task still runs in every arm. Clustering decides only which tasks enter the primary test.
