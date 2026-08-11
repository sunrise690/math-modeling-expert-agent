from __future__ import annotations

import threading
import unittest

from codex_login import CodexLoginError, CodexLoginManager


class _Notification:
    success = True
    error = None


class _Handle:
    login_id = "runtime-login"
    verification_url = "https://auth.openai.com/codex/device"
    user_code = "ABCD-EFGH"
    auth_url = "https://auth.openai.com/oauth/authorize"

    def __init__(self) -> None:
        self.ready = threading.Event()

    def wait(self):
        self.ready.wait(2)
        return _Notification()

    def cancel(self):
        self.ready.set()


class _Codex:
    def __init__(self, *, device_error: bool = False) -> None:
        self.handle = _Handle()
        self.device_error = device_error
        self.closed = False

    def __enter__(self):
        return self

    def login_chatgpt_device_code(self):
        if self.device_error:
            raise RuntimeError("403 Forbidden")
        return self.handle

    def login_chatgpt(self):
        return self.handle

    def close(self):
        self.closed = True


class _Response:
    def read(self, _size):
        return b"ok"

    def close(self):
        pass


class CodexLoginTests(unittest.TestCase):
    def test_device_code_login_returns_browser_url_and_code(self) -> None:
        runtime = _Codex()
        manager = CodexLoginManager(codex_factory=lambda: runtime, ttl_seconds=30, login_flow="device")
        login = manager.start()
        self.assertEqual(login["mode"], "device-code")
        self.assertEqual(login["userCode"], "ABCD-EFGH")
        self.assertTrue(login["verificationUrl"].startswith("https://"))
        runtime.handle.ready.set()
        runtime.handle.ready.wait(1)

    def test_browser_login_fallback_relays_only_exact_local_callback(self) -> None:
        runtime = _Codex(device_error=True)
        opened: list[str] = []

        def opener(request, _timeout):
            opened.append(request.full_url)
            runtime.handle.ready.set()
            return _Response()

        manager = CodexLoginManager(codex_factory=lambda: runtime, callback_opener=opener, ttl_seconds=30, login_flow="auto")
        login = manager.start()
        self.assertEqual(login["mode"], "browser-callback")
        with self.assertRaises(CodexLoginError):
            manager.relay_callback(login["id"], "https://evil.example/auth/callback?code=a&state=b")
        callback = "http://localhost:1455/auth/callback?code=abc&state=xyz"
        manager.relay_callback(login["id"], callback)
        self.assertEqual(opened, [callback])

    def test_browser_login_is_default_and_uses_local_callback_automatically(self) -> None:
        runtime = _Codex()
        manager = CodexLoginManager(codex_factory=lambda: runtime, ttl_seconds=30)
        login = manager.start()
        self.assertEqual(login["mode"], "browser-callback")
        self.assertEqual(login["authUrl"], runtime.handle.auth_url)
        self.assertIn("自动接收回调", login["message"])
        runtime.handle.ready.set()


if __name__ == "__main__":
    unittest.main()
