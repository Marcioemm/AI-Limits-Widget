"""Provedor dos limites retornados pelo app-server do Codex."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from typing import Any, cast

try:
    from ..models import NormalizedLimits, ProviderName, RateLimitWindow
except ImportError:  # Execução direta de app.py.
    from models import NormalizedLimits, ProviderName, RateLimitWindow

from .base import ProviderError, configured_executable


class CodexClient:
    """Cliente JSON-RPC mínimo para o app-server local do Codex."""

    provider_name: ProviderName = "codex"
    minimum_refresh_interval_seconds = 0

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
            raise ProviderError(
                "codex",
                "Codex CLI não encontrado. Instale-o, entre com sua conta ChatGPT e abra o widget novamente.",
            )

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
        try:
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
        except OSError as exc:
            raise ProviderError("codex", "Não foi possível iniciar o serviço local do Codex.") from exc
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
            raise ProviderError("codex", "Serviço local do Codex indisponível.")
        request_id = self.next_id
        self.next_id += 1
        process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 15
        while True:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                raise ProviderError("codex", "O Codex demorou demais para responder.")
            try:
                message = self.messages.get(timeout=timeout)
            except queue.Empty as exc:
                raise ProviderError("codex", "O Codex demorou demais para responder.") from exc
            if message is None:
                raise ProviderError("codex", "O serviço local do Codex foi encerrado.")
            if message.get("id") != request_id:
                continue
            if message.get("error"):
                error = message["error"]
                detail = error.get("message") if isinstance(error, dict) else None
                raise ProviderError("codex", detail or "Erro retornado pelo Codex.")
            return message.get("result")

    @staticmethod
    def _extract_rate_limits(response: dict[str, Any]) -> NormalizedLimits:
        """Classifica janelas pela duração, sem confiar em primary/secondary."""
        groups: list[dict[str, Any]] = []
        direct = response.get("rateLimits")
        if isinstance(direct, dict):
            groups.append(direct)
        by_id = response.get("rateLimitsByLimitId")
        if isinstance(by_id, dict):
            groups.extend(item for item in by_id.values() if isinstance(item, dict))

        plan = next((str(group["planType"]) for group in groups if group.get("planType")), "—")
        windows: list[tuple[int, RateLimitWindow]] = []
        seen: set[tuple[int, Any, Any]] = set()
        for group in groups:
            for key in ("primary", "secondary"):
                window = group.get(key)
                if not isinstance(window, dict):
                    continue
                try:
                    duration_value = window.get("windowDurationMins")
                    if duration_value is None:
                        continue
                    duration = int(duration_value)
                except (TypeError, ValueError):
                    continue
                identity = (duration, window.get("usedPercent"), window.get("resetsAt"))
                if duration > 0 and identity not in seen:
                    seen.add(identity)
                    windows.append((duration, cast(RateLimitWindow, window)))

        five_hour = min(
            (item for item in windows if item[0] <= 24 * 60),
            key=lambda item: abs(item[0] - 5 * 60),
            default=None,
        )
        weekly = min(
            (item for item in windows if item[0] > 24 * 60),
            key=lambda item: abs(item[0] - 7 * 24 * 60),
            default=None,
        )
        if not windows and groups:
            primary = groups[0].get("primary")
            secondary = groups[0].get("secondary")
            five_hour = (0, cast(RateLimitWindow, primary)) if isinstance(primary, dict) else None
            weekly = (0, cast(RateLimitWindow, secondary)) if isinstance(secondary, dict) else None
        return {
            "plan": plan,
            "five_hour": five_hour[1] if five_hour else None,
            "weekly": weekly[1] if weekly else None,
        }

    def read_limits(self) -> NormalizedLimits:
        with self.lock:
            try:
                for attempt in range(2):
                    try:
                        if not self.process or self.process.poll() is not None:
                            self._start()
                        response = self._request("account/rateLimits/read", None)
                        if not isinstance(response, dict):
                            raise ProviderError("codex", "Resposta de limites do Codex inválida.")
                        return self._extract_rate_limits(response)
                    except Exception as exc:
                        self.close()
                        if attempt:
                            if isinstance(exc, ProviderError):
                                raise
                            raise ProviderError("codex", "Não foi possível consultar o Codex.") from exc
                raise ProviderError("codex", "Não foi possível consultar o Codex.")
            finally:
                self.close()

    def close(self) -> None:
        process, self.process = self.process, None
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                process.kill()
