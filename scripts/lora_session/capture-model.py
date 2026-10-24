import hashlib
import json
from pathlib import Path

revision = 'c03e6d358207e414f1eca0bb1891e29f1db0e242'
snapshot = Path('/root/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-7B-Instruct/snapshots') / revision
assert snapshot.is_dir(), 'Pinned model snapshot missing'
files = {}
for path in sorted(snapshot.rglob('*')):
    if path.is_file():
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        files[str(path.relative_to(snapshot))] = {'sha256': digest, 'bytes': path.stat().st_size}
assert any(name.endswith('.safetensors') for name in files), 'No weights in snapshot'
tokenizer = json.loads((snapshot / 'tokenizer_config.json').read_text())
template_hash = hashlib.sha256(tokenizer['chat_template'].encode()).hexdigest()
assert template_hash == 'cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f'
report = {'revision': revision, 'snapshot': str(snapshot), 'files': files, 'chat_template_sha256': template_hash,
          'config': json.loads((snapshot / 'config.json').read_text())}
Path('/pilot-evidence/model-files.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'snapshot': str(snapshot), 'file_count': len(files), 'chat_template_sha256': template_hash}))
