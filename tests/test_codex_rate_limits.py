import json
import pathlib
import unittest

from ai_limits_widget.providers.codex import CodexClient

FIXTURES = pathlib.Path(__file__).with_name("fixtures")


class CodexRateLimitCompatibilityTests(unittest.TestCase):
    def response(self, name: str) -> dict:
        fixture = FIXTURES / name
        return json.loads(fixture.read_text(encoding="utf-8"))

    def test_reads_both_windows_from_their_durations(self) -> None:
        limits = CodexClient._extract_rate_limits(self.response("codex_both_windows.json"))
        self.assertEqual(24, limits["five_hour"]["usedPercent"])
        self.assertEqual(61, limits["weekly"]["usedPercent"])

    def test_leaves_absent_short_window_empty(self) -> None:
        limits = CodexClient._extract_rate_limits(self.response("codex_weekly_only.json"))
        self.assertIsNone(limits["five_hour"])
        self.assertEqual(19, limits["weekly"]["usedPercent"])

    def test_does_not_assume_primary_means_five_hours(self) -> None:
        limits = CodexClient._extract_rate_limits(self.response("codex_split_windows.json"))
        self.assertEqual(81, limits["five_hour"]["usedPercent"])
        self.assertEqual(19, limits["weekly"]["usedPercent"])

    def test_keeps_legacy_primary_secondary_compatibility(self) -> None:
        limits = CodexClient._extract_rate_limits(self.response("codex_legacy.json"))
        self.assertEqual(40, limits["five_hour"]["usedPercent"])
        self.assertEqual(70, limits["weekly"]["usedPercent"])


if __name__ == "__main__":
    unittest.main()
