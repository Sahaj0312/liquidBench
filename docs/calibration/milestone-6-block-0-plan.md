# Block 0 operational check — part of the frozen Milestone 6 study

Prepared 2026-10-23. **Subsequently approved and completed; the Pod was deleted.**
See the [results and cleanup evidence](milestone-6-block-0-results.md). The quote
and approval request below are retained as the pre-deployment record. This is block
0 of [the existing plan](../../experiments/m6-plan.json), repetition 1 / seed 42,
not an extra pilot or a replacement experiment. The other 14 blocks remain
unattempted. Scores will not select which attempts run or whether this block stops.

| Task | Original category | Difficulty | Frozen condition order |
| --- | --- | --- | --- |
| announcement-subtitle | section-modification | easy | base, full, on_demand, neutral |
| asset-references | theme-references | easy | full, on_demand, neutral, base |
| blocks-schema | section-schema | hard | on_demand, neutral, base, full |
| cart-arithmetic | rendering | medium | neutral, base, full, on_demand |

## Live quote and proposed approval envelope

Runpod `get-gpu-type`, filtered to one Secure Cloud Pod and CUDA >=13.0, returned
**NVIDIA A40, 48 GB, LOW availability in EU-SE-1, $0.59/hour**, with CUDA 13.2
capacity. `list-pods` and `list-network-volumes` were both empty. This is a point-in-time
quote, not a reservation; recheck stock and the rate immediately before creation.
Stop if no qualifying A40 is available; no GPU substitution or automatic replacement.

[Current Runpod storage pricing](https://docs.runpod.io/pods/pricing) lists container
disk at $0.10/GB/month, billed per second. Plan: **100 GB ephemeral container disk**,
no volume disk or network volume. Using a 720-hour month:

- GPU: $0.59/hour ×110/60 = $1.081667.
- Disk: 100 ×$0.10/720 ×110/60 = $0.025463.
- Maximum-duration estimate: **$1.107130 before tax/adjustments**.
- Requested authorization: **one A40 session, at most 110 minutes and $2 USD all-in**,
  using existing credits. This authorizes Block 0 only, not the remaining blocks.

There are 80 nominal agent-budget minutes (16 ×300 seconds), with 30 minutes
reserved for setup, preflight, grading, evidence export and cleanup. Agent deadlines
do not include all final grading and can overrun during an in-flight tool, so this
is headroom, not a guarantee of completion. Supervise the external Pod deadline.
Do not start the block if setup leaves inadequate completion/export headroom.
Budget/deadline or infrastructure failures leave missing attempts in the study;
they never authorize selective reruns. Delete before the approved deadline/cap,
even if the block is incomplete, preserving all available evidence.

The connected tools do not expose the account's current credit balance. Previous
funding is known, but is not a fresh balance read. No additional top-up or auto-pay
change is authorized. Actual settled cost must come from billing; if not posted at
cleanup, report observed lifetime ×rate separately as an estimate, with settled
cost pending rather than claiming an exact invoice.

## Deployment verification and execution

The public Docker registry returned the exact pinned vLLM manifest digest; the
Hugging Face pinned revision remains available and its four advertised weight-shard
SHA-256 values match the prior verified deployment. The unchanged boot script is
prepared locally. This verifies artifact availability, not a running host's state.
After approval, capture and verify host/GPU/driver, BF16 weights/KV, all packages,
weight/tokenizer hashes, chat template and complete command before inference.

Use the unchanged configuration from [the Milestone 6 plan](milestone-6-plan.md)
and [preflight v2](preflight-v2.md): Qwen checkpoint
`c03e6d358207e414f1eca0bb1891e29f1db0e242`, image
`sha256:6ee133356d49ed24cee03dd0cda3d3980279a11c107ce3e752c89e76540f41c9`,
BF16/no quantization, vLLM 0.32.0, 32,768 context, 393,216 cumulative tokens,
12 turns, 1,024 output, 300 seconds, temperature 0, top_p 1, seed 42, one sequence,
TP1, GPU memory utilization 0.9, xgrammar, generation config `vllm`, prefix caching.
No tasks, prompts, graders, documents, budgets or model settings change.

Use the existing local SSH identity through the prior verified boot script's
`PUBLIC_KEY` handling. Expose only SSH; tunnel local 127.0.0.1:8000 to the model
port. Verify the host fingerprint from authenticated Runpod boot-log evidence.
No public unauthenticated model API is required. Runpod account SSH-key inventory
is empty; the prepared custom bootstrap installs the supplied public key directly.
No account key changes are needed.

`caffeinate -is -t 14400` is active during preparation. Renew it before provisioning
if necessary, verify its assertions, and keep it active through export/cleanup.
It prevents idle sleep; it cannot prevent a shutdown, closed-lid sleep or a network
outage. Keep the Mac powered and open during the session. Stop the session's
caffeinate process after verified cleanup.

After host readiness, run preflight once to a fresh directory, then the existing
runner with `--block 0`. Mandatory-gate failures stop; long-context model diagnostics
remain evidence. All 80 initial prompt counts are verified before the 16 attempts.
There are no additional model probes or retries outside the frozen policies.

```sh
uv run python scripts/preflight_endpoint.py --config configs/m6-base.json \
  --output runs/m6/session-01/preflight
uv run python scripts/run_loading_study.py --execute --block 0 \
  --preflight runs/m6/session-01/preflight/report.json \
  --serving-evidence runs/m6/session-01/serving.json --output runs/m6/block-00
uv run python scripts/analyze_loading_study.py runs/m6/block-00/attempts \
  > runs/m6/session-01/comparison.json
```

Preserve failed attempts, traces, patches, final snapshots, grades, document
exposure/reads, usage, latency, diagnostic errors and operational missingness.
Export host/preflight/attempt evidence and hash the archive before deleting the
Pod. Verify deletion and zero remaining session resources by independent get/list
reads. Do not stop and retain disk, create replacement Pods or retain a network
volume. Raw skill-containing traces remain private under the existing permission
restriction; commit only reviewed metadata and analysis.

Report completed attempts/hour, tokens/second of model/attempt elapsed time where
measurable, total Pod lifetime and setup/preflight/execution/export overhead
separately. Forecast the other blocks from observed throughput plus their 300-second
ceilings, without selecting them on scores. This mixed four-task block is an
operational sample, not a precision estimate of all task durations.

## Analysis-only addition before first study attempt

`scripts/analyze_loading_study.py` now computes all six unordered condition
contrasts, oriented as full/base, on_demand/base, neutral/base, full/neutral,
on_demand/full and on_demand/neutral. Counts are **per repetition**, overall and by
original category, difficulty, category ×difficulty, and an explicit broad-domain
crosswalk. Original manifest labels are retained and validated against frozen task
digests. The crosswalk groups legacy rendering/conditional/modification labels with
their newer counterparts; it does not alter any task or score.

Wins/losses use the unchanged successful-attempt status (`passed` versus `failed`),
not raw grader correctness or best-of-repeat selection. Ties distinguish both-pass
from both-fail. Any missing member makes a missing pair; otherwise an infrastructure
member makes an infrastructure pair. Neither is a win/loss/tie. Raw paired outcomes
retain both statuses. There is no pooled independent-sample interpretation.

Only the analysis script/tests and this operational note change. The frozen study
plan, source digest, task digests, feasibility report and inference code are
unchanged. Grouping tests cover wins, losses, both tie types, missingness,
infrastructure, label integrity and separation of repeats.
