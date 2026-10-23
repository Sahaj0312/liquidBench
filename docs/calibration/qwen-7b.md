# Qwen2.5-Coder-7B-Instruct deployment and calibration

Milestone 4 now supplies a [pinned deployment manifest](qwen-7b-pilot.json),
[execution runbook](qwen-7b-pilot.md), and [preparation/cost report](milestone-4.md).
After the initial preparation-only milestone, the user approved an A40 session.
The pinned vLLM 0.32.0 deployment passed preflight and solved **2/5 development
tasks**. The GPU was terminated after export. See the [pilot results](milestone-4-results.md)
and [observed serving metadata](qwen-7b-observed.json). Use the runbook's complete
arguments and verification gates for any future approved session.

The adapter is compatible at the HTTP/schema level: the official model supports
chat messages through a vLLM chat-completions server, and LiquidBench consumes
text content plus prompt/completion usage. It deliberately does not require
native function calling. Automated tests exercise the 7B configuration, request
shape, finish reason and usage parsing. The completed pilot also verifies this
path on the recorded A40/BF16 deployment; it does not certify other serving builds.

The checked checkpoint is
`Qwen/Qwen2.5-Coder-7B-Instruct@c03e6d358207e414f1eca0bb1891e29f1db0e242`.
Its configuration declares `Qwen2ForCausalLM`, BF16, 28 layers and a 32,768-token
native context. The tokenizer also declares 32,768. The model card describes
longer context using YaRN; this calibration does **not** enable it. Use an
explicit **8,192-token serving limit**, matching `configs/qwen-base.json` and the
local calibration. [Official model card](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct),
[pinned config](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct/blob/c03e6d358207e414f1eca0bb1891e29f1db0e242/config.json).

## Serving configuration

The original minimal serving command is below. Milestone 4's runbook adds the
pinned container, explicit JSON backend and evidence capture to these settings:

```sh
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct \
  --revision c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --tokenizer-revision c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --dtype bfloat16 --max-model-len 8192 --max-num-seqs 1 \
  --generation-config vllm --seed 42 --host 127.0.0.1 --port 8000
```

The request explicitly sets temperature 0, top_p 1, seed 42 and maximum output
1,024, plus `response_format: {"type":"json_object"}` for syntactic JSON output.
No task-specific decoding schema is supplied. Verify this mode is enforced on the
chosen serving build; it must remain identical across all four configurations.
`--generation-config vllm` avoids inheriting checkpoint-specific sampling
defaults. Record GPU model, driver/CUDA/vLLM versions, container digest, complete
command, effective generation settings, tokenizer/chat-template hashes, precision,
KV-cache dtype, checkpoint revision and runtime image ID. Do not use an unpinned
`latest` image for comparisons. The pinned build passed the recorded pilot
preflight. Recheck any replacement build before freezing it for comparisons.
[vLLM serving documentation](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/).

The `vllm` counting adapter sends the same messages/model to `/tokenize` with a
generation prompt and without adding special tokens a second time. Verify its
count against `usage.prompt_tokens` on short and near-limit conversations using
the chosen server build. The analogous llama.cpp path uses `/apply-template`
then `/tokenize`; the local runs test actual agreement.
[vLLM tokenizer protocol](https://github.com/vllm-project/vllm/blob/main/vllm/entrypoints/serve/tokenize/protocol.py),
[llama.cpp server API](https://github.com/ggml-org/llama.cpp/tree/master/tools/server#api-endpoints).

For a remote endpoint, use authenticated HTTPS or an SSH tunnel to localhost;
credentials stay in `api_key_env`, never task files. Remote HTTPS must also expose
the authorized `/tokenize` route on the same endpoint prefix. The approved pilot
used an SSH tunnel and has been terminated; no paid endpoint remains allocated.

## Precision and memory

Use BF16 for the proposed controlled 7B comparison. FP16 is an alternative only if
chosen consistently and recorded for every condition. Q4_K_M local runs are
development diagnostics, not interchangeable with BF16 7B measurements. Keep
inference precision and any adapter merge/quantization procedure constant across
the eventual four configurations.

At approximately 7.6B parameters, two-byte weights alone need about **15.2 GB**
(decimal), before KV cache, activations and runtime overhead. From the pinned
28-layer, four-KV-head, 128-dimension attention configuration, an 8K two-byte KV
cache is about **0.47 GB** per sequence. A 24 GB GPU is a reasonable planning target
for one sequence, but must be verified with the chosen runtime. These are size
estimates, not measured deployment requirements. This 8 GB unified-memory Mac
cannot run BF16 7B; running a roughly 4–5 GB quantized 7B alongside the 2 GB VM
would leave little OS/runtime headroom. The additional local diagnostic instead
uses the official 3B Q4_K_M model (about 2.1 GB on disk).

## Cost planning

No paid endpoint remains allocated. The completed pilot estimates $0.0445 in
rental charges; the provider invoice was not yet posted when recorded.
`qwen-base.json` keeps token prices `null`; a rental invoice must be tracked
separately from token-based estimates.

For input/output prices `p_in` and `p_out` in dollars per million tokens, an
observed run costs `(input_tokens*p_in + output_tokens*p_out)/1e6`. Cached input
is conservatively charged at the full input rate unless a separately validated
billing model is added. Failed requests with unknown usage invalidate the total.

The original five-task smoke used 42,221 input and 3,419 output tokens. At purely
illustrative rates of $0.20/$0.40 per million, that would be **$0.00981**; at
$1/$3, **$0.05248**. These are arithmetic scenarios, not provider quotes or a
prediction of 7B token usage. Different models/instructions may consume more.

The final JSON-mode 1.5B smoke used 8,140 input and 996 output tokens: **$0.00203**
or **$0.01113** under those same illustrative rates. Its earlier incorrect
submissions account for much of the reduction; do not project that lower cost
onto a competent 7B agent doing more useful work.

With the unchanged 24K cap, five attempts admit at most 120K measured tokens;
four configurations on these five tasks admit 480K. At a maximum input/output
rate of $0.40/M that is **$0.048 per five-task suite / $0.192 for four suites**;
at $3/M it is **$0.36 / $1.44**. These nominal ceilings exclude unknown-usage
retries, provider accounting overruns, hosting minimums and storage. Report such
exceptions rather than treating the admission cap as a billing guarantee.

For an hourly GPU, estimate `hourly_rate * billed_hours`, including model loading,
warmup and idle time. Token pricing cannot estimate rented-GPU cost. The pilot used
265 seconds from Pod creation to deletion request at $0.59/hour plus ephemeral
storage. Future sessions still require a current quote and explicit spending
approval; the previous session approval is not an ongoing rental authorization.

## Gate before a controlled four-configuration comparison

Freeze task/evaluator/runtime hashes, protocol/system prompt, visible context
policy, budgets, decoding, seed schedule, provider retries, precision and serving
build for all four conditions. Keep all development failures, length stops,
context stops and infrastructure errors visible. Rerun every condition after any
harness change. Future skill tokens must count against the same context and
cumulative allowances; do not silently enlarge one condition's budget.

The five-task pilot is complete with exact token-count agreement and interpretable
model failures. The next recommended gate is a matched base/base-plus-skills
development ablation, after pinning and reviewing the skill bundle. Five easy
fixtures do not establish research generalization or difficulty tiers. This
milestone adds no skills, post-training, held-out tasks or leaderboard.
