"""Contrato compartilhado pelos provedores de limites."""

from __future__ import annotations

import os
import pathlib
import shutil
from typing import Protocol

try:
    from ..models import NormalizedLimits, ProviderName
except ImportError:  # Execução direta de app.py.
    from models import NormalizedLimits, ProviderName


PROVIDER_COMMANDS: dict[ProviderName, tuple[str, ...]] = {
    "codex": ("codex.exe", "codex.cmd", "codex"),
    "claude": ("claude.exe", "claude.cmd", "claude"),
    "gemini": ("agy.exe", "agy.cmd", "agy"),
    "grok": ("grok.exe", "grok.cmd", "grok"),
}


class ProviderError(RuntimeError):
    """Erro de provedor com origem e detalhe estáveis para a interface."""

    def __init__(self, provider: ProviderName, detail: str) -> None:
        self.provider = provider
        self.detail = detail
        super().__init__(detail)


class LimitsProvider(Protocol):
    provider_name: ProviderName
    minimum_refresh_interval_seconds: int

    def read_limits(self) -> NormalizedLimits: ...

    def close(self) -> None: ...


def provider_commands(provider: ProviderName) -> tuple[str, ...]:
    if os.name != "nt":
        return {"codex": ("codex",), "claude": ("claude",), "gemini": ("agy",), "grok": ("grok",)}[provider]
    return PROVIDER_COMMANDS[provider]


def configured_executable(path: str | None, commands: tuple[str, ...]) -> str | None:
    if path and pathlib.Path(path).is_file():
        return path
    return next((found for command in commands if (found := shutil.which(command))), None)
