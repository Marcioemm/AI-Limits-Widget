import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from ai_limits_widget import app


RUN_TK_SMOKE = os.environ.get("AI_LIMITS_RUN_TK_SMOKE") == "1"


@unittest.skipUnless(RUN_TK_SMOKE, "smoke gráfico executado separadamente com Xvfb")
class TkSmokeTests(unittest.TestCase):
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

            with patch.object(app, "CONFIG_FILE", config_file):
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
