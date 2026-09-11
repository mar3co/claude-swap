"""Codex CLI provider: slot homes, usage, and the consumer-facing engine."""

from __future__ import annotations

CODEX_NUM_PREFIX = "codex:"


def split_provider_num(num: str | int) -> tuple[str, str]:
    """``"codex:2"`` → ``("codex", "2")``; ``2`` / ``"2"`` → ``("claude", "2")``."""
    text = str(num)
    if text.startswith(CODEX_NUM_PREFIX):
        return "codex", text[len(CODEX_NUM_PREFIX):]
    return "claude", text
