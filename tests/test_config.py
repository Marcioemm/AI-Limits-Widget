import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from ai_limits_widget import config as config_module
from ai_limits_widget import profiles as profiles_module


class ConfigLoadTests(unittest.TestCase):
    def test_missing_file_uses_independent_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "missing.json"
            first = config_module.load_config(path)
            second = config_module.load_config(path)

        first["providers"].append("gemini")
        self.assertEqual(["codex", "claude"], second["providers"])
        self.assertFalse(second["startWithWindows"])
        self.assertEqual(1, second["compactVisibleCount"])

    def test_corrupt_file_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.json"
            path.write_text('{"layout":', encoding="utf-8")
            loaded = config_module.load_config(path)

        self.assertEqual("cards", loaded["layout"])
        self.assertEqual(["codex", "claude"], loaded["providers"])

    def test_legacy_config_is_migrated_and_clamped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "providers": ["codex", "invalid", "gemini"],
                        "refreshMinutes": 500,
                        "executables": {"codex": "codex.exe"},
                        "startWithWindows": True,
                        "compactPrimaryProfileId": " claude-default ",
                        "compactVisibleCount": 9,
                    }
                ),
                encoding="utf-8",
            )
            loaded = config_module.load_config(path)

        self.assertEqual(["codex", "gemini"], loaded["providers"])
        self.assertEqual(120, loaded["refreshMinutes"])
        self.assertEqual("codex.exe", loaded["executables"]["codex"])
        self.assertTrue(loaded["startWithWindows"])
        self.assertEqual("claude-default", loaded["compactPrimaryProfileId"])
        self.assertEqual(3, loaded["compactVisibleCount"])

    def test_profiles_are_normalized_and_invalid_entries_are_removed(self) -> None:
        loaded = config_module.normalize_config(
            {
                "profiles": [
                    {"provider": "codex", "label": "  Trabalho  "},
                    {"provider": "invalid", "label": "Ignorar"},
                    "inválido",
                ]
            }
        )

        self.assertEqual(1, len(loaded["profiles"]))
        self.assertEqual("codex-1", loaded["profiles"][0]["id"])
        self.assertEqual("Trabalho", loaded["profiles"][0]["label"])

    def test_legacy_provider_list_still_creates_default_profiles(self) -> None:
        legacy = config_module.normalize_config({"providers": ["codex"], "executables": {"codex": "codex.exe"}})
        with patch.object(profiles_module, "load_config", return_value=legacy):
            profiles = profiles_module.load_profiles()

        self.assertEqual(
            [
                {
                    "id": "codex-default",
                    "provider": "codex",
                    "label": "Padrão",
                    "executable": "codex.exe",
                    "configDir": None,
                }
            ],
            profiles,
        )

    def test_saved_profiles_are_merged_with_discovered_claude_accounts(self) -> None:
        configured = config_module.normalize_config(
            {
                "providers": ["codex", "claude"],
                "executables": {"claude": "claude.exe"},
                "profiles": [
                    {"id": "codex-default", "provider": "codex", "label": "Padrão"},
                    {"id": "claude-default", "provider": "claude", "label": "UF"},
                ],
            }
        )
        discovered = [
            {
                "id": "claude-default",
                "provider": "claude",
                "label": "Padrão",
                "executable": "claude.exe",
                "configDir": None,
            },
            {
                "id": "claude-lazaro",
                "provider": "claude",
                "label": "lazaro",
                "executable": "claude.exe",
                "configDir": str(pathlib.Path.home() / ".claude-lazaro"),
            },
        ]

        with (
            patch.object(profiles_module, "load_config", return_value=configured),
            patch.object(profiles_module, "discover_claude_profiles", return_value=discovered),
        ):
            profiles = profiles_module.load_profiles()

        self.assertEqual(["codex-default", "claude-default", "claude-lazaro"], [item["id"] for item in profiles])
        self.assertEqual("UF", profiles[1]["label"])

    def test_manual_claude_directory_is_not_duplicated_by_discovery(self) -> None:
        extra_directory = str(pathlib.Path.home() / ".claude-lazaro")
        configured = config_module.normalize_config(
            {
                "providers": ["claude"],
                "profiles": [
                    {"id": "claude-default", "provider": "claude", "label": "UF"},
                    {
                        "id": "claude-personal",
                        "provider": "claude",
                        "label": "Pessoal",
                        "configDir": extra_directory,
                    },
                ],
            }
        )
        discovered = [
            {
                "id": "claude-lazaro",
                "provider": "claude",
                "label": "lazaro",
                "executable": None,
                "configDir": extra_directory,
            }
        ]

        with (
            patch.object(profiles_module, "load_config", return_value=configured),
            patch.object(profiles_module, "discover_claude_profiles", return_value=discovered),
        ):
            profiles = profiles_module.load_profiles()

        self.assertEqual(["claude-default", "claude-personal"], [item["id"] for item in profiles])


class ConfigSaveTests(unittest.TestCase):
    def test_save_is_atomic_and_round_trips_normalized_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.json"
            saved = config_module.save_config(
                {"providers": ["gemini"], "layout": "compact", "compactVisibleCount": 2},
                path,
            )
            loaded = config_module.load_config(path)
            temporary_files = list(path.parent.glob(f".{path.name}.*.tmp"))

        self.assertEqual(saved, loaded)
        self.assertEqual("compact", loaded["layout"])
        self.assertEqual([], temporary_files)

    def test_failed_replace_preserves_previous_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.json"
            original = '{"layout": "cards"}\n'
            path.write_text(original, encoding="utf-8")

            with patch.object(config_module.os, "replace", side_effect=OSError("bloqueado")):
                with self.assertRaises(OSError):
                    config_module.save_config({"layout": "compact"}, path)

            self.assertEqual(original, path.read_text(encoding="utf-8"))
            self.assertEqual([], list(path.parent.glob(f".{path.name}.*.tmp")))


if __name__ == "__main__":
    unittest.main()
