import unittest
from unittest.mock import ANY, MagicMock, patch

from ai_limits_widget import startup


class StartWithWindowsTests(unittest.TestCase):
    def test_enabling_creates_windows_run_entry(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = object()
        registry.KEY_SET_VALUE = 2
        registry.REG_SZ = 1
        with (
            patch.object(startup, "winreg", registry),
            patch.object(startup, "startup_command", return_value='"C:\\app.exe"'),
        ):
            startup.set_start_with_windows(True)

        registry.SetValueEx.assert_called_once_with(
            ANY,
            startup.WINDOWS_RUN_VALUE,
            0,
            registry.REG_SZ,
            '"C:\\app.exe"',
        )

    def test_disabling_removes_windows_run_entry(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = object()
        registry.KEY_SET_VALUE = 2
        with patch.object(startup, "winreg", registry):
            startup.set_start_with_windows(False)

        registry.DeleteValue.assert_called_once_with(ANY, startup.WINDOWS_RUN_VALUE)


if __name__ == "__main__":
    unittest.main()
