"""Widget nativo para acompanhar os limites do Codex e Claude Code."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import queue
import shutil
import subprocess
import threading
import time
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import urllib.error
import urllib.request
import webbrowser
from typing import Any


BG = "#11130f"
PANEL = "#191c17"
PANEL_2 = "#20241d"
LINE = "#30352c"
TEXT = "#f0f2eb"
MUTED = "#969d8c"
ORANGE = "#c46a2b"
CLAUDE_PURPLE = "#9672c4"
YELLOW = "#f5c451"
RED = "#f47676"
WINDOW_WIDTH = 356
WINDOW_HEIGHT = 438
COLLAPSED_HEIGHT = 42
APP_DATA_DIR = pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home())) / "LimitesIA"
CONFIG_FILE = APP_DATA_DIR / "config.json"
DEFAULT_CONFIG = {
    "providers": ["codex", "claude"],
    "refreshMinutes": 5,
    "layout": "cards",
    "executables": {"codex": None, "claude": None},
    "profiles": [],
}
CODEX_CLI_DOCS = "https://learn.chatgpt.com/docs/codex/cli"
CLAUDE_CODE_DOCS = "https://docs.anthropic.com/en/docs/claude-code/getting-started"


def load_config() -> dict[str, Any]:
    """Lê preferências locais sem jamais incluir credenciais."""
    config = {
        "providers": list(DEFAULT_CONFIG["providers"]),
        "refreshMinutes": DEFAULT_CONFIG["refreshMinutes"],
        "layout": DEFAULT_CONFIG["layout"],
        "executables": dict(DEFAULT_CONFIG["executables"]),
        "profiles": [],
    }
    try:
        loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return config

    providers = loaded.get("providers")
    if isinstance(providers, list):
        config["providers"] = [item for item in providers if item in {"codex", "claude"}]
    try:
        config["refreshMinutes"] = max(5, min(120, int(loaded.get("refreshMinutes", 5))))
    except (TypeError, ValueError):
        pass
    if loaded.get("layout") in {"cards", "compact"}:
        config["layout"] = loaded["layout"]
    executables = loaded.get("executables")
    if isinstance(executables, dict):
        for provider in ("codex", "claude"):
            value = executables.get(provider)
            config["executables"][provider] = value if isinstance(value, str) and value.strip() else None
    if isinstance(loaded.get("profiles"), list):
        config["profiles"] = loaded["profiles"]
    return config


def claude_account_email(config_dir: pathlib.Path, is_default: bool) -> str | None:
    """Lê apenas o e-mail da conta no .claude.json; nunca toca em tokens."""
    state_file = pathlib.Path.home() / ".claude.json" if is_default else config_dir / ".claude.json"
    try:
        account = json.loads(state_file.read_text(encoding="utf-8")).get("oauthAccount") or {}
    except (OSError, ValueError, AttributeError):
        return None
    email = account.get("emailAddress") if isinstance(account, dict) else None
    return email if isinstance(email, str) and email.strip() else None


def discover_claude_profiles(executable: str | None) -> list[dict[str, Any]]:
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

    profiles: list[dict[str, Any]] = []
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


def load_profiles() -> list[dict[str, Any]]:
    """Carrega perfis configurados e converte a configuração antiga quando necessário."""
    config = load_config()
    loaded = config.get("profiles")
    profiles: list[dict[str, Any]] = []
    if isinstance(loaded, list):
        for index, item in enumerate(loaded):
            if not isinstance(item, dict) or item.get("provider") not in {"codex", "claude"}:
                continue
            provider = item["provider"]
            label = str(item.get("label") or f"{provider.title()} {index + 1}").strip()
            profiles.append(
                {
                    "id": str(item.get("id") or f"{provider}-{index + 1}"),
                    "provider": provider,
                    "label": label[:40],
                    "executable": item.get("executable") if isinstance(item.get("executable"), str) else None,
                    "configDir": item.get("configDir") if isinstance(item.get("configDir"), str) else None,
                }
            )
    if profiles:
        return profiles

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
    return profiles


def configured_executable(path: str | None, commands: tuple[str, ...]) -> str | None:
    if path and pathlib.Path(path).is_file():
        return path
    return next((found for command in commands if (found := shutil.which(command))), None)


def profile_is_available(profile: dict[str, Any]) -> bool:
    return profile_unavailable_reason(profile) is None


def profile_unavailable_reason(profile: dict[str, Any]) -> str | None:
    provider = profile["provider"]
    executable = profile.get("executable")
    commands = ("codex.exe", "codex.cmd", "codex") if provider == "codex" else ("claude.exe", "claude.cmd", "claude")
    if not configured_executable(executable, commands):
        if provider == "codex":
            return "Codex CLI não encontrado. Instale-o e entre com sua conta ChatGPT."
        return "Claude Code não encontrado. Instale-o e entre com sua conta Anthropic."
    if provider == "claude":
        config_dir = profile.get("configDir") or os.environ.get("CLAUDE_CONFIG_DIR")
        credentials = (pathlib.Path(config_dir) / ".credentials.json") if config_dir else pathlib.Path.home() / ".claude" / ".credentials.json"
        if not credentials.is_file():
            return 'Claude Code não autenticado. Execute "claude auth login" e abra o widget novamente.'
    return None


def clamp_percent(value: Any) -> int | None:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return None


def remaining(used: Any) -> int | None:
    value = clamp_percent(used)
    return None if value is None else 100 - value


def format_reset(value: Any) -> str:
    if not value:
        return "Renovação indisponível"
    try:
        if isinstance(value, (int, float)):
            parsed = dt.datetime.fromtimestamp(value, tz=dt.timezone.utc)
        else:
            parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        local = parsed.astimezone()
        return f"Renova {local:%d/%m às %H:%M}"
    except (TypeError, ValueError, OSError):
        return "Renovação indisponível"


def virtual_screen_bounds(root: tk.Misc) -> tuple[int, int, int, int]:
    """Retorna (x, y, largura, altura) da área que cobre todos os monitores."""
    if os.name == "nt":
        try:
            import ctypes

            metrics = ctypes.windll.user32.GetSystemMetrics
            # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN
            left, top, width, height = (metrics(index) for index in (76, 77, 78, 79))
            if width > 0 and height > 0:
                return left, top, width, height
        except (AttributeError, OSError):
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def primary_work_area(root: tk.Misc) -> tuple[int, int, int, int]:
    """Retorna a área útil do monitor principal, sem a barra de tarefas."""
    if os.name == "nt":
        try:
            import ctypes
            import ctypes.wintypes

            rect = ctypes.wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        except (AttributeError, OSError):
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def fit_to_bounds(x: int, y: int, bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    """Desloca a janela para dentro da área visível, preservando a posição quando possível."""
    left, top, width, height = bounds
    x = max(left, min(x, left + width - WINDOW_WIDTH))
    y = max(top, min(y, top + height - WINDOW_HEIGHT))
    return x, y


def is_on_monitor(x: int, y: int) -> bool:
    """Confere se a barra de título cai em algum monitor (a área virtual pode ter lacunas)."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        import ctypes.wintypes

        rect = ctypes.wintypes.RECT(x, y, x + WINDOW_WIDTH, y + COLLAPSED_HEIGHT)
        monitor_from_rect = ctypes.windll.user32.MonitorFromRect
        monitor_from_rect.restype = ctypes.c_void_p
        return bool(monitor_from_rect(ctypes.byref(rect), 0))  # MONITOR_DEFAULTTONULL
    except (AttributeError, OSError):
        return True


