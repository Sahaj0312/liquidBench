# Diagnostic v1 results

All **80/80** frozen attempts ran in order in one approved A40 session. There were no
infrastructure errors, missing attempts, retries or plan deviations. Before every block,
all 20 local prompt token counts matched the live endpoint exactly. Development-only
result: 5 tasks, not a research claim. Plan: [plan.md](plan.md).

## Outcomes

Every task gave **the same result in all 4 repetitions** (temperature 0, seed 42).
Each condition therefore really rests on 5 task-level observations, not 20.

| Task | original | clarified | reference | neutral |
| --- | :-: | :-: | :-: | :-: |
| announcement-subtitle (modification, easy) | 0/4 | 0/4 | 0/4 | 0/4 |
| customer-name (rendering, easy) | 0/4 | 0/4 | 0/4 | 0/4 |
| eligibility-branch (syntax, hard) | 0/4 | 0/4 | 0/4 | 0/4 |
| locale-references (references, medium) | **4/4** | 0/4 | **4/4** | 0/4 |
| select-schema (schema, medium) | **4/4** | **4/4** | 0/4 | 0/4 |
| **Total** | **8/20** | 4/20 | 4/20 | 0/20 |

Paired win/tie/loss, pooled over repetitions (left vs right):

| Contrast | Tests | W / T / L |
| --- | --- | :-: |
| clarified − original | tool instructions | 0 / 16 / 4 |
| neutral − clarified | added length alone | 0 / 16 / 4 |
| reference − neutral | relevant content at equal tokens | **4 / 16 / 0** |
| reference − clarified | total effect of loading the reference | 4 / 12 / 4 |

## Findings

1. **Context placed before the task breaks tool discipline, whatever it contains.**
   The share of attempts that read the target file before their first write was:

   | original | clarified | reference | neutral |
   | :-: | :-: | :-: | :-: |
   | 20/20 | 20/20 | 4/20 | 8/20 |

   On select-schema, both context arms wrote the file from memory without reading it.
   The reference arm broke the byte-preserved markup (`preserved_markup`). The neutral
   arm produced an invalid schema layout (`single_top_level_schema`). The clarified arm
   read the file first and passed. This
   reproduces Milestone 6's "skipped reading and validation" pattern in a controlled
   setting.
2. **Relevant content beats equal-length noise, but not no context at all.**
   The reference document restored locale-references (reference 4/4 vs neutral 0/4).
   Its net effect against clarified alone was zero: it gained locale-references and lost
   select-schema. The neutral control scored 0/20, so the length penalty is real.
3. **The clarified tool instructions did not help.** Their only effect was a loss on
   locale-references. With the extra system text, the deterministic first edit changed:
   the model fixed one key instead of two. It then rewrote the protected `locales/*.json`
   files to fit its own wrong key, despite the instruction not to edit protected
   resources to clear diagnostics. The clarification did not stop it chasing warnings.
4. **Three tasks fail in every arm.** These are customer-name (trimming and joining),
   eligibility-branch (compound boolean logic; every arm used up all 12 turns) and
   announcement-subtitle. No prompt or loading change moved them. They point to the
   model's underlying Liquid ability rather than to instructions or loading.

## Implications

- Prompt-level fixes are exhausted for this model. Front-loading any context, including
  relevant skills, costs more in tool discipline than it adds in knowledge.
- If skills are used, deliver them after the agent has read the target files, or on
  demand. Do not prepend them.
- The always-failing tasks, together with the read → edit → validate discipline, are
  the natural targets for post-training on verified trajectories, evaluated on a
  separate held-out benchmark.

## Limitations

There are only 5 tasks, and repetitions were deterministic, so each contrast turns on one
or two task flips. The clarification text was written after seeing Milestone 6. The
neutral control matches length, not format. The same tasks were used in Milestone 6.
See the validity concerns in [plan.md](plan.md).

## Session and cleanup

| Measure | Observed |
| --- | --- |
| Pod | `vi7jlfbfsicyzy`, A40 48 GB, Secure Cloud, EU-SE-1, CUDA 13.2 |
| Rate (live read) | $0.59/h GPU + 100 GB ephemeral disk at $0.10/GB/month |
| Created → deleted | 00:56:24 → ≤01:44:44 UTC (≤48.3 min) |
| Blocks 0–19 | 01:00 → 01:44:17 UTC; one preflight, no refresh needed |
| Estimated total | **$0.4865** (lifetime × live rate, before tax/adjustments; not a settled invoice) |
| Cleanup | `delete-pod` returned 204; `get-pod` returned 404; Pod and network-volume lists empty |

The image, serving command and boot script were byte-identical to Milestone 6 session 02.
The SSH host key was verified against authenticated boot logs. All pinned model files,
BF16, the 32K context and no quantization were verified on the host. Private evidence is
under `runs/diagnostic-v1/` and `runs/diagnostic-v1-session-01/` (gitignored), including
the hashed final host archive `host-final.tar.gz`
(`49d73ed559a174d006a6a60bc9103857a02c796ce586dc63251b93c38634e458`).
