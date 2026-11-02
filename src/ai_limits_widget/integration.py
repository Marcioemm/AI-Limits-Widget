"""Public, read-only snapshot transport. No provider or UI dependencies."""

from __future__ import annotations

import copy
import datetime as dt
import math
import os
import pathlib
import threading
import time
import uuid
from typing import Any

from . import __version__
from .config import APP_DATA_DIR, _atomic_json_write

HEARTBEAT_SECONDS = 15


def timestamp(value: Any) -> float | None:
    try:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, str):
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None
            value = parsed.timestamp()
        result = float(value)
        return result if math.isfinite(result) and result > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def utc(value: Any) -> str | None:
    seconds = timestamp(value)
    if seconds is None:
        return None
    try:
        return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError, OSError):
        return None


class ProducerBusy(RuntimeError):
    pass


class ProducerLock:
    """Kernel-owned advisory lock; the persistent file is never a PID lock."""

    def __init__(self, directory: pathlib.Path = APP_DATA_DIR) -> None:
        self.path = directory / "producer.lock"
        self.stream: Any = None

    def __enter__(self) -> ProducerLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                if self.path.stat().st_size == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]
        except OSError as exc:
            stream.close()
            raise ProducerBusy("AI Limits já possui um produtor ativo. Encerre-o antes de trocar de modo.") from exc
        self.stream = stream
        return self

    def __exit__(self, *args: Any) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


class SnapshotPublisher:
    def __init__(self, directory: pathlib.Path = APP_DATA_DIR) -> None:
        self.path = directory / "integration" / "v1" / "snapshot.json"
        self.instance_id = str(uuid.uuid4())
        self.revision = 0
        self.last_error: str | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.profiles: list[dict[str, Any]] = []

    def update(self, profiles: list[dict[str, Any]]) -> None:
        with self._lock:
            self.profiles = profiles
            self._publish()

    def _publish(self) -> None:
        seconds = time.time()
        now = utc(seconds)
        profiles = copy.deepcopy(self.profiles)
        for profile in profiles:
            for window in profile["windows"]:
                reset = timestamp(window["resetsAt"])
                valid = timestamp(window["validUntil"])
                if reset is not None and reset <= seconds:
                    window["remainingPercent"] = None
                if valid is None or valid <= seconds or (reset is not None and reset <= seconds):
                    if profile["status"] == "ok":
                        profile["status"] = "stale"
                        profile["error"] = {"code": "stale_data", "message": "Observação desatualizada"}
        self.revision += 1
        value = {
            "schemaVersion": 1,
            "producer": {"name": "ai-limits-widget", "version": __version__},
            "instanceId": self.instance_id,
            "revision": self.revision,
            "publishedAt": now,
            "heartbeatAt": now,
            "heartbeatIntervalSeconds": HEARTBEAT_SECONDS,
            "profiles": profiles,
        }
        # A reader may temporarily hold the destination on Windows. Never truncate it.
        for delay in (0, 0.05, 0.15, 0.3):
            if delay:
                time.sleep(delay)
            try:
                _atomic_json_write(self.path, value)
                self.last_error = None
                return
            except OSError:
                self.last_error = "Não foi possível publicar o snapshot local."

    def start(self) -> None:
        self._thread = threading.Thread(target=self._heartbeat, name="integration-heartbeat", daemon=True)
        self._thread.start()

    def _heartbeat(self) -> None:
        while not self._stop.wait(HEARTBEAT_SECONDS):
            with self._lock:
                self._publish()

    def close(self, *, remove: bool = False) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        if remove:
            self.path.unlink(missing_ok=True)
