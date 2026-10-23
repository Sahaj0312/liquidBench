# Milestone 6 — Block 0 results

**Block 0 completed all 16 predefined attempts, without replacements or changes to
execution.** This is repetition 1 / seed 42 of the existing 240-attempt development
study. The remaining 224 attempts are unattempted, not rejected or selected on
these scores. No fine-tuning or training-data generation was started.

| Task | Category / difficulty | Baseline | Full skills | On-demand | Neutral |
| --- | --- | --- | --- | --- | --- |
| announcement-subtitle | section-modification / easy | fail | fail | fail | fail |
| asset-references | theme-references / easy | pass | fail | pass | pass |
| blocks-schema | section-schema / hard | pass | fail | pass | fail |
| cart-arithmetic | rendering / medium | fail | fail | fail | fail |
| **Block total** | **4 tasks per condition** | **2/4** | **0/4** | **2/4** | **1/4** |

The [machine-readable report](milestone-6-block-0-results.json) includes per-attempt
hashes, statuses, tokens, actions, feedback line numbers, skill exposure and paired
counts by category, difficulty, category ×difficulty and broad domain. The analysis
uses unchanged `passed`/`failed` attempt status. It separates both-pass/both-fail
ties and excludes missing/infra pairs from wins/ties/losses. Repeats stay separate.

## Operational verification

- One approved A40 48 GB Secure Cloud Pod, `g1fplyxkfnegun`, in EU-SE-1; $0.59/hour
  plus 100 GB ephemeral disk. No persistent/network volume or replacement Pod.
- Pinned Qwen revision `c03e6d358207e414f1eca0bb1891e29f1db0e242` and all 14 downloaded
  model/tokenizer files verified against prior hashes, including all four weight
  shards and the chat template. Exact pinned vLLM image and local runtime ID matched.
- A40, driver 595.91.07, host CUDA 13.2; vLLM 0.32.0, torch 2.13.0+cu130,
  transformers 5.19.0, tokenizers 0.23.3, xgrammar 0.2.8. BF16 supported; engine
  logged BF16, no quantization, KV dtype auto, prefix caching enabled and the
  unchanged 32K/one-sequence/TP1/xgrammar configuration. The complete command is
  preserved and exactly matches the prior approved deployment.
- SSH host fingerprint matched authenticated Runpod boot logs. The model API used
  a local SSH tunnel; no public model HTTP port was exposed. `caffeinate -is`
  prevented idle sleep during preparation, inference and export.
- **Preflight v2 ran once and passed all six checks**, including both representative
  generation diagnostics. No diagnostic prompt was modified or retried.
- All **80 initial prompt counts** matched the local tokenizer. All **88 benchmark
  model calls** had a reported-versus-counted input delta of zero.
- **Zero provider errors, protocol errors, infrastructure terminations or output
  truncations.** Five public tool errors occurred: four missing-file reads and
  one invalid Liquid render. These were model actions with recorded feedback.
- Thirteen attempts explicitly finished. Three exhausted the unchanged 12-turn
  allowance: full/asset-references, baseline/cart-arithmetic and
  on-demand/cart-arithmetic. No attempt hit the time, context or token ceiling.

The image cold start was substantially longer than the previous cached deployment:
Runpod spent several minutes downloading/extracting layers before boot, followed
by model loading/compilation. It progressed without an error or recovery change.
No benchmark attempt was restarted. The local VM/runtime was ready before rental.

