import io
import json
import pathlib
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from ai_limits_widget.providers import ProviderError, create_provider
from ai_limits_widget.providers.claude import ClaudeClient
from ai_limits_widget.providers.codex import CodexClient
from ai_limits_widget.providers.gemini import GeminiClient
from ai_limits_widget.providers.grok import GrokClient


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
        for provider in ("codex", "claude", "gemini", "grok"):
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
                GeminiClient(path, allow_live=False).read_limits()
        self.assertEqual("gemini", caught.exception.provider)
        self.assertIn("não pôde ser lida", caught.exception.detail)

    def test_live_quota_keeps_only_the_gemini_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token = pathlib.Path(directory) / "token.json"
            token.write_text(
                json.dumps({"token": {"access_token": "secret", "expiry": "2099-01-01T00:00:00+00:00"}}),
                encoding="utf-8",
            )
            client = GeminiClient(allow_live=True, token_path=token)
            loaded = {"cloudaicompanionProject": {"id": "project-1"}}
            summary = {
                "groups": [
                    {
                        "displayName": "Claude and GPT",
                        "buckets": [{"window": "weekly", "remainingFraction": 0.1}],
                    },
                    {
                        "displayName": "Gemini Models",
                        "buckets": [
                            {"window": "5h", "remainingFraction": 0.75, "resetTime": "soon"},
                            {"window": "weekly", "remainingFraction": 0.4, "resetTime": "later"},
                        ],
                    },
                ]
            }
            with patch(
                "ai_limits_widget.providers.gemini.urllib.request.urlopen",
                side_effect=[_Response(loaded), _Response(summary)],
            ) as opened:
                result = client.read_limits()
        self.assertEqual(25.0, result["five_hour"]["usedPercent"])
        self.assertEqual(300, result["five_hour"]["windowDurationMins"])
        self.assertEqual(60.0, result["weekly"]["usedPercent"])
        self.assertEqual("Gemini Models", result["weekly"]["modelName"])
        self.assertNotIn("project-1", json.dumps(result))
        self.assertEqual(2, opened.call_count)

    def test_live_failure_falls_back_to_statusline_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            token = root / "token.json"
            token.write_text(json.dumps({"access_token": "secret"}), encoding="utf-8")
            cache = root / "quota.json"
            cache.write_text(
                json.dumps(
                    {
                        "model": {"displayName": "Gemini"},
                        "quota": {"remainingFraction": 0.5, "resetTime": "week"},
                        "capturedAt": 10,
                    }
                ),
                encoding="utf-8",
            )
            client = GeminiClient(cache, allow_live=True, token_path=token)
            with patch(
                "ai_limits_widget.providers.gemini.urllib.request.urlopen",
                side_effect=urllib.error.URLError("rede"),
            ):
                result = client.read_limits()
        self.assertIsNone(result["five_hour"])
        self.assertEqual(50.0, result["weekly"]["usedPercent"])

    def test_missing_token_does_not_call_the_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            cache = root / "quota.json"
            cache.write_text(
                json.dumps(
                    {
                        "model": {"id": "gemini"},
                        "quota": {"remainingFraction": 1, "resetTime": "week"},
                        "capturedAt": 1,
                    }
                ),
                encoding="utf-8",
            )
            client = GeminiClient(cache, allow_live=True, token_path=root / "missing.json")
            with patch("ai_limits_widget.providers.gemini.urllib.request.urlopen") as opened:
                result = client.read_limits()
        opened.assert_not_called()
        self.assertEqual(0.0, result["weekly"]["usedPercent"])


class GrokProviderTests(unittest.TestCase):
    def test_fraction_and_percent_are_normalized_to_weekly_usage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth = pathlib.Path(directory) / "auth.json"
            auth.write_text(
                json.dumps({"auth.x.ai": {"key": "secret", "email": "ada@x.ai", "expires_at": "2099-01-01T00:00:00Z"}}),
                encoding="utf-8",
            )
            client = GrokClient(config_dir=directory)
            with patch(
                "ai_limits_widget.providers.grok.urllib.request.urlopen",
                return_value=_Response({"config": {"creditUsagePercent": 0.25, "currentPeriod": {"end": "week"}}}),
            ):
                fraction = client.read_limits()
            with patch(
                "ai_limits_widget.providers.grok.urllib.request.urlopen",
                return_value=_Response({"config": {"creditUsagePercent": 40, "billingPeriodEnd": "later"}}),
            ):
                percent = client.read_limits()
        self.assertIsNone(fraction["five_hour"])
        self.assertEqual(25.0, fraction["weekly"]["usedPercent"])
        self.assertEqual("week", fraction["weekly"]["resetsAt"])
        self.assertEqual(40.0, percent["weekly"]["usedPercent"])
        self.assertNotIn("secret", json.dumps(fraction))

    def test_auth_failure_uses_a_static_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth = pathlib.Path(directory) / "auth.json"
            auth.write_text(json.dumps({"key": "secret", "email": "ada@x.ai"}), encoding="utf-8")
            client = GrokClient(config_dir=directory)
            error = urllib.error.HTTPError(
                "https://cli-chat-proxy.grok.com/v1/billing?format=credits",
                401,
                "denied",
                hdrs=None,
                fp=io.BytesIO(b'{"token":"do-not-leak"}'),
            )
            with patch("ai_limits_widget.providers.grok.urllib.request.urlopen", side_effect=error):
                with self.assertRaises(ProviderError) as caught:
                    client.read_limits()
        self.assertEqual("grok", caught.exception.provider)
        self.assertIn("grok login", caught.exception.detail)
        self.assertNotIn("do-not-leak", caught.exception.detail)

    def test_expired_token_is_not_sent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth = pathlib.Path(directory) / "auth.json"
            auth.write_text(json.dumps({"key": "secret", "expires_at": 1}), encoding="utf-8")
            client = GrokClient(config_dir=directory)
            with patch("ai_limits_widget.providers.grok.urllib.request.urlopen") as opened:
                with self.assertRaises(ProviderError):
                    client.read_limits()
        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
