"""Leitura, validação e gravação atômica das preferências locais."""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
from collections.abc import Mapping
from typing import Any, cast

try:
    from .models import PROVIDERS, AppConfig, LayoutName, Profile, ProviderName
except ImportError:  # Execução direta por scripts/start.ps1.
    from models import PROVIDERS, AppConfig, LayoutName, Profile, ProviderName


APP_DATA_DIR = pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home())) / "LimitesIA"
CONFIG_FILE = APP_DATA_DIR / "config.json"


def default_config() -> AppConfig:
    """Cria uma configuração independente, sem compartilhar listas ou mapas."""
    return {
        "providers": ["codex", "claude"],
        "refreshMinutes": 5,
        "layout": "cards",
        "compactPrimaryProfileId": None,
        "compactVisibleCount": 1,
        "startWithWindows": False,
        "executables": {"codex": None, "claude": None, "gemini": None},
        "profiles": [],
    }


def _normalize_profile(value: Any, index: int) -> Profile | None:
    if not isinstance(value, Mapping) or value.get("provider") not in PROVIDERS:
        return None
    provider = cast(ProviderName, value["provider"])
    label = str(value.get("label") or f"{provider.title()} {index + 1}").strip()
    executable = value.get("executable")
    config_dir = value.get("configDir")
    return {
        "id": str(value.get("id") or f"{provider}-{index + 1}"),
        "provider": provider,
        "label": label[:40],
        "executable": executable if isinstance(executable, str) else None,
        "configDir": config_dir if isinstance(config_dir, str) else None,
    }


def normalize_config(value: Any) -> AppConfig:
    """Converte configurações antigas ou parciais para o formato atual."""
    config = default_config()
    if not isinstance(value, Mapping):
        return config

    providers = value.get("providers")
    if isinstance(providers, list):
        config["providers"] = [cast(ProviderName, item) for item in providers if item in PROVIDERS]
    try:
        config["refreshMinutes"] = max(5, min(120, int(value.get("refreshMinutes", 5))))
    except (TypeError, ValueError):
        pass
    if value.get("layout") in {"cards", "compact"}:
        config["layout"] = cast(LayoutName, value["layout"])
    primary_profile_id = value.get("compactPrimaryProfileId")
    if isinstance(primary_profile_id, str) and primary_profile_id.strip():
        config["compactPrimaryProfileId"] = primary_profile_id.strip()
    try:
        config["compactVisibleCount"] = max(1, min(3, int(value.get("compactVisibleCount", 1))))
    except (TypeError, ValueError):
        pass
    if isinstance(value.get("startWithWindows"), bool):
        config["startWithWindows"] = value["startWithWindows"]

    executables = value.get("executables")
    if isinstance(executables, Mapping):
        for provider in PROVIDERS:
            executable = executables.get(provider)
            config["executables"][provider] = executable if isinstance(executable, str) and executable.strip() else None

    profiles = value.get("profiles")
    if isinstance(profiles, list):
        config["profiles"] = [
            profile for index, item in enumerate(profiles) if (profile := _normalize_profile(item, index)) is not None
        ]
    return config


def load_config(path: pathlib.Path | None = None) -> AppConfig:
    """Lê preferências locais sem jamais incluir credenciais."""
    target = path or CONFIG_FILE
    try:
        loaded = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return default_config()
    return normalize_config(loaded)


def _atomic_json_write(path: pathlib.Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def save_config(value: Mapping[str, Any], path: pathlib.Path | None = None) -> AppConfig:
    """Valida e grava preferências sem deixar um arquivo parcial para trás."""
    config = normalize_config(value)
    _atomic_json_write(path or CONFIG_FILE, config)
    return config
