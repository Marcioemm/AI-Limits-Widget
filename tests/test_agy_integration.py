import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_limits_widget.agy_integration import (  # noqa: E402
    AgyClient,
    extract_gemini_quota,
    install_statusline,
    is_our_bridge,
    remove_statusline,
    save_statusline_payload,
    statusline_state,
)


class AgyQuotaTests(unittest.TestCase):
    def payload(self, model: str = "Gemini 3.1 Pro (High)") -> dict:
        return {
            "cwd": "C:/private/project",
            "email": "private@example.com",
            "conversation_id": "secret-conversation",
            "model": {"id": model, "display_name": model},
            "quota": {
                "gemini-weekly": {
                    "remaining_fraction": 0.7054,
                    "reset_time": "2026-10-16T12:00:00Z",
                    "reset_in_seconds": 90300,
                },
                "other-weekly": {"remaining_fraction": 1.0},
            },
        }

    def test_extracts_only_active_gemini_and_quota(self) -> None:
        result = extract_gemini_quota(self.payload(), captured_at=1234)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("Gemini 3.1 Pro (High)", result["model"]["displayName"])
        self.assertEqual(0.7054, result["quota"]["remainingFraction"])
        serialized = json.dumps(result)
        self.assertNotIn("private@example.com", serialized)
        self.assertNotIn("secret-conversation", serialized)
        self.assertNotIn("C:/private/project", serialized)

    def test_does_not_replace_gemini_with_another_active_provider(self) -> None:
        self.assertIsNone(extract_gemini_quota(self.payload("Claude Sonnet 4.5")))

    def test_cache_is_converted_to_widget_weekly_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "quota.json"
            self.assertTrue(save_statusline_payload(self.payload(), path=path, captured_at=1234))
            data = AgyClient(path).read_limits()
        self.assertAlmostEqual(29.46, data["weekly"]["usedPercent"], places=2)
        self.assertEqual(10080, data["weekly"]["windowDurationMins"])
        self.assertEqual("Gemini 3.1 Pro (High)", data["model"])


class AgySettingsTests(unittest.TestCase):
    def test_recognizes_windows_and_linux_bridge_names(self) -> None:
        self.assertTrue(is_our_bridge(r'"C:\App\AI Limits AGY Bridge.exe"'))
        self.assertTrue(is_our_bridge("/usr/lib/ai-limits-widget/ai-limits-agy-bridge"))

    def test_installs_and_removes_only_our_statusline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "settings.json"
            path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
            result = install_statusline(path, command='"C:\\App\\AI Limits AGY Bridge.exe"')
            self.assertEqual("installed", result)
            self.assertEqual("ready", statusline_state(path))
            settings = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("dark", settings["theme"])
            self.assertTrue(remove_statusline(path))
            self.assertEqual("missing", statusline_state(path))
            self.assertEqual({"theme": "dark"}, json.loads(path.read_text(encoding="utf-8")))

    def test_never_overwrites_a_custom_statusline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "settings.json"
            original = {"statusLine": {"type": "command", "command": "custom-status.exe"}}
            path.write_text(json.dumps(original), encoding="utf-8")
            self.assertEqual("conflict", install_statusline(path, command="our-bridge.exe"))
            self.assertEqual(original, json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
