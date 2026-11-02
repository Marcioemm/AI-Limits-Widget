import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import Mock, patch

from ai_limits_widget import app, config

RUN_TK_SMOKE = os.environ.get("AI_LIMITS_RUN_TK_SMOKE") == "1"


@unittest.skipUnless(RUN_TK_SMOKE, "smoke gráfico executado separadamente com Xvfb")
class TkSmokeTests(unittest.TestCase):
    def test_widget_publishes_the_same_collection_without_duplicate_queries(self):
        from ai_limits_widget import collector
        from ai_limits_widget.ui import app as ui_app

        with tempfile.TemporaryDirectory() as directory:
            data = pathlib.Path(directory)
            config_file = data / "config.json"
            config_file.write_text(
                json.dumps(
                    {
                        "providers": ["codex"],
                        "integrationEnabled": True,
                        "executables": {"grok": None},
                    }
                ),
                encoding="utf-8",
            )
            client = Mock(minimum_refresh_interval_seconds=1)
            client.read_limits.return_value = {"five_hour": {"usedPercent": 28, "windowDurationMins": 300}}
            with (
                patch.object(config, "CONFIG_FILE", config_file),
                patch.object(collector, "APP_DATA_DIR", data),
                patch.object(ui_app, "profile_is_available", return_value=True),
                patch.object(ui_app, "profile_unavailable_reason", return_value=None),
                patch.object(ui_app, "create_provider", return_value=client),
            ):
                widget = ui_app.UsageWidget()
                try:
                    widget._refresh_worker(True)
                    # The collector also exports unavailable profiles, which have no meter.
                    widget.events.put(("profile_error", ({"id": "hidden-unavailable"}, "CLI ausente")))
                    widget._drain_events()
                    snapshot = json.loads((data / "integration/v1/snapshot.json").read_text(encoding="utf-8"))
                    self.assertEqual(72, snapshot["profiles"][0]["windows"][0]["remainingPercent"])
                    self.assertEqual(28, widget.last_meter_data["codex-default"][0]["usedPercent"])
                    widget._refresh_worker(True)
                    client.read_limits.assert_called_once()
                finally:
                    widget.close()

    def test_widget_and_settings_render_without_providers(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = pathlib.Path(directory) / "config.json"
            config_file.write_text(
                json.dumps(
                    {
                        "providers": [],
                        "refreshMinutes": 5,
                        "layout": "cards",
                        "startAtLogin": False,
                        "executables": {"codex": None, "claude": None, "gemini": None},
                        "profiles": [],
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(config, "CONFIG_FILE", config_file):
                widget = app.UsageWidget()
                try:
                    widget.root.update_idletasks()
                    self.assertEqual("Limites de IA", widget.root.title())
                    self.assertGreaterEqual(widget.root.winfo_width(), app.WINDOW_WIDTH)

                    widget.toggle_collapse()
                    self.assertTrue(widget.collapsed)
                    widget.toggle_collapse()
                    self.assertFalse(widget.collapsed)

                    widget.toggle_layout()
                    self.assertEqual("compact", widget.layout)
                    widget.toggle_layout()
                    self.assertEqual("cards", widget.layout)

                    settings = app.SettingsDialog(widget)
                    settings.update_idletasks()
                    self.assertIn("Configurações", settings.title())
                    settings.destroy()
                finally:
                    if widget.root.winfo_exists():
                        widget.close()


if __name__ == "__main__":
    unittest.main()