class CodexClient:
    """Cliente JSON-RPC mínimo para o app-server local do Codex."""

    def __init__(self, executable: str | None = None, config_dir: str | None = None) -> None:
        self.executable = executable
        self.config_dir = config_dir
        self.process: subprocess.Popen[str] | None = None
        self.messages: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self.next_id = 1
        self.lock = threading.RLock()

    def _start(self) -> None:
        executable = self.executable or configured_executable(
            None, ("codex.exe", "codex.cmd", "codex") if os.name == "nt" else ("codex",)
        )
        if not executable:
            raise RuntimeError("Codex CLI não encontrado. Instale-o, entre com sua conta ChatGPT e abra o widget novamente.")

        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW

        self.messages = queue.Queue()
        environment = os.environ.copy()
        if self.config_dir:
            environment["CODEX_HOME"] = self.config_dir
        self.process = subprocess.Popen(
            [executable, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            startupinfo=startupinfo,
            creationflags=creationflags,
            env=environment,
        )
        threading.Thread(target=self._reader, args=(self.process, self.messages), daemon=True).start()
        self._request(
            "initialize",
            {
                "clientInfo": {"name": "ai-limits-widget", "version": "0.1.0"},
                "capabilities": {"experimentalApi": True},
            },
        )

    @staticmethod
    def _reader(process: subprocess.Popen[str], messages: queue.Queue[dict[str, Any] | None]) -> None:
        if not process.stdout:
            return
        try:
            for line in process.stdout:
                try:
                    messages.put(json.loads(line))
                except json.JSONDecodeError:
                    continue
        finally:
            messages.put(None)

    def _request(self, method: str, params: Any) -> Any:
        process = self.process
        if not process or process.poll() is not None or not process.stdin:
            raise RuntimeError("Serviço local do Codex indisponível.")
        request_id = self.next_id
        self.next_id += 1
        process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 15
        while True:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                raise TimeoutError("O Codex demorou demais para responder.")
            try:
                message = self.messages.get(timeout=timeout)
            except queue.Empty as exc:
                raise TimeoutError("O Codex demorou demais para responder.") from exc
            if message is None:
                raise RuntimeError("O serviço local do Codex foi encerrado.")
            if message.get("id") != request_id:
                continue
            if message.get("error"):
                raise RuntimeError(message["error"].get("message", "Erro retornado pelo Codex."))
            return message.get("result")

    @staticmethod
    def _extract_rate_limits(response: dict[str, Any]) -> dict[str, Any]:
        """Encontra as janelas de 5 horas e semanal sem supor primary/secondary.

        O app-server pode expor mais de um limite e não garante que ``primary``
        seja sempre a janela curta. A duração é a fonte de verdade para o rótulo.
        """
        groups: list[dict[str, Any]] = []
        direct = response.get("rateLimits")
        if isinstance(direct, dict):
            groups.append(direct)
        by_id = response.get("rateLimitsByLimitId")
        if isinstance(by_id, dict):
            groups.extend(item for item in by_id.values() if isinstance(item, dict))

        plan = next((str(group["planType"]) for group in groups if group.get("planType")), "—")
        windows: list[tuple[int, dict[str, Any]]] = []
        seen: set[tuple[int, Any, Any]] = set()
        for group in groups:
            for key in ("primary", "secondary"):
                window = group.get(key)
                if not isinstance(window, dict):
                    continue
                try:
                    duration = int(window.get("windowDurationMins"))
                except (TypeError, ValueError):
                    continue
                identity = (duration, window.get("usedPercent"), window.get("resetsAt"))
                if duration > 0 and identity not in seen:
                    seen.add(identity)
                    windows.append((duration, window))

        five_hour = min(
            (item for item in windows if item[0] <= 24 * 60),
            key=lambda item: abs(item[0] - 5 * 60),
            default=None,
        )
        seven_day = min(
            (item for item in windows if item[0] > 24 * 60),
            key=lambda item: abs(item[0] - 7 * 24 * 60),
            default=None,
        )

        # Versões antigas não traziam windowDurationMins. Mantém a compatibilidade
        # apenas quando não há qualquer duração para classificar.
        if not windows and groups:
            five_hour = (0, groups[0].get("primary")) if isinstance(groups[0].get("primary"), dict) else None
            seven_day = (0, groups[0].get("secondary")) if isinstance(groups[0].get("secondary"), dict) else None

        return {
            "plan": plan,
            "primary": five_hour[1] if five_hour else None,
            "secondary": seven_day[1] if seven_day else None,
        }

    def read_limits(self) -> dict[str, Any]:
        with self.lock:
            try:
                for attempt in range(2):
                    try:
                        if not self.process or self.process.poll() is not None:
                            self._start()
                        response = self._request("account/rateLimits/read", None)
                        if not isinstance(response, dict):
                            raise RuntimeError("Resposta de limites do Codex inválida.")
                        return self._extract_rate_limits(response)
                    except Exception:
                        self.close()
                        if attempt:
                            raise
                raise RuntimeError("Não foi possível consultar o Codex.")
            finally:
                # O app-server só permanece aberto durante a leitura. Isso reduz
                # o consumo em repouso sem alterar o intervalo de atualização.
                self.close()

    def close(self) -> None:
        process, self.process = self.process, None
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                process.kill()


class ClaudeClient:
    """Consulta o uso OAuth sem expor a credencial fora deste processo."""

    BACKOFF_SECONDS = (15 * 60, 30 * 60, 60 * 60)

    def __init__(self, executable: str | None = None, config_dir: str | None = None, profile_id: str = "default") -> None:
        self.executable = executable
        self.config_dir = config_dir
        self.profile_id = profile_id
        self.last_data: dict[str, Any] | None = None
        self.next_retry_at = 0.0
        self.backoff_index = 0
        self._load_state()

    @property
    def state_file(self) -> pathlib.Path:
        return APP_DATA_DIR / f"claude_usage_cache_{self.profile_id}.json"

    def _load_state(self) -> None:
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
            data = state.get("data")
            self.last_data = data if isinstance(data, dict) else None
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

    def _stale_result(self, reason: str) -> dict[str, Any]:
        if not self.last_data:
            retry = dt.datetime.fromtimestamp(self.next_retry_at).strftime("%H:%M")
            raise RuntimeError(f"Claude: nova tentativa às {retry}")
        result = dict(self.last_data)
        result.update({"stale": True, "staleReason": reason, "nextRetryAt": self.next_retry_at})
        return result

    def _rate_limited(self, retry_after: str | None) -> dict[str, Any]:
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
        return pathlib.Path(base) / ".credentials.json" if base else pathlib.Path.home() / ".claude" / ".credentials.json"

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

    def read_limits(self, allow_token_refresh: bool = True) -> dict[str, Any]:
        if time.time() < self.next_retry_at:
            return self._stale_result("Aguardando o intervalo de segurança do Claude.")

        try:
            credentials = json.loads(self.credentials_file().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError('Claude não autenticado. Execute "claude auth login".') from exc

        oauth = credentials.get("claudeAiOauth") or credentials
        token = oauth.get("accessToken")
        if not token:
            raise RuntimeError('Credencial do Claude ausente. Execute "claude auth login".')

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
                raise RuntimeError('Sessão do Claude expirada. Execute "claude auth login".') from exc
            if exc.code == 429:
                return self._rate_limited(exc.headers.get("Retry-After"))
            raise RuntimeError(f"Falha ao consultar o Claude (HTTP {exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if self.last_data:
                self.next_retry_at = time.time() + 5 * 60
                self._save_state()
                return self._stale_result("Falha temporária ao consultar o Claude.")
            raise RuntimeError("Não foi possível conectar ao serviço de uso do Claude.") from exc

        five = body.get("five_hour") or next(
            (item for item in body.get("limits", []) if item.get("group") == "session"), None
        )
        seven = body.get("seven_day") or next(
            (item for item in body.get("limits", []) if item.get("kind") == "weekly_all"), None
        )
        data = {
            "plan": oauth.get("subscriptionType") or "pro",
            "five_hour": {
                "usedPercent": (five or {}).get("utilization", (five or {}).get("percent")),
                "resetsAt": (five or {}).get("resets_at"),
            },
            "seven_day": {
                "usedPercent": (seven or {}).get("utilization", (seven or {}).get("percent")),
                "resetsAt": (seven or {}).get("resets_at"),
            },
            "fetchedAt": time.time(),
        }
        self.last_data = data
        self.next_retry_at = 0.0
        self.backoff_index = 0
        self._save_state()
        return {**data, "stale": False}


class Meter(tk.Frame):
    def __init__(self, master: tk.Misc, title: str, accent: str) -> None:
        super().__init__(master, bg=PANEL, highlightbackground=accent, highlightthickness=1)
        self.accent = accent
        self.columnconfigure(0, weight=1)
        self.title = tk.Label(self, text=title.upper(), bg=PANEL, fg=accent, font=("Segoe UI", 9, "bold"))
        self.title.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        self.value = tk.Label(self, text="—", bg=PANEL, fg=TEXT, font=("Segoe UI", 22, "bold"))
        self.value.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 2))
        self.canvas = tk.Canvas(self, height=13, bg=PANEL, highlightthickness=0)
        self.canvas.grid(row=2, column=0, sticky="ew", padx=12)
        self.reset = tk.Label(self, text="Carregando…", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), anchor="w")
        self.reset.grid(row=3, column=0, sticky="ew", padx=12, pady=(5, 10))
        self.percent: int | None = None
        self.canvas.bind("<Configure>", lambda _event: self._draw())

    def set_data(self, used: Any, resets_at: Any) -> None:
        self.percent = remaining(used)
        self.value.configure(text="—" if self.percent is None else f"{self.percent}%")
        self.reset.configure(text=format_reset(resets_at), fg=MUTED)
        self._draw()

    def set_error(self, message: str) -> None:
        self.percent = None
        self.value.configure(text="—")
        self.reset.configure(text=message, fg=RED)
        self._draw()

    def set_unavailable(self, message: str) -> None:
        """Mostra que a CLI respondeu, mas não publicou aquela janela."""
        self.percent = None
        self.value.configure(text="—")
        self.reset.configure(text=message, fg=MUTED)
        self._draw()

    def _draw(self) -> None:
        self.canvas.delete("all")
        width = max(24, self.canvas.winfo_width())
        height = 13
        body_end = width - 7
        self.canvas.create_rectangle(1, 1, body_end, height - 2, outline=self.accent, width=1)
        self.canvas.create_rectangle(body_end + 1, 4, width - 1, height - 5, fill=self.accent, outline=self.accent)
        if self.percent is None:
            return
        color = RED if self.percent < 15 else YELLOW if self.percent < 35 else self.accent
        fill_width = max(0, (body_end - 5) * self.percent / 100)
        self.canvas.create_rectangle(3, 3, 3 + fill_width, height - 4, fill=color, outline="")
        for fraction in (0.25, 0.5, 0.75):
            x = 3 + (body_end - 5) * fraction
            self.canvas.create_line(x, 3, x, height - 4, fill=PANEL, width=2)


