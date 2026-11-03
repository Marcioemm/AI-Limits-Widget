"""Smoke the real frozen executable with isolated data and no provider calls."""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

executable = pathlib.Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="ai-limits-package-") as directory:
    data = pathlib.Path(directory) / ("LimitesIA" if os.name == "nt" else "ai-limits-widget")
    data.mkdir()
    (data / "config.json").write_text(
        json.dumps({"providers": [], "profiles": [], "executables": {"grok": None}}), encoding="utf-8"
    )
    env = {**os.environ, "LOCALAPPDATA": directory, "XDG_CONFIG_HOME": directory}
    process = subprocess.Popen([str(executable), "--integration"], env=env)
    try:
        snapshot = data / "integration/v1/snapshot.json"
        deadline = time.monotonic() + 30
        while not snapshot.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert snapshot.exists(), "Executable did not publish"
        first = json.loads(snapshot.read_text(encoding="utf-8"))
        assert first["schemaVersion"] == 1 and first["profiles"] == []
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            current = json.loads(snapshot.read_text(encoding="utf-8"))
            if current["revision"] > first["revision"]:
                break
            time.sleep(0.2)
        else:
            raise AssertionError("No heartbeat from packaged executable")
        subprocess.run([str(executable), "--stop-integration"], env=env, check=True, timeout=15)
        assert process.wait(timeout=15) == 0
        assert snapshot.exists()
        print("Packaged headless: snapshot v1, heartbeat and clean shutdown OK")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
