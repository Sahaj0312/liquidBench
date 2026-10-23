# Milestone 6 continuation: blocks 1–14

Prepared 2026-10-23. **Approved: one A40 session, at most eight hours and $6 all-in.**
The user approved this envelope and requested a practical per-block reserve before
execution. No additional session, substitution, top-up or extension is authorized.
Block 0 remains part of the study. This note changes operational session grouping,
not the experiment, its attempt order, or any per-attempt limit.

**Completed:** all 224 remaining attempts ran in order with the approved 120-minute
admission reserve. The one session lasted 95m11.88s through verified cleanup,
estimated $0.958150 before unreported adjustments; final settled billing is pending.
Both preflights passed and all resources were deleted. See the
[complete study report](milestone-6-results.md). The authorization and historical
proposal below remain as provenance, not permission for another rental.

## Proposed session and spending authorization

Target **one A40 session for all remaining 224 attempts**, with a maximum of
**8 hours from Pod creation and $6 USD all-in**, using existing credits. Delete
immediately after execution/export; eight hours is a ceiling, not a rental target.
Do not automatically provision a second session. If insufficient admission
headroom remains, export and delete, report the next untouched block, and request
a new concrete session authorization. This bounds approved spending; it does not
promise completion through arbitrary infrastructure failures or worst-case delays.

The live Runpod `get-gpu-type` read on 2026-10-23 returned NVIDIA A40 48 GB Secure
Cloud at **$0.59/hour**, LOW stock in **CA-MTL-1 and EU-SE-1**, and CUDA 13.2
capacity, filtered to one Pod and CUDA >=13.0. Prefer EU-SE-1 to match Block 0;
CA-MTL-1 is an eligible A40 location, with its host/location recorded explicitly.
Stock is not reserved. Recheck immediately before creation; do not substitute a
GPU or exceed the quoted rate without renewed approval.