class BatteryMeter(tk.Canvas):
    """Medidor minimalista no formato de bateria para o modo compacto."""

    def __init__(self, master: tk.Misc, accent: str) -> None:
        super().__init__(master, height=68, bg=BG, highlightthickness=0, cursor="hand2")
        self.accent = accent
        self.percent: int | None = None
        self.error = False
        self.bind("<Configure>", lambda _event: self._draw())

    def set_hover_handlers(self, on_enter: Any, on_leave: Any) -> None:
        """Permite revelar detalhes sem acoplar o medidor à janela principal."""
        self.bind("<Enter>", lambda _event: on_enter(self))
        self.bind("<Motion>", lambda _event: on_enter(self))
        self.bind("<Leave>", lambda _event: on_leave(self))

    def set_data(self, used: Any, _resets_at: Any) -> None:
        self.percent = remaining(used)
        self.error = False
        self._draw()

    def set_error(self, _message: str) -> None:
        self.percent = None
        self.error = True
        self._draw()

    def set_unavailable(self, _message: str) -> None:
        self.percent = None
        self.error = False
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = max(72, self.winfo_width())
        height = max(46, self.winfo_height())
        terminal_width = max(7, width // 14)
        left, top = 3, 8
        right, bottom = width - terminal_width - 5, height - 8
        outline = RED if self.error else self.accent
        self.create_rectangle(left, top, right, bottom, outline=outline, width=2)
        terminal_top = top + (bottom - top) * 0.30
        terminal_bottom = bottom - (bottom - top) * 0.30
        self.create_rectangle(right + 2, terminal_top, width - 2, terminal_bottom, fill=outline, outline=outline)

        label = "—" if self.percent is None else f"{self.percent}%"
        if self.percent is not None:
            color = RED if self.percent < 15 else YELLOW if self.percent < 35 else self.accent
            inner_left, inner_top, inner_right, inner_bottom = left + 4, top + 4, right - 4, bottom - 4
            fill_right = inner_left + (inner_right - inner_left) * self.percent / 100
            self.create_rectangle(inner_left, inner_top, fill_right, inner_bottom, fill=color, outline="")
            # Quatro células, como a barra do modo de cartões. As divisões
            # ficam visíveis somente sobre a parte carregada da bateria.
            for fraction in (0.25, 0.5, 0.75):
                x = inner_left + (inner_right - inner_left) * fraction
                self.create_line(x, inner_top, x, inner_bottom, fill=BG, width=3)
        self.create_text((left + right) / 2, (top + bottom) / 2, text=label, fill=TEXT,
                         font=("Segoe UI", 16, "bold"))


class HoverTooltip:
    """Balão curto para explicar os ícones da barra superior."""

    def __init__(self, widget: tk.Misc, text: str, delay_ms: int = 550) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.after_id: str | None = None
        self.window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def set_text(self, text: str) -> None:
        self.text = text
        if self.window:
            self._hide()

    def _schedule(self, _event: tk.Event | None = None) -> None:
        self._cancel_timer()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel_timer(self) -> None:
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

    def _show(self) -> None:
        self.after_id = None
        if not self.widget.winfo_exists() or self.window:
            return
        tip = tk.Toplevel(self.widget)
        self.window = tip
        tip.withdraw()
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        label = tk.Label(
            tip, text=self.text, bg="#292d25", fg=TEXT, bd=1, relief="solid",
            padx=7, pady=4, font=("Segoe UI", 8),
        )
        label.pack()
        tip.update_idletasks()
        left, top, width, height = virtual_screen_bounds(self.widget)
        tip_width, tip_height = tip.winfo_reqwidth(), tip.winfo_reqheight()
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() - tip_width) // 2
        x = max(left + 4, min(x, left + width - tip_width - 4))
        below = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        y = below if below + tip_height <= top + height - 4 else self.widget.winfo_rooty() - tip_height - 6
        tip.geometry(f"+{x}+{max(top + 4, y)}")
        tip.deiconify()
        tip.lift()

    def _hide(self, _event: tk.Event | None = None) -> None:
        self._cancel_timer()
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None


