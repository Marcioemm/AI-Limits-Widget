import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from ai_limits_widget.collector import Collector
from ai_limits_widget.integration import ProducerBusy, ProducerLock, SnapshotPublisher, timestamp, utc
from ai_limits_widget.providers.claude import ClaudeClient


def profile(pid="internal-account@example.com", provider="codex"):
    return {"id": pid, "provider": provider, "label": "Private discovered name", "executable": None, "configDir": None}


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = pathlib.Path(self.temp.name)
        self.now = 2000000000.0
        self.client = Mock(minimum_refresh_interval_seconds=1)
        self.client.read_limits.return_value = self.data()

    def data(self, used=28.25):
        return {"five_hour": {"usedPercent": used, "windowDurationMins": 120, "resetsAt": self.now + 3600}}

    def collector(self, profiles=None, **kwargs):
        collector = Collector(
            profiles or [profile()],
            directory=self.directory,
            clock=lambda: self.now,
            factory=lambda _: self.client,
            availability=lambda _: None,
            **kwargs,
        )
        self.addCleanup(collector.close)
        return collector

    def test_remaining_precision_null_zero_and_invalid(self):
        for used, expected in [
            (28.25, 71.75),
            (100, 0),
            (0, 100),
            (None, None),
            (float("nan"), None),
            (float("inf"), None),
            (True, None),
            (-2, None),
            (101, None),
        ]:
            collector = self.collector()
            self.client.read_limits.return_value = self.data(used)
            collector.collect()
            window = collector.snapshot()[0]["windows"][0]
            self.assertEqual(expected, window["remainingPercent"])
            self.assertEqual(120, window["durationMinutes"])

    def test_ids_stable_opaque_and_public_allowlist(self):
        first = self.collector()
        first.collect()
        state = first.snapshot()[0]
        self.assertEqual(state["id"], self.collector().snapshot()[0]["id"])
        self.assertNotIn("account", json.dumps(state))
        self.assertEqual("Codex", state["label"])
        self.assertNotIn("configDir", state)
        self.assertNotIn("executable", state)

    def test_cache_time_not_renewed_and_retry_respected(self):
        self.client.read_limits.return_value = {
            **self.data(),
            "fetchedAt": self.now - 900,
            "stale": True,
            "nextRetryAt": self.now + 1800,
        }
        collector = self.collector()
        collector.collect()
        state = collector.snapshot()[0]
        self.assertEqual("stale", state["status"])
        self.assertEqual(utc(self.now - 900), state["windows"][0]["observedAt"])
        self.assertEqual(utc(self.now - 300), state["windows"][0]["validUntil"])
        self.assertIsNone(state["lastSuccessAt"])
        self.now += 300
        collector.collect(force=True)
        self.client.read_limits.assert_called_once()

    def test_error_preserves_data_then_recovers(self):
        collector = self.collector()
        collector.collect()
        success = collector.snapshot()[0]["lastSuccessAt"]
        self.now += 300
        self.client.read_limits.side_effect = RuntimeError("secret token /private/path")
        collector.collect()
        state = collector.snapshot()[0]
        self.assertEqual("stale", state["status"])
        self.assertEqual(success, state["lastSuccessAt"])
        self.assertEqual(71.75, state["windows"][0]["remainingPercent"])
        self.assertNotIn("secret", json.dumps(state))
        self.now += 300
        self.client.read_limits.side_effect = None
        collector.collect()
        self.assertEqual("ok", collector.snapshot()[0]["status"])
        self.assertGreater(timestamp(collector.snapshot()[0]["lastSuccessAt"]), timestamp(success))

    def test_reset_expires_without_assuming_full(self):
        collector = self.collector()
        collector.collect()
        self.now += 3601
        state = collector.snapshot()[0]
        self.assertEqual("stale", state["status"])
        self.assertIsNone(state["windows"][0]["remainingPercent"])

    def test_older_fallback_cache_does_not_replace_a_newer_observation(self):
        collector = self.collector()
        collector.collect()
        first = collector.snapshot()[0]["windows"]
        self.now += 300
        self.client.read_limits.return_value = {**self.data(90), "stale": True, "fetchedAt": self.now - 1800}
        collector.collect()
        state = collector.snapshot()[0]
        self.assertEqual("stale", state["status"])
        self.assertEqual(first, state["windows"])

    def test_partial_failure_isolated_and_no_extra_poll_queries(self):
        bad = Mock(minimum_refresh_interval_seconds=1)
        bad.read_limits.side_effect = RuntimeError("credential login secret")
        collector = Collector(
            [profile("one"), profile("two", "claude")],
            directory=self.directory,
            clock=lambda: self.now,
            availability=lambda _: None,
            factory=lambda p: self.client if p["id"] == "one" else bad,
        )
        self.addCleanup(collector.close)
        collector.collect()
        for _ in range(10):
            collector.snapshot()
            collector.collect(force=True)
        self.assertEqual(["ok", "auth_required"], [p["status"] for p in collector.snapshot()])
        self.client.read_limits.assert_called_once()
        bad.read_limits.assert_called_once()

    def test_minimum_and_exponential_backoff(self):
        self.client.minimum_refresh_interval_seconds = 600
        self.client.read_limits.side_effect = RuntimeError("offline")
        collector = self.collector()
        collector.collect()
        self.now += 300
        collector.collect(force=True)
        self.assertEqual(1, self.client.read_limits.call_count)
        self.now += 300
        collector.collect()
        self.assertEqual(utc(self.now + 1200), collector.snapshot()[0]["nextAttemptAt"])

    def test_missing_cli_visible_before_first_collection(self):
        collector = Collector([profile()], directory=self.directory, availability=lambda _: "CLI ausente")
        self.addCleanup(collector.close)
        self.assertEqual("unavailable", collector.snapshot()[0]["status"])
        collector.collect()
        self.assertEqual([], collector.snapshot()[0]["windows"])

    def test_absent_short_window_and_empty_profiles(self):
        self.client.read_limits.return_value = {"weekly": {"usedPercent": 100}}
        collector = self.collector()
        collector.collect()
        self.assertEqual(["weekly"], [w["id"] for w in collector.snapshot()[0]["windows"]])
        empty = Collector([], directory=self.directory)
        self.addCleanup(empty.close)
        self.assertEqual([], empty.snapshot())

    def test_claude_does_not_invoke_prompt_token_refresh(self):
        client = ClaudeClient(state_path=self.directory / "cache.json")
        collector = Collector(
            [profile(provider="claude")],
            directory=self.directory,
            factory=lambda _: client,
            availability=lambda _: None,
        )
        self.addCleanup(collector.close)
        with patch.object(client, "read_limits", return_value=self.data()) as read:
            collector.collect()
        read.assert_called_once_with(allow_token_refresh=False)


