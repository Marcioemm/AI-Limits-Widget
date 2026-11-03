"""Shared collection, scheduling and public-state normalization, independent of Tk."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import pathlib
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from .config import APP_DATA_DIR, _atomic_json_write, load_config
from .integration import SnapshotPublisher, timestamp, utc
from .models import NormalizedLimits, Profile
from .profiles import profile_unavailable_reason
from .providers import LimitsProvider, create_provider
from .providers.claude import ClaudeClient

ERRORS = {
    "unavailable": "CLI ou sessão local indisponível",
    "auth_required": "Autentique novamente o provedor",
    "rate_limited": "Nova tentativa agendada",
    "collection_failed": "Não foi possível atualizar os limites",
    "stale_data": "Observação desatualizada",
}


def error_code(message: str) -> str:
    # Only fixed codes/messages cross the public boundary, never exception text.
    text = message.lower()
    if any(word in text for word in ("autentic", "credencial", "expirada", "login", "sessão")):
        return "auth_required"
    return "collection_failed"


class Collector:
    def __init__(
        self,
        profiles: list[Profile],
        interval: int = 300,
        *,
        directory: pathlib.Path | None = None,
        publish: bool = False,
        factory: Callable[[Profile], LimitsProvider] = create_provider,
        availability: Callable[[Profile], str | None] = profile_unavailable_reason,
        clock: Callable[[], float] = time.time,
    ) -> None:
        directory = directory or APP_DATA_DIR
        self.profiles = profiles
        self.interval = interval
        self.clock = clock
        self.factory = factory
        self.availability = availability
        self.clients: dict[str, LimitsProvider] = {}
        self.states: dict[str, dict[str, Any]] = {}
        self.next_attempt: dict[str, float] = {}
        self.failures: dict[str, int] = {}
        self._lock = threading.RLock()
        self.publisher = SnapshotPublisher(directory) if publish else None
        chosen_labels = {p["id"]: p["label"] for p in load_config()["profiles"]}
        ids_path = directory / "integration-profile-ids.json"
        try:
            ids = json.loads(ids_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            ids = {}
        if not isinstance(ids, dict):
            ids = {}
        for profile in profiles:
            # Private map uses hashed internal keys, export IDs are random and persistent.
            key = hashlib.sha256(f"{profile['provider']}:{profile['id']}".encode()).hexdigest()
            try:
                public_id = str(uuid.UUID(ids[key]))
            except (KeyError, ValueError, TypeError, AttributeError):
                public_id = str(uuid.uuid4())
            ids[key] = public_id
            self.states[profile["id"]] = {
                "id": public_id,
                "provider": profile["provider"],
                "label": chosen_labels.get(profile["id"], profile["provider"].title()),
                "status": "loading",
                "lastAttemptAt": None,
                "lastSuccessAt": None,
                "nextAttemptAt": None,
                "error": None,
                "windows": [],
            }
            reason = availability(profile)
            if reason:
                code = "auth_required" if error_code(reason) == "auth_required" else "unavailable"
                self.states[profile["id"]].update(status=code, error={"code": code, "message": ERRORS[code]})
        _atomic_json_write(ids_path, ids)
        self._publish()
        if self.publisher:
            self.publisher.start()

    def _publish(self) -> None:
        if self.publisher:
            self.publisher.update(self.snapshot())

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            result = copy.deepcopy(list(self.states.values()))
            now = self.clock()
            for state in result:
                for window in state["windows"]:
                    reset = timestamp(window["resetsAt"])
                    valid = timestamp(window["validUntil"])
                    if reset is not None and reset <= now:
                        window["remainingPercent"] = None
                    if valid is None or valid <= now or (reset is not None and reset <= now):
                        if state["status"] == "ok":
                            state["status"] = "stale"
                            state["error"] = {"code": "stale_data", "message": ERRORS["stale_data"]}
            return result

    def collect(self, force: bool = False, emit: Callable[[str, Any], None] | None = None) -> None:
        # force requests an update, but never bypasses provider minimums or backoff.
        with self._lock:
            for profile in self.profiles:
                pid = profile["id"]
                now = self.clock()
                if now < self.next_attempt.get(pid, 0):
                    continue
                state = self.states[pid]
                state["lastAttemptAt"] = utc(now)
                reason = self.availability(profile)
                if reason:
                    code = "auth_required" if error_code(reason) == "auth_required" else "unavailable"
                    self._failed(pid, code, now)
                    if emit:
                        emit("profile_error", (profile, reason))
                    self._publish()
                    continue
                try:
                    client = self.clients.get(pid)
                    if client is None:
                        client = self.clients[pid] = self.factory(profile)
                    if isinstance(client, ClaudeClient):
                        data = client.read_limits(allow_token_refresh=False)
                    else:
                        data = client.read_limits()
                    self._received(pid, data, self.clock(), client)
                    if emit:
                        emit("profile", (profile, data))
                except Exception as exc:
                    client = self.clients.get(pid)
                    retry = timestamp(getattr(client, "next_retry_at", None))
                    code = "rate_limited" if retry and retry > now else error_code(str(exc))
                    self._failed(pid, code, now, retry)
                    if emit:
                        emit("profile_error", (profile, str(exc)))
                self._publish()
        if emit:
            emit("done", None)

    def _failed(self, pid: str, code: str, now: float, retry: float | None = None) -> None:
        state = self.states[pid]
        self.failures[pid] = min(self.failures.get(pid, 0) + 1, 4)
        delay = max(self.interval, getattr(self.clients.get(pid), "minimum_refresh_interval_seconds", 0))
        self.next_attempt[pid] = max(now + delay * 2 ** (self.failures[pid] - 1), retry or 0)
        state.update(
            status="stale" if state["windows"] else (code if code in ("auth_required", "unavailable") else "error"),
            error={"code": code, "message": ERRORS[code]},
            nextAttemptAt=utc(self.next_attempt[pid]),
        )

    def _received(self, pid: str, data: NormalizedLimits, now: float, client: LimitsProvider) -> None:
        state = self.states[pid]
        interval = max(self.interval, client.minimum_refresh_interval_seconds)
        retry = timestamp(data.get("nextRetryAt")) or 0
        self.next_attempt[pid] = max(now + interval, retry)
        self.failures[pid] = 0
        windows = []
        fresh_observations = []
        for wid in ("five_hour", "weekly"):
            window = data.get(wid)
            if not isinstance(window, dict):
                continue
            observed = timestamp(window.get("fetchedAt", data.get("fetchedAt")))
            # Providers without a cache timestamp (Codex) return a live observation.
            if observed is None and "fetchedAt" not in window and "fetchedAt" not in data and not data.get("stale"):
                observed = now
            if observed is not None and observed > now + 1:
                observed = None
            used = window.get("usedPercent")
            remaining = None
            if (
                isinstance(used, (int, float))
                and not isinstance(used, bool)
                and math.isfinite(used)
                and 0 <= used <= 100
            ):
                remaining = 100 - used
            resets = timestamp(window.get("resetsAt"))
            if resets is not None and resets <= now:
                remaining = None
            valid = observed + 2 * interval if observed is not None else None
            if valid and resets:
                valid = min(valid, resets)
            duration = window.get("windowDurationMins")
            if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
                duration = None
            exported_window = {
                "id": wid,
                "label": "Janela curta" if wid == "five_hour" else "Janela semanal",
                "durationMinutes": duration,
                "remainingPercent": remaining,
                "observedAt": utc(observed),
                "validUntil": utc(valid),
                "resetsAt": utc(resets),
            }
            previous = next((w for w in state["windows"] if w["id"] == wid), None)
            if previous and (timestamp(previous["observedAt"]) or 0) > (observed or 0):
                exported_window = copy.deepcopy(previous)
            windows.append(exported_window)
            if remaining is not None and observed is not None and not data.get("stale") and valid and valid > now:
                fresh_observations.append(observed)
        if fresh_observations:
            success = max(fresh_observations)
            if success > (timestamp(state["lastSuccessAt"]) or 0):
                state["lastSuccessAt"] = utc(success)
        stale = bool(data.get("stale")) or bool(windows and not fresh_observations)
        code = "rate_limited" if retry > now else "stale_data"
        state.update(
            windows=windows,
            status="stale" if stale else ("ok" if windows else "unavailable"),
            error={"code": code, "message": ERRORS[code]} if stale else None,
            nextAttemptAt=utc(self.next_attempt[pid]),
        )

    def close(self, *, remove_snapshot: bool = False) -> None:
        with self._lock:
            for client in self.clients.values():
                try:
                    client.close()
                except Exception:
                    pass
            self.clients.clear()
        if self.publisher:
            self.publisher.close(remove=remove_snapshot)
