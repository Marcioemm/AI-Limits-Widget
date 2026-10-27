import pathlib
import shlex
import tempfile
import unittest
from unittest.mock import ANY, MagicMock

from ai_limits_widget import app, platform_support


class PlatformDirectoryTests(unittest.TestCase):
    def test_windows_preserves_historical_directory(self):
        result = platform_support.config_dir(
            {"LOCALAPPDATA": r"C:\Users\example\AppData\Local"},
            pathlib.Path(r"C:\Users\example"),
            windows=True,
        )
        self.assertEqual(pathlib.Path(r"C:\Users\example\AppData\Local") / "LimitesIA", result)

    def test_linux_uses_xdg_directories(self):
        environment = {
            "XDG_CONFIG_HOME": "/tmp/example-config",
            "XDG_CACHE_HOME": "/tmp/example-cache",
        }
        self.assertEqual(
            pathlib.Path("/tmp/example-config/ai-limits-widget"),
            platform_support.config_dir(environment, pathlib.Path("/home/example"), windows=False),
        )
        self.assertEqual(
            pathlib.Path("/tmp/example-cache/ai-limits-widget"),
            platform_support.cache_dir(environment, pathlib.Path("/home/example"), windows=False),
        )

    def test_linux_uses_xdg_defaults(self):
        home = pathlib.Path("/home/example")
        self.assertEqual(home / ".config" / "ai-limits-widget", platform_support.config_dir({}, home, windows=False))
        self.assertEqual(home / ".cache" / "ai-limits-widget", platform_support.cache_dir({}, home, windows=False))


class CommandTests(unittest.TestCase):
    def test_provider_commands_are_native_on_linux(self):
        self.assertEqual(("codex",), app.provider_commands("codex", windows=False))
        self.assertEqual(("claude",), app.provider_commands("claude", windows=False))
        self.assertEqual(("agy",), app.provider_commands("gemini", windows=False))

    def test_provider_commands_keep_windows_launchers(self):
        self.assertEqual(("codex.exe", "codex.cmd", "codex"), app.provider_commands("codex", windows=True))

    def test_linux_file_dialog_accepts_any_executable_name(self):
        self.assertEqual([("Todos os arquivos", "*")], app.executable_filetypes(windows=False))

    def test_posix_command_preserves_arguments_with_spaces(self):
        parts = ["/usr/bin/python3", "/opt/AI Limits Widget/app.py"]
        command = platform_support.quote_command(parts, windows=False)
        self.assertEqual(parts, shlex.split(command))

    def test_linux_startup_command_uses_python_and_app_path(self):
        command = platform_support.startup_command(
            pathlib.PurePosixPath("/opt/AI Limits Widget/app.py"),
            executable=pathlib.PurePosixPath("/usr/bin/python3"),
            frozen=False,
            windows=False,
        )
        self.assertEqual(["/usr/bin/python3", "/opt/AI Limits Widget/app.py"], shlex.split(command))


class StartAtLoginTests(unittest.TestCase):
    def test_linux_creates_and_removes_desktop_file(self):
        with tempfile.TemporaryDirectory() as directory:
            desktop_file = pathlib.Path(directory) / "autostart" / "ai-limits-widget.desktop"
            command = platform_support.quote_command(
                ["/usr/bin/python3", "/opt/AI Limits Widget/app.py"],
                windows=False,
            )

            platform_support.set_start_at_login(False, command, windows=False, desktop_file=desktop_file)
            platform_support.set_start_at_login(True, command, windows=False, desktop_file=desktop_file)

            contents = desktop_file.read_text(encoding="utf-8")
            self.assertIn("[Desktop Entry]", contents)
            self.assertIn('Exec="/usr/bin/python3" "/opt/AI Limits Widget/app.py"', contents)
            self.assertIn("Terminal=false", contents)

            platform_support.set_start_at_login(False, command, windows=False, desktop_file=desktop_file)
            self.assertFalse(desktop_file.exists())

    def test_windows_writes_registry_value(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = object()
        registry.KEY_SET_VALUE = 2
        registry.REG_SZ = 1

        platform_support.set_start_at_login(
            True,
            '"C:\\app.exe"',
            windows=True,
            registry=registry,
        )

        registry.SetValueEx.assert_called_once_with(
            ANY,
            platform_support.WINDOWS_RUN_VALUE,
            0,
            registry.REG_SZ,
            '"C:\\app.exe"',
        )


class LinuxSourceInstallTests(unittest.TestCase):
    def test_linux_scripts_and_desktop_template_are_present(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        start_script = root / "scripts" / "start.sh"
        setup_script = root / "scripts" / "setup.sh"
        desktop_template = root / "packaging" / "linux" / "ai-limits-widget.desktop.in"

        self.assertTrue(start_script.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash"))
        self.assertIn("python3-tk", setup_script.read_text(encoding="utf-8"))
        desktop = desktop_template.read_text(encoding="utf-8")
        self.assertIn("Type=Application", desktop)
        self.assertIn('Exec="@AI_LIMITS_EXECUTABLE@"', desktop)
        self.assertIn("Terminal=false", desktop)

    def test_linux_distribution_files_are_complete(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        build_script = (root / "scripts" / "build-linux.sh").read_text(encoding="utf-8")
        desktop = (root / "packaging" / "linux" / "ai-limits-widget.desktop").read_text(encoding="utf-8")
        control = (root / "packaging" / "linux" / "control.in").read_text(encoding="utf-8")
        workflow = (root / ".github" / "workflows" / "build-linux.yml").read_text(encoding="utf-8")

        self.assertTrue(build_script.startswith("#!/usr/bin/env bash"))
        self.assertIn("-m PyInstaller", build_script)
        self.assertIn("dpkg-deb --root-owner-group --build", build_script)
        self.assertIn("sha256sum", build_script)
        self.assertIn("Exec=/usr/bin/ai-limits-widget", desktop)
        for field in ("Package:", "Version:", "Architecture:", "Maintainer:", "Description:"):
            self.assertIn(field, control)
        self.assertIn("ubuntu-24.04", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)


class WindowsInstallerBuildTests(unittest.TestCase):
    def test_windows_build_bundles_agy_and_tests_executable_before_installer(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        build_script = (root / "scripts" / "build-installer.ps1").read_text(encoding="utf-8")

        hidden_import = "--hidden-import ai_limits_widget.agy_integration"
        smoke_test = "-ArgumentList '--build-smoke-test'"
        inno_setup = '& $iscc "/DMyAppVersion=$Version"'
        self.assertIn(hidden_import, build_script)
        self.assertIn(smoke_test, build_script)
        self.assertLess(build_script.index(smoke_test), build_script.index(inno_setup))


if __name__ == "__main__":
    unittest.main()
