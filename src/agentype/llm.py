"""LLM inference for persona discovery (BYOK opt-in only)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class LlmConfig:
    base_url: str
    model: str
    api_key: str


def config_for_llm(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> LlmConfig | None:
    """Build an LlmConfig if all three params are available (CLI or env), else None."""
    resolved_base = base_url or os.getenv("AGENTYPE_LLM_BASE_URL")
    resolved_key = api_key or os.getenv("AGENTYPE_LLM_API_KEY")
    resolved_model = model or os.getenv("AGENTYPE_LLM_MODEL")
    if not resolved_base or not resolved_key or not resolved_model:
        return None
    return LlmConfig(base_url=resolved_base, api_key=resolved_key, model=resolved_model)


def chat(
    prompt: str,
    *,
    system: str | None = None,
    max_tokens: int = 1024,
    timeout: int = 60,
    config: LlmConfig,
) -> str:

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": config.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    if "minimax" in config.base_url or "minimaxi" in config.base_url:
        body["reasoning_split"] = True
    request = urllib.request.Request(
        _chat_endpoint(config.base_url),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/cyzlmh/agentype",
            "X-Title": "Agentype",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

    try:
        text = payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LLM response did not contain a chat message.") from exc

    # strip <think>...</think> blocks from reasoning models
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()
    return text


def _chat_endpoint(base_url: str) -> str:
    endpoint = base_url.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    return f"{endpoint}/chat/completions"
