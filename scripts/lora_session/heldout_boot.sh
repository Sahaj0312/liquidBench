set -euo pipefail
trap 'echo "STAGE failed at line $LINENO" | tee -a /pilot-evidence/stages.log; sleep infinity' ERR
umask 077
# Held-out session: serve the pinned base model, then on request swap to the merged
# LoRA adapter. vLLM runs as a child so a swap never restarts the container.
mkdir -p /pilot-evidence /run/sshd /root/.ssh /workspace/upload
nvidia-smi -q > /pilot-evidence/nvidia-smi.txt
df -h > /pilot-evidence/disk.txt
free -h > /pilot-evidence/memory.txt
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends openssh-server
printf '%s\n' "$PUBLIC_KEY" > /root/.ssh/authorized_keys
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
ssh-keygen -A
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
/usr/sbin/sshd -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o PermitRootLogin=prohibit-password -o AllowTcpForwarding=yes
python3 - <<'CHECK'
import importlib.metadata as metadata
import json
import platform
import torch
from pathlib import Path
versions={name:metadata.version(name) for name in ('vllm','torch','transformers','tokenizers','xgrammar')}
evidence={'python':platform.python_version(),'packages':versions,'torch_cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0),'compute_capability':torch.cuda.get_device_capability(0),'bf16_supported':torch.cuda.is_bf16_supported(),'gpu_memory_bytes':torch.cuda.get_device_properties(0).total_memory}
Path('/pilot-evidence/software.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(json.dumps(evidence),flush=True)
assert versions['vllm']=='0.32.0', 'Unexpected vLLM version'
assert evidence['bf16_supported'], 'BF16 is not supported'
assert 'A40' in evidence['gpu'], 'Unexpected GPU'
CHECK
echo "STAGE download" | tee -a /pilot-evidence/stages.log
python3 -c "from huggingface_hub import snapshot_download; print(snapshot_download('Qwen/Qwen2.5-Coder-7B-Instruct', revision='c03e6d358207e414f1eca0bb1891e29f1db0e242'))"
pip install --no-deps --quiet peft==0.21.2 accelerate==1.15.0
python3 -c "import importlib.metadata as m, json; print(json.dumps({p: m.version(p) for p in ('vllm','torch','transformers','peft','accelerate')}))" | tee /pilot-evidence/training-packages.json
SNAPSHOT=/root/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-7B-Instruct/snapshots/c03e6d358207e414f1eca0bb1891e29f1db0e242
echo "STAGE serve-base" | tee -a /pilot-evidence/stages.log
printf '%s\n' '["vllm", "serve", "Qwen/Qwen2.5-Coder-7B-Instruct", "--revision", "c03e6d358207e414f1eca0bb1891e29f1db0e242", "--tokenizer-revision", "c03e6d358207e414f1eca0bb1891e29f1db0e242", "--dtype", "bfloat16", "--kv-cache-dtype", "auto", "--max-model-len", "32768", "--max-num-seqs", "1", "--tensor-parallel-size", "1", "--gpu-memory-utilization", "0.9", "--generation-config", "vllm", "--structured-outputs-config", "{\"backend\":\"xgrammar\"}", "--seed", "42", "--host", "0.0.0.0", "--port", "8000"]' > /pilot-evidence/command.json
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --revision c03e6d358207e414f1eca0bb1891e29f1db0e242 --tokenizer-revision c03e6d358207e414f1eca0bb1891e29f1db0e242 --dtype bfloat16 --kv-cache-dtype auto --max-model-len 32768 --max-num-seqs 1 --tensor-parallel-size 1 --gpu-memory-utilization 0.9 --generation-config vllm --structured-outputs-config '{"backend":"xgrammar"}' --seed 42 --host 0.0.0.0 --port 8000 > /pilot-evidence/server.log 2>&1 &
BASE_PID=$!
echo "STAGE waiting-for-swap" | tee -a /pilot-evidence/stages.log
while [ ! -f /workspace/upload/SWAP ]; do sleep 5; done
kill "$BASE_PID" || true
wait "$BASE_PID" || true
cd /workspace/upload
echo "STAGE merge" | tee -a /pilot-evidence/stages.log
python3 merge_lora.py --base "$SNAPSHOT" --adapter adapter --out /workspace/lora-v1/merged > /pilot-evidence/merge.log 2>&1
cp /workspace/lora-v1/merged/merged-files.json /pilot-evidence/merged-files.json
echo "STAGE serve-tuned" | tee -a /pilot-evidence/stages.log
printf '%s\n' '["vllm", "serve", "/workspace/lora-v1/merged", "--served-model-name", "liquidbench-lora-v1", "--dtype", "bfloat16", "--kv-cache-dtype", "auto", "--max-model-len", "32768", "--max-num-seqs", "1", "--tensor-parallel-size", "1", "--gpu-memory-utilization", "0.9", "--generation-config", "vllm", "--structured-outputs-config", "{\"backend\":\"xgrammar\"}", "--seed", "42", "--host", "0.0.0.0", "--port", "8000"]' > /pilot-evidence/command-tuned.json
vllm serve /workspace/lora-v1/merged --served-model-name liquidbench-lora-v1 --dtype bfloat16 --kv-cache-dtype auto --max-model-len 32768 --max-num-seqs 1 --tensor-parallel-size 1 --gpu-memory-utilization 0.9 --generation-config vllm --structured-outputs-config '{"backend":"xgrammar"}' --seed 42 --host 0.0.0.0 --port 8000 > /pilot-evidence/server-tuned.log 2>&1 &
wait $! || true
echo "STAGE tuned-server-exited" | tee -a /pilot-evidence/stages.log
sleep infinity