class TransportTests(unittest.TestCase):
    def test_atomic_reads_retries_and_heartbeat_without_observation_change(self):
        with tempfile.TemporaryDirectory() as directory:
            publisher = SnapshotPublisher(pathlib.Path(directory))
            publisher.update([])
            original = publisher.path.read_bytes()
            with (
                patch("ai_limits_widget.config.os.replace", side_effect=PermissionError),
                patch("ai_limits_widget.integration.time.sleep"),
            ):
                publisher.update([])
            self.assertEqual(original, publisher.path.read_bytes())
            self.assertIsNotNone(publisher.last_error)
            errors = []
            stop = threading.Event()

            def reader():
                while not stop.is_set():
                    try:
                        self.assertEqual(1, json.loads(publisher.path.read_text(encoding="utf-8"))["schemaVersion"])
                    except PermissionError:
                        pass  # Transient Windows sharing violation: consumer retries next poll.
                    except Exception as exc:
                        errors.append(exc)

            thread = threading.Thread(target=reader)
            thread.start()
            try:
                for _ in range(40):
                    publisher.update([])
            finally:
                stop.set()
                thread.join()
            self.assertEqual([], errors)
            # Continuous readers may exhaust bounded Windows retries. Recovery
            # after the reader releases the file must succeed.
            publisher.update([])
            self.assertIsNone(publisher.last_error)
            publisher.close(remove=True)
            self.assertFalse(publisher.path.exists())

    def test_heartbeat_keeps_real_observation_and_does_not_query(self):
        with tempfile.TemporaryDirectory() as directory, patch("ai_limits_widget.integration.HEARTBEAT_SECONDS", 0.02):
            client = Mock(minimum_refresh_interval_seconds=1)
            observed = time.time()
            client.read_limits.return_value = {"weekly": {"usedPercent": 10}, "fetchedAt": observed}
            collector = Collector(
                [profile()],
                directory=pathlib.Path(directory),
                publish=True,
                factory=lambda _: client,
                availability=lambda _: None,
            )
            try:
                collector.collect()
                first = json.loads(collector.publisher.path.read_text(encoding="utf-8"))
                time.sleep(0.1)
                last = json.loads(collector.publisher.path.read_text(encoding="utf-8"))
                self.assertGreater(last["revision"], first["revision"])
                self.assertEqual(first["profiles"], last["profiles"])
                client.read_limits.assert_called_once()
            finally:
                collector.close()

    def test_kernel_lock_released_after_process_death(self):
        with tempfile.TemporaryDirectory() as directory:
            code = (
                "import pathlib,time; from ai_limits_widget.integration import ProducerLock; "
                f"lock=ProducerLock(pathlib.Path({directory!r})); lock.__enter__(); print('ready',flush=True); time.sleep(30)"
            )
            process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual("ready", process.stdout.readline().strip())
                with self.assertRaises(ProducerBusy):
                    with ProducerLock(pathlib.Path(directory)):
                        pass
            finally:
                process.kill()
                process.wait(timeout=10)
                process.stdout.close()
            with ProducerLock(pathlib.Path(directory)):
                pass

    def test_headless_entry_point_never_imports_ui_and_stops_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            data = pathlib.Path(directory) / "LimitesIA"
            data.mkdir()
            (data / "config.json").write_text(
                json.dumps({"providers": [], "profiles": [], "executables": {"grok": None}}), encoding="utf-8"
            )
            env = {**os.environ, "LOCALAPPDATA": directory, "XDG_CONFIG_HOME": directory}
            if os.name != "nt":
                data = pathlib.Path(directory) / "ai-limits-widget"
                data.mkdir()
                (data / "config.json").write_text(
                    json.dumps({"providers": [], "profiles": [], "executables": {"grok": None}}), encoding="utf-8"
                )
            code = (
                "import sys; from ai_limits_widget.app import main; main(); "
                "assert not any(n == 'tkinter' or n.startswith('ai_limits_widget.ui') for n in sys.modules)"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", code, "--integration"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                snapshot = data / "integration/v1/snapshot.json"
                deadline = time.monotonic() + 10
                while not snapshot.exists() and time.monotonic() < deadline and process.poll() is None:
                    time.sleep(0.05)
                self.assertTrue(snapshot.exists())
                self.assertEqual([], json.loads(snapshot.read_text(encoding="utf-8"))["profiles"])
                second = subprocess.run(
                    [sys.executable, "-m", "ai_limits_widget", "--widget"],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(2, second.returncode)
                subprocess.run(
                    [sys.executable, "-m", "ai_limits_widget", "--stop-integration"],
                    env=env,
                    check=True,
                    capture_output=True,
                    timeout=10,
                )
                _, err = process.communicate(timeout=10)
                self.assertEqual(0, process.returncode, err)
                self.assertTrue(json.loads((data / "config.json").read_text())["integrationMode"])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=10)

    def test_timestamp_rejects_unknown_nonfinite_and_timezone_naive(self):
        for value in (None, 0, True, "2026-11-02T12:00:00", "invalid", float("inf")):
            self.assertIsNone(utc(value))
        self.assertEqual("2026-11-02T15:00:00Z", utc("2026-11-02T12:00:00-03:00"))
