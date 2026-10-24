# LoRA v2: development-split check

v2 changes only the training data. After v1, rendered-output traces had to render
the edited file after their final write. Twenty-nine traces were recollected with
a teacher-only note asking for edge-case renders
(`configs/teacher-note-render.txt`). The student never sees that note: kept
transcripts contain only the unchanged harness prompt, and a test enforces this.
Hyperparameters, selection rule, serving and evaluation are identical to v1
(`docs/training/lora-v1-dev.md`).

| | v1 | v2 |
|---|---:|---:|
| Train / val examples | 129 / 14 | 134 / 14 (same 14 validation tasks) |
| Rendered-task traces that render after the last write | 57 / 80 | 85 / 85 |
| Validation loss, epochs 1–3 | 0.0583, 0.0522, 0.0509 | 0.0714, 0.0586, 0.0580 |
| Selected epoch | 3 | 3 |

The validation losses are not directly comparable: two validation traces changed.

Pre-scoring checks passed, with the same set as v1:
- Base files and chat template match the pinned ones.
- The adapter hash `b53bf9e8…` matches between the Pod and the local copy.
- Endpoint preflight passed.

The Pod was Runpod A40 `n5gnp4d8y2hc70`, up about 41 minutes for about $0.40. It was deleted and confirmed gone.

Recollection cost $1.28 of API spend: 28 of 29 traces kept. The miss was `contact-form-fields`, where both teachers failed.

## Result

| Task | Base | v1 | v2 |
|---|:-:|:-:|:-:|
| 7 tasks every model passes | pass | pass | pass |
| `announcement-subtitle`, `status-priority` | fail | pass | pass |
| `product-card` | fail | pass | **fail** |
| `tag-membership` | pass | fail | fail |
| 9 tasks every model fails | fail | fail | fail |
| **Total** | **8/20** | **10/20** | **9/20** |

The two repetitions of each model were identical.

## Behavior

- **Rendering:** v2 rendered after its final write in 7 of 20 attempts; v1 rendered in only 2. The data change did transfer the habit.
- **`product-card` regression:** v2 looped. It rewrote the same file and reran `check` six times in response to a harmless OrphanedSnippet warning, and hit the 12-turn budget without finishing. v1 finished this task correctly.
- **`tag-membership`:** v2 now renders, but it tested `["a", "archived", "b", "featured", "c"]`. That input does not expose its bug, which is a loop exit on `featured` before a later `archived`.

## Selection for the held-out evaluation

The 20-task split cannot separate v1 from v2: one task differs. By the
development score, v1 (10/20) is the fine-tuned model carried forward to the
held-out evaluation. v2 shows that the rendering habit can be taught. What v2 lacks
is test choice: the renders need to target the case that could actually fail.
