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

    def post(self, route, payload, timeout, *, root=False):
        headers = {}
        key_name = self.config.get("api_key_env")
        if key_name:
            key = os.environ.get(key_name)
            if not key:
                raise ProviderError(f"Missing credential environment variable: {key_name}")
            headers["Authorization"] = "Bearer " + key
        endpoint = self.config["endpoint"].rstrip("/")
        if root:
            if not endpoint.endswith("/v1"):
                raise ProviderError("Server token counting requires an endpoint ending in /v1")
            endpoint = endpoint[:-3]
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
                response = client.post(endpoint + route, headers=headers, json=payload)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ProviderError(type(exc).__name__, retryable=True) from exc
        if response.status_code != 200:
            raise ProviderError(
                f"Provider HTTP {response.status_code}",
                retryable=response.status_code in {408, 429, 500, 502, 503, 504},
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("Provider returned invalid JSON") from exc

    def count_prompt(self, messages, timeout):
        """Count the server's chat template; no inference or hidden task data involved."""
        backend = self.config["token_counting"]
        try:
            if backend == "llama_cpp":
                prompt = self.post("/apply-template", {"messages": messages}, timeout, root=True)[
                    "prompt"
                ]
                if not isinstance(prompt, str):
                    raise ValueError("Invalid chat template")
                tokens = self.post(
                    "/tokenize",
                    {"content": prompt, "add_special": True, "parse_special": True},
                    timeout,
                    root=True,
                )["tokens"]
                if not isinstance(tokens, list) or any(type(t) is not int for t in tokens):
                    raise ValueError("Invalid token IDs")
                count = len(tokens)
            elif backend == "vllm":
                count = self.post(
                    "/tokenize",
                    {
                        "model": self.config["model"],
                        "messages": messages,
                        "add_generation_prompt": True,
                        "add_special_tokens": False,
                    },
                    timeout,
                    root=True,
                )["count"]
            else:
                raise ValueError("Unsupported token-counting backend")
            if type(count) is not int or count <= 0:
                raise ValueError("Invalid prompt count")
            return count
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Provider returned invalid prompt token count") from exc

    def complete(self, messages, max_tokens, timeout):
        payload = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": self.config["temperature"],
            "top_p": self.config["top_p"],
            "seed": self.config["seed"],
            "stream": False,
        }
        data = self.post("/chat/completions", payload, timeout)
        try:
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
