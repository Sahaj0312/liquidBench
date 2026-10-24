# LoRA v1: development-split check

The first fine-tune of Qwen2.5-Coder-7B-Instruct on teacher trajectories, scored on
the 20 development tasks only. The held-out benchmark was not touched.

## Setup

| | |
|---|---|
| Data | 129 train / 14 val trajectories, one per task (`docs/training/sft-manifest.json`) |
| Method | BF16 LoRA, r 16, alpha 32, dropout 0.05, all attention and MLP projections; assistant tokens only |
| Schedule | 3 epochs, lr 1e-4 cosine, 5% warmup, effective batch 8, seed 42 (51 steps) |
| Selection | lowest validation loss across epochs, fixed before training (epoch 3) |
| Validation loss | 0.0583, 0.0522, 0.0509 after epochs 1–3 |
| Serving | adapter merged into BF16 weights; base serving command with only the model path changed |
| Eval | `configs/lora-v1-dev.json`: same budgets, temperature 0, seed 42 as the Milestone 6 baseline |
| Session | Runpod A40 `y7ujhntu6v9rql`, about 33 min, about $0.33; deleted and confirmed gone |

Pre-scoring checks:
- Base weights byte-identical to the diagnostic's.
- Chat template hash matches the pinned base template.
- Software matches the diagnostic.
- Endpoint preflight passed.
- Adapter `7b29cb79…` saved locally.

## Result

| | Passing | Rate |
|---|---:|---:|
| Base (Milestone 6, 3 repetitions) | 8/20 each | 40% |
| LoRA v1 (2 repetitions) | 10/20 each | 50% |

Both repetitions were identical. Paired by task:
- **Gained (3):** `announcement-subtitle`, `product-card`, `status-priority`. The base model failed `announcement-subtitle` in every arm of the diagnostic.
- **Lost (1):** `tag-membership`.
- **Unchanged:** 16 tasks, 7 passing and 9 failing in both.

Three gains against one loss is not statistically distinguishable from no effect
(exact two-sided sign test, p = 0.625). The 20-task development split is too small
to establish an improvement; this is a direction, not a result.

## Behavior

- **Reading and checking:** the fine-tuned model read the target before its first write in 20/20 attempts and made at least one validation call in 20/20. The base model's figures were 20/20 and 16/20.
- **Static checks over rendering:** it validated with Theme Check (`check`) in every attempt but rendered in only 2. Static checks cannot catch wrong output. The teachers rendered in 53 of the 129 training trajectories (41%), so the student under-learned the habit.
- **The regression:** in `tag-membership` the model broke out of the loop on the first `featured` tag, so a later `archived` tag lost its priority. One render with `["featured", "archived"]` would have shown the bug.
- **Implication for training data:** the next round should favor trajectories that render edge cases before finishing.
