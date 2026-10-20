"""Integração local e sem credenciais com o Antigravity CLI (``agy``)."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import time
from typing import Any

try:
    from .platform_support import cache_dir as platform_cache_dir, is_windows, quote_command
except ImportError:  # Execução direta pelo bridge durante desenvolvimento.
    from platform_support import cache_dir as platform_cache_dir, is_windows, quote_command

BRIDGE_EXE_NAME = "AI Limits AGY Bridge.exe"
BRIDGE_POSIX_NAME = "ai-limits-agy-bridge"


def app_data_dir() -> pathlib.Path:
    """Compatibilidade: os dados sanitizados do AGY agora vivem no cache da plataforma."""
    return platform_cache_dir()


def cache_file() -> pathlib.Path:
    return app_data_dir() / "agy_gemini_quota.json"


def settings_file() -> pathlib.Path:
    return pathlib.Path.home() / ".gemini" / "antigravity-cli" / "settings.json"


def bridge_command() -> str:
    """Retorna o comando persistente que o AGY chamará como statusline."""
    if getattr(sys, "frozen", False):
        bridge_name = BRIDGE_EXE_NAME if is_windows() else BRIDGE_POSIX_NAME
        executable = pathlib.Path(sys.executable).with_name(bridge_name)
        parts = [str(executable)]
    else:
        bridge = pathlib.Path(__file__).with_name("agy_bridge.py").resolve()
        parts = [sys.executable, str(bridge)]
    return quote_command(parts)


def is_our_bridge(command: Any) -> bool:
    if not isinstance(command, str):
        return False
    lowered = command.lower()
    return (
        "ai limits agy bridge" in lowered
        or "ai-limits-agy-bridge" in lowered
        or "agy_bridge.py" in lowered
    )


def statusline_state(path: pathlib.Path | None = None) -> str:
    """Retorna ``ready``, ``missing`` ou ``conflict`` sem alterar o AGY."""
    path = path or settings_file()
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "missing"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return "conflict"
    statusline = settings.get("statusLine") if isinstance(settings, dict) else None
    if not statusline:
        return "missing"
    if isinstance(statusline, dict) and is_our_bridge(statusline.get("command")):
        return "ready"
    return "conflict"


def install_statusline(path: pathlib.Path | None = None, command: str | None = None) -> str:
    """Instala o bridge preservando todas as demais configurações.

    Uma statusline de terceiros nunca é sobrescrita. O retorno é ``installed``,
    ``ready`` ou ``conflict``.
    """
    path = path or settings_file()
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        settings = {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("O arquivo de configurações do AGY não pôde ser lido.") from exc
    if not isinstance(settings, dict):
        raise RuntimeError("O arquivo de configurações do AGY não contém um objeto JSON válido.")

    current = settings.get("statusLine")
    if current and not (isinstance(current, dict) and is_our_bridge(current.get("command"))):
        return "conflict"

    new_command = command or bridge_command()
    if isinstance(current, dict) and current.get("command") == new_command and current.get("enabled", True):
        return "ready"
    settings["statusLine"] = {
        "type": "command",
        "command": new_command,
        "enabled": True,
        "stack_with_default": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json_write(path, settings)
    return "installed"


def remove_statusline(path: pathlib.Path | None = None) -> bool:
    """Remove somente a integração pertencente ao widget."""
    path = path or settings_file()
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
    current = settings.get("statusLine") if isinstance(settings, dict) else None
    if not (isinstance(current, dict) and is_our_bridge(current.get("command"))):
        return False
    del settings["statusLine"]
    _atomic_json_write(path, settings)
    return True


def _atomic_json_write(path: pathlib.Path, value: dict[str, Any]) -> None:
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def extract_gemini_quota(payload: dict[str, Any], captured_at: float | None = None) -> dict[str, Any] | None:
    """Reduz o payload da statusline à cota do modelo Gemini ativo.

    Campos pessoais presentes no payload original são deliberadamente
    descartados. Atualizações de modelos Claude/GPT não substituem o último
    Gemini ativo conhecido.
    """
    model = payload.get("model")
    if not isinstance(model, dict):
        return None
    model_id = model.get("id") if isinstance(model.get("id"), str) else ""
    display_name = model.get("display_name") if isinstance(model.get("display_name"), str) else model_id
    active_name = (display_name or model_id).strip()
    if active_name and "gemini" not in active_name.lower():
        return None

    quotas = payload.get("quota")
    if not isinstance(quotas, dict):
        return None
    candidates = [
        (str(bucket), value)
        for bucket, value in quotas.items()
        if "gemini" in str(bucket).lower() and isinstance(value, dict)
    ]
    if not candidates:
        return None
    bucket, quota = next(
        ((key, value) for key, value in candidates if "week" in key.lower()),
        candidates[0],
    )
    try:
        remaining_fraction = max(0.0, min(1.0, float(quota["remaining_fraction"])))
    except (KeyError, TypeError, ValueError):
        return None

    captured = float(captured_at if captured_at is not None else time.time())
    reset_time = quota.get("reset_time")
    reset_seconds = quota.get("reset_in_seconds")
    if reset_time is None and isinstance(reset_seconds, (int, float)):
        reset_time = captured + reset_seconds
    return {
        "schemaVersion": 1,
        "provider": "gemini",
        "model": {
            "id": model_id[:160],
            "displayName": (display_name or model_id or "Gemini")[:160],
        },
        "quota": {
            "bucket": bucket[:120],
            "remainingFraction": remaining_fraction,
            "resetTime": reset_time if isinstance(reset_time, (str, int, float)) else None,
            "resetInSeconds": reset_seconds if isinstance(reset_seconds, (int, float)) else None,
        },
        "capturedAt": captured,
    }


def save_statusline_payload(
    payload: dict[str, Any], path: pathlib.Path | None = None, captured_at: float | None = None
) -> bool:
    sanitized = extract_gemini_quota(payload, captured_at=captured_at)
    if not sanitized:
        return False
    target = path or cache_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json_write(target, sanitized)
    return True


class AgyClient:
    """Lê apenas o cache sanitizado produzido pela statusline oficial."""

    def __init__(self, path: pathlib.Path | None = None) -> None:
        self.path = path or cache_file()

    def read_limits(self) -> dict[str, Any]:
        try:
            cached = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RuntimeError("Abra o AGY uma vez para receber a cota do modelo Gemini ativo.") from exc
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("A última cota recebida do AGY não pôde ser lida.") from exc
        model = cached.get("model") if isinstance(cached, dict) else None
        quota = cached.get("quota") if isinstance(cached, dict) else None
        if not isinstance(model, dict) or not isinstance(quota, dict):
            raise RuntimeError("A última cota recebida do AGY é inválida.")
        try:
            remaining_fraction = max(0.0, min(1.0, float(quota["remainingFraction"])))
            captured_at = float(cached.get("capturedAt", 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("A última cota recebida do AGY é inválida.") from exc
        return {
            "model": str(model.get("displayName") or model.get("id") or "Gemini"),
            "weekly": {
                "usedPercent": (1.0 - remaining_fraction) * 100.0,
                "resetsAt": quota.get("resetTime"),
                "windowDurationMins": 7 * 24 * 60,
                "modelName": str(model.get("displayName") or model.get("id") or "Gemini"),
                "fetchedAt": captured_at,
            },
            "fetchedAt": captured_at,
        }
