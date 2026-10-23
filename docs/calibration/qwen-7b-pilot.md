# Executing the prepared 7B development pilot

This is a runbook for a **future explicitly approved** GPU session. Nothing here
provisions a GPU. The [manifest](qwen-7b-pilot.json) is a candidate deployment,
not observed hardware or a completed run. See the [status and cost report](milestone-4.md).

## Before starting a billable resource

Confirm a quote within the approved amount and duration, including disk, taxes,
egress and any minimum deposit. Target one A40 48 GB, roughly 48 GB host RAM,
100 GB disk, Linux x86_64 and NVIDIA driver branch 580 or newer. The pinned image
advertises CUDA 13.0.2. Verify NVIDIA container support and BF16 support, not just
the GPU's name. Do not substitute FP16, quantized weights or a shorter context.

Choose a host that can run the pinned Docker image, or a provider's custom-image
Pod with that exact digest and entrypoint arguments. A Pod need not support
Docker inside Docker: configure its image and startup arguments in the provider
instead. Confirm a working SSH tunnel or authenticated HTTPS route for **both**
`/v1/chat/completions` and `/tokenize` before approving the rental. A provider's
generic OpenAI proxy may omit tokenization and is insufficient.

For a custom Pod, set `VLLM_API_KEY` through its secret facility if using HTTPS;
set a matching local environment variable and `api_key_env` in an ignored copy
of the benchmark config. Do not expose an unauthenticated public inference port.
For a Docker host, the example below publishes only to loopback; use SSH. The
local orchestrator and isolated grader stay on the trusted workstation. Mount
only model cache on the GPU host, never the repository, evaluator data or Docker
socket into the model container.

Record rental start time and a shutdown deadline before startup. Two hours is
the proposed session cap, not a measured runtime. Stop on a failed deployment
gate; diagnose using synthetic probes without spending benchmark attempts.

## Candidate launch and host evidence

On an approved Docker-capable GPU host (commands have **not** been run here):

```sh
mkdir -p pilot-evidence model-cache
nvidia-smi -q > pilot-evidence/nvidia-smi.txt
df -h > pilot-evidence/disk.txt
free -h > pilot-evidence/memory.txt
PILOT_IMAGE=vllm/vllm-openai@sha256:6ee133356d49ed24cee03dd0cda3d3980279a11c107ce3e752c89e76540f41c9
docker pull --platform linux/amd64 "$PILOT_IMAGE"
docker image inspect "$PILOT_IMAGE" > pilot-evidence/image.json
docker run -d --name liquidbench-qwen7b --platform linux/amd64 \
  --gpus device=0 --shm-size 8g \
  -p 127.0.0.1:8000:8000 \
  -v "$PWD/model-cache:/root/.cache/huggingface" \
  "$PILOT_IMAGE" Qwen/Qwen2.5-Coder-7B-Instruct \
  --revision c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --tokenizer-revision c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --dtype bfloat16 --kv-cache-dtype auto \
  --max-model-len 8192 --max-num-seqs 1 --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.9 --generation-config vllm \
  --structured-outputs-config '{"backend":"xgrammar"}' \
  --seed 42 --host 0.0.0.0 --port 8000
docker inspect --format '{{json .Config.Cmd}}' liquidbench-qwen7b > pilot-evidence/command.json
docker logs liquidbench-qwen7b > pilot-evidence/server.log 2>&1
```

