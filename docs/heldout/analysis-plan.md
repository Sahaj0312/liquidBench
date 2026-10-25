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

## Addition 2 (before freezing, before any held-out attempt)

The first ambiguity-audit pass (batch `msgbatch_01T6mb9j7ssX2PfvZQDu4xbV`) ran without extended thinking, averaging 270 output tokens per task. It flagged 2 of the 78 tasks. A second pass (batch `msgbatch_01PVLoGGAxXeZunFL2CMWTZQ`) audits the remaining 76 with adaptive thinking. A task is kept only if both passes judged it clear. Theme clustering (Addition 1) runs after both passes.

## Addition 3 (after the first base run stopped, before any tuned attempt)

The first base run (`runs/heldout/base`, Pod `ug888pmiezmfss`) stopped after 167 of 400 attempts. Attempt 167 (`size-guide-units`, base + skills, repetition 1) was recorded as an infrastructure error. The trace shows the model produced a full 1,024-token response on each of 9 turns, about 30 s each. With 26 s left, the runner cut the request timeout to fit the 300 s attempt deadline. The request then timed out, and the retry loop raised "Attempt deadline reached during provider retries" as a provider error. The server stayed healthy throughout. Under the Milestone 6 plan this is a deadline termination ("operational missingness, not a model failure"), not an infrastructure fault.

Changes:

- **Runner:** a request that the attempt deadline leaves no time to retry now ends the attempt with termination `time_budget` (status failed, as for every other budget termination). It no longer raises an infrastructure error. A genuine server hang that coincides with the deadline is classified the same way; any real outage still fails the next attempt's requests and stops the phase. Test: `test_request_cut_short_by_attempt_deadline_is_time_budget`.
- **Plan re-freeze:** the frozen plan pins a digest of the Python source, so the runner change required regenerating `experiments/heldout-plan.json`. Only `python_source_digest` changed (`334dfde8…` → `02975843…`); attempts, order, configs and task digests are identical. In `docs/heldout/initial-counts.json` only `plan_sha256` changed (`49cfadff…` → `c345d514…`); every token count is identical.
- **Base phase:** rerun from the first attempt in the frozen order, into `runs/heldout/base-r2`, with a fresh preflight on the same Pod and serving command. Nothing from the stopped run is resumed, merged or replaced. The stopped run is kept as evidence; its 166 completed attempts are compared with the rerun as a same-host determinism check.
- **Disclosure:** before this addition, the per-attempt log of the stopped run was visible. Repetition 1 pass counts over its first 83 tasks were base 12, base + skills 14. No tuned attempt has run. Nothing in the tests, groups or primary comparison changes.

The measured pace (43.6 s per attempt) means both phases cannot finish within the approved session. The tuned phase runs in a later session that is approved separately. It reruns the base and tuned development checks (8/20 and 10/20) on its host before any held-out attempt. If that session also reruns the base phase, the tuned-versus-base comparison uses the same-host base run, and the cross-host base agreement is reported.
