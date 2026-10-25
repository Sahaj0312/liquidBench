# Held-out session 01 (Pod `ug888pmiezmfss`, one A40 Secure, $0.59/h)

Approved: 10 h, at most $7, one session, delete by 2026-10-25T09:55Z. **Actual: $7.54 (over the cap by $0.54).** The Pod was never deleted by this session.

| Time (UTC) | Event |
|---|---|
| 10-24 23:55 | Pod created; base model served; dev check 8/20 (matches Milestone 6) |
| 10-25 00:14–02:16 | Base run 1: stopped at attempt 167, a deadline cut mislabelled as an infrastructure error (Addition 3) |
| 02:32 | Runner fixed, plan re-frozen (source digest only), base rerun `base-r2` started |
| 04:53 | Operator Mac entered low-power sleep on battery at 1%, overriding caffeinate. The tunnel dropped, and `base-r2` stopped at attempt 199 (ConnectError, a genuine infrastructure stop) |
| ~12:25 | Pod terminated outside this session (billing ends; no host evidence copied) |
| 14:20 | Mac woke on AC power |

Results so far, kept as evidence only and not scored:

- `base-r2` agrees with run 1 on all 166 attempts both completed (same-host determinism).
- `size-guide-units`, the attempt that stopped run 1, now ends in `time_budget` in both base arms.
- Pace was 43.6 s per attempt, so one 400-attempt phase takes about 4.9 h; both phases plus the swap take about 10.5 h.

The tuned phase has not run. No held-out result exists yet.

Lessons for the next session:

- Run the controlling machine on AC power with sleep disabled.
- Enforce the Pod deadline on the host as well, not only from the controlling machine.
- Budget at least 12 h for both phases on one host.
