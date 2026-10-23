"""Modelos compartilhados pelo domínio, configuração e interface."""

from __future__ import annotations

from typing import Literal, TypedDict

ProviderName = Literal["codex", "claude", "gemini"]
LayoutName = Literal["cards", "compact"]
PROVIDERS: tuple[ProviderName, ...] = ("codex", "claude", "gemini")


class Profile(TypedDict):
    id: str
    provider: ProviderName
    label: str
    executable: str | None
    configDir: str | None


class AppConfig(TypedDict):
    providers: list[ProviderName]
    refreshMinutes: int
    layout: LayoutName
    compactPrimaryProfileId: str | None
    compactVisibleCount: int
    startWithWindows: bool
    executables: dict[ProviderName, str | None]
    profiles: list[Profile]


class RateLimitWindow(TypedDict, total=False):
    usedPercent: int | float | None
    resetsAt: str | int | float | None
    windowDurationMins: int | None
    modelName: str
    fetchedAt: int | float


class NormalizedLimits(TypedDict, total=False):
    five_hour: RateLimitWindow | None
    weekly: RateLimitWindow | None
    plan: str
    stale: bool
    staleReason: str
    fetchedAt: int | float
    nextRetryAt: int | float
