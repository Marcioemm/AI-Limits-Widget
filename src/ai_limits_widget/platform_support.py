"""Integrações pequenas e testáveis com Windows e desktops Linux."""

from __future__ import annotations

import os
import pathlib
import shlex
import subprocess
import sys
from collections.abc import Mapping
from typing import Any

APP_SLUG = "ai-limits-widget"
WINDOWS_APP_DIR = "LimitesIA"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_RUN_VALUE = "AI Limits Widget"
AUTOSTART_FILENAME = f"{APP_SLUG}.desktop"


def is_windows() -> bool:
    return os.name == "nt"


def _home_path(home: pathlib.Path | None = None) -> pathlib.Path:
    return home if home is not None else pathlib.Path.home()


def config_dir(
    environment: Mapping[str, str] | None = None,
    home: pathlib.Path | None = None,
    *,
    windows: bool | None = None,
) -> pathlib.Path:
    """Retorna o diretório de configuração sem criar arquivos."""
    env = os.environ if environment is None else environment
    home_path = _home_path(home)
    on_windows = is_windows() if windows is None else windows
    if on_windows:
        return pathlib.Path(env.get("LOCALAPPDATA") or home_path) / WINDOWS_APP_DIR
    return pathlib.Path(env.get("XDG_CONFIG_HOME") or home_path / ".config") / APP_SLUG


def cache_dir(
    environment: Mapping[str, str] | None = None,
    home: pathlib.Path | None = None,
    *,
    windows: bool | None = None,
) -> pathlib.Path:
    """Retorna o diretório de cache; no Windows preserva o caminho histórico."""
    env = os.environ if environment is None else environment
    home_path = _home_path(home)
    on_windows = is_windows() if windows is None else windows
    if on_windows:
        return pathlib.Path(env.get("LOCALAPPDATA") or home_path) / WINDOWS_APP_DIR
    return pathlib.Path(env.get("XDG_CACHE_HOME") or home_path / ".cache") / APP_SLUG


def font_family(*, windows: bool | None = None) -> str:
    return "Segoe UI" if (is_windows() if windows is None else windows) else "DejaVu Sans"


def symbol_font_family(*, windows: bool | None = None) -> str:
    return "Segoe UI Symbol" if (is_windows() if windows is None else windows) else "DejaVu Sans"


def quote_command(parts: list[str], *, windows: bool | None = None) -> str:
    """Formata um comando para o interpretador usado pela plataforma."""
    on_windows = is_windows() if windows is None else windows
    return subprocess.list2cmdline(parts) if on_windows else shlex.join(parts)


def startup_command(
    app_path: pathlib.PurePath,
    *,
    executable: pathlib.PurePath | None = None,
    frozen: bool | None = None,
    windows: bool | None = None,
) -> str:
    """Retorna o comando persistente usado para iniciar o widget após o login."""
    on_windows = is_windows() if windows is None else windows
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    python = pathlib.Path(sys.executable) if executable is None else executable
    if is_frozen:
        return quote_command([str(python)], windows=on_windows)
    if on_windows:
        pythonw = python.with_name("pythonw.exe")
        if pythonw.is_file():
            python = pythonw
    return quote_command([str(python), str(app_path)], windows=on_windows)


def autostart_file(
    environment: Mapping[str, str] | None = None,
    home: pathlib.Path | None = None,
) -> pathlib.Path:
    env = os.environ if environment is None else environment
    home_path = _home_path(home)
    base = pathlib.Path(env.get("XDG_CONFIG_HOME") or home_path / ".config")
    return base / "autostart" / AUTOSTART_FILENAME


def _desktop_exec(command: str) -> str:
    """Escapa um comando já tokenizado para o campo Exec de um arquivo desktop."""
    parts = shlex.split(command)
    escaped = []
    for part in parts:
        value = part.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
        escaped.append(f'"{value}"')
    return " ".join(escaped)


def set_start_at_login(
    enabled: bool,
    command: str,
    *,
    windows: bool | None = None,
    registry: Any = None,
    desktop_file: pathlib.Path | None = None,
) -> None:
    """Ativa o login automático no Registro ou via XDG Autostart."""
    on_windows = is_windows() if windows is None else windows
    if on_windows:
        if registry is None:
            try:
                import winreg as registry
            except ImportError as exc:
                raise OSError("O Registro do Windows não está disponível.") from exc
        with registry.CreateKeyEx(registry.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, registry.KEY_SET_VALUE) as key:
            if enabled:
                registry.SetValueEx(key, WINDOWS_RUN_VALUE, 0, registry.REG_SZ, command)
                return
            try:
                registry.DeleteValue(key, WINDOWS_RUN_VALUE)
            except FileNotFoundError:
                pass
        return

    target = desktop_file or autostart_file()
    if not enabled:
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    contents = "\n".join(
        (
            "[Desktop Entry]",
            "Type=Application",
            "Name=AI Limits Widget",
            f"Exec={_desktop_exec(command)}",
            "Terminal=false",
            "X-GNOME-Autostart-enabled=true",
            "",
        )
    )
    target.write_text(contents, encoding="utf-8")
