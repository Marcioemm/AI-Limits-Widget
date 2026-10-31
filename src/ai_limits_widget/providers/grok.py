"""Provedor de cota semanal do Grok CLI, usando só o token já gravado pelo login."""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.request
from typing import Any

try:
    from ..models import NormalizedLimits, ProviderName, RateLimitWindow
except ImportError:  # Execução direta de app.py.
    from models import NormalizedLimits, ProviderName, RateLimitWindow

from .base import ProviderError

BILLING_URL = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"
LOGIN_MESSAGE = 'Sessão do Grok expirada. Execute "grok login".'


class GrokClient:
    """Consulta a piscina semanal sem gravar nem renovar a credencial."""

    provider_name: ProviderName = "grok"
    minimum_refresh_interval_seconds = 1

    def __init__(self, executable: str | None = None, config_dir: str | None = None) -> None:
        self.executable = executable
        self.config_dir = config_dir

    def read_limits(self) -> NormalizedLimits:
        token = grok_access_token(self.config_dir)
        if not token:
            raise ProviderError("grok", LOGIN_MESSAGE)
        request = urllib.request.Request(
            BILLING_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "x-xai-token-auth": "xai-grok-cli",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ProviderError("grok", LOGIN_MESSAGE) from exc
            raise ProviderError("grok", f"Falha ao consultar o Grok (HTTP {exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError("grok", "Não foi possível conectar ao serviço de uso do Grok.") from exc
        window = _weekly_window(body)
        if window is None:
            raise ProviderError("grok", "Resposta de limites do Grok inválida.")
        return {"five_hour": None, "weekly": window, "fetchedAt": window["fetchedAt"]}

    def close(self) -> None:
        return None


def grok_auth_file(config_dir: str | None = None) -> pathlib.Path | None:
    """Localiza auth.json sem ler o conteúdo."""
    if config_dir:
        candidate = pathlib.Path(config_dir) / "auth.json"
        return candidate if candidate.is_file() else None
    if env_dir := os.environ.get("GROK_HOME"):
        candidate = pathlib.Path(env_dir) / "auth.json"
        if candidate.is_file():
            return candidate
    default = pathlib.Path.home() / ".grok" / "auth.json"
    return default if default.is_file() else None


def grok_has_session(config_dir: str | None = None) -> bool:
    return grok_access_token(config_dir) is not None


def grok_account_label(config_dir: str | None = None) -> str | None:
    """Devolve só o local-part do e-mail. A chave nunca sai desta função."""
    email = _selected_entry(config_dir)[1]
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[0][:40] or None


def grok_access_token(config_dir: str | None = None) -> str | None:
    token, _email = _selected_entry(config_dir)
    return token


def _selected_entry(config_dir: str | None) -> tuple[str | None, str | None]:
    path = grok_auth_file(config_dir)
    if path is None:
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None, None
    entries = _auth_entries(payload)
    preferred = [item for item in entries if "auth.x.ai" in item[0]]
    for _name, entry in preferred or entries:
        token = entry.get("key")
        if not isinstance(token, str) or not token.strip():
            continue
        if _is_expired(entry.get("expires_at")):
            continue
        email = entry.get("email")
        return token, email if isinstance(email, str) else None
    return None, None


def _auth_entries(payload: Any, name: str = "") -> list[tuple[str, dict[str, Any]]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("key"), str):
            return [(name, payload)]
        found: list[tuple[str, dict[str, Any]]] = []
        for key, value in payload.items():
            child = str(key)
            found.extend(_auth_entries(value, child if not name else f"{name}.{child}"))
        return found
    if isinstance(payload, list):
        found = []
        for item in payload:
            found.extend(_auth_entries(item, name))
        return found
    return []


def _is_expired(value: Any) -> bool:
    expires_at = _parse_expiry(value)
    return expires_at is not None and expires_at <= time.time()


def _parse_expiry(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 1000.0 if number > 10_000_000_000 else number
    if isinstance(value, str) and value.strip():
        try:
            number = float(value)
        except ValueError:
            try:
                return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return None
        return number / 1000.0 if number > 10_000_000_000 else number
    return None


def _weekly_window(body: Any) -> RateLimitWindow | None:
    config = body.get("config") if isinstance(body, dict) else None
    if not isinstance(config, dict):
        config = body if isinstance(body, dict) else None
    if not isinstance(config, dict):
        return None
    used = _usage_percent(config.get("creditUsagePercent"))
    if used is None:
        return None
    period = config.get("currentPeriod")
    resets_at = period.get("end") if isinstance(period, dict) else None
    if not resets_at:
        resets_at = config.get("billingPeriodEnd") or (body.get("billingPeriodEnd") if isinstance(body, dict) else None)
    return {
        "usedPercent": used,
        "resetsAt": resets_at if isinstance(resets_at, (str, int, float)) else None,
        "windowDurationMins": 7 * 24 * 60,
        "fetchedAt": time.time(),
    }


def _usage_percent(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= number <= 1:
        return number * 100.0
    if 1 < number <= 100:
        return number
    return None
