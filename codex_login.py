from __future__ import annotations

import os
import threading
import time
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse


class CodexLoginError(RuntimeError):
    pass


@dataclass
class _LoginSession:
    id: str
    mode: str
    status: str
    created_at: float
    expires_at: float
    auth_url: str = ""
    verification_url: str = ""
    user_code: str = ""
    message: str = ""
    codex: Any = None
    handle: Any = None


class CodexLoginManager:
    """Own one live Codex login attempt without exposing stored credentials."""

    def __init__(
        self,
        *,
        codex_factory: Callable[[], Any] | None = None,
        callback_opener: Callable[[urllib.request.Request, float], Any] | None = None,
        ttl_seconds: float = 10 * 60,
        login_flow: str | None = None,
    ) -> None:
        self._codex_factory = codex_factory
        self._callback_opener = callback_opener or self._open_callback
        self._ttl_seconds = ttl_seconds
        self._login_flow = (login_flow or os.environ.get("CODEX_LOGIN_FLOW", "browser")).strip().casefold()
        if self._login_flow not in {"browser", "device", "auto"}:
            raise ValueError("CODEX_LOGIN_FLOW 必须是 browser、device 或 auto")
        self._lock = threading.RLock()
        self._session: _LoginSession | None = None

    def start(self) -> dict[str, Any]:
        with self._lock:
            self._expire_locked()
            if self._session and self._session.status == "pending":
                return self._public(self._session)

            codex = self._new_codex()
            try:
                codex.__enter__()
                if self._login_flow == "browser":
                    handle = codex.login_chatgpt()
                    mode = "browser-callback"
                    auth_url = str(handle.auth_url)
                    verification_url = ""
                    user_code = ""
                    message = "请在浏览器确认登录；完成后本机会自动接收回调，无需复制地址。"
                else:
                    try:
                        handle = codex.login_chatgpt_device_code()
                        mode = "device-code"
                        auth_url = ""
                        verification_url = str(handle.verification_url)
                        user_code = str(handle.user_code)
                        message = "请在浏览器登录 ChatGPT，然后输入一次性验证码。"
                    except Exception:
                        if self._login_flow == "device":
                            raise
                        handle = codex.login_chatgpt()
                        mode = "browser-callback"
                        auth_url = str(handle.auth_url)
                        verification_url = ""
                        user_code = ""
                        message = "请在浏览器确认登录；完成后本机会自动接收回调，无需复制地址。"
            except Exception as error:
                self._close_codex(codex)
                raise CodexLoginError(self._safe_error(error)) from error

            now = time.time()
            session = _LoginSession(
                id=uuid.uuid4().hex,
                mode=mode,
                status="pending",
                created_at=now,
                expires_at=now + self._ttl_seconds,
                auth_url=auth_url,
                verification_url=verification_url,
                user_code=user_code,
                message=message,
                codex=codex,
                handle=handle,
            )
            self._session = session
            threading.Thread(target=self._wait, args=(session,), daemon=True, name="codex-login-wait").start()
            expiry_timer = threading.Timer(self._ttl_seconds, self._expire_session, args=(session.id,))
            expiry_timer.daemon = True
            expiry_timer.start()
            return self._public(session)

    def status(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            self._expire_locked()
            if not self._session or self._session.id != session_id:
                raise CodexLoginError("登录会话不存在或已过期，请重新点击登录。")
            return self._public(self._session)

    def relay_callback(self, session_id: str, callback_url: str) -> dict[str, Any]:
        with self._lock:
            self._expire_locked()
            session = self._session
            if not session or session.id != session_id or session.status != "pending":
                raise CodexLoginError("登录会话不存在、已完成或已过期。")
            if session.mode != "browser-callback":
                raise CodexLoginError("当前登录方式不需要粘贴回调地址。")
            safe_url = self._validated_callback_url(callback_url)

        request = urllib.request.Request(safe_url, headers={"Accept": "text/html"}, method="GET")
        try:
            response = self._callback_opener(request, 12.0)
            try:
                response.read(64 * 1024)
            finally:
                response.close()
        except Exception as error:
            raise CodexLoginError(f"无法把登录结果交给服务器：{self._safe_error(error)}") from error
        return self.status(session_id)

    def cancel(self, session_id: str) -> None:
        with self._lock:
            session = self._session
            if not session or session.id != session_id:
                return
            self._cancel_locked(session, "cancelled", "登录已取消。")

    def close(self) -> None:
        with self._lock:
            if self._session and self._session.status == "pending":
                self._cancel_locked(self._session, "cancelled", "服务已停止。")

    def _wait(self, session: _LoginSession) -> None:
        try:
            notification = session.handle.wait()
            success = bool(getattr(notification, "success", False))
            error = str(getattr(notification, "error", "") or "").strip()
            with self._lock:
                if self._session is not session or session.status != "pending":
                    return
                session.status = "completed" if success else "failed"
                session.message = "Codex 账号登录成功。" if success else (error or "Codex 登录未完成。")
        except Exception as error:
            with self._lock:
                if self._session is session and session.status == "pending":
                    session.status = "failed"
                    session.message = self._safe_error(error)
        finally:
            self._close_codex(session.codex)
            session.codex = None
            session.handle = None

    def _expire_session(self, session_id: str) -> None:
        with self._lock:
            if self._session and self._session.id == session_id and self._session.status == "pending":
                self._cancel_locked(self._session, "expired", "登录会话已过期，请重新开始。")

    def _expire_locked(self) -> None:
        if self._session and self._session.status == "pending" and time.time() >= self._session.expires_at:
            self._cancel_locked(self._session, "expired", "登录会话已过期，请重新开始。")

    def _cancel_locked(self, session: _LoginSession, status: str, message: str) -> None:
        session.status = status
        session.message = message
        try:
            session.handle.cancel()
        except Exception:
            pass
        self._close_codex(session.codex)
        session.codex = None
        session.handle = None

    def _new_codex(self) -> Any:
        if self._codex_factory:
            return self._codex_factory()
        try:
            from openai_codex import Codex
        except ImportError as error:
            raise CodexLoginError("服务器未安装 Codex Runtime。") from error
        return Codex()

    @staticmethod
    def _validated_callback_url(value: str) -> str:
        if len(value) > 8_000:
            raise CodexLoginError("回调地址过长。")
        try:
            parsed = urlparse(value.strip())
            port = parsed.port
        except ValueError as error:
            raise CodexLoginError("回调地址无效。") from error
        query = parse_qs(parsed.query)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1"}
            or port != 1455
            or parsed.path != "/auth/callback"
            or parsed.username
            or parsed.password
            or parsed.fragment
            or not query.get("code")
            or not query.get("state")
        ):
            raise CodexLoginError("请粘贴浏览器地址栏中完整的 localhost:1455/auth/callback 地址。")
        return value.strip()

    @staticmethod
    def _open_callback(request: urllib.request.Request, timeout: float) -> Any:
        return urllib.request.urlopen(request, timeout=timeout)

    @staticmethod
    def _close_codex(codex: Any) -> None:
        if codex is None:
            return
        try:
            codex.close()
        except Exception:
            pass

    @staticmethod
    def _safe_error(error: Exception) -> str:
        compact = " ".join(str(error).split()).strip()[:300]
        return compact or type(error).__name__

    @staticmethod
    def _public(session: _LoginSession) -> dict[str, Any]:
        return {
            "id": session.id,
            "mode": session.mode,
            "status": session.status,
            "authUrl": session.auth_url,
            "verificationUrl": session.verification_url,
            "userCode": session.user_code,
            "message": session.message,
            "expiresAt": datetime.fromtimestamp(session.expires_at, UTC).isoformat(),
        }
