"""Minimal OpenAI-compatible chat client, standard library only.

The deployment this targets is a LiteLLM gateway in front of a reasoning model:
the response carries ``message.reasoning_content`` next to ``message.content``,
and the reasoning budget is charged to ``max_tokens``. Only ``content`` is ever
treated as code.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any

DEFAULT_TIMEOUT = 90.0


class LLMError(Exception):
    """A failure with a stable, client-facing code."""

    def __init__(
        self,
        code: str,
        message: str = "",
        *,
        status: int | None = None,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message
        self.status = status
        self.retry_after = retry_after
        self.details = details or {}


def _retry_after(error: urllib.error.HTTPError) -> float | None:
    value = error.headers.get("Retry-After") if error.headers else None
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    timeout: float = DEFAULT_TIMEOUT,
    disable_thinking: bool = True,
    allow_truncation: bool = False,
) -> dict[str, Any]:
    """Call ``/chat/completions`` and return the answer plus usage.

    ``allow_truncation`` exists for conversations: a reply cut off by
    ``max_tokens`` is still a usable answer with a visible cut, while a rewritten
    source file that stops mid-line is garbage, so the mirror path keeps it as an
    error.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if disable_thinking:
        # This deployment burns its whole budget on hidden reasoning otherwise:
        # measured 42 s and 6000 reasoning tokens for a five-line file, with no
        # code emitted at all.
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise LLMError("bad_key", f"HTTP {error.code}", status=error.code) from error
        if error.code == 429:
            raise LLMError(
                "rate_limited",
                "HTTP 429",
                status=429,
                retry_after=_retry_after(error),
            ) from error
        raise LLMError("upstream_error", f"HTTP {error.code}", status=error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as error:
        raise LLMError("upstream_error", str(error)) from error

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise LLMError("upstream_error", "response was not JSON") from error

    choices = data.get("choices") or []
    if not choices:
        raise LLMError("upstream_error", "response had no choices")
    choice = choices[0]
    message = choice.get("message") or {}
    content = message.get("content") or ""
    finish_reason = choice.get("finish_reason")

    usage = data.get("usage") or {}
    truncated = finish_reason == "length"
    if truncated and not allow_truncation:
        raise LLMError(
            "truncated",
            "the model exhausted max_tokens before writing code",
            status=200,
        )
    if not content.strip():
        raise LLMError("empty_completion", "the model returned no code", status=200)

    return {
        "content": content,
        "reasoning": message.get("reasoning_content") or "",
        "finish_reason": finish_reason,
        "truncated": truncated,
        "usage": usage,
        "model": data.get("model") or model,
    }


__all__ = ["LLMError", "chat", "DEFAULT_TIMEOUT"]