class SettingsDialog(tk.Toplevel):
    """Configuração local. Nunca lê ou grava tokens, apenas caminhos e perfis."""

    def __init__(self, widget: "UsageWidget") -> None:
        super().__init__(widget.root)
        self.widget = widget
        self.config = load_config()
        self.title("Configurações — Limites de IA")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(widget.root)
        self.grab_set()

        enabled = set(self.config["providers"])
        self.provider_vars = {
            "codex": tk.BooleanVar(value="codex" in enabled),
            "claude": tk.BooleanVar(value="claude" in enabled),
        }
        self.path_vars = {
            provider: tk.StringVar(value=self.config["executables"].get(provider) or "")
            for provider in ("codex", "claude")
        }
        self.refresh_var = tk.StringVar(value=str(self.config["refreshMinutes"]))
        self.extra_profiles = [
            dict(item)
            for item in self.config.get("profiles", [])
            if isinstance(item, dict) and item.get("id") not in {"codex-default", "claude-default"}
        ]
        self._build()

    def _label(self, master: tk.Misc, text: str) -> tk.Label:
        label = tk.Label(master, text=text, bg=BG, fg=TEXT, font=("Segoe UI", 9))
        label.pack(anchor="w", pady=(8, 2))
        return label

    def _build(self) -> None:
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)
        tk.Label(body, text="CONFIGURAÇÕES", bg=BG, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(
            body,
            text="Os caminhos são opcionais: em branco, o widget procura a CLI instalada no sistema.",
            bg=BG, fg=MUTED, justify="left", wraplength=480, font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(3, 5))

        providers = tk.Frame(body, bg=BG)
        providers.pack(anchor="w")
        tk.Checkbutton(providers, text="Codex CLI", variable=self.provider_vars["codex"], bg=BG, fg=TEXT,
                       selectcolor=PANEL_2, activebackground=BG, activeforeground=TEXT).pack(side="left", padx=(0, 14))
        tk.Checkbutton(providers, text="Claude Code", variable=self.provider_vars["claude"], bg=BG, fg=TEXT,
                       selectcolor=PANEL_2, activebackground=BG, activeforeground=TEXT).pack(side="left")

        for provider, title in (("codex", "Executável do Codex CLI"), ("claude", "Executável do Claude Code")):
            self._label(body, title)
            row = tk.Frame(body, bg=BG)
            row.pack(fill="x")
            tk.Entry(row, textvariable=self.path_vars[provider], width=51, bg=PANEL, fg=TEXT,
                     insertbackground=TEXT, relief="flat").pack(side="left", ipady=4)
            self._action_button(row, "Procurar…", lambda key=provider: self._choose_executable(key)).pack(side="left", padx=(6, 0))

        self._label(body, "Intervalo de atualização (minutos, de 5 a 120)")
        tk.Entry(body, textvariable=self.refresh_var, width=8, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                 relief="flat").pack(anchor="w", ipady=4)

        self._label(body, "Perfis adicionais")
        profile_row = tk.Frame(body, bg=BG)
        profile_row.pack(fill="x")
        self.profile_list = tk.Listbox(profile_row, height=4, width=53, bg=PANEL, fg=TEXT, selectbackground=LINE,
                                       relief="flat", highlightthickness=0)
        self.profile_list.pack(side="left", fill="x", expand=True)
        side = tk.Frame(profile_row, bg=BG)
        side.pack(side="left", padx=(6, 0))
        self._action_button(side, "Adicionar", self._add_profile).pack(fill="x")
        self._action_button(side, "Remover", self._remove_profile).pack(fill="x", pady=(5, 0))
        self._refresh_profile_list()

        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(14, 0))
        self._action_button(actions, "Cancelar", self.destroy).pack(side="right")
        self._action_button(actions, "Salvar e verificar", self._save).pack(side="right", padx=(0, 6))

    @staticmethod
    def _action_button(master: tk.Misc, text: str, command: Any) -> tk.Button:
        return tk.Button(master, text=text, command=command, bg=PANEL_2, fg=TEXT, activebackground=LINE,
                         activeforeground=TEXT, bd=0, padx=9, pady=4, font=("Segoe UI", 8), cursor="hand2")

    def _choose_executable(self, provider: str) -> None:
        filename = filedialog.askopenfilename(parent=self, title=f"Selecione o executável do {provider.title()}",
                                              filetypes=[("Executáveis", "*.exe *.cmd"), ("Todos os arquivos", "*.*")])
        if filename:
            self.path_vars[provider].set(filename)

    def _refresh_profile_list(self) -> None:
        self.profile_list.delete(0, tk.END)
        for profile in self.extra_profiles:
            directory = profile.get("configDir") or "padrão"
            self.profile_list.insert(tk.END, f"{profile.get('provider', 'codex').upper()} · {profile.get('label', 'Perfil')} · {directory}")

    def _add_profile(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Adicionar perfil")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        provider = tk.StringVar(value="codex")
        label = tk.StringVar()
        config_dir = tk.StringVar()
        frame = tk.Frame(dialog, bg=BG)
        frame.pack(padx=14, pady=12)
        for text, variable in (("Provedor (codex ou claude)", provider), ("Nome do perfil", label), ("Pasta de configuração (opcional)", config_dir)):
            tk.Label(frame, text=text, bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 2))
            tk.Entry(frame, textvariable=variable, width=48, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat").pack(ipady=4)

        def choose_dir() -> None:
            directory = filedialog.askdirectory(parent=dialog, title="Selecione a pasta de configuração")
            if directory:
                config_dir.set(directory)

        self._action_button(frame, "Escolher pasta…", choose_dir).pack(anchor="w", pady=(5, 0))

        def add() -> None:
            provider_name = provider.get().strip().lower()
            profile_label = label.get().strip()
            if provider_name not in {"codex", "claude"} or not profile_label:
                messagebox.showerror("Perfil", "Informe codex ou claude e um nome para o perfil.", parent=dialog)
                return
            safe_label = "".join(char if char.isalnum() else "-" for char in profile_label.lower()).strip("-") or "perfil"
            self.extra_profiles.append({
                "id": f"{provider_name}-{safe_label}-{len(self.extra_profiles) + 1}",
                "provider": provider_name,
                "label": profile_label[:40],
                "executable": self.path_vars[provider_name].get().strip() or None,
                "configDir": config_dir.get().strip() or None,
            })
            self._refresh_profile_list()
            dialog.destroy()

        self._action_button(frame, "Adicionar perfil", add).pack(anchor="e", pady=(12, 0))

    def _remove_profile(self) -> None:
        selection = self.profile_list.curselection()
        if selection:
            del self.extra_profiles[selection[0]]
            self._refresh_profile_list()

    def _save(self) -> None:
        providers = [name for name, variable in self.provider_vars.items() if variable.get()]
        if not providers:
            messagebox.showerror("Configurações", "Selecione pelo menos um provedor.", parent=self)
            return
        try:
            refresh_minutes = max(5, min(120, int(self.refresh_var.get())))
        except ValueError:
            messagebox.showerror("Configurações", "O intervalo deve ser um número entre 5 e 120.", parent=self)
            return
        executables = {provider: variable.get().strip() or None for provider, variable in self.path_vars.items()}
        profiles = [
            {"id": f"{provider}-default", "provider": provider, "label": "Padrão", "executable": executables[provider], "configDir": None}
            for provider in providers
        ]
        profiles.extend(self.extra_profiles)
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps({"providers": providers, "refreshMinutes": refresh_minutes,
                                               "layout": self.widget.layout, "executables": executables,
                                               "profiles": profiles}, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Configurações", f"Não foi possível salvar as configurações: {exc}", parent=self)
            return
        self.widget.rescan_integrations()
        self.destroy()


class UsageWidget:
    def __init__(self) -> None:
        self.clients: dict[str, CodexClient | ClaudeClient] = {}
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.last_claude_at: dict[str, float] = {}
        self.warnings: dict[str, str | None] = {}
        self.last_windows: dict[str, dict[str, int | None]] = {}
        self.last_meter_data: dict[str, tuple[dict[str, Any] | None, dict[str, Any] | None]] = {}
        self.last_meter_errors: dict[str, str] = {}
        self.compact_details: dict[str, dict[str, Any]] = {}
        self.last_refresh_text = "Última atualização: —"
        self.refresh_scheduled = False
        self._discover_profiles()
        self.window_height = max(102 if self.layout == "compact" else 168, 114 + 142 * len(self.profiles))
        self.root = tk.Tk()
        self.root.title("Limites de IA")
        self.root.configure(bg=BG)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.97)
        self.root.resizable(False, False)
        self.refreshing = False
        self.collapsed = False
        self.topmost = True
        self.drag_origin = (0, 0)
        self.hover_after: str | None = None
        self.hide_hover_after: str | None = None
        self.hover_meter: BatteryMeter | None = None
        self.hover_panel: tk.Frame | None = None
        self.hover_title: tk.Label | None = None
        self.hover_window: tk.Label | None = None
        self.hover_value: tk.Label | None = None
        self.hover_reset: tk.Label | None = None
        self.hover_updated: tk.Label | None = None
        self.button_tooltips: dict[tk.Button, HoverTooltip] = {}
        self._place_window()
        self._build()
        # A quantidade de cartões e as métricas de fonte do Windows variam.
        # Mede o layout pronto para que o rodapé nunca seja cortado.
        self.root.update_idletasks()
        self._resize_to_content()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._drain_events)
        self.root.after(200, self._poll_hover_target)
        if self.profiles:
            self.root.after(250, lambda: self.refresh(force_claude=True))
            self._schedule_refresh()

    def _discover_profiles(self) -> None:
        self.config = load_config()
        self.layout = self.config["layout"]
        self.configured_profiles = load_profiles()
        self.unavailable_profiles = [
            (profile, reason) for profile in self.configured_profiles if (reason := profile_unavailable_reason(profile))
        ]
        self.profiles = [profile for profile in self.configured_profiles if profile_is_available(profile)]
        self.refresh_seconds = self.config["refreshMinutes"] * 60
        self.clients = {}
        for profile in self.profiles:
            if profile["provider"] == "codex":
                self.clients[profile["id"]] = CodexClient(profile["executable"], profile["configDir"])
            else:
                self.clients[profile["id"]] = ClaudeClient(profile["executable"], profile["configDir"], profile["id"])
        self.last_claude_at = {}
        self.warnings = {profile["id"]: None for profile in self.profiles}
        self.last_windows = {}
        self.last_meter_data = {}
        self.last_meter_errors = {}

    def _close_clients(self) -> None:
        for client in self.clients.values():
            if isinstance(client, CodexClient):
                client.close()

    def _resize_to_content(self) -> None:
        self.root.update_idletasks()
        minimum_height = 102 if self.layout == "compact" else 168
        self.window_height = max(minimum_height, self.root.winfo_reqheight())
        if not self.collapsed:
            self.root.geometry(f"{WINDOW_WIDTH}x{self.window_height}+{self.root.winfo_x()}+{self.root.winfo_y()}")

    def _schedule_refresh(self) -> None:
        if self.refresh_scheduled:
            return
        self.refresh_scheduled = True
        self.root.after(self.refresh_seconds * 1000, self._scheduled_refresh)

    def _place_window(self) -> None:
        left, top, width, _height = primary_work_area(self.root)
        x, y = left + max(12, width - WINDOW_WIDTH - 24), top + 70
        self.root.geometry(f"{WINDOW_WIDTH}x{self.window_height}+{x}+{y}")

    def _build(self) -> None:
        titlebar = tk.Frame(self.root, bg=PANEL_2, height=42, highlightbackground=LINE, highlightthickness=1)
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)
        label = tk.Label(titlebar, text="LIMITES DE IA", bg=PANEL_2, fg=TEXT, font=("Segoe UI", 10, "bold"))
        label.pack(side="left", padx=12)
        self._button(titlebar, "×", self.close, "Fechar").pack(side="right", padx=(0, 5))
        self.collapse_button = self._button(titlebar, "–", self.toggle_collapse, "Recolher")
        self.collapse_button.pack(side="right")
        self.pin_button = self._button(titlebar, "●", self.toggle_topmost, "Desafixar da frente")
        self.pin_button.configure(fg=ORANGE)
        self.pin_button.pack(side="right")
        layout_hint = "Usar modo compacto" if self.layout == "cards" else "Mostrar detalhes"
        self.layout_button = self._button(
            titlebar, "⊟" if self.layout == "cards" else "⊞", self.toggle_layout, layout_hint
        )
        self.layout_button.pack(side="right")
        self._button(titlebar, "⚙", self.open_settings, "Configurações").pack(side="right")
        self._button(titlebar, "?", self.copy_diagnostics, "Copiar diagnóstico").pack(side="right")
        self._button(titlebar, "↻", self.refresh_or_rescan, "Atualizar ou verificar integrações").pack(side="right")
        for widget in (titlebar, label):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._save_position)

        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=12, pady=(6, 10))
        self._build_body()

    def _build_body(self) -> None:
        self.meters: dict[str, tuple[Meter | BatteryMeter, Meter | BatteryMeter | None]] = {}
        self.hover_panel = None
        self.hover_title = None
        self.hover_window = None
        self.hover_value = None
        self.hover_reset = None
        self.hover_updated = None
        if not self.profiles:
            instructions = "Para acompanhar seus limites, instale e autentique pelo menos uma CLI:\n\n"
            instructions += "\n".join(f"• {reason}" for _, reason in self.unavailable_profiles)
            instructions += "\n\nDepois de instalar ou entrar, use Verificar novamente."
            tk.Label(
                self.body,
                text=instructions,
                bg=BG,
                fg=YELLOW,
                justify="left",
                font=("Segoe UI", 9),
                wraplength=WINDOW_WIDTH - 40,
            ).pack(anchor="w", pady=16)
            missing = {profile["provider"] for profile, _ in self.unavailable_profiles}
            actions = tk.Frame(self.body, bg=BG)
            actions.pack(anchor="w", pady=(0, 5))
            if "codex" in missing:
                self._action_button(actions, "Instalar Codex CLI", lambda: webbrowser.open(CODEX_CLI_DOCS)).pack(side="left")
            if "claude" in missing:
                self._action_button(actions, "Instalar Claude Code", lambda: webbrowser.open(CLAUDE_CODE_DOCS)).pack(side="left", padx=(6, 0))
            self._action_button(self.body, "Verificar novamente", self.rescan_integrations).pack(anchor="w", pady=(2, 0))
        compact_grid: tk.Frame | None = None
        if self.layout == "compact" and self.profiles:
            compact_grid = tk.Frame(self.body, bg=BG)
            compact_grid.pack(fill="x", pady=(4, 0))
            compact_grid.columnconfigure(0, weight=1, uniform="batteries")
            compact_grid.columnconfigure(1, weight=1, uniform="batteries")

        for index, profile in enumerate(self.profiles):
            accent = CLAUDE_PURPLE if profile["provider"] == "codex" else ORANGE
            company = "OPENAI" if profile["provider"] == "codex" else "ANTHROPIC"
            title = "CODEX" if profile["provider"] == "codex" else "CLAUDE CODE"
            if self.layout == "compact":
                assert compact_grid is not None
                short = BatteryMeter(compact_grid, accent)
                short.set_hover_handlers(
                    lambda meter, current=profile: self._schedule_hover_details(current, meter),
                    self._defer_hide_hover_details,
                )
                column = index % 2
                short.grid(row=index // 2, column=column, sticky="ew", padx=(0, 5) if column == 0 else (5, 0), pady=(0, 8))
                week = None
            else:
                self._provider_title(f"{title} · {profile['label'].upper()}", company, accent)
                grid = tk.Frame(self.body, bg=BG)
                grid.pack(fill="x")
                grid.columnconfigure(0, weight=1, uniform="meters")
                grid.columnconfigure(1, weight=1, uniform="meters")
                short = Meter(grid, "5 horas", accent)
                short.grid(row=0, column=0, sticky="ew", padx=(0, 4))
                week = Meter(grid, "Semana", accent)
                week.grid(row=0, column=1, sticky="ew", padx=(4, 0))
            self.meters[profile["id"]] = (short, week)

        if self.layout == "compact" and self.profiles:
            self.hover_panel = tk.Frame(self.body, bg=PANEL_2, highlightbackground=LINE, highlightthickness=1)
            self.hover_title = tk.Label(self.hover_panel, bg=PANEL_2, font=("Segoe UI", 9, "bold"), anchor="w")
            self.hover_title.pack(fill="x", padx=10, pady=(8, 2))
            self.hover_window = tk.Label(self.hover_panel, bg=PANEL_2, fg=MUTED,
                                         font=("Segoe UI", 8, "bold"), anchor="w")
            self.hover_window.pack(fill="x", padx=10)
            self.hover_value = tk.Label(self.hover_panel, bg=PANEL_2, fg=TEXT,
                                        font=("Segoe UI", 15, "bold"), anchor="w")
            self.hover_value.pack(fill="x", padx=10, pady=(1, 2))
            self.hover_reset = tk.Label(self.hover_panel, bg=PANEL_2, fg=MUTED,
                                        font=("Segoe UI", 8), anchor="w")
            self.hover_reset.pack(fill="x", padx=10)
            self.hover_updated = tk.Label(self.hover_panel, bg=PANEL_2, fg=MUTED,
                                          font=("Segoe UI", 8), anchor="w")
            self.hover_updated.pack(fill="x", padx=10, pady=(2, 8))
            for child in (self.hover_panel, *self.hover_panel.winfo_children()):
                child.bind("<Enter>", lambda _event: self._cancel_hide_hover_timer())
                child.bind("<Leave>", lambda _event: self._defer_hide_hover_details(self.hover_meter))

        status_text = "Conectando…" if self.profiles else "Aguardando uma CLI disponível"
        status_color = MUTED if self.profiles else YELLOW
        self.status = tk.Label(self.body, text=status_text, bg=BG, fg=status_color, font=("Segoe UI", 8), anchor="w")
        if self.layout != "compact":
            self.status.pack(fill="x", pady=(12, 0))
        self.last_updated = tk.Label(
            self.body,
            text="Última atualização: —",
            bg=BG,
            fg="#62685b",
            font=("Segoe UI", 8),
            anchor="w",
        )
        if self.layout != "compact":
            self.last_updated.pack(fill="x", pady=(2, 0))

    def _action_button(self, master: tk.Misc, text: str, command: Any) -> tk.Button:
        return tk.Button(
            master, text=text, command=command, bg=PANEL_2, fg=TEXT, activebackground=LINE, activeforeground=TEXT,
            bd=0, padx=9, pady=4, font=("Segoe UI", 8), cursor="hand2"
        )

    def _button(self, master: tk.Misc, text: str, command: Any, tooltip: str) -> tk.Button:
        button = tk.Button(
            master,
            text=text,
            command=command,
            bg=PANEL_2,
            fg=MUTED,
            activebackground=LINE,
            activeforeground=TEXT,
            bd=0,
            width=3,
            font=("Segoe UI Symbol", 10),
            cursor="hand2",
        )
        self.button_tooltips[button] = HoverTooltip(button, tooltip)
        return button

    def _provider_title(self, text: str, company: str, accent: str) -> None:
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x", pady=(8, 5))
        tk.Frame(row, bg=accent, width=4, height=13).pack(side="left", padx=(0, 7))
        tk.Label(row, text=text, bg=BG, fg=accent, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(row, text=f"  /  {company}", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event: tk.Event) -> None:
        self.root.geometry(f"+{event.x_root - self.drag_origin[0]}+{event.y_root - self.drag_origin[1]}")

    def _save_position(self, _event: tk.Event | None = None) -> None:
        # A posição vale durante esta execução. Na próxima abertura, o widget
        # volta ao monitor principal para nunca iniciar fora da tela.
        return

    def _cancel_hover_timer(self) -> None:
        if self.hover_after:
            self.root.after_cancel(self.hover_after)
            self.hover_after = None

    def _cancel_hide_hover_timer(self) -> None:
        if self.hide_hover_after:
            self.root.after_cancel(self.hide_hover_after)
            self.hide_hover_after = None

    def _schedule_hover_details(self, profile: dict[str, Any], meter: BatteryMeter) -> None:
        """Mostra o painel somente após um segundo contínuo sobre a bateria."""
        panel_visible = bool(self.hover_panel and self.hover_panel.winfo_manager())
        if self.hover_meter is meter and (self.hover_after or panel_visible):
            return
        self._cancel_hover_timer()
        self._cancel_hide_hover_timer()
        if self.hover_meter is not meter:
            self._hide_hover_details()
        self.hover_meter = meter
        self.hover_after = self.root.after(1000, lambda: self._show_hover_details(profile, meter))

    def _poll_hover_target(self) -> None:
        """Cobre o caso em que o widget aparece já sob um cursor parado."""
        try:
            target = self.root.winfo_containing(self.root.winfo_pointerx(), self.root.winfo_pointery())
            if self._is_inside_hover_panel(target):
                self._cancel_hide_hover_timer()
            else:
                for profile in self.profiles:
                    meter, _week = self.meters.get(profile["id"], (None, None))
                    if isinstance(meter, BatteryMeter) and target is meter:
                        self._schedule_hover_details(profile, meter)
                        break
                else:
                    if self.hover_meter:
                        self._defer_hide_hover_details(self.hover_meter)
        except tk.TclError:
            return
        self.root.after(200, self._poll_hover_target)

    def _is_inside_hover_panel(self, target: tk.Misc | None) -> bool:
        current = target
        while current:
            if current is self.hover_panel:
                return True
            current = current.master
        return False

    def _defer_hide_hover_details(self, meter: BatteryMeter | None) -> None:
        if meter is None or meter is not self.hover_meter:
            return
        self._cancel_hover_timer()
        self._cancel_hide_hover_timer()
        # Dá tempo de o cursor atravessar da bateria para o painel expandido.
        self.hide_hover_after = self.root.after(180, self._hide_hover_details)

    def _hide_hover_details(self) -> None:
        self._cancel_hover_timer()
        self._cancel_hide_hover_timer()
        self.hover_meter = None
        if self.hover_panel and self.hover_panel.winfo_exists() and self.hover_panel.winfo_manager():
            self.hover_panel.pack_forget()
            if self.root.winfo_exists():
                self._resize_to_content()

    def _show_hover_details(self, profile: dict[str, Any], meter: BatteryMeter) -> None:
        self.hover_after = None
        if self.layout != "compact" or meter is not self.hover_meter or not meter.winfo_exists():
            return
        details = self.compact_details.get(profile["id"], {})
        accent = CLAUDE_PURPLE if profile["provider"] == "codex" else ORANGE
        provider = "CODEX" if profile["provider"] == "codex" else "CLAUDE CODE"
        percent = details.get("percent")
        value = "—" if percent is None else f"{percent}% restante"
        message = details.get("message") or format_reset(details.get("resetsAt"))
        if not all((self.hover_panel, self.hover_title, self.hover_window, self.hover_value,
                    self.hover_reset, self.hover_updated)):
            return
        self.hover_panel.configure(highlightbackground=accent)
        self.hover_title.configure(text=f"{provider} · {profile['label'].upper()}", fg=accent)
        self.hover_window.configure(text=details.get("window", "LIMITE"))
        self.hover_value.configure(text=value)
        self.hover_reset.configure(text=message, fg=RED if details.get("error") else MUTED)
        self.hover_updated.configure(text=self.last_refresh_text)
        if not self.hover_panel.winfo_manager():
            self.hover_panel.pack(fill="x", pady=(2, 6))
            self._resize_to_content()

    def toggle_collapse(self) -> None:
        self._hide_hover_details()
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body.pack_forget()
            self.root.geometry(f"{WINDOW_WIDTH}x{COLLAPSED_HEIGHT}")
        else:
            self.body.pack(fill="both", expand=True, padx=12, pady=(6, 10))
            self.root.geometry(f"{WINDOW_WIDTH}x{self.window_height}")
        self.button_tooltips[self.collapse_button].set_text("Expandir" if self.collapsed else "Recolher")

    def toggle_topmost(self) -> None:
        self.topmost = not self.topmost
        self.root.attributes("-topmost", self.topmost)
        self.pin_button.configure(fg=ORANGE if self.topmost else MUTED)
        self.button_tooltips[self.pin_button].set_text(
            "Desafixar da frente" if self.topmost else "Manter sempre visível"
        )

    def toggle_layout(self) -> None:
        # A troca de aparência não inicia uma consulta: reaproveita o último
        # resultado recebido, inclusive enquanto uma atualização está em curso.
        self._hide_hover_details()
        status_text, status_color = self.status.cget("text"), self.status.cget("fg")
        updated_text = self.last_updated.cget("text")
        self.layout = "compact" if self.layout == "cards" else "cards"
        self.config["layout"] = self.layout
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
        for child in self.body.winfo_children():
            child.destroy()
        self._build_body()
        for profile in self.profiles:
            saved = self.last_meter_data.get(profile["id"])
            if saved:
                self._render_profile_meters(profile, *saved)
            if message := self.last_meter_errors.get(profile["id"]):
                self._render_profile_error(profile, message)
        self.layout_button.configure(text="⊟" if self.layout == "cards" else "⊞")
        self.button_tooltips[self.layout_button].set_text(
            "Usar modo compacto" if self.layout == "cards" else "Mostrar detalhes"
        )
        self.status.configure(text=status_text, fg=status_color)
        self.last_updated.configure(text=updated_text)
        self._resize_to_content()

    def _scheduled_refresh(self) -> None:
        self.refresh_scheduled = False
        self.refresh(force_claude=False)
        self._schedule_refresh()

    def refresh_or_rescan(self) -> None:
        # Permite terminar uma instalação ou login sem reiniciar o aplicativo.
        if self.unavailable_profiles or not self.profiles:
            self.rescan_integrations()
        else:
            self.refresh(force_claude=True)

    def rescan_integrations(self) -> None:
        if self.refreshing:
            return
        self._hide_hover_details()
        self._close_clients()
        self._discover_profiles()
        for child in self.body.winfo_children():
            child.destroy()
        self._build_body()
        self._resize_to_content()
        if self.profiles:
            self._schedule_refresh()
            self.refresh(force_claude=True)

    def open_settings(self) -> None:
        SettingsDialog(self)

    def copy_diagnostics(self) -> None:
        """Copia informações úteis de suporte, deliberadamente sem IDs ou credenciais."""
        cli: dict[str, dict[str, Any]] = {}
        for provider, commands in {
            "codex": ("codex.exe", "codex.cmd", "codex"),
            "claude": ("claude.exe", "claude.cmd", "claude"),
        }.items():
            executable = configured_executable(self.config["executables"].get(provider), commands)
            info: dict[str, Any] = {"encontrado": bool(executable)}
            if executable:
                try:
                    result = subprocess.run([executable, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", timeout=5,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                    output = (result.stdout or result.stderr).strip().splitlines()
                    info["versao"] = output[0][:160] if output and result.returncode == 0 else "não informada"
                except (OSError, subprocess.SubprocessError):
                    info["versao"] = "não informada"
            cli[provider] = info
        report = {
            "aplicativo": "AI Limits Widget",
            "versao": "0.1.15",
            "atualizacaoMinutos": self.config["refreshMinutes"],
            "cli": cli,
            "perfis": [
                {
                    "provedor": profile["provider"], "disponivel": profile_is_available(profile),
                    "janelasMinutos": self.last_windows.get(profile["id"], {}),
                    "teveAviso": bool(self.warnings.get(profile["id"])),
                }
                for profile in self.configured_profiles
            ],
        }
        self.root.clipboard_clear()
        self.root.clipboard_append(json.dumps(report, ensure_ascii=False, indent=2))
        self.status.configure(text="Diagnóstico seguro copiado", fg=MUTED)

    def refresh(self, force_claude: bool = False) -> None:
        if not self.profiles:
            self.status.configure(text="Instale e autentique uma CLI; depois, use Verificar novamente.", fg=YELLOW)
            return
        if self.refreshing:
            return
        self.refreshing = True
        self.status.configure(text="Atualizando…", fg=MUTED)
        threading.Thread(target=self._refresh_worker, args=(force_claude,), daemon=True).start()

    def _refresh_worker(self, force_claude: bool) -> None:
        for profile in self.profiles:
            profile_id = profile["id"]
            client = self.clients[profile_id]
            try:
                if profile["provider"] == "claude" and not (
                    force_claude or time.monotonic() - self.last_claude_at.get(profile_id, 0.0) >= self.refresh_seconds
                ):
                    continue
                self.events.put(("profile", (profile, client.read_limits())))
                if profile["provider"] == "claude":
                    self.last_claude_at[profile_id] = time.monotonic()
            except Exception as exc:
                self.events.put(("profile_error", (profile, str(exc))))
        self.events.put(("done", None))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "profile":
                    profile, data = payload
                    short, week = self.meters[profile["id"]]
                    first = data.get("primary") if profile["provider"] == "codex" else data.get("five_hour")
                    second = data.get("secondary") if profile["provider"] == "codex" else data.get("seven_day")
                    self.last_meter_data[profile["id"]] = (first, second)
                    self.last_meter_errors.pop(profile["id"], None)
                    self._render_profile_meters(profile, first, second)
                    self.last_windows[profile["id"]] = {
                        "cincoHoras": (first or {}).get("windowDurationMins"),
                        "semana": (second or {}).get("windowDurationMins"),
                    }
                    if profile["provider"] == "claude" and data.get("stale"):
                        fetched = dt.datetime.fromtimestamp(data.get("fetchedAt", 0)).strftime("%H:%M")
                        retry = dt.datetime.fromtimestamp(data.get("nextRetryAt", 0)).strftime("%H:%M")
                        self.warnings[profile["id"]] = f"{profile['label']}: dados de {fetched} · nova tentativa {retry}"
                    else:
                        self.warnings[profile["id"]] = None
                elif kind == "profile_error":
                    profile, message = payload
                    self._render_profile_error(profile, message)
                    self.last_meter_errors[profile["id"]] = message
                    self.warnings[profile["id"]] = message
                elif kind == "done":
                    self.refreshing = False
                    self.last_refresh_text = f"Última atualização: {dt.datetime.now():%H:%M}"
                    self.last_updated.configure(text=self.last_refresh_text)
                    if self.hover_updated and self.hover_updated.winfo_exists():
                        self.hover_updated.configure(text=self.last_refresh_text)
                    warnings = [warning for warning in self.warnings.values() if warning]
                    if warnings:
                        self.status.configure(text=" · ".join(warnings), fg=YELLOW)
                    else:
                        self.status.configure(text="Atualização concluída", fg=MUTED)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    @staticmethod
    def _update_meter(meter: Meter | BatteryMeter, data: dict[str, Any] | None) -> None:
        if data and data.get("usedPercent") is not None:
            meter.set_data(data.get("usedPercent"), data.get("resetsAt"))
        else:
            meter.set_unavailable("Não informado pela CLI")

    def _render_profile_meters(
        self, profile: dict[str, Any], first: dict[str, Any] | None, second: dict[str, Any] | None
    ) -> None:
        short, week = self.meters[profile["id"]]
        if self.layout == "compact":
            if first and first.get("usedPercent") is not None:
                data, window = first, "5 HORAS"
            elif second:
                data, window = second, "SEMANA"
            else:
                data, window = first, "5 HORAS"
            self._update_meter(short, data)
            self.compact_details[profile["id"]] = {
                "window": window,
                "percent": remaining((data or {}).get("usedPercent")),
                "resetsAt": (data or {}).get("resetsAt"),
            }
            if self.hover_meter is short and self.hover_panel and self.hover_panel.winfo_manager():
                self._show_hover_details(profile, short)
            return
        self._update_meter(short, first)
        if week:
            self._update_meter(week, second)

    def _render_profile_error(self, profile: dict[str, Any], message: str) -> None:
        short, week = self.meters[profile["id"]]
        short.set_error(message)
        if self.layout == "compact":
            self.compact_details[profile["id"]] = {"window": "LIMITE", "percent": None, "message": message, "error": True}
            if self.hover_meter is short and self.hover_panel and self.hover_panel.winfo_manager():
                self._show_hover_details(profile, short)
        if week:
            week.set_error(f"{profile['label']} indisponível")

    def close(self) -> None:
        self._hide_hover_details()
        self._save_position()
        self._close_clients()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def print_once() -> None:
    profiles = [profile for profile in load_profiles() if profile_is_available(profile)]
    if not profiles:
        raise RuntimeError("Nenhuma CLI disponível. Instale e autentique o Codex CLI ou o Claude Code.")
    try:
        output: dict[str, Any] = {}
        for profile in profiles:
            if profile["provider"] == "codex":
                data = CodexClient(profile["executable"], profile["configDir"]).read_limits()
                first, second = data.get("primary"), data.get("secondary")
            else:
                data = ClaudeClient(profile["executable"], profile["configDir"], profile["id"]).read_limits()
                first, second = data.get("five_hour"), data.get("seven_day")
            output[f"{profile['provider']}:{profile['label']}"] = {
                "five_hour_remaining": remaining((first or {}).get("usedPercent")),
                "weekly_remaining": remaining((second or {}).get("usedPercent")),
            }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Widget de limites do Codex e Claude Code")
    parser.add_argument("--once", action="store_true", help="consulta uma vez sem abrir a interface")
    args = parser.parse_args()
    if args.once:
        print_once()
    else:
        UsageWidget().run()


if __name__ == "__main__":
    main()