The container entrypoint is already `vllm serve`; do not repeat it in arguments.
No custom chat template, remote-code trust, LoRA, quantization or reasoning/tool
parser is enabled. `auto` KV precision must resolve to BF16 with BF16 weights;
confirm in startup evidence. Pin the generic JSON decoder to xgrammar; do not
constrain tool names or task-specific output schemas.
[vLLM structured-output configuration](https://github.com/vllm-project/vllm/blob/v0.32.0/vllm/config/structured_outputs.py).

Capture actual package and GPU data **inside the serving container**. On a Pod,
run the Python body directly; on a Docker host:

```sh
docker exec -i liquidbench-qwen7b python - > pilot-evidence/software.json <<'PY'
import importlib.metadata as metadata
import json
import platform
import torch
print(json.dumps({
    "python": platform.python_version(),
    "packages": {name: metadata.version(name) for name in
                 ("vllm", "torch", "transformers", "tokenizers", "xgrammar")},
    "torch_cuda": torch.version.cuda,
    "gpu": torch.cuda.get_device_name(0),
    "compute_capability": torch.cuda.get_device_capability(0),
    "bf16_supported": torch.cuda.is_bf16_supported(),
    "gpu_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
}, indent=2))
PY
```

Require the expected vLLM version, BF16 support, sufficient free GPU memory and
successful initialization with the pinned revision, dtype and 8192 context.
Save effective engine/sampling configuration from logs, including KV dtype,
JSON backend, compilation/cache settings and default penalties. `--generation-config
vllm` prevents model-card generation defaults from changing the experiment.
Request temperature 0, top_p 1 and seed 42 remain explicitly set by the harness.

Verify the cache snapshot directory corresponds to the pinned revision. Save
SHA-256 hashes of every downloaded config, tokenizer and weight file (follow
snapshot symlinks); retain the file list and resolved snapshot path. Compute the
UTF-8 `chat_template` hash from `tokenizer_config.json` and compare with
`cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`.
The older [serving metadata](serving.json) config hashes use JSON reserialization;
label newly collected raw-file hashes separately. An HTTP model ID alone cannot
prove revision, weights or precision.

For provider Pods, capture the equivalent image digest, startup arguments,
provider GPU/driver information and full server logs. Record any inability to
obtain evidence as unresolved. Do not mark deployment verified based on the
planned manifest. Preserve a separate `observed-serving.json` in the run bundle
with GPU, driver, packages/CUDA, model/tokenizer revision and hashes, effective
precision/settings, image digest and evidence paths.

## Endpoint and frozen-harness preflight

On the workstation, for an SSH-capable host:

```sh
ssh -N -L 127.0.0.1:8000:127.0.0.1:8000 APPROVED_GPU_HOST
```

Use a second terminal. Start the local Docker runtime, verify the committed
working tree is clean, and confirm no task/harness/config changes since the
baseline in the manifest. The config file hash and Git tree IDs in that manifest
permit this check; `git rev-parse HEAD:src HEAD:tasks HEAD:runtime HEAD:configs`
must match. The committed `qwen-base.json` retains its historical descriptive
revision string; the separate manifest supplies the exact serving pin without
changing any experimental setting. For HTTPS, only endpoint and credential-env
fields should differ in an ignored config copy.

```sh
uv sync --frozen
uv run liquidbench doctor
uv run pytest -q -m 'not integration'
LIQUIDBENCH_INTEGRATION=1 uv run pytest -q -m integration
uv run python scripts/preflight_endpoint.py \
  --config configs/qwen-base.json --output runs/7b-preflight-01
```

The preflight creates a new directory and refuses overwrite. It makes at most
four generation requests, with the configured 1,024-token output cap and no
retries, plus bounded tokenization calls. These synthetic warmup/diagnostic calls
are charged wall time but **not** benchmark attempts. They read no task or hidden
data, and do not modify the benchmark prompt. A near-window prompt leaves the
full output allowance and the harness's 32-token safety reservation.

Require exit 0, exact `/tokenize` versus `usage.prompt_tokens` agreement, strict
JSON on a prompt that asks for plain text, valid requested read/finish actions,
and normal finish reasons. Review raw responses and server logs: a probe success
alone cannot prove enforcement rather than voluntary JSON, so also verify the
server activated xgrammar for `response_format=json_object`. A model failing to
follow the synthetic action instruction is distinct from an HTTP/counting fault.
The report's `gpu_precision_revision_verified` remains false by design; HTTP
probes do not attest hardware.

This preflight checks message compatibility, not actual execution of model
actions. The integration tests cover real sandbox read/write/search/analyze/
render/check tools and all 71 grader verdicts; the pilot must still establish
whether 7B chooses and uses those tools effectively. No automatic fallbacks to
text output, different precision or altered budgets are allowed.

## Exactly one attempt per development task

After host evidence and endpoint gates pass, run once:

```sh
uv run liquidbench run-suite --config configs/qwen-base.json
```

Keep 12 turns, 24K cumulative tokens, 1,024 output tokens, 300 seconds per attempt,
90-second request timeout, two transient retries and an 8K context. Preserve the
entire returned `runs/suite-*` directory: summary, all traces, results, patches,
final snapshots and visible task manifests. The suite records the immutable
local sandbox image ID and source/task/config fingerprints. Attach host evidence
and preflight artifacts to the same retained bundle; do not mount that bundle
into an agent container. No second attempt to improve a failure's score.

Exit 1 indicates valid captured model failures; exit 2 indicates infrastructure
errors. Review every result before claiming five completed attempts. Save
interrupted attempts too. Do not selectively replace an infrastructure failure
with a passing rerun: identify any corrected suite separately.

Summarize with the existing script, substituting the actual new suite path:

```sh
uv run python scripts/analyze_runs.py \
  qwen_1_5b=runs/suite-20261023T013146Z-f5c34ab9 \
  qwen_3b=runs/suite-20261023T012954Z-ef72862f \
  qwen_7b=runs/ACTUAL_7B_SUITE > runs/7b-comparison.json
```

Report success, protocol/tool/provider errors, counts, all termination reasons,
prompt-count deltas, per-task and aggregate elapsed time. The script's per-run
records contain elapsed time; sum those separately from billable rental time.
Inspect trace and patch line evidence for the failure taxonomy in the
[analysis plan](milestone-4.md). Counts and grades alone do not explain failure.
Review artifacts for credentials before sharing; keep complete originals locally
and publish only reviewed report excerpts and artifact hashes.

## End the paid session

Export all serving evidence and artifacts before the deadline. Record final
logs, billed start/end, GPU rate, storage, transfer, tax and invoice total. Stop
the model container, close the tunnel, **terminate the rented resource**, and
remove unwanted billable volumes. Stopping vLLM or a container is not cancellation
of cloud billing. Confirm the provider shows no active billed resources for this
pilot. Preserve receipts and report unknown charges as unknown until settled.

Do not automatically extend the session if setup takes too long. Report partial
preparation or missing attempts and obtain separate approval for more compute.
Only then evaluate the gate for skills integration; do not begin it in this pilot.
