"""Descoberta e disponibilidade de perfis configurados."""

from __future__ import annotations

import json
import os
import pathlib

try:
    from .agy_integration import cache_file, statusline_state
    from .config import CONFIG_FILE, load_config, raw_config_mentions
    from .models import Profile
    from .providers import configured_executable, provider_commands
    from .providers.gemini import gemini_has_session
    from .providers.grok import grok_account_label, grok_auth_file, grok_has_session
except ImportError:  # Execução direta de app.py.
    from agy_integration import cache_file, statusline_state
    from config import CONFIG_FILE, load_config, raw_config_mentions
    from models import Profile
    from providers import configured_executable, provider_commands
    from providers.gemini import gemini_has_session
    from providers.grok import grok_account_label, grok_auth_file, grok_has_session


def claude_account_email(config_dir: pathlib.Path, is_default: bool) -> str | None:
    """Lê apenas o e-mail da conta no .claude.json; nunca toca em tokens."""
    state_file = pathlib.Path.home() / ".claude.json" if is_default else config_dir / ".claude.json"
    try:
        account = json.loads(state_file.read_text(encoding="utf-8")).get("oauthAccount") or {}
    except (OSError, ValueError, AttributeError):
        return None
    email = account.get("emailAddress") if isinstance(account, dict) else None
    return email if isinstance(email, str) and email.strip() else None


def discover_claude_profiles(executable: str | None) -> list[Profile]:
    """Encontra contas do Claude Code em ~/.claude, ~/.claude-* e CLAUDE_CONFIG_DIR."""
    home = pathlib.Path.home()
    default_dir = home / ".claude"
    candidates = [default_dir]
    if env_dir := os.environ.get("CLAUDE_CONFIG_DIR"):
        candidates.append(pathlib.Path(env_dir))
    try:
        candidates.extend(sorted(path for path in home.glob(".claude-*") if path.is_dir()))
    except OSError:
        pass

    profiles: list[Profile] = []
    seen_dirs: set[str] = set()
    seen_accounts: set[str] = set()
    for directory in candidates:
        key = os.path.normcase(str(directory.resolve()))
        if key in seen_dirs or not (directory / ".credentials.json").is_file():
            continue
        seen_dirs.add(key)
        is_default = key == os.path.normcase(str(default_dir.resolve()))
        email = claude_account_email(directory, is_default)
        if email:
            if email.lower() in seen_accounts:
                continue
            seen_accounts.add(email.lower())
        name = directory.name.lstrip(".").removeprefix("claude-") or "extra"
        suffix = "default" if is_default else "".join(ch if ch.isalnum() else "-" for ch in name)
        label = email.split("@")[0] if email else ("Padrão" if is_default else directory.name.lstrip("."))
        profiles.append(
            {
                "id": f"claude-{suffix}",
                "provider": "claude",
                "label": label[:40],
                "executable": executable,
                "configDir": None if is_default else str(directory),
            }
        )
    return profiles


def discover_grok_profiles(executable: str | None) -> list[Profile]:
    """Encontra a sessão do Grok em ~/.grok ou GROK_HOME, sem copiar a chave."""
    auth_file = grok_auth_file()
    if auth_file is None or not grok_has_session(str(auth_file.parent)):
        return []
    return [
        {
            "id": "grok-default",
            "provider": "grok",
            "label": grok_account_label(str(auth_file.parent)) or "Padrão",
            "executable": executable,
            "configDir": str(auth_file.parent),
        }
    ]


def load_profiles() -> list[Profile]:
    """Carrega perfis configurados e converte a configuração antiga quando necessário."""
    config = load_config()
    if config["profiles"]:
        profiles = [profile.copy() for profile in config["profiles"]]
    else:
        profiles = []
        executables = config["executables"]
        for provider in config["providers"]:
            if provider == "claude":
                discovered = discover_claude_profiles(executables.get(provider))
                if discovered:
                    profiles.extend(discovered)
                    continue
            profiles.append(
                {
                    "id": f"{provider}-default",
                    "provider": provider,
                    "label": "Padrão",
                    "executable": executables.get(provider),
                    "configDir": None,
                }
            )
    return _merge_discovered_grok(profiles, config["executables"].get("grok"))


def _merge_discovered_grok(profiles: list[Profile], executable: str | None) -> list[Profile]:
    """Inclui o Grok só enquanto o JSON salvo nunca citou o provedor."""
    if any(profile["provider"] == "grok" for profile in profiles):
        return profiles
    if raw_config_mentions("grok", CONFIG_FILE):
        return profiles
    discovered = discover_grok_profiles(executable)
    return [*profiles, *discovered] if discovered else profiles


def profile_is_available(profile: Profile) -> bool:
    return profile_unavailable_reason(profile) is None


def profile_unavailable_reason(profile: Profile) -> str | None:
    provider = profile["provider"]
    executable = profile.get("executable")
    commands = provider_commands(provider)
    has_executable = configured_executable(executable, commands) is not None
    if provider == "grok":
        if grok_has_session(profile.get("configDir")):
            return None
        if not has_executable:
            return "Grok CLI não encontrado"
        return 'Execute "grok login".'
    if provider == "gemini" and (gemini_has_session() or cache_file().is_file()):
        return None
    if not has_executable:
        if provider == "codex":
            return "Codex CLI não encontrado. Instale-o e entre com sua conta ChatGPT."
        if provider == "claude":
            return "Claude Code não encontrado. Instale-o e entre com sua conta Anthropic."
        return "AGY não encontrado. Instale o Antigravity CLI e entre com sua conta Google."
    if provider == "claude":
        config_dir = profile.get("configDir") or os.environ.get("CLAUDE_CONFIG_DIR")
        credentials = (
            (pathlib.Path(config_dir) / ".credentials.json")
            if config_dir
            else pathlib.Path.home() / ".claude" / ".credentials.json"
        )
        if not credentials.is_file():
            return 'Claude Code não autenticado. Execute "claude auth login" e abra o widget novamente.'
    if provider == "gemini":
        state = statusline_state()
        if state == "missing":
            return "Integração do AGY ainda não ativada. Abra Configurações e salve com Gemini marcado."
        if state == "conflict":
            return "O AGY já possui outra statusline; ela não foi sobrescrita."
    return None
