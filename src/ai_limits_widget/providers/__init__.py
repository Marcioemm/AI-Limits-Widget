"""Registro e fábrica dos provedores de limites."""

from __future__ import annotations

from collections.abc import Callable

try:
    from ..models import Profile, ProviderName
except ImportError:  # Execução direta de app.py.
    from models import Profile, ProviderName

from .base import LimitsProvider, ProviderError, configured_executable, provider_commands
from .claude import ClaudeClient
from .codex import CodexClient
from .gemini import AgyClient, GeminiClient

ProviderFactory = Callable[[Profile], LimitsProvider]


def _codex(profile: Profile) -> LimitsProvider:
    return CodexClient(profile["executable"], profile["configDir"])


def _claude(profile: Profile) -> LimitsProvider:
    return ClaudeClient(profile["executable"], profile["configDir"], profile["id"])


def _gemini(_profile: Profile) -> LimitsProvider:
    return GeminiClient()


PROVIDER_FACTORIES: dict[ProviderName, ProviderFactory] = {
    "codex": _codex,
    "claude": _claude,
    "gemini": _gemini,
}


def create_provider(profile: Profile) -> LimitsProvider:
    try:
        factory = PROVIDER_FACTORIES[profile["provider"]]
    except KeyError as exc:
        raise ProviderError(profile["provider"], "Provedor de limites não registrado.") from exc
    return factory(profile)


__all__ = [
    "AgyClient",
    "ClaudeClient",
    "CodexClient",
    "GeminiClient",
    "LimitsProvider",
    "ProviderError",
    "configured_executable",
    "create_provider",
    "provider_commands",
]
