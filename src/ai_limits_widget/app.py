"""Ponto de entrada compatível para a interface modular."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Any

if __package__ in {None, ""}:  # Execução direta por scripts/start.ps1.
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ai_limits_widget.agy_integration import bridge_command, install_statusline
from ai_limits_widget.config import APP_DATA_DIR, load_config, save_config
from ai_limits_widget.integration import ProducerBusy, ProducerLock
from ai_limits_widget.profiles import load_profiles, profile_is_available
from ai_limits_widget.providers import create_provider


def __getattr__(name: str) -> Any:
    if name in {"UsageWidget", "SettingsDialog"}:
        from ai_limits_widget.ui.app import UsageWidget
        from ai_limits_widget.ui.settings import SettingsDialog

        return {"UsageWidget": UsageWidget, "SettingsDialog": SettingsDialog}[name]
    if name == "WINDOW_WIDTH":
        from ai_limits_widget.ui.theme import WINDOW_WIDTH

        return WINDOW_WIDTH
    raise AttributeError(name)


def remaining(value: Any) -> float | None:
    return None if value is None else max(0, min(100, 100 - float(value)))


def run_integration() -> None:
    import signal
    import threading

    from ai_limits_widget.collector import Collector

    stop = threading.Event()
    stop_file = APP_DATA_DIR / "integration.stop"
    stop_file.unlink(missing_ok=True)
    previous = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, lambda *_: stop.set())
    config = load_config()
    collector = Collector(load_profiles(), config["refreshMinutes"] * 60, publish=True)
    try:
        while not stop.is_set() and not stop_file.exists():
            collector.collect()
            stop.wait(1)
    finally:
        collector.close()
        stop_file.unlink(missing_ok=True)
        for signum, handler in previous.items():
            signal.signal(signum, handler)


__all__ = ["executable_filetypes", "main", "print_once", "provider_commands"]


def provider_commands(provider: str, *, windows: bool | None = None) -> tuple[str, ...]:
    """Expõe os comandos nativos para integrações e testes de plataforma."""
    on_windows = os.name == "nt" if windows is None else windows
    commands = (
        {
            "codex": ("codex.exe", "codex.cmd", "codex"),
            "claude": ("claude.exe", "claude.cmd", "claude"),
            "gemini": ("agy.exe", "agy.cmd", "agy"),
            "grok": ("grok.exe", "grok.cmd", "grok"),
        }
        if on_windows
        else {"codex": ("codex",), "claude": ("claude",), "gemini": ("agy",), "grok": ("grok",)}
    )
    return commands[provider]


def executable_filetypes(*, windows: bool | None = None) -> list[tuple[str, str]]:
    on_windows = os.name == "nt" if windows is None else windows
    return (
        [("Executáveis", "*.exe *.cmd"), ("Todos os arquivos", "*.*")] if on_windows else [("Todos os arquivos", "*")]
    )


def print_once() -> None:
    profiles = [profile for profile in load_profiles() if profile_is_available(profile)]
    if not profiles:
        raise RuntimeError("Nenhuma CLI disponível. Instale e autentique o Codex CLI ou o Claude Code.")
    output: dict[str, Any] = {}
    for profile in profiles:
        client = create_provider(profile)
        try:
            data = client.read_limits()
            first, second = data.get("five_hour"), data.get("weekly")
            output[f"{profile['provider']}:{profile['label']}"] = {
                "five_hour_remaining": remaining((first or {}).get("usedPercent")),
                "weekly_remaining": remaining((second or {}).get("usedPercent")),
            }
        finally:
            client.close()
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Widget de limites do Codex, Claude Code e Gemini via AGY")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--integration", action="store_true", help="publica limites sem abrir janela")
    modes.add_argument("--widget", action="store_true", help="abre o widget e preserva este modo no login")
    modes.add_argument(
        "--stop-integration", action="store_true", help="encerra o modo sem janela após a consulta atual"
    )
    modes.add_argument("--once", action="store_true", help="consulta uma vez sem abrir a interface")
    modes.add_argument(
        "--install-agy-integration", action="store_true", help="configura o coletor local de cotas na statusline do AGY"
    )
    modes.add_argument("--build-smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.build_smoke_test:
        return
    if args.stop_integration:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        (APP_DATA_DIR / "integration.stop").touch()
    elif args.install_agy_integration:
        result = install_statusline(command=bridge_command())
        if result == "conflict":
            raise RuntimeError("O AGY já possui uma statusline personalizada; nenhuma configuração foi alterada.")
        print("Integração com AGY ativada.")
    else:
        try:
            with ProducerLock():
                if args.once:
                    print_once()
                    return
                config = load_config()
                if args.integration or args.widget:
                    config["integrationMode"] = args.integration
                    if args.integration:
                        config["integrationEnabled"] = True
                    config = save_config(config)
                if config["integrationMode"]:
                    run_integration()
                else:
                    if not config["integrationEnabled"]:
                        (APP_DATA_DIR / "integration" / "v1" / "snapshot.json").unlink(missing_ok=True)
                    from ai_limits_widget.ui.app import UsageWidget

                    UsageWidget().run()
        except ProducerBusy as exc:
            if sys.stderr is not None:
                print(str(exc), file=sys.stderr)
            else:
                import ctypes

                ctypes.windll.user32.MessageBoxW(None, str(exc), "AI Limits", 0x40)
            raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
