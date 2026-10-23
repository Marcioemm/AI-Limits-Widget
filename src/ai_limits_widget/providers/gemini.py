"""Provedor Gemini baseado no cache sanitizado da integração AGY."""

from __future__ import annotations

import json
import pathlib

try:
    from ..agy_integration import cache_file
    from ..models import NormalizedLimits, ProviderName
except ImportError:  # Execução direta de app.py.
    from agy_integration import cache_file
    from models import NormalizedLimits, ProviderName

from .base import ProviderError


class GeminiClient:
    """Lê apenas o cache sanitizado produzido pela statusline oficial."""

    provider_name: ProviderName = "gemini"
    minimum_refresh_interval_seconds = 0

    def __init__(self, path: pathlib.Path | None = None) -> None:
        self.path = path or cache_file()

    def read_limits(self) -> NormalizedLimits:
        try:
            cached = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ProviderError("gemini", "Abra o AGY uma vez para receber a cota do modelo Gemini ativo.") from exc
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderError("gemini", "A última cota recebida do AGY não pôde ser lida.") from exc
        model = cached.get("model") if isinstance(cached, dict) else None
        quota = cached.get("quota") if isinstance(cached, dict) else None
        if not isinstance(model, dict) or not isinstance(quota, dict):
            raise ProviderError("gemini", "A última cota recebida do AGY é inválida.")
        try:
            remaining_fraction = max(0.0, min(1.0, float(quota["remainingFraction"])))
            captured_at = float(cached.get("capturedAt", 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("gemini", "A última cota recebida do AGY é inválida.") from exc
        model_name = str(model.get("displayName") or model.get("id") or "Gemini")
        return {
            "five_hour": None,
            "weekly": {
                "usedPercent": (1.0 - remaining_fraction) * 100.0,
                "resetsAt": quota.get("resetTime"),
                "windowDurationMins": 7 * 24 * 60,
                "modelName": model_name,
                "fetchedAt": captured_at,
            },
            "fetchedAt": captured_at,
        }

    def close(self) -> None:
        return None


AgyClient = GeminiClient
