"""Integração de inicialização automática no Windows."""

from __future__ import annotations

import pathlib
import sys
from typing import Any

winreg: Any
try:
    import winreg as _winreg
except ImportError:  # Permite importar para testes fora do Windows.
    winreg = None
else:
    winreg = _winreg

WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_RUN_VALUE = "AI Limits Widget"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    python = pathlib.Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    executable = pythonw if pythonw.is_file() else python
    app = pathlib.Path(__file__).with_name("app.py").resolve()
    return f'"{executable}" "{app}"'


def set_start_with_windows(enabled: bool) -> None:
    if winreg is None:
        raise OSError("A inicialização automática só está disponível no Windows.")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, WINDOWS_RUN_VALUE, 0, winreg.REG_SZ, startup_command())
            return
        try:
            winreg.DeleteValue(key, WINDOWS_RUN_VALUE)
        except FileNotFoundError:
            pass
