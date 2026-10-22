"""A small HTTP adapter for Qwen-compatible chat-completions servers."""

from dataclasses import dataclass
import os
from urllib.parse import urlparse

import httpx

from .sandbox import InfrastructureError


class ProviderError(InfrastructureError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class Completion:
    content: str
    input_tokens: int
    output_tokens: int
    metadata: dict


class ChatProvider:
    def __init__(self, config):
        self.config = config
        endpoint = urlparse(config["endpoint"])
        if (
            endpoint.scheme not in {"http", "https"}
            or not endpoint.hostname
            or endpoint.username
            or endpoint.password
            or endpoint.query
            or endpoint.fragment
        ):
            raise ValueError("Use an HTTP(S) endpoint without credentials, query, or fragment")
        local = endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
        if endpoint.scheme != "https" and not local:
            raise ValueError("Remote model endpoints must use HTTPS")

    def complete(self, messages, max_tokens, timeout):
        headers = {}
        key_name = self.config.get("api_key_env")
        if key_name:
            key = os.environ.get(key_name)
            if not key:
                raise ProviderError(f"Missing credential environment variable: {key_name}")
            headers["Authorization"] = "Bearer " + key
        payload = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": self.config["temperature"],
            "top_p": self.config["top_p"],
            "seed": self.config["seed"],
            "stream": False,
        }
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
                response = client.post(
                    self.config["endpoint"].rstrip("/") + "/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ProviderError(type(exc).__name__, retryable=True) from exc
        if response.status_code != 200:
            raise ProviderError(
                f"Provider HTTP {response.status_code}",
                retryable=response.status_code in {408, 429, 500, 502, 503, 504},
            )
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data["usage"]
            prompt = usage["prompt_tokens"]
            output = usage["completion_tokens"]
            if (
                not isinstance(content, str)
                or type(prompt) is not int
                or type(output) is not int
                or prompt < 0
                or output < 0
            ):
                raise ValueError("Invalid response fields")
            return Completion(
                content,
                prompt,
                output,
                {
                    "served_model": data.get("model"),
                    "system_fingerprint": data.get("system_fingerprint"),
                    "finish_reason": data["choices"][0].get("finish_reason"),
                    "usage": usage,
                },
            )
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Provider response lacks valid content or token usage") from exc
