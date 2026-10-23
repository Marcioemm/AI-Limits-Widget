"""Ponto de entrada compatível para a interface modular."""

from __future__ import annotations

import argparse
import json
from typing import Any

try:
    from .agy_integration import bridge_command, install_statusline
    from .profiles import load_profiles, profile_is_available
    from .providers import create_provider
    from .ui.app import UsageWidget
    from .ui.theme import remaining
except ImportError:  # Execução direta por scripts/start.ps1.
    from agy_integration import bridge_command, install_statusline
    from profiles import load_profiles, profile_is_available
    from providers import create_provider
    from ui.app import UsageWidget
    from ui.theme import remaining


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
    parser.add_argument("--once", action="store_true", help="consulta uma vez sem abrir a interface")
    parser.add_argument(
        "--install-agy-integration",
        action="store_true",
        help="configura o coletor local de cotas na statusline do AGY",
    )
    args = parser.parse_args()
    if args.install_agy_integration:
        result = install_statusline(command=bridge_command())
        if result == "conflict":
            raise RuntimeError("O AGY já possui uma statusline personalizada; nenhuma configuração foi alterada.")
        print("Integração com AGY ativada.")
    elif args.once:
        print_once()
    else:
        UsageWidget().run()


if __name__ == "__main__":
    main()
