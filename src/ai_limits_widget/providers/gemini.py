"""Provedor Gemini: cota ao vivo do AGY, com o cache da statusline como reserva."""

from __future__ import annotations

import json
import pathlib
import platform
import time
import urllib.error
import urllib.request
from typing import Any

try:
    from ..agy_integration import cache_file
    from ..models import NormalizedLimits, ProviderName, RateLimitWindow
except ImportError:  # Execução direta de app.py.
    from agy_integration import cache_file
    from models import NormalizedLimits, ProviderName, RateLimitWindow

from .base import ProviderError

LOAD_URL = "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist"
QUOTA_URL = "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary"
SESSION_MESSAGE = "Sessão do Gemini expirada. Abra o AGY e entre novamente."


class GeminiClient:
    """Consulta a cota do grupo Gemini. Não grava token nem o id do projeto."""

    provider_name: ProviderName = "gemini"
    minimum_refresh_interval_seconds = 1

    def __init__(
        self,
        path: pathlib.Path | None = None,
        *,
        allow_live: bool | None = None,
        token_path: pathlib.Path | None = None,
    ) -> None:
        self.path = path or cache_file()
        # Um caminho explícito é o gancho dos testes de cache: não sai para a rede.
        self.allow_live = path is None if allow_live is None else allow_live
        self.token_path = token_path

    def read_limits(self) -> NormalizedLimits:
        token = gemini_access_token(self.token_path) if self.allow_live else None
        if token:
            try:
                return self._read_live(token)
            except ProviderError:
                if self.path.is_file():
                    return self._read_cache()
                raise
        return self._read_cache()

    def _read_live(self, token: str) -> NormalizedLimits:
        try:
            loaded = _post_json(LOAD_URL, token, {"metadata": {"ideType": "ANTIGRAVITY"}})
            project = _project_id(loaded)
            if not project:
                raise ProviderError("gemini", "A cota ao vivo do Gemini não informou o projeto.")
            summary = _post_json(QUOTA_URL, token, {"project": project})
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ProviderError("gemini", SESSION_MESSAGE) from exc
            raise ProviderError("gemini", f"Falha ao consultar o Gemini (HTTP {exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError("gemini", "Não foi possível conectar ao serviço de uso do Gemini.") from exc
        limits = _normalize_summary(summary)
        if limits is None:
            raise ProviderError("gemini", "Resposta de cota do Gemini inválida.")
        return limits

    def _read_cache(self) -> NormalizedLimits:
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


def gemini_token_file(path: pathlib.Path | None = None) -> pathlib.Path:
    return path or pathlib.Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"


def gemini_has_session(path: pathlib.Path | None = None) -> bool:
    return gemini_access_token(path) is not None


def gemini_access_token(path: pathlib.Path | None = None) -> str | None:
    """Lê o access token já gravado pelo AGY. Não renova e não devolve token a vencer em 60s."""
    try:
        payload = json.loads(gemini_token_file(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    nested = payload.get("token") if isinstance(payload, dict) else None
    token_payload = nested if isinstance(nested, dict) else payload
    if not isinstance(token_payload, dict):
        return None
    token = token_payload.get("access_token")
    if not isinstance(token, str) or not token.strip():
        return None
    expires_at = _parse_expiry(token_payload.get("expiry") or token_payload.get("expires_at"))
    if expires_at is not None and expires_at - time.time() < 60:
        return None
    return token


def _parse_expiry(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 1000.0 if number > 10_000_000_000 else number
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        number = float(value)
    except ValueError:
        from datetime import datetime

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return number / 1000.0 if number > 10_000_000_000 else number


def _user_agent() -> str:
    system = platform.system().lower()
    os_type = {"windows": "windows", "linux": "linux", "darwin": "darwin"}.get(system, "linux")
    machine = platform.machine().lower()
    arch = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
    return f"antigravity/cli/1.4.0 (aidev_client; os_type={os_type}; arch={arch})"


def _post_json(url: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _user_agent(),
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ProviderError("gemini", "Resposta de cota do Gemini inválida.")
    return payload


def _project_id(payload: dict[str, Any]) -> str | None:
    project = payload.get("cloudaicompanionProject")
    if isinstance(project, str) and project.strip():
        return project.strip()
    if isinstance(project, dict):
        project_id = project.get("id")
        if isinstance(project_id, str) and project_id.strip():
            return project_id.strip()
    return None


def _normalize_summary(payload: dict[str, Any]) -> NormalizedLimits | None:
    groups = payload.get("groups")
    if not isinstance(groups, list):
        return None
    group = next(
        (
            item
            for item in groups
            if isinstance(item, dict) and "gemini" in str(item.get("displayName") or "").lower()
        ),
        None,
    )
    if not isinstance(group, dict):
        return None
    buckets = group.get("buckets")
    if not isinstance(buckets, list):
        return None
    model_name = str(group.get("displayName") or "Gemini")[:160]
    fetched_at = time.time()
    five_hour = _window(_matching_bucket(buckets, "5h"), 300, model_name, fetched_at)
    weekly = _window(_matching_bucket(buckets, "weekly"), 7 * 24 * 60, model_name, fetched_at)
    if five_hour is None and weekly is None:
        return None
    return {"five_hour": five_hour, "weekly": weekly, "fetchedAt": fetched_at}


def _matching_bucket(buckets: list[Any], kind: str) -> dict[str, Any] | None:
    for bucket in buckets:
        if not isinstance(bucket, dict) or bucket.get("disabled") is True:
            continue
        window = str(bucket.get("window") or "").lower()
        bucket_id = str(bucket.get("bucketId") or "").lower()
        if kind == "5h" and ("5h" in window or "5h" in bucket_id or "hour" in window):
            return bucket
        if kind == "weekly" and ("week" in window or "week" in bucket_id):
            return bucket
    return None


def _window(bucket: dict[str, Any] | None, duration: int, model_name: str, fetched_at: float) -> RateLimitWindow | None:
    if bucket is None:
        return None
    raw_fraction = _remaining_fraction(bucket)
    if raw_fraction is None:
        return None
    try:
        remaining = max(0.0, min(1.0, float(raw_fraction)))
    except (TypeError, ValueError):
        return None
    nested = bucket.get("remaining")
    reset_time = bucket.get("resetTime") or bucket.get("reset_time")
    if reset_time is None and isinstance(nested, dict):
        reset_time = nested.get("resetTime") or nested.get("reset_time")
    return {
        "usedPercent": (1.0 - remaining) * 100.0,
        "resetsAt": reset_time if isinstance(reset_time, (str, int, float)) else None,
        "windowDurationMins": duration,
        "modelName": model_name,
        "fetchedAt": fetched_at,
    }


def _remaining_fraction(bucket: dict[str, Any]) -> Any:
    for key in ("remainingFraction", "remaining_fraction"):
        if key in bucket:
            return bucket[key]
    nested = bucket.get("remaining")
    if isinstance(nested, dict):
        for key in ("remainingFraction", "remaining_fraction"):
            if key in nested:
                return nested[key]
    return None
