# Held-out results

The comparisons follow the pre-registered plan in [`analysis-plan.md`](analysis-plan.md), including Additions 1–3. The numbers are in [`results.json`](results.json), produced by:

```
uv run python scripts/analyze_heldout.py --base runs/heldout/base-s2 --tuned runs/heldout/tuned-s2
```

Both phases ran on one host in session 02 (see [`session-02.md`](session-02.md)):

- 800 attempts in total.
- 0 infrastructure errors.
- Every task ran in every arm, twice.
- Repetition 1 is scored.

## Primary result

**Fine-tuning helps.** On the primary set, LoRA v1 passes **20 of 58** tasks and the base model passes **10 of 58**:

- 10 tasks pass only with tuned, and 0 pass only with base.
- Paired difference **+17.2 points**, exact 95% interval [+6.6, +17.2].
- McNemar **p = 0.0020**.

The primary set is the 24 original tasks plus one task per extension theme cluster.

Counting a task as passed only if both repetitions passed gives the same result: 20 vs 10, 10 vs 0, p = 0.0020.

The 10 tasks that only the tuned model passes span all five categories. Each passes in both repetitions:

| Suite | Tasks |
|---|---|
| Original | `breadcrumb-trail`, `discount-label`, `logo-asset`, `store-hours` |
| Extension | `back-to-top-icon`, `before-after-slider`, `how-it-works-trimmed`, `not-found-labels`, `size-guide-panel`, `social-feed-wall` |

## Results by arm (repetition 1)

| Arm | All 100 tasks | Primary 58 | Original 24 | Extension 76 |
|---|---|---|---|---|
| base | 20 | 10 | 9 | 11 |
| base + skills | 21 | 11 | 9 | 12 |
| tuned | 39 | 20 | 13 | 26 |
| tuned + skills | 40 | 19 | 12 | 28 |

## All comparisons

The primary set is pre-registered. Every other row is exploratory, with no multiplicity correction. The "only" columns give the number of tasks that pass only under the treated arm and only under the control.

| Comparison | Group | Treated only | Control only | Difference (points) | 95% interval | p |
|---|---|---|---|---|---|---|
| **tuned vs base** | **primary (58)** | **10** | **0** | **+17.2** | **[+6.6, +17.2]** | **0.002** |
| tuned vs base | all (100) | 21 | 2 | +19.0 | [+10.1, +22.5] | 0.0001 |
| tuned vs base | original (24) | 4 | 0 | +16.7 | [−3.4, +16.7] | 0.125 |
| tuned vs base | extension (76) | 17 | 2 | +19.7 | [+8.4, +24.3] | 0.0007 |
| base + skills vs base | primary | 3 | 2 | +1.7 | [−6.1, +7.7] | 1.0 |
| base + skills vs base | all | 4 | 3 | +1.0 | [−4.4, +5.6] | 1.0 |
| tuned + skills vs tuned | primary | 0 | 1 | −1.7 | [−1.7, +1.6] | 1.0 |
| tuned + skills vs tuned | all | 3 | 2 | +1.0 | [−3.5, +4.5] | 1.0 |
| tuned + skills vs base | primary | 9 | 0 | +15.5 | [+5.1, +15.5] | 0.004 |
| tuned + skills vs base | all | 21 | 1 | +20.0 | [+11.9, +21.9] | <0.0001 |

**Skills make no measurable difference.** With skills loaded on demand, neither model changes by more than one task net, on any group. Each skills comparison moves at most 7 tasks in total, split almost evenly between gains and losses. So all of the gain over base comes from fine-tuning.

Tuned vs base by category (repetition 1, all tasks):

| Category | Tasks | Tuned passes | Base passes |
|---|---|---|---|
| Section schema | 27 | 22 | 13 |
| Liquid syntax | 19 | 6 | 2 |
| Theme references | 15 | 6 | 2 |
| Rendering | 18 | 3 | 1 |
| Theme modification | 21 | 2 | 2 |

Theme modification, meaning edits across several files, is the weakest category: base and tuned each pass 2 of 21, and tuned + skills passes 3.

## Behavior (repetition 1, 100 attempts per arm)

| Arm | Read before first write | Called a validator | Rendered after last write (of 58 rendered tasks) | Turn budget exhausted | Protocol errors |
|---|---|---|---|---|---|
| base | 74 | 85 | 2 | 32 | 9 |
| base + skills | 86 | 89 | 2 | 35 | 9 |
| tuned | 100 | 98 | 18 | 16 | 18 |
| tuned + skills | 100 | 98 | 17 | 12 | 18 |

The tuned model works more like the training trajectories:

- It always reads the file before editing it.
- It almost always validates its edit.
- It re-renders after its last write nine times as often as base.
- It runs out of turns half as often.

It also makes twice as many protocol errors (malformed tool calls). These did not stop it from passing more tasks.

## Reproducibility

- **Repetitions:** 2 of 400 task-arm pairs disagree between repetitions 1 and 2:
  - `local-currency-notice` (tuned)
  - `lookbook-grid-defaults` (tuned + skills)

  Neither is in the primary comparison's discordant set.
- **Base across hosts and sessions:**
  - The session-02 base run (`base-s2`) agrees with every attempt that both earlier session-01 base runs completed:
    - `base`: 167 of 167
    - `base-r2`: 199 of 199
  - Base output is deterministic across Pods.
  - The rep-1 counts disclosed in Addition 3 (12 and 14 over the first 83 tasks) come from those runs.
- **Tuned development check:** on the session-02 host, the merged model passed the same 10 of 20 development tasks as both earlier LoRA v1 runs (`runs/lora-v1/dev-rep1`, `dev-rep2`). The base model passed the same 8 of 20 as before.

## Exclusions

The first ambiguity-audit pass judged two extension tasks ambiguous, and they were removed before freezing:

- `cookie-banner-labels`
- `size-guide-labels`

Both are in `docs/heldout/audit.json` and `runs/heldout-ext-rejected/`. No task was edited, and no task was dropped after any attempt ran.

## Cost

- **Claude API** (task authoring, training trajectories, audits): **$42.13**, from `runs/training/ledger-full.jsonl`.
- **Held-out GPU:** one A40 Secure at $0.59/h, about **$13.17** in total:
  - session 01: $7.54
  - session 02: about $5.63

  Session 02 billing read $5.04 at deletion while still lagging. The figure above is 9.33 h at $0.604/h including disk.