[Runpod's current pricing](https://docs.runpod.io/pods/pricing) lists container disk
at $0.10/GB/month, with compute/storage billed by the second. Use the same 100 GB
ephemeral container disk and no persistent/network volumes. Using 720 hours/month:

| Item | Hourly estimate | At the eight-hour ceiling |
| --- | ---: | ---: |
| A40 | $0.590000 | $4.720000 |
| 100 GB ephemeral disk | $0.013889 | $0.111111 |
| Combined, before taxes/adjustments | **$0.603889** | **$4.831111** |
| Requested all-in spending cap | — | **$6.00** |

The $1.168889 difference is a ceiling buffer, not permission to extend duration.
At each admission, reserve cost through the planned cleanup deadline, not just
cost accrued so far. Use the earlier time/spend deadline. If known adjustments or
credit availability make the envelope infeasible, stop before provisioning; no
top-up or auto-pay change is authorized. Account balance was not freshly verified
by this catalog read. Settled billing and lifetime-times-rate estimates must remain
separate in the report.

Block 0's measured pace projects about **87 minutes of block execution** for the
remaining 14 blocks. Allowing startup, fresh preflights, checkpoints and export,
**roughly 1.7–2 hours / $1.03–$1.21 before adjustments** is a planning scenario,
not a promise. Do not use that average to admit a block. Eight hours provides room
for conservative admission while avoiding repeated cold starts. If the next block
cannot be admitted, the maximum authorized cost remains $6; a guaranteed cost to
finish all blocks cannot be inferred from four tasks or promised under failures.

## Frozen schedule

Run one block at a time with the existing CLI. Session 02 targets every row below
in order; a later approved session, if needed, starts only at the next untouched
block after a clean between-block stop. Every row contains 16 attempts, using the
exact condition ordering in `experiments/m6-plan.json`.

| Block | Repetition | Task order |
| ---: | ---: | --- |
| 1 | 1 | customer-name, eligibility-branch, icon-reference, locale-references |
| 2 | 1 | notice-link, option-list, optional-caption, product-card |
| 3 | 1 | range-schema, section-schema, select-schema, shipping-message |
| 4 | 1 | status-priority, stylesheet-pair, tag-membership, visible-list-limit |
| 5 | 2 | locale-references, notice-link, option-list, optional-caption |
| 6 | 2 | product-card, range-schema, section-schema, select-schema |
| 7 | 2 | shipping-message, status-priority, stylesheet-pair, tag-membership |
| 8 | 2 | visible-list-limit, announcement-subtitle, asset-references, blocks-schema |
| 9 | 2 | cart-arithmetic, customer-name, eligibility-branch, icon-reference |
| 10 | 3 | select-schema, shipping-message, status-priority, stylesheet-pair |
| 11 | 3 | tag-membership, visible-list-limit, announcement-subtitle, asset-references |
| 12 | 3 | blocks-schema, cart-arithmetic, customer-name, eligibility-branch |
| 13 | 3 | icon-reference, locale-references, notice-link, option-list |
| 14 | 3 | optional-caption, product-card, range-schema, section-schema |

Block 0's 16 attempts plus these 224 are the original 240; none is replaced.
Repetitions retain seed 42 and temperature zero, with fresh sandbox/history per
attempt. Prefix caching stays enabled across blocks on the same server. Record
session, host, block, sequence and timestamps to expose cache/time confounding in
latency comparisons. Never reset the server/cache to improve a condition's score.

## Approved admission adjustment

Before provisioning, the user explicitly requested replacing the 340-minute
admission requirement below with a conservative execution/cleanup reserve.
The session will use **120 minutes remaining before each block**: 80 minutes for
16 unchanged 300-second agent limits, 20 minutes for final grading/in-flight tools,
5 minutes for the initial count gate, and 15 minutes for export/deletion/verification.
This is operational headroom, not a sum of every HTTP and grader timeout and not
an unconditional guarantee through infrastructure stalls. No per-attempt limit
or freshness rule changes. The original proposal is retained below for provenance;
its 340-minute admission threshold and 20-minute cleanup threshold are superseded
by 120 and 15 minutes respectively.

Admission also reserves the corresponding cost. The controller stops launching
blocks when fewer than 120 minutes remain, stops any still-running process by the
session's final 15-minute cleanup reserve, and saves partial evidence/missingness.
An unexpectedly slow count gate or grader is preserved as an operational problem,
not repaired by changing the harness or selectively retrying. Preflight refresh
remains at 50 minutes between blocks; the frozen validation rule remains <1 hour.
Do not use scores in admission or stopping decisions. All remaining blocks may
share the session if these conditions continue to hold.

## Original admission proposal (superseded as stated above)

Before every block require **at least 340 minutes (5h40m) of remaining approved
session time**, and sufficient reserved spend for that interval. This deliberately
uses configured-timeout exposure, not the six-minute Block 0 observation:

- The unchanged block CLI repeats all 80 initial token-count requests, each with
  a 90-second timeout: a nominal **120-minute gate allowance**.
- The agent's 300-second timer excludes final snapshot/cleanup/grading, and an
  already-started tool may finish after the agent deadline. A conservative
  per-attempt planning expression is `490 + 25 × E` seconds, where `E` is the
  maximum number of evaluator sandbox calls for that task. This includes 300
  agent seconds, 25 in-flight tool seconds, 40 for snapshot/agent-container
  removal, 70 for grader initialization/removal, 25 for Theme Check, and 30
  seconds of local bookkeeping contingency. Add 90 seconds per block for image
  inspection and orchestration. The largest remaining block is below **200
  minutes** by this expression. Short-circuit grading is not assumed.
- Reserve **20 minutes for evidence export, deletion and verification** after
  the gate and attempt/grading allowances. Total: `120 + 200 + 20 = 340`.

These are conservative configured-timeout allowances, not a mathematical upper
bound under a hung OS, slow-drip HTTP response, or unavailable Runpod control
plane. In particular, HTTPX timeouts are per network phase, not an absolute
whole-request wall clock. The existing harness therefore cannot honestly promise
an unconditional worst-case completion time without changes. Preserve it as
requested: independently supervise the rental deadline, and treat any overrun as
an operational interruption with retained evidence/missingness, never a longer
agent budget. Do not claim this reservation makes infrastructure failure impossible.

Operational sequence at each boundary:

1. Check monotonic elapsed time, the absolute UTC deletion deadline, accrued and
   reserved spend, endpoint/host identity, and the next frozen block ID. If less
   than 340 minutes remains, export/delete before starting any new block. With
   an eight-hour session, the last block must be launched within the first 140
   minutes; this still accommodates the approximately 87-minute observed-pace
   scenario for all 14 blocks.
2. Run the unchanged preflight on every new deployment. Reuse a passing report
   only for the same verified server/config/source. Refresh between blocks when
   its `started_utc` age reaches 50 minutes, leaving margin for admission. The
   unchanged hard rule in `validate_report` remains **age <3600 seconds at CLI
   validation**, measured from preflight start, not completion. Recheck remaining
   rental/spend headroom after a refresh. A new server identity/restart also needs
   fresh host verification and preflight; an unplanned restart stops this session.
3. Use a new output path for every preflight, retain all reports, and never repeat
   a failed mandatory gate to obtain a pass. Diagnostic model failures retain
   their existing non-blocking classification. Once a block is admitted, the
   preflight becoming one hour old mid-block does not interrupt it: the frozen
   freshness policy is checked at block entry, not every attempt.
4. Invoke the unchanged block runner with its selected report and serving-evidence
   hashes. It performs all 80 count checks and rejects an existing output path.
   Exit code 1 from completed model failures is not a stop criterion; confirm
   `summary.complete` and continue in order. Gate/infrastructure failure, missing
   summary, incomplete block or external deadline interruption stops the session.
5. Export/checkpoint each completed block locally before considering the next.
   Preserve partial outputs on any failure. Start final export no later than
   20 minutes before the rental deadline, or earlier if spending requires it;
   delete and verify before the deadline. Do not start another block just because
   earlier blocks were fast, passed, or failed.

No benchmark retry, resume inside a block, replacement attempt, or score-based
selection is permitted. Existing transient provider retries inside an attempt
remain unchanged. An interrupted block keeps its original failed/partial/missing
slots; any recovery requires an explicitly documented protocol decision rather
than quietly rerunning it. A clean between-block stop leaves later blocks pending
and eligible for a subsequently approved session in their original order.

## Pins, export and final analysis

Use the exact deployment from Block 0 and preflight v2:

- Qwen2.5-Coder-7B-Instruct revision
  `c03e6d358207e414f1eca0bb1891e29f1db0e242`, BF16, no quantization.
- vLLM image
  `sha256:6ee133356d49ed24cee03dd0cda3d3980279a11c107ce3e752c89e76540f41c9`,
  vLLM 0.32.0; verify all package, weight/tokenizer and startup-command evidence.
- One A40, one sequence, TP1, GPU utilization 0.9, xgrammar, generation config
  `vllm`, prefix caching enabled. Context 32,768; cumulative tokens 393,216;
  12 turns; 1,024 output tokens; 300 agent seconds; request timeout 90 seconds;
  two transient retries; temperature 0, top_p 1, seed 42.
- Frozen plan file SHA-256
  `5155fe8ce80adaafd0d6bd8c23da71f2aa9d99d7e1a345433811bff812bac2f0`;
  Python source digest
  `63be28169db8365064dc6dc8e7228a1ed3178dc2975828221dd7122ec5991828`;
  local runtime ID
  `sha256:ffd88aa28203d5582a880a59727f5e4700f1bf225387a381b60cb60bbadc9638`.
- Original upstream skill pin/content, index and neutral text remain unchanged.

Before spending, start/verify the original local runtime, cached tokenizer and
private skill checkout; dry-validate the frozen plan; prepare evidence paths and
the existing SSH bootstrap. Use `caffeinate -is` tied to the supervised session,
with power assertions verified, until cleanup. Expose SSH only and verify the
host fingerprint before tunneling the model endpoint. Keep the Mac powered/open.

Export complete traces, patches, snapshots, grades, token usage, skill accesses,
exposure records, diagnostics and host logs after each session. Hash the private
archive before deleting the Pod. Obtain independent get/list evidence that the
Pod and its billable storage are gone. No retained volumes or stopped Pods.
Record billing entries if posted, otherwise a clearly labeled lifetime estimate.
Stop the tunnel, local VM and session caffeinate after verified cleanup.

The final comparison joins Block 0 and all later blocks on the original
task/repetition/condition keys. Report per-repeat correctness and explicit-submit
success separately; all six paired win/tie/loss contrasts by category, difficulty
and category × difficulty; both-pass/both-fail ties; missing/infra pairs; original
five versus new fifteen descriptively; injected versus requested/delivered skill
reads; input/output/total tokens; validation actions and responses; latency by
session; and trace-supported failure patterns including syntax, boolean defaults,
preservation and ignored feedback. Never pool deterministic repeats as independent
samples or attribute no-read on-demand success to retrieved skills. Raw skill
bodies/traces stay private; publish reviewed metadata and analysis only.

Local preparation validation: the unchanged runner's dry plan rebuilt and matched
the frozen 240-attempt/15-block plan, with no inference. No source, task, prompt,
grader, skill, experiment configuration or model budget was modified. Full CI for
the unchanged implementation passed on `d58d374`. No post-training is authorized.
