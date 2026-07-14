"""
Unified multi-provider LLM client.

Provider priority:  Gemini (primary) → Groq (secondary)

The public API is a single dataclass `LLMClient` with one method:
    text = client.generate(prompt, system_prompt=None, max_tokens=2048)

Fallback is fully transparent — callers never need to know which provider
was used.  The module logs which provider handled each request and why any
fallback was triggered.

Adding a new provider later (OpenRouter, OpenAI, Ollama, …) only requires:
  1. Write a `_call_<name>` function.
  2. Append it (with its human-readable name) to `_PROVIDERS`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

import google.genai as genai
from google.genai import types as genai_types
from groq import Groq

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model names (override via env if needed)
# ---------------------------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GROQ_MODEL   = os.getenv("GROQ_MODEL",   "llama-3.1-8b-instant")

# Exceptions we consider "transient / quota" — triggers fallback
_FALLBACK_EXCEPTIONS = (
    Exception,          # catch-all; individual providers may raise many types
)


# ---------------------------------------------------------------------------
# Provider call functions
# Each function receives (prompt, system_prompt, max_tokens) → str
# Raise any exception to trigger fallback.
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str, system_prompt: str | None, max_tokens: int) -> str:
    """Call Google Gemini via the `google-genai` SDK (google.genai.Client)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)

    config = genai_types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        temperature=0.1,
        system_instruction=system_prompt if system_prompt else None,
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=config,
    )
    return response.text


def _call_groq(prompt: str, system_prompt: str | None, max_tokens: int) -> str:
    """Call Groq Cloud via the `groq` SDK."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")

    client = Groq(api_key=api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.1,
    )
    return completion.choices[0].message.content


# ---------------------------------------------------------------------------
# Provider registry — add new providers here in priority order
# ---------------------------------------------------------------------------
_PROVIDERS: list[tuple[str, callable]] = [
    ("Gemini",  _call_gemini),
    ("Groq",    _call_groq),
    # ("OpenRouter", _call_openrouter),   ← easy to add later
    # ("OpenAI",     _call_openai),
]


# ---------------------------------------------------------------------------
# Public LLMClient
# ---------------------------------------------------------------------------

class LLMClient:
    """
    Drop-in replacement for the old `anthropic.Anthropic` client.

    Usage:
        client = LLMClient()
        text = client.generate(prompt, system_prompt=SYSTEM_PROMPT)

    The `messages_create` compatibility shim means existing code that calls
        client.messages_create(prompt=..., system=..., max_tokens=...)
    continues to work unchanged (used by generator.py / eval/run.py).
    """

    def __init__(self) -> None:
        self._last_provider: str | None = None

    @property
    def last_provider(self) -> str | None:
        """Name of the provider that handled the most recent request."""
        return self._last_provider

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """
        Try each provider in order, fall back silently on any error.
        Returns the raw text string from the LLM.
        Raises RuntimeError only if ALL providers fail.
        """
        last_error: Exception | None = None

        for name, call_fn in _PROVIDERS:
            try:
                t0 = time.perf_counter()
                text = call_fn(prompt, system_prompt, max_tokens)
                elapsed = time.perf_counter() - t0
                self._last_provider = name
                logger.info(
                    f"[LLMClient] Provider={name} | "
                    f"tokens_approx={len(text.split())} | "
                    f"elapsed={elapsed:.2f}s ✓"
                )
                return text

            except _FALLBACK_EXCEPTIONS as exc:
                last_error = exc
                logger.warning(
                    f"[LLMClient] Provider={name} FAILED — "
                    f"{type(exc).__name__}: {exc}. "
                    f"Falling back to next provider..."
                )

        raise RuntimeError(
            f"All LLM providers exhausted. Last error: {last_error}"
        ) from last_error

    # ------------------------------------------------------------------
    # Compatibility shim — keeps generator.py / eval/run.py unchanged
    # ------------------------------------------------------------------

    def messages_create(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        **_kwargs,          # absorb unsupported kwargs silently
    ) -> "_FakeResponse":
        """Thin compatibility wrapper matching the old Anthropic call signature."""
        text = self.generate(prompt, system_prompt=system, max_tokens=max_tokens)
        return _FakeResponse(text)


class _FakeResponse:
    """Mimics the minimal anthropic.Message interface used in this codebase."""

    def __init__(self, text: str) -> None:
        self.content = [_FakeContent(text)]


class _FakeContent:
    def __init__(self, text: str) -> None:
        self.text = text


# ---------------------------------------------------------------------------
# Module-level helpers used by api.py / eval/run.py
# ---------------------------------------------------------------------------

def get_llm_client() -> LLMClient:
    """
    Factory.  Validates that at least one provider key is configured.
    Raises RuntimeError (→ HTTP 500 in FastAPI) if neither key is present.
    """
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_groq   = bool(os.getenv("GROQ_API_KEY"))

    if not has_gemini and not has_groq:
        raise RuntimeError(
            "No LLM API keys configured. "
            "Set GEMINI_API_KEY and/or GROQ_API_KEY in your .env file."
        )

    if not has_gemini:
        logger.warning("[LLMClient] GEMINI_API_KEY not set — Groq will be the only provider.")
    if not has_groq:
        logger.warning("[LLMClient] GROQ_API_KEY not set — Gemini will be the only provider.")

    return LLMClient()


def parse_json_response(raw_text: str, source: str = "") -> dict:
    """
    Shared JSON parser for LLM responses.
    Strips markdown fences, attempts json.loads, returns fallback on failure.
    """
    text = raw_text.strip()

    # Strip ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from {source or 'LLM'}: {text[:300]}")
        return {"answer": "INSUFFICIENT_CONTEXT", "citations": []}
