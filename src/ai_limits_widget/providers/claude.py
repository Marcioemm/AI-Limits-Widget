"""Provedor de uso OAuth do Claude Code."""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any, cast

try:
    from ..config import APP_DATA_DIR
    from ..models import NormalizedLimits, ProviderName, RateLimitWindow
except ImportError:  # Execução direta de app.py.
    from config import APP_DATA_DIR
    from models import NormalizedLimits, ProviderName, RateLimitWindow

from .base import ProviderError, configured_executable


class ClaudeClient:
    """Consulta o uso OAuth sem expor a credencial fora deste processo."""

    provider_name: ProviderName = "claude"
    minimum_refresh_interval_seconds = 1
    BACKOFF_SECONDS = (15 * 60, 30 * 60, 60 * 60)

    def __init__(
        self,
        executable: str | None = None,
        config_dir: str | None = None,
        profile_id: str = "default",
        state_path: pathlib.Path | None = None,
    ) -> None:
        self.executable = executable
        self.config_dir = config_dir
        self.profile_id = profile_id
        self._state_path = state_path
        self.last_data: NormalizedLimits | None = None
        self.next_retry_at = 0.0
        self.backoff_index = 0
        self._load_state()

    @property
    def state_file(self) -> pathlib.Path:
        return self._state_path or APP_DATA_DIR / f"claude_usage_cache_{self.profile_id}.json"

    def _load_state(self) -> None:
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
            data = state.get("data")
            if isinstance(data, dict):
                migrated = dict(data)
                if "weekly" not in migrated and "seven_day" in migrated:
                    migrated["weekly"] = migrated.pop("seven_day")
                self.last_data = cast(NormalizedLimits, migrated)
            else:
                self.last_data = None
            self.next_retry_at = float(state.get("nextRetryAt", 0))
            self.backoff_index = max(0, int(state.get("backoffIndex", 0)))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    def _save_state(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(
                json.dumps(
                    {
                        "data": self.last_data,
                        "nextRetryAt": self.next_retry_at,
                        "backoffIndex": self.backoff_index,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _stale_result(self, reason: str) -> NormalizedLimits:
        if not self.last_data:
            retry = dt.datetime.fromtimestamp(self.next_retry_at).strftime("%H:%M")
            raise ProviderError("claude", f"Claude: nova tentativa às {retry}")
        result = cast(NormalizedLimits, dict(self.last_data))
        result.update({"stale": True, "staleReason": reason, "nextRetryAt": self.next_retry_at})
        return result

    def _rate_limited(self, retry_after: str | None) -> NormalizedLimits:
        step = self.BACKOFF_SECONDS[min(self.backoff_index, len(self.BACKOFF_SECONDS) - 1)]
        try:
            server_delay = max(0, int(retry_after or 0))
        except ValueError:
            server_delay = 0
        self.next_retry_at = time.time() + max(step, server_delay)
        self.backoff_index = min(self.backoff_index + 1, len(self.BACKOFF_SECONDS) - 1)
        self._save_state()
        return self._stale_result("Consulta do Claude temporariamente limitada.")

    def credentials_file(self) -> pathlib.Path:
        base = self.config_dir or os.environ.get("CLAUDE_CONFIG_DIR")
        return (
            pathlib.Path(base) / ".credentials.json" if base else pathlib.Path.home() / ".claude" / ".credentials.json"
        )

    def _refresh_access_token(self) -> bool:
        executable = self.executable or configured_executable(
            None, ("claude.exe", "claude.cmd", "claude") if os.name == "nt" else ("claude",)
        )
        if not executable:
            npm_cli = pathlib.Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd"
            executable = str(npm_cli) if npm_cli.is_file() else None
        if not executable:
            return False
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW
        try:
            result = subprocess.run(
                [executable, "-p", "/usage", "--output-format", "json"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                startupinfo=startupinfo,
                creationflags=creationflags,
                env={**os.environ, **({"CLAUDE_CONFIG_DIR": self.config_dir} if self.config_dir else {})},
                check=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def read_limits(self, allow_token_refresh: bool = True) -> NormalizedLimits:
        if time.time() < self.next_retry_at:
            return self._stale_result("Aguardando o intervalo de segurança do Claude.")
        try:
            credentials = json.loads(self.credentials_file().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderError("claude", 'Claude não autenticado. Execute "claude auth login".') from exc
        oauth = credentials.get("claudeAiOauth") or credentials
        token = oauth.get("accessToken") if isinstance(oauth, dict) else None
        if not token:
            raise ProviderError("claude", 'Credencial do Claude ausente. Execute "claude auth login".')

        request = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                "anthropic-beta": "oauth-2025-04-20",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                if allow_token_refresh and self._refresh_access_token():
                    return self.read_limits(allow_token_refresh=False)
                raise ProviderError("claude", 'Sessão do Claude expirada. Execute "claude auth login".') from exc
            if exc.code == 429:
                return self._rate_limited(exc.headers.get("Retry-After"))
            raise ProviderError("claude", f"Falha ao consultar o Claude (HTTP {exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if self.last_data:
                self.next_retry_at = time.time() + 5 * 60
                self._save_state()
                return self._stale_result("Falha temporária ao consultar o Claude.")
            raise ProviderError("claude", "Não foi possível conectar ao serviço de uso do Claude.") from exc
        if not isinstance(body, dict):
            raise ProviderError("claude", "Resposta de limites do Claude inválida.")

        limits = body.get("limits")
        limit_items = limits if isinstance(limits, list) else []
        five = body.get("five_hour") or next(
            (item for item in limit_items if isinstance(item, dict) and item.get("group") == "session"), None
        )
        seven = body.get("seven_day") or next(
            (item for item in limit_items if isinstance(item, dict) and item.get("kind") == "weekly_all"), None
        )

        def window(value: Any, duration: int) -> RateLimitWindow | None:
            if not isinstance(value, dict):
                return None
            return {
                "usedPercent": value.get("utilization", value.get("percent")),
                "resetsAt": value.get("resets_at"),
                "windowDurationMins": duration,
            }

        data: NormalizedLimits = {
            "plan": str(oauth.get("subscriptionType") or "pro"),
            "five_hour": window(five, 5 * 60),
            "weekly": window(seven, 7 * 24 * 60),
            "fetchedAt": time.time(),
        }
        self.last_data = data
        self.next_retry_at = 0.0
        self.backoff_index = 0
        self._save_state()
        return {**data, "stale": False}

    def close(self) -> None:
        return None
