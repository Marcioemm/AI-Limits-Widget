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
import urllib.error
import urllib.request
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
CODEX_REFRESH_SECONDS = 300
CLAUDE_REFRESH_SECONDS = 300


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

    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.messages: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self.next_id = 1
        self.lock = threading.RLock()

    def _start(self) -> None:
        executable = shutil.which("codex.exe" if os.name == "nt" else "codex")
        if not executable:
            raise RuntimeError("Codex CLI não encontrado no PATH.")

        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW

        self.messages = queue.Queue()
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

    def read_limits(self) -> dict[str, Any]:
        with self.lock:
            try:
                for attempt in range(2):
                    try:
                        if not self.process or self.process.poll() is not None:
                            self._start()
                        response = self._request("account/rateLimits/read", None)
                        limits = response.get("rateLimits") or next(
                            iter(response.get("rateLimitsByLimitId", {}).values()), {}
                        )
                        return {
                            "plan": limits.get("planType") or "—",
                            "primary": limits.get("primary"),
                            "secondary": limits.get("secondary"),
                        }
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

    def __init__(self) -> None:
        self.last_data: dict[str, Any] | None = None
        self.next_retry_at = 0.0
        self.backoff_index = 0
        self._load_state()

    @property
    def state_file(self) -> pathlib.Path:
        base = pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home())) / "LimitesIA"
        return base / "claude_usage_cache.json"

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
        base = os.environ.get("CLAUDE_CONFIG_DIR")
        return pathlib.Path(base) / ".credentials.json" if base else pathlib.Path.home() / ".claude" / ".credentials.json"

    def _refresh_access_token(self) -> bool:
        candidates = [
            shutil.which("claude.exe"),
            shutil.which("claude.cmd"),
            str(pathlib.Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd"),
            shutil.which("claude"),
        ]
        executable = next((item for item in candidates if item and pathlib.Path(item).exists()), None)
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


class UsageWidget:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Limites de IA")
        self.root.configure(bg=BG)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.97)
        self.root.resizable(False, False)
        self.codex = CodexClient()
        self.claude = ClaudeClient()
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.refreshing = False
        self.collapsed = False
        self.topmost = True
        self.drag_origin = (0, 0)
        self.last_claude_at = 0.0
        self.warnings: dict[str, str | None] = {"codex": None, "claude": None}
        self._place_window()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._drain_events)
        self.root.after(250, lambda: self.refresh(force_claude=True))
        self.root.after(CODEX_REFRESH_SECONDS * 1000, self._scheduled_refresh)

    @property
    def settings_file(self) -> pathlib.Path:
        base = pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home())) / "LimitesIA"
        return base / "settings.json"

    def _place_window(self) -> None:
        default = (self.root.winfo_screenwidth() - WINDOW_WIDTH - 24, 70)
        x, y = default
        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
            x, y = int(data.get("x", x)), int(data.get("y", y))
        except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
            pass
        # Uma posição salva em um monitor desconectado ou após mudança de
        # resolução deixaria a janela sem borda invisível e fora da barra de tarefas.
        x, y = fit_to_bounds(x, y, virtual_screen_bounds(self.root))
        if not is_on_monitor(x, y):
            x, y = default
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

    def _build(self) -> None:
        titlebar = tk.Frame(self.root, bg=PANEL_2, height=42, highlightbackground=LINE, highlightthickness=1)
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)
        label = tk.Label(titlebar, text="LIMITES DE IA", bg=PANEL_2, fg=TEXT, font=("Segoe UI", 10, "bold"))
        label.pack(side="left", padx=12)
        self._button(titlebar, "×", self.close).pack(side="right", padx=(0, 5))
        self._button(titlebar, "–", self.toggle_collapse).pack(side="right")
        self.pin_button = self._button(titlebar, "●", self.toggle_topmost)
        self.pin_button.configure(fg=ORANGE)
        self.pin_button.pack(side="right")
        self._button(titlebar, "↻", lambda: self.refresh(force_claude=True)).pack(side="right")
        for widget in (titlebar, label):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._save_position)

        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=12, pady=(6, 10))
        self._provider_title("CODEX", "OPENAI", CLAUDE_PURPLE)
        codex_grid = tk.Frame(self.body, bg=BG)
        codex_grid.pack(fill="x")
        codex_grid.columnconfigure(0, weight=1, uniform="meters")
        codex_grid.columnconfigure(1, weight=1, uniform="meters")
        self.codex_short = Meter(codex_grid, "5 horas", CLAUDE_PURPLE)
        self.codex_short.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.codex_week = Meter(codex_grid, "Semana", CLAUDE_PURPLE)
        self.codex_week.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self._provider_title("CLAUDE CODE", "ANTHROPIC", ORANGE)
        claude_grid = tk.Frame(self.body, bg=BG)
        claude_grid.pack(fill="x")
        claude_grid.columnconfigure(0, weight=1, uniform="meters")
        claude_grid.columnconfigure(1, weight=1, uniform="meters")
        self.claude_short = Meter(claude_grid, "5 horas", ORANGE)
        self.claude_short.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.claude_week = Meter(claude_grid, "Semana", ORANGE)
        self.claude_week.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.status = tk.Label(self.body, text="Conectando…", bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w")
        self.status.pack(fill="x", pady=(12, 0))
        self.legend = tk.Label(
            self.body,
            text="Percentual restante · atualização automática",
            bg=BG,
            fg="#62685b",
            font=("Segoe UI", 8),
            anchor="w",
        )
        self.legend.pack(fill="x", pady=(2, 0))

    def _button(self, master: tk.Misc, text: str, command: Any) -> tk.Button:
        return tk.Button(
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
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            self.settings_file.write_text(
                json.dumps({"x": self.root.winfo_x(), "y": self.root.winfo_y()}), encoding="utf-8"
            )
        except OSError:
            pass

    def toggle_collapse(self) -> None:
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body.pack_forget()
            self.root.geometry(f"{WINDOW_WIDTH}x{COLLAPSED_HEIGHT}")
        else:
            self.body.pack(fill="both", expand=True, padx=12, pady=(6, 10))
            self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

    def toggle_topmost(self) -> None:
        self.topmost = not self.topmost
        self.root.attributes("-topmost", self.topmost)
        self.pin_button.configure(fg=ORANGE if self.topmost else MUTED)

    def _scheduled_refresh(self) -> None:
        self.refresh(force_claude=False)
        self.root.after(CODEX_REFRESH_SECONDS * 1000, self._scheduled_refresh)

    def refresh(self, force_claude: bool = False) -> None:
        if self.refreshing:
            return
        self.refreshing = True
        self.status.configure(text="Atualizando…", fg=MUTED)
        threading.Thread(target=self._refresh_worker, args=(force_claude,), daemon=True).start()

    def _refresh_worker(self, force_claude: bool) -> None:
        try:
            self.events.put(("codex", self.codex.read_limits()))
        except Exception as exc:
            self.events.put(("codex_error", str(exc)))

        should_read_claude = force_claude or time.monotonic() - self.last_claude_at >= CLAUDE_REFRESH_SECONDS
        if should_read_claude:
            try:
                self.events.put(("claude", self.claude.read_limits()))
                self.last_claude_at = time.monotonic()
            except Exception as exc:
                self.events.put(("claude_error", str(exc)))
        self.events.put(("done", None))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "codex":
                    self._update_meter(self.codex_short, payload.get("primary"))
                    self._update_meter(self.codex_week, payload.get("secondary"))
                    self.warnings["codex"] = None
                elif kind == "claude":
                    self._update_meter(self.claude_short, payload.get("five_hour"))
                    self._update_meter(self.claude_week, payload.get("seven_day"))
                    if payload.get("stale"):
                        fetched = dt.datetime.fromtimestamp(payload.get("fetchedAt", 0)).strftime("%H:%M")
                        retry = dt.datetime.fromtimestamp(payload.get("nextRetryAt", 0)).strftime("%H:%M")
                        self.warnings["claude"] = f"Claude: dados de {fetched} · nova tentativa {retry}"
                    else:
                        self.warnings["claude"] = None
                elif kind == "codex_error":
                    self.codex_short.set_error(payload)
                    self.codex_week.set_error("Codex indisponível")
                    self.warnings["codex"] = "Codex indisponível"
                elif kind == "claude_error":
                    self.claude_short.set_error(payload)
                    self.claude_week.set_error("Claude indisponível")
                    self.warnings["claude"] = payload
                elif kind == "done":
                    self.refreshing = False
                    warnings = [warning for warning in self.warnings.values() if warning]
                    if warnings:
                        self.status.configure(text=" · ".join(warnings), fg=YELLOW)
                    else:
                        self.status.configure(text=f"Atualizado às {dt.datetime.now():%H:%M}", fg=MUTED)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    @staticmethod
    def _update_meter(meter: Meter, data: dict[str, Any] | None) -> None:
        if data:
            meter.set_data(data.get("usedPercent"), data.get("resetsAt"))
        else:
            meter.set_error("Limite indisponível")

    def close(self) -> None:
        self._save_position()
        self.codex.close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def print_once() -> None:
    codex = CodexClient()
    try:
        codex_data = codex.read_limits()
        claude_data = ClaudeClient().read_limits()
        output = {
            "codex": {
                "five_hour_remaining": remaining((codex_data.get("primary") or {}).get("usedPercent")),
                "weekly_remaining": remaining((codex_data.get("secondary") or {}).get("usedPercent")),
            },
            "claude": {
                "five_hour_remaining": remaining((claude_data.get("five_hour") or {}).get("usedPercent")),
                "weekly_remaining": remaining((claude_data.get("seven_day") or {}).get("usedPercent")),
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        codex.close()


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

