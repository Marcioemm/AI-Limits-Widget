import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_limits_widget.app import CodexClient  # noqa: E402


class CodexRateLimitCompatibilityTests(unittest.TestCase):
    def response(self, name: str) -> dict:
        fixture = ROOT / "tests" / "fixtures" / name
        return json.loads(fixture.read_text(encoding="utf-8"))

    def test_reads_both_windows_from_their_durations(self) -> None:
        limits = CodexClient._extract_rate_limits(self.response("codex_both_windows.json"))
        self.assertEqual(24, limits["primary"]["usedPercent"])
        self.assertEqual(61, limits["secondary"]["usedPercent"])

    def test_leaves_absent_short_window_empty(self) -> None:
        limits = CodexClient._extract_rate_limits(self.response("codex_weekly_only.json"))
        self.assertIsNone(limits["primary"])
        self.assertEqual(19, limits["secondary"]["usedPercent"])

    def test_does_not_assume_primary_means_five_hours(self) -> None:
        limits = CodexClient._extract_rate_limits(self.response("codex_split_windows.json"))
        self.assertEqual(81, limits["primary"]["usedPercent"])
        self.assertEqual(19, limits["secondary"]["usedPercent"])

    def test_keeps_legacy_primary_secondary_compatibility(self) -> None:
        limits = CodexClient._extract_rate_limits(self.response("codex_legacy.json"))
        self.assertEqual(40, limits["primary"]["usedPercent"])
        self.assertEqual(70, limits["secondary"]["usedPercent"])


if __name__ == "__main__":
    unittest.main()
