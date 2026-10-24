# Training data, stage 1

Claude-authored training tasks (`tasks/train/`, split `train`) and teacher
trajectories for supervised fine-tuning of Qwen2.5-Coder-7B-Instruct. Nothing
here was generated from held-out or development task content; every spec passed
the held-out leak and similarity guards before it was kept.

## Tasks

A spec is kept only when the container grader agrees with it: the reference
passes the author's independently written cases, the starter and every wrong
solution fail, and the reference has no static errors (`src/liquidbench/training_tasks.py`).

| Source | Specs | Kept | USD | USD per kept |
|---|---:|---:|---:|---:|
| Pilot (live, Opus 5.5) | 3 | 3 | — | — |
| Pilot (live, Sonnet 5.5) | 4 | 1 | — | — |
| Batch `msgbatch_01UuKBSaGmiFmCmj4AvxgtVB` (Opus 5.5, medium effort, 60 × 2) | 120 | 104 | 10.57 | 0.10 |
| Live hybrid, two rounds (Opus 5.5, 2 per call) | 50 | 41 | 9.81 | 0.24 |

Pilot spend ($2.24) is in the pilot ledger; the rest is in `runs/training/ledger-full.jsonl` (private).

The batch sat at 0 of 60 processed for over three hours, then completed in
full. Live authoring was the fallback while it waited; live calls reserve
every pending batch's worst case so the $50 cap holds.

The 149 tasks are 33 section-schema, 31 theme-references, 31 theme-modification,
29 liquid-syntax and 25 rendering, and 45 easy, 54 medium and 50 hard.

Rejection reasons:
- **Wrong solution passes.** Most rejections were an "unescaped" wrong solution that passed, because no case contained `<`, `&` or `"`.
- **Static errors in the reference.** Some theme-references specs had a reference that still failed Theme Check.
- **Held-out leak.** Two specs were rejected because they touched held-out material (`price-render`, `store-hours`).
- **Reused family name.** Before commit `3350f93`, a spec that reused a family name was discarded. It is now renamed (`-2`, `-3`, …) and kept.

## Trajectories

Teachers solved each task in the unchanged Qwen harness
(`scripts/collect_trajectories.py`, `configs/train-collect.json`). A run is
kept when it passed the hidden grader, had no protocol errors or truncated
actions, read the target before its first write, and fits Qwen's 32K context.

| Teacher | Attempts | Kept | USD |
|---|---:|---:|---:|
| Sonnet 5.5 (low effort), first | 150 | 135 | 3.39 |
| Opus 5.5 (low effort), retries of misses | 18 | 10 | 0.85 |

Attempts and kept counts include the pilot; USD excludes it. 143 of 149 tasks have one kept trajectory. Sonnet failed 12 tasks outright; Opus
passed several of those but often skipped reading before writing, so those runs
were dropped. The six tasks without a trajectory stay in `tasks/train`:

- `author-byline-3`
- `bundle-eligibility-2`
- `bundle-eligibility-notice`
- `contact-form-fields`
- `store-info-hours`
- `warranty-status-2`

Stage 1 total: $24.62 of the $50 study-material cap.
