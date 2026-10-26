# Held-out session 02 (Pod `kp179xwdr7s4ug`, one A40 Secure, EU-SE-1, $0.59/h)

Approved: one Pod, 13 h, at most $8.50. Both phases ran on this host.

- The Pod carried a host-side deadline: it deletes itself with its pod-scoped key after 45,900 s, in `scripts/lora_session/heldout_boot.sh`. A local guard was set for 10:30Z.
- **Actual: about $5.63** (9.33 h). Billing read $5.04 at deletion, while it was still lagging.
- The Pod was deleted by this session, and `list-pods` returned empty afterwards.

| Time (UTC) | Event |
|---|---|
| 10-25 22:09 | Pod created; host key verified against the boot log; pod API check returned 200 |
| ~22:20 | Adapter sha256 verified, model files identical to session 01; preflight passed; base dev check 8/20 (same 8 tasks) |
| 22:22–02:58 | Base phase `runs/heldout/base-s2`: 400/400, 0 infrastructure errors |
| 10-26 02:58 | Swap: base server stopped, LoRA v1 merged to BF16 (`merged-files.json`), served as `liquidbench-lora-v1` |
| 03:00–03:05 | Tuned dev check 10/20, the same 10 tasks as `runs/lora-v1/dev-rep1` and `dev-rep2`; tuned preflight passed |
| 03:05–07:27 | Tuned phase `runs/heldout/tuned-s2`: 400/400, 0 infrastructure errors |
| 07:28 | `/pilot-evidence` copied to `host-final.tar.gz` (sha256 `e9e72b42…`); tunnel closed |
| 07:29 | Pod deleted (204); `list-pods` empty |

The controlling Mac ran on battery from about 00:40Z to 03:40Z, lowest reading 83%, then on AC. It did not sleep.

Results: [`results.md`](results.md).
