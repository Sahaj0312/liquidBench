"""BF16 LoRA fine-tune of Qwen2.5-Coder-7B-Instruct on the frozen SFT split, then merge.

Loss is on assistant actions only (liquidbench.sft.tokenize). Validation loss is
measured after every epoch and the epoch with the lowest validation loss is the
one merged; that rule is fixed before training. Tokenization must reproduce the
frozen manifest's token counts exactly, or training refuses to start.
python scripts/train_lora.py --model /workspace/qwen --out /workspace/lora-v1
python scripts/train_lora.py --model <tiny model> --out /tmp/smoke --smoke
"""

import argparse
import json
import math
from pathlib import Path
import shutil
import time

import torch

from liquidbench.sft import IGNORE, tokenize

TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


class Examples(torch.utils.data.Dataset):
    def __init__(self, rows, tokenizer):
        self.items = [tokenize(row["messages"], tokenizer) for row in rows]

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        ids, labels = self.items[i]
        return {"input_ids": ids, "labels": labels}


def collate(batch, pad_id):
    width = max(len(b["input_ids"]) for b in batch)
    pad = lambda seq, value: seq + [value] * (width - len(seq))  # noqa: E731
    return {
        "input_ids": torch.tensor([pad(b["input_ids"], pad_id) for b in batch]),
        "labels": torch.tensor([pad(b["labels"], IGNORE) for b in batch]),
        "attention_mask": torch.tensor([pad([1] * len(b["input_ids"]), 0) for b in batch]),
    }


def main():
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", default="runs/training/sft")
    parser.add_argument("--out", required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--alpha", type=int, default=32)
    parser.add_argument("--dropout", type=float, default=0.05)
    parser.add_argument("--accumulation", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--smoke", action="store_true", help="2 steps on CPU; no manifest check")
    args = parser.parse_args()
    data, out = Path(args.data), Path(args.out)
    rows = {
        name: [json.loads(line) for line in (data / f"{name}.jsonl").read_text().splitlines()]
        for name in ("train", "val")
    }
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    datasets = {name: Examples(r, tokenizer) for name, r in rows.items()}
    if not args.smoke:
        manifest = json.loads((data / "manifest.json").read_text())
        for name, ds in datasets.items():
            tokens = sum(len(ids) for ids, _ in ds.items)
            if tokens != manifest["splits"][name]["tokens"]:
                raise SystemExit(f"{name}: {tokens} tokens, manifest says otherwise")
    torch.manual_seed(args.seed)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.float32 if args.smoke else torch.bfloat16
    )
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(
        model,
        LoraConfig(
            r=args.rank,
            lora_alpha=args.alpha,
            lora_dropout=args.dropout,
            target_modules=TARGETS,
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()
    steps = math.ceil(len(datasets["train"]) / args.accumulation) * args.epochs
    training = TrainingArguments(
        output_dir=str(out / "checkpoints"),
        num_train_epochs=args.epochs,
        max_steps=2 if args.smoke else -1,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=1 if args.smoke else args.accumulation,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=max(1, round(0.05 * steps)),
        weight_decay=0.0,
        bf16=not args.smoke,
        use_cpu=args.smoke,
        logging_steps=1,
        eval_strategy="steps" if args.smoke else "epoch",
        eval_steps=1 if args.smoke else None,
        save_strategy="steps" if args.smoke else "epoch",
        save_steps=1 if args.smoke else None,
        save_total_limit=None,
        seed=args.seed,
        data_seed=args.seed,
        report_to=[],
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=training,
        train_dataset=datasets["train"],
        eval_dataset=datasets["val"],
        data_collator=lambda batch: collate(batch, tokenizer.pad_token_id),
    )
    started = time.time()
    trainer.train()
    history = trainer.state.log_history
    evals = [h for h in history if "eval_loss" in h]
    best = min(evals, key=lambda h: h["eval_loss"])
    checkpoint = out / "checkpoints" / f"checkpoint-{best['step']}"
    adapter = out / "adapter"
    shutil.copytree(checkpoint, adapter, dirs_exist_ok=True)
    del trainer, model
    model = PeftModel.from_pretrained(
        AutoModelForCausalLM.from_pretrained(
            args.model, dtype=torch.float32 if args.smoke else torch.bfloat16
        ),
        adapter,
    ).merge_and_unload()
    model.save_pretrained(out / "merged")
    tokenizer.save_pretrained(out / "merged")
    (out / "training.json").write_text(
        json.dumps(
            {
                "args": vars(args),
                "seconds": round(time.time() - started, 1),
                "best": best,
                "history": history,
                "versions": {
                    "torch": torch.__version__,
                    **{
                        m: __import__(m).__version__ for m in ("transformers", "peft", "accelerate")
                    },
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"best": best, "merged": str(out / "merged")}))


if __name__ == "__main__":
    main()
