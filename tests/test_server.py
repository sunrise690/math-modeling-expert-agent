from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from agent_backend import RunManager, RunStore
from server import AgentHTTPServer, create_server, normalize_frontend_origin, normalize_frontend_url
from runtime_paths import agent_data_dir


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


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "index.html").write_text("<!doctype html><title>test</title>", encoding="utf-8")
        (self.root / ".env").write_text("AGENT_API_KEY=never-serve-this", encoding="utf-8")
        (self.root / "agent_backend.py").write_text("secret source", encoding="utf-8")
        (self.root / ".agent-data").mkdir()
        self.manager = RunManager(
            RunStore(self.root / ".agent-data/runs.db"),
            self.root,
            max_workers=1,
            max_queued_runs=1,
        )
        self.server = AgentHTTPServer(("127.0.0.1", 0), self.manager)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.manager.close()
        self.temp_dir.cleanup()

    def request(self, path: str, *, method: str = "GET", payload=None, headers=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
            return response.status, json.loads(body) if body and response.headers.get_content_type() == "application/json" else body

    def test_static_router_does_not_expose_project_files(self) -> None:
        for path in ("/.env", "/agent_backend.py", "/.agent-data/knowledge.db"):
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as raised:
                self.request(path)
            self.assertEqual(raised.exception.code, 404)
            raised.exception.close()
        status, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"<title>test</title>", body)

    def test_rejects_foreign_origin_and_accepts_same_origin(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/runtime", headers={"Origin": "https://evil.example"})
        self.assertEqual(raised.exception.code, 403)
        raised.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as rebound:
            self.request(
                "/api/runtime",
                headers={"Host": "evil.example", "Origin": "http://evil.example"},
            )
        self.assertEqual(rebound.exception.code, 403)
        rebound.exception.close()
        status, payload = self.request("/api/runtime", headers={"Origin": self.base_url})
        self.assertEqual(status, 200)
        self.assertIn("activeCount", payload)

    def test_configured_workbench_origin_can_reach_loopback_runtime(self) -> None:
        self.server.frontend_origins.add("https://workbench.example")
        status, payload = self.request("/api/health", headers={"Origin": "https://workbench.example"})
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        request = urllib.request.Request(
            f"{self.base_url}/api/health",
            headers={
                "Origin": "https://workbench.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Private-Network": "true",
            },
            method="OPTIONS",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://workbench.example")
            self.assertEqual(response.headers.get("Access-Control-Allow-Private-Network"), "true")

    def test_official_online_workbench_can_reach_loopback_runtime(self) -> None:
        status, payload = self.request("/api/health", headers={"Origin": "https://qilintex.top"})
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

    def test_graphical_provider_config_saves_encrypted_secret_and_tests_codex(self) -> None:
        with patch("provider_config.codex_cli_status", return_value=CODEX_STATUS), patch(
            "agent_backend.codex_cli_status",
            return_value=CODEX_STATUS,
        ), patch("server.codex_cli_status", return_value=CODEX_STATUS):
            status, payload = self.request(
                "/api/config",
                method="POST",
                payload={
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "baseUrl": "https://api.deepseek.com",
                    "apiKey": "deepseek-secret",
                },
            )
            self.assertEqual(status, 200)
            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("deepseek-secret", serialized)
            self.assertTrue(payload["config"]["apiKeyConfigured"])
            self.assertTrue((self.root / ".agent-data/provider-secrets/deepseek.bin").is_file())

            _, current = self.request("/api/config")
            self.assertEqual(current["activeProvider"], "deepseek")
            self.assertEqual(current["codexLogin"]["transport"], "app-server-sdk")

            _, tested = self.request(
                "/api/config/test",
                method="POST",
                payload={"provider": "codex-cli", "model": "gpt-test"},
            )
            self.assertTrue(tested["test"]["ok"])
            self.assertEqual(tested["test"]["defaultModel"], "gpt-test")

    def test_codex_browser_login_routes_only_return_public_session_state(self) -> None:
        session_id = "d" * 32

        class LoginStub:
            callback = ""

            def start(self):
                return {"id": session_id, "mode": "device-code", "status": "pending", "verificationUrl": "https://auth.example/device", "userCode": "ABCD"}

            def status(self, requested_id):
                self.requested_id = requested_id
                return {"id": requested_id, "mode": "device-code", "status": "pending"}

            def relay_callback(self, requested_id, callback_url):
                self.callback = callback_url
                return {"id": requested_id, "mode": "browser-callback", "status": "pending"}

            def cancel(self, requested_id):
                self.cancelled = requested_id

            def close(self):
                pass

        stub = LoginStub()
        self.server.codex_login = stub
        status, started = self.request("/api/codex-login", method="POST", payload={})
        self.assertEqual(status, 202)
        self.assertEqual(started["login"]["userCode"], "ABCD")
        _, current = self.request(f"/api/codex-login/{session_id}")
        self.assertEqual(current["login"]["id"], session_id)
        callback = "http://localhost:1455/auth/callback?code=x&state=y"
        self.request("/api/codex-login/callback", method="POST", payload={"id": session_id, "callbackUrl": callback})
        self.assertEqual(stub.callback, callback)
        self.request(f"/api/codex-login/{session_id}", method="DELETE")
        self.assertEqual(stub.cancelled, session_id)

    def test_create_server_refuses_non_loopback_binding(self) -> None:
        with self.assertRaises(ValueError):
            create_server("0.0.0.0", 0, self.root / "rejected.db")

    def test_unified_frontend_url_is_normalized_and_validated(self) -> None:
        self.assertEqual(normalize_frontend_url("http://localhost:5173"), "http://localhost:5173/")
        self.assertEqual(normalize_frontend_url("https://modeling.example/app/"), "https://modeling.example/app/")
        for value in ("localhost:5173", "file:///tmp/app", "https://user:secret@example.com"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_frontend_url(value)

        self.assertEqual(normalize_frontend_origin("https://QILINTEX.top/"), "https://qilintex.top")
        for value in ("qilintex.top", "file:///tmp/app", "https://qilintex.top/path", "https://user:secret@qilintex.top"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_frontend_origin(value)

    def test_agent_data_directory_supports_repository_relative_configuration(self) -> None:
        with patch.dict(os.environ, {"AGENT_DATA_DIR": "runtime/agent"}):
            self.assertEqual(agent_data_dir(self.root), (self.root / "runtime/agent").resolve())


if __name__ == "__main__":
    unittest.main()
