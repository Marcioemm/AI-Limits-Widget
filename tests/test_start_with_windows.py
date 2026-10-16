import json
import pathlib
import tempfile
import unittest
from unittest.mock import ANY, MagicMock, patch

from ai_limits_widget import app


class StartWithWindowsTests(unittest.TestCase):
    def test_load_config_reads_start_with_windows_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = pathlib.Path(directory) / "config.json"
            config_file.write_text(json.dumps({"startWithWindows": True}), encoding="utf-8")
            with patch.object(app, "CONFIG_FILE", config_file):
                self.assertTrue(app.load_config()["startWithWindows"])

    def test_load_config_uses_false_when_preference_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(app, "CONFIG_FILE", pathlib.Path(directory) / "config.json"):
                self.assertFalse(app.load_config()["startWithWindows"])

    def test_enabling_creates_windows_run_entry(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = object()
        registry.KEY_SET_VALUE = 2
        registry.REG_SZ = 1
        with patch.object(app, "winreg", registry), patch.object(app, "startup_command", return_value='"C:\\app.exe"'):
            app.set_start_with_windows(True)

        registry.SetValueEx.assert_called_once_with(
            ANY,
            app.WINDOWS_RUN_VALUE,
            0,
            registry.REG_SZ,
            '"C:\\app.exe"',
        )

    def test_disabling_removes_windows_run_entry(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = object()
        registry.KEY_SET_VALUE = 2
        with patch.object(app, "winreg", registry):
            app.set_start_with_windows(False)

        registry.DeleteValue.assert_called_once_with(ANY, app.WINDOWS_RUN_VALUE)


if __name__ == "__main__":
    unittest.main()
