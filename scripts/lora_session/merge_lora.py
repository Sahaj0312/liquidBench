"""Merge a saved LoRA adapter into the pinned base weights exactly as train_lora.py does.

BF16 base loaded on CPU, adapter applied, merge_and_unload, saved with the base
tokenizer. Writes a sha256 listing of the merged files for the session evidence.
python scripts/lora_session/merge_lora.py --base <snapshot> --adapter <dir> --out <dir>
"""

import argparse
import hashlib
import json
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    args = parser.parse_args()
    out = Path(args.out)
    model = PeftModel.from_pretrained(
        AutoModelForCausalLM.from_pretrained(args.base, dtype=getattr(torch, args.dtype)),
        args.adapter,
    ).merge_and_unload()
    model.save_pretrained(out)
    AutoTokenizer.from_pretrained(args.base).save_pretrained(out)
    digests = {}
    for path in sorted(out.iterdir()):
        with path.open("rb") as stream:
            digests[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    (out / "merged-files.json").write_text(json.dumps(digests, indent=2) + "\n")
    print(json.dumps({"merged": str(out), "files": len(digests)}))


if __name__ == "__main__":
    main()
