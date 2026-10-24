"""Claude as a trajectory teacher inside the unchanged Qwen agent harness.

Token figures returned to the runner are Qwen tokenizer counts, so every kept
trajectory provably fits the student's real context and per-action limits.
Claude's billed usage (including thinking) is kept in metadata and charged to a
spending ledger that refuses calls past its cap.
"""

from datetime import datetime, timezone
import json
from pathlib import Path

from .provider import Completion, ProviderError

# USD per million tokens (Claude API first-party rates, cached 2026-10-06).
PRICES = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50},
}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def usage_cost(model, usage, *, batch=False):
    price = PRICES[model]
    tokens = {
        "input": usage.get("input_tokens") or 0,
        "output": usage.get("output_tokens") or 0,
        "cache_read": usage.get("cache_read_input_tokens") or 0,
        "cache_write": usage.get("cache_creation_input_tokens") or 0,
    }
    cost = sum(tokens[k] * price[k] for k in tokens) / 1_000_000
    return cost / 2 if batch else cost


class Ledger:
    """Append-only spend record; every paid call checks the cap first."""

    def __init__(self, path, cap_usd):
        self.path = Path(path)
        self.cap = float(cap_usd)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def spent(self):
        if not self.path.exists():
            return 0.0
        return sum(json.loads(line)["usd"] for line in self.path.read_text().splitlines())

    def require(self, reserve_usd):
        if self.spent() + reserve_usd > self.cap:
            raise ProviderError(f"Spending cap ${self.cap:.2f} reached; no call made")

    def record(self, purpose, model, usage, *, batch=False):
        usd = usage_cost(model, usage, batch=batch)
        entry = {
            "utc": datetime.now(timezone.utc).isoformat(),
            "purpose": purpose,
            "model": model,
            "usage": usage,
            "batch": batch,
            "usd": usd,
        }
        with self.path.open("a") as handle:
            handle.write(json.dumps(entry) + "\n")
        return usd


def qwen_tokenizer():
    from transformers import AutoTokenizer

    root = Path(__file__).resolve().parents[2] / ".cache/qwen-7b-tokenizer"
    return AutoTokenizer.from_pretrained(root, local_files_only=True)


class ClaudeProvider:
    """Runner provider: same complete() contract as ChatProvider."""

    def __init__(
        self,
        model,
        ledger,
        *,
        effort="low",
        thinking_tokens=16000,
        reserve_usd=0.10,
        client=None,
        tokenizer=None,
    ):
        if model not in PRICES:
            raise ValueError(f"No pinned price for {model}")
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.model, self.ledger, self.effort = model, ledger, effort
        self.thinking_tokens, self.reserve = thinking_tokens, reserve_usd
        self.client = client
        self.transcript = None
        self.tokenizer = tokenizer or qwen_tokenizer()

    def qwen_prompt_tokens(self, messages):
        rendered = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return len(self.tokenizer.encode(rendered, add_special_tokens=False))

    def count_prompt(self, messages, timeout):
        return self.qwen_prompt_tokens(messages)

    def complete(self, messages, max_tokens, timeout):
        import anthropic

        if not messages or messages[0]["role"] != "system":
            raise ProviderError("Harness messages must start with the system prompt")
        self.ledger.require(self.reserve)
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                # Room for Claude's thinking; the visible action is held to max_tokens below.
                max_tokens=self.thinking_tokens + max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": messages[0]["content"],
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": m["role"], "content": m["content"]} for m in messages[1:]],
                cache_control={"type": "ephemeral"},
                output_config={"effort": self.effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
                timeout=max(timeout, 60),
            )
        except (
            anthropic.RateLimitError,
            anthropic.APIConnectionError,
            anthropic.InternalServerError,
        ) as exc:
            raise ProviderError(
                f"Claude transient error: {type(exc).__name__}", retryable=True
            ) from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        usage = response.usage.model_dump(exclude_none=True)
        usd = self.ledger.record("trajectory", self.model, usage)
        if response.stop_reason == "refusal":
            raise ProviderError("Claude declined the request")
        text = "".join(b.text for b in response.content if b.type == "text")
        # The exact student-format conversation: what was sent plus this reply.
        self.transcript = [*messages, {"role": "assistant", "content": text}]
        visible = len(self.tokenizer.encode(text, add_special_tokens=False))
        truncated = response.stop_reason == "max_tokens" or visible > max_tokens
        return Completion(
            text,
            self.qwen_prompt_tokens(messages),
            visible,
            {
                "finish_reason": "length" if truncated else "stop",
                "served_model": response.model,
                "teacher": self.model,
                "claude_usage": usage,
                "usd": usd,
                "stop_reason": response.stop_reason,
            },
        )
