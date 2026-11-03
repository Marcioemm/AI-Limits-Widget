import ctypes
import os
import pathlib
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from ai_limits_widget import app, config
from ai_limits_widget.tray import IntegrationTray


class BackgroundTransitionsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config_file = pathlib.Path(directory.name) / "config.json"
        self.patch = patch.object(config, "CONFIG_FILE", self.config_file)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_background_returns_to_widget_and_saves_preference_under_same_lock(self):
        config.save_config({"integrationMode": True, "integrationEnabled": True})
        widget = Mock(background_requested=False)
        with (
            patch("sys.argv", ["ai-limits-widget"]),
            patch.object(app, "ProducerLock") as lock,
            patch.object(app, "run_integration", return_value=True) as background,
            patch("ai_limits_widget.ui.app.UsageWidget", return_value=widget),
        ):
            app.main()
        background.assert_called_once_with()
        widget.run.assert_called_once_with()
        lock.assert_called_once_with()
        self.assertFalse(config.load_config()["integrationMode"])
        self.assertTrue(config.load_config()["integrationEnabled"])

    def test_settings_request_switches_to_background_without_a_second_process(self):
        config.save_config({"integrationEnabled": True})
        widget = Mock(background_requested=True)

        def save_background():
            config.save_config({"integrationMode": True, "integrationEnabled": True})

        widget.run.side_effect = save_background
        with (
            patch("sys.argv", ["ai-limits-widget"]),
            patch.object(app, "ProducerLock") as lock,
            patch.object(app, "run_integration", return_value=False) as background,
            patch("ai_limits_widget.ui.app.UsageWidget", return_value=widget) as create_widget,
        ):
            app.main()
        create_widget.assert_called_once_with()
        background.assert_called_once_with()
        lock.assert_called_once_with()
        self.assertTrue(config.load_config()["integrationMode"])

    def test_exiting_background_preserves_saved_mode(self):
        config.save_config({"integrationMode": True})
        with (
            patch("sys.argv", ["ai-limits-widget"]),
            patch.object(app, "ProducerLock"),
            patch.object(app, "run_integration", return_value=False),
            patch("ai_limits_widget.ui.app.UsageWidget") as widget,
        ):
            app.main()
        widget.assert_not_called()
        self.assertTrue(config.load_config()["integrationMode"])


@unittest.skipUnless(os.name == "nt", "Windows notification area")
class WindowsTrayTests(unittest.TestCase):
    def test_native_tray_opens_widget_and_releases_window_and_thread(self):
        from ctypes import wintypes as wt

        stop, show = threading.Event(), threading.Event()
        tray = IntegrationTray(stop, show)
        try:
            tray.start()
            self.assertIsNotNone(tray.hwnd)
            self.assertTrue(tray.thread.is_alive())
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
            self.assertTrue(user.PostMessageW(tray.hwnd, 0x8001, 0, 0x0203))
            self.assertTrue(stop.wait(5))
            self.assertTrue(show.is_set())
        finally:
            tray.close()
        self.assertIsNone(tray.error)
        self.assertIsNone(tray.hwnd)
        self.assertFalse(tray.thread.is_alive())

    def test_closing_native_tray_exits_without_requesting_widget(self):
        stop, show = threading.Event(), threading.Event()
        tray = IntegrationTray(stop, show)
        try:
            tray.start()
        finally:
            tray.close()
        self.assertTrue(stop.is_set())
        self.assertFalse(show.is_set())
        self.assertIsNone(tray.error)
        self.assertFalse(tray.thread.is_alive())
