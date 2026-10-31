"""Tokens visuais e formatação compartilhada pela interface."""

from __future__ import annotations

import datetime as dt
from typing import Any

BG = "#11130f"
PANEL = "#191c17"
PANEL_2 = "#20241d"
LINE = "#30352c"
TEXT = "#f0f2eb"
MUTED = "#969d8c"
ORANGE = "#c46a2b"
CLAUDE_PURPLE = "#9672c4"
GEMINI_BLUE = "#68a5f3"
GROK_LIGHT = "#d7dbe3"
YELLOW = "#f5c451"
RED = "#f47676"
TRANSPARENT_KEY = "#010203"

WINDOW_WIDTH = 356
WINDOW_HEIGHT = 438
COLLAPSED_HEIGHT = 42
COMPACT_ISLAND_MIN_WIDTH = 118
COMPACT_BATTERY_SLOT_WIDTH = 94
COMPACT_ISLAND_HEIGHT = 48
COMPACT_METER_WIDTH = 88
COMPACT_METER_HEIGHT = 32
COMPACT_ANIMATION_FRAME_MS = 16
COMPACT_EXPAND_DURATION_MS = 220
COMPACT_COLLAPSE_DURATION_MS = 180


def provider_visuals(provider: str) -> tuple[str, str, str]:
    return {
        "codex": (CLAUDE_PURPLE, "CODEX", "OPENAI"),
        "claude": (ORANGE, "CLAUDE CODE", "ANTHROPIC"),
        "gemini": (GEMINI_BLUE, "GEMINI", "GOOGLE"),
        "grok": (GROK_LIGHT, "GROK", "XAI"),
    }[provider]


def clamp_percent(value: Any) -> int | None:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return None


def remaining(used: Any) -> int | None:
    percent = clamp_percent(used)
    return None if percent is None else 100 - percent


def format_reset(value: Any) -> str:
    if not value:
        return "Renovação não informada"
    try:
        if isinstance(value, (int, float)):
            moment = dt.datetime.fromtimestamp(value)
        else:
            moment = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
        return f"Renova {moment:%d/%m às %H:%M}"
    except (ValueError, OSError, OverflowError):
        return f"Renova em {value}"
