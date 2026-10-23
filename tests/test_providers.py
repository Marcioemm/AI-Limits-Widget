import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from ai_limits_widget.providers import ProviderError, create_provider
from ai_limits_widget.providers.claude import ClaudeClient
from ai_limits_widget.providers.codex import CodexClient
from ai_limits_widget.providers.gemini import GeminiClient


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class ProviderContractTests(unittest.TestCase):
    def profile(self, provider: str) -> dict:
        return {
            "id": f"{provider}-default",
            "provider": provider,
            "label": "Padrão",
            "executable": None,
            "configDir": None,
        }

    def test_factory_returns_common_provider_contract(self) -> None:
        for provider in ("codex", "claude", "gemini"):
            client = create_provider(self.profile(provider))
            self.assertEqual(provider, client.provider_name)
            self.assertTrue(callable(client.read_limits))
            self.assertTrue(callable(client.close))

    def test_codex_invalid_response_has_provider_context(self) -> None:
        client = CodexClient()
        with patch.object(client, "_start"), patch.object(client, "_request", return_value=[]):
            with self.assertRaises(ProviderError) as caught:
                client.read_limits()
        self.assertEqual("codex", caught.exception.provider)
        self.assertIn("inválida", caught.exception.detail)


class ClaudeProviderTests(unittest.TestCase):
    def test_legacy_cache_is_migrated_to_normalized_weekly_window(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = pathlib.Path(directory) / "state.json"
            state.write_text(
                json.dumps(
                    {
                        "data": {
                            "five_hour": {"usedPercent": 12},
                            "seven_day": {"usedPercent": 34},
                            "fetchedAt": 100,
                        },
                        "nextRetryAt": 200,
                        "backoffIndex": 1,
                    }
                ),
                encoding="utf-8",
            )
            client = ClaudeClient(state_path=state)
        self.assertEqual(34, client.last_data["weekly"]["usedPercent"])
        self.assertNotIn("seven_day", client.last_data)

    def test_success_is_normalized_before_returning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            credentials = root / ".credentials.json"
            credentials.write_text(
                json.dumps({"claudeAiOauth": {"accessToken": "secret", "subscriptionType": "pro"}}),
                encoding="utf-8",
            )
            client = ClaudeClient(config_dir=directory, state_path=root / "state.json")
            payload = {
                "five_hour": {"utilization": 22, "resets_at": "short"},
                "seven_day": {"utilization": 63, "resets_at": "week"},
            }
            with patch("ai_limits_widget.providers.claude.urllib.request.urlopen", return_value=_Response(payload)):
                result = client.read_limits()
        self.assertEqual(22, result["five_hour"]["usedPercent"])
        self.assertEqual(300, result["five_hour"]["windowDurationMins"])
        self.assertEqual(63, result["weekly"]["usedPercent"])
        self.assertFalse(result["stale"])

    def test_incomplete_response_returns_empty_windows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / ".credentials.json").write_text(json.dumps({"accessToken": "secret"}), encoding="utf-8")
            client = ClaudeClient(config_dir=directory, state_path=root / "state.json")
            with patch("ai_limits_widget.providers.claude.urllib.request.urlopen", return_value=_Response({})):
                result = client.read_limits()
        self.assertIsNone(result["five_hour"])
        self.assertIsNone(result["weekly"])

    def test_rate_limit_returns_cached_data_and_persists_backoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = pathlib.Path(directory) / "state.json"
            client = ClaudeClient(state_path=state)
            client.last_data = {"five_hour": {"usedPercent": 10}, "weekly": None, "fetchedAt": 100}
            result = client._rate_limited("60")
            persisted = json.loads(state.read_text(encoding="utf-8"))
        self.assertTrue(result["stale"])
        self.assertGreater(result["nextRetryAt"], 0)
        self.assertEqual(1, persisted["backoffIndex"])


class GeminiProviderTests(unittest.TestCase):
    def test_corrupt_cache_has_provider_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "quota.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(ProviderError) as caught:
                GeminiClient(path).read_limits()
        self.assertEqual("gemini", caught.exception.provider)
        self.assertIn("não pôde ser lida", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
