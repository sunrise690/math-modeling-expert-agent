from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from provider_config import ProviderConfigError, ProviderConfigStore


CODEX_STATUS = {
    "installed": True,
    "invokable": True,
    "available": True,
    "loggedIn": True,
    "authenticated": True,
    "sameAccount": True,
    "version": "test",
    "account": {"type": "chatgpt", "email": "te***@example.com", "planType": "test"},
    "reason": "",
    "executable": "",
    "transport": "app-server-sdk",
    "models": [
        {
            "id": "gpt-test",
            "displayName": "GPT Test",
            "isDefault": True,
            "defaultReasoningEffort": "medium",
            "supportedReasoningEfforts": ["low", "medium", "high"],
        }
    ],
}


class ProviderConfigTests(unittest.TestCase):
    def test_dpapi_secrets_are_independent_and_never_public(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "provider_config.codex_cli_status",
            return_value=CODEX_STATUS,
        ):
            store = ProviderConfigStore(Path(temp_dir))
            store.save(
                {
                    "provider": "openai-responses",
                    "model": "gpt-test",
                    "baseUrl": "https://api.openai.com/v1",
                    "apiKey": "openai-secret",
                }
            )
            public = store.save(
                {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "baseUrl": "https://api.deepseek.com",
                    "apiKey": "deepseek-secret",
                }
            )
            serialized = json.dumps(public, ensure_ascii=False)
            self.assertNotIn("openai-secret", serialized)
            self.assertNotIn("deepseek-secret", serialized)
            self.assertTrue(public["profiles"]["openai-responses"]["apiKeyConfigured"])
            self.assertTrue(public["profiles"]["deepseek"]["apiKeyConfigured"])
            self.assertNotIn(b"deepseek-secret", store._secret_path("deepseek").read_bytes())

            store.save({"provider": "openai-responses", "model": "gpt-test"})
            values = store.load_values()
            self.assertEqual(values["AGENT_API_KEY"], "openai-secret")
            store.save({"provider": "deepseek", "clearApiKey": True})
            self.assertEqual(store.load_values()["AGENT_API_KEY"], "")
            self.assertTrue(store._secret_path("openai-responses").is_file())

    def test_rejects_insecure_remote_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProviderConfigStore(Path(temp_dir))
            with self.assertRaises(ProviderConfigError):
                store.save(
                    {
                        "provider": "openai-compatible",
                        "model": "model",
                        "baseUrl": "http://example.com/v1",
                    }
                )
            with self.assertRaisesRegex(ProviderConfigError, "端口无效"):
                store.save(
                    {
                        "provider": "openai-compatible",
                        "model": "model",
                        "baseUrl": "https://example.com:99999/v1",
                    }
                )

    def test_binds_saved_secret_to_provider_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "provider_config.codex_cli_status",
            return_value=CODEX_STATUS,
        ):
            store = ProviderConfigStore(Path(temp_dir))
            store.save(
                {
                    "provider": "openai-compatible",
                    "model": "model-a",
                    "baseUrl": "https://one.example/v1",
                    "apiKey": "origin-bound-secret",
                }
            )
            with self.assertRaisesRegex(ProviderConfigError, "重新输入"):
                store.preview_values(
                    {
                        "provider": "openai-compatible",
                        "model": "model-b",
                        "baseUrl": "https://two.example/v1",
                    }
                )
            preview = store.preview_values(
                {
                    "provider": "openai-compatible",
                    "model": "model-a",
                    "baseUrl": "https://one.example/v1",
                    "clearApiKey": True,
                }
            )
            self.assertEqual(preview["AGENT_API_KEY"], "")

    def test_configuration_lock_makes_graphical_store_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text("AGENT_CONFIG_LOCK=1\n", encoding="utf-8")
            store = ProviderConfigStore(root)
            self.assertTrue(store.config_locked())
            with self.assertRaisesRegex(ProviderConfigError, "只读"):
                store.save({"provider": "codex-cli", "model": "gpt-test"})

    def test_fixed_providers_reject_non_official_origins(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProviderConfigStore(Path(temp_dir))
            with self.assertRaisesRegex(ProviderConfigError, "官方接口"):
                store.save(
                    {
                        "provider": "deepseek",
                        "model": "deepseek-chat",
                        "baseUrl": "https://evil.example/v1",
                    }
                )

    def test_public_codex_profile_contains_dynamic_model_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "provider_config.codex_cli_status",
            return_value=CODEX_STATUS,
        ):
            store = ProviderConfigStore(Path(temp_dir))
            public = store.save({"provider": "codex-cli", "model": "gpt-test"})
            self.assertEqual(public["codexLogin"]["transport"], "app-server-sdk")
            self.assertIsNone(public["codexLogin"]["sameDesktopAccount"])
            self.assertNotIn("executable", json.dumps(public, ensure_ascii=False))
            self.assertEqual(public["defaultModel"], "gpt-test")
            self.assertEqual(public["profiles"]["codex-cli"]["models"][0]["id"], "gpt-test")


if __name__ == "__main__":
    unittest.main()