The analysis-only preparation commit is `702d53896c65e74971e13afbefa33c81c3c60e9c`.
[CI passed](https://github.com/Sahaj0312/liquidBench/actions/runs/40021348125):
**186 unit +282 container tests**, including all **236 grader verdicts**, plus lint
and formatting. The plan file, Python inference-source digest, tasks, prompts,
graders, upstream skill content, model settings and budgets remained frozen.

## Tokens, latency and document use

| Condition | Input tokens | Output tokens | Total tokens | Model calls | Summed attempt seconds | Read before first write | Any validation call |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 32,837 | 1,553 | 34,390 | 23 | 81.31 | 4/4 | 3/4 |
| Full skills | 230,542 | 1,403 | 231,945 | 21 | 75.47 | 1/4 | 2/4 |
| On-demand | 29,939 | 1,493 | 31,432 | 23 | 78.06 | 4/4 | 3/4 |
| Neutral | 229,530 | 1,714 | 231,244 | 21 | 91.65 | 2/4 | 3/4 |

Full skills used **6.74× baseline tokens**; neutral used **6.72×**; on-demand used
**0.914×** in this block. These are observed trajectories, not matched total-token
experiments. Full and neutral initial overhead remained exactly matched. Cached
input tokens still counted in full. Latency is descriptive: prefix caching, request
length, network RTT and different action sequences prevent a simple token-to-time
interpretation. Runpod charges by rental time, not by these token totals.

All three full-bundle entries were delivered in each full attempt (12 entry
exposures). **Neither full nor on-demand made any explicit skill-document read.**
On-demand received only the fixed index. Its 2/4 score therefore does not demonstrate
successful retrieval or a benefit from skill knowledge. Index exposure, delivered
entry content, explicit document reads and code correctness are separate fields.

## Failure evidence and validation behavior

Trace line numbers below refer to the private `trace.jsonl` for the task/condition;
the JSON report maps each run to its artifact directory and file hashes. Upstream
skill bodies and complete raw traces remain local, not redistributed.

- **Announcement:** baseline and on-demand read the source, inserted a filter
  directly inside an `if` condition, and finished without validating (baseline
  lines 3/7/11; on-demand 5/9/13). Strict Liquid rejects that syntax. Full wrote
  without reading, rewrote the protected schema/defaults, introduced untranslated
  schema keys, removed section-ID escaping, and also used an invalid filtered
  condition (write line 9, finish 13). Neutral actually rendered, received the
  syntax error at line 15, rewrote at 17 and rendered again at 21. It corrected
  syntax but used a simple nonempty comparison, still mishandling null/whitespace
  requirements. This is partial use of feedback, not a passing repair.
- **References:** baseline, on-demand and neutral repaired the literals and ran
  Theme Check before finishing. Neutral first made two missing-path reads, then
  recovered. Full used an `assets/` prefix where the filter already adds it.
  Theme Check repeatedly identified `assets/assets/promo-banner.css` (lines
  19/39/47/55). It read unrelated nonexistent configuration files, then edited the
  protected CSS instead of correcting the reference (writes at 41/49), violating
  scope and exhausting turns. The diagnostic was available; the repair did not
  address it. This is model reasoning/scope failure, not a missing tool or checker.
- **Block schema:** baseline and on-demand read, repaired, checked and finished
  successfully. Both full and neutral wrote bare JSON without first reading,
  removing the schema delimiters and surrounding markup, and finished without
  validation (full lines 9/13; neutral 5/9). They also changed fields outside the
  declared schema contract. The recorded verdict fails the top-level schema gate.
- **Arithmetic:** baseline repeatedly retained unsupported `reduce`/`max` filters
  despite five Theme Check diagnostics (lines 13/21/29/37/45). On-demand similarly
  retained `max` after feedback (15/23/31/39/47). Both used all 12 turns without
  finishing. Full and neutral used known loop/filter syntax but accumulated
  `(total + price) ×quantity` instead of `total + price ×quantity`, and used absolute
  value rather than clamping a negative total to zero. After orphaned-snippet
  warnings, they created an unauthorized `sections/cart.liquid` (full line 17;
  neutral lines 13/21). Their binary verdict is scope failure; the arithmetic
  defects are an additional code inspection finding, not a substituted score.

The full announcement also changed the protected `show_body` default from false
to true. No condition solved that task, and this block does not establish a fix
for boolean-default handling. No positive guidance effect can be attributed to
reference reads because there were none.

These patterns separate working transport/protocol/grading from model failures.
The public tools exposed useful diagnostics, but a validation call did not reliably
lead to a valid change. Large full and neutral messages both coincided with some
write-without-reading and file-preservation failures. That is compatible with a
context effect; it does not isolate causation. Full also had the distinct repeated
reference/scope error. Four tasks are insufficient to select a new treatment or
claim a general skills effect.

## Paired counts for the four observed tasks

Wins are for the left condition. These are repetition-1 task pairs, not independent
replicate statistics. Other planned tasks are explicitly unattempted in the report.

| Comparison | Wins | Ties | Losses |
| --- | ---: | ---: | ---: |
| Full / baseline | 0 | 2 | 2 |
| On-demand / baseline | 0 | 4 | 0 |
| Neutral / baseline | 0 | 3 | 1 |
| Full / neutral | 0 | 3 | 1 |
| On-demand / full | 2 | 2 | 0 |
| On-demand / neutral | 1 | 3 | 0 |

## Cost, throughput and cleanup

The Pod was created **20:43:38.752 UTC**, deletion requested **21:00:46 UTC**, and
absence independently verified **21:00:53 UTC** on 2026-10-23. That is **17m 14.248s**
through cleanup verification, well inside the approved 110-minute envelope.

The verified-lifetime estimate is **$0.173492**: GPU $0.169502 plus container disk
$0.003990, using the live $0.59/hour rate and the current
[$0.10/GB/month disk rate](https://docs.runpod.io/pods/pricing), with a 720-hour
month. Using deletion-request time instead gives $0.172318. These are rental
estimates before any unreported adjustments, **not a settled invoice**. The
Pod-specific billing read returned zero posted records, so settled charge is
`null`, not $0. The approval cap was $2; no top-up or other purchase was made.

| Phase / measure | Observed |
| --- | ---: |
| Creation to first observed healthy endpoint | 8m 22.317s |
| Health to Block 0 launch (verification + preflight) | 1m 33.802s |
| Runner, including all 80 initial count checks | 6m 11.378s |
| Sum of 16 attempt durations, including grading | 5m 26.501s |
| Count gate and orchestration outside attempts | 44.878s |
| Execution end to verified cleanup | 1m 6.756s |
| Mean attempt duration / observed range | 20.41s / 9.72–45.72s |
| Throughput during runner execution | 155.10 attempts/hour |
| Throughput across full Pod lifetime | 55.69 attempts/hour |
| Benchmark input / output tokens | 522,848 / 6,163 |
| Output tokens per second of completed model-request latency | 27.42 |

The last metric includes prefill and transport latency; it is not pure decode
speed. Preflight work is separate from the 88 benchmark model calls.

Evidence was downloaded and archived **before deletion**, then cleanup and cost
metadata were included in the final private archive. `delete-pod` returned 204;
fresh `get-pod` returned 404, `list-pods` was empty and `list-network-volumes` was
empty. No billable session resource remains. The local runtime VM was stopped.

- Pre-deletion archive: `runs/m6-block-00-predelete.tar.gz`, SHA-256
  `cb4bfa656d10f74750aa0daa3fbe92435a61cb29658e285027ba6c3ea7e6cd61`.
- Final archive: `runs/m6-block-00-evidence.tar.gz`, SHA-256
  `7818756180e6e3c8c045ae1b9838195e2a947c0d7c6881fc193875a34b3047ca`.

## Remaining blocks

Operationally, the frozen pipeline is ready to continue **blocks 1–14 in order**,
subject to fresh compute approval. Keep all conditions, budgets and tasks unchanged;
this block stays in the final study. Its scores do not justify selective stopping,
replacement, or post-training.

If the other blocks matched this block's execution time, 224 attempts would need
about **1.44 GPU hours of execution (~$0.87 at this rate)**, plus session overhead.
Repeating this entire cold-start/export pattern for 14 separate sessions would be
about **4.02 hours and $2.43** before adjustments. These are projections from four
fixed tasks, not guaranteed bounds. Other tasks may use substantially more turns.
Their nominal maximum agent budget remains **18.67 hours**, plus setup, grading
and export; a 14 ×110-minute separate-session envelope would be **25.67 hours,
~$15.50** before adjustments at today's combined rate.

For the next approval, use explicit duration/dollar caps with room for worst-case
blocks, and recheck live stock/prices. Several predefined blocks can share a session
if its approved headroom and fresh-preflight requirements permit; do not silently
extend a session to finish. Preserve any operational missingness. The long image
cold start argues for amortizing setup where approved, not changing the experiment.
