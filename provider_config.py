from __future__ import annotations

import ctypes
import ipaddress
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class ProviderConfigError(RuntimeError):
    pass


PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "codex-cli": {
        "label": "Codex Runtime 当前登录账号",
        "description": "调用本机官方 Codex Runtime，并使用当前 CODEX_HOME 中已探测到的 ChatGPT 登录会话。",
        "defaultModel": "gpt-5.6-sol",
        "defaultBaseUrl": "",
        "requiresApiKey": False,
        "accountMode": "codex-login",
    },
    "openai-responses": {
        "label": "OpenAI API",
        "description": "使用独立 OpenAI API Key 与 Responses API。",
        "defaultModel": "gpt-5.6-sol",
        "defaultBaseUrl": "https://api.openai.com/v1",
        "requiresApiKey": True,
        "accountMode": "api-key",
    },
    "deepseek": {
        "label": "DeepSeek API",
        "description": "使用独立 DeepSeek API Key，通过兼容 Chat Completions 接口调用。",
        "defaultModel": "deepseek-chat",
        "defaultBaseUrl": "https://api.deepseek.com",
        "requiresApiKey": True,
        "accountMode": "api-key",
    },
    "openai-compatible": {
        "label": "OpenAI 兼容接口",
        "description": "连接自定义 OpenAI Chat Completions 兼容服务。",
        "defaultModel": "",
        "defaultBaseUrl": "",
        "requiresApiKey": True,
        "accountMode": "api-key",
    },
    "ollama": {
        "label": "Ollama 本地模型",
        "description": "连接本机 Ollama；默认无需 API Key。",
        "defaultModel": "",
        "defaultBaseUrl": "http://127.0.0.1:11434/v1",
        "requiresApiKey": False,
        "accountMode": "local",
    },
}

DEFAULT_PROFILE: dict[str, Any] = {
    "timeout": 180.0,
    "toolsEnabled": True,
    "qualityEnabled": True,
    "qualityThreshold": 82,
    "maxRevisions": 1,
    "maxConcurrentRuns": 2,
    "maxQueuedRuns": 20,
    "reasoningEffort": "medium",
    "textVerbosity": "medium",
    "responseStore": False,
}

_CODEX_STATUS_LOCK = threading.Lock()
_CODEX_STATUS_CACHE: tuple[float, str, dict[str, Any]] | None = None


def _is_loopback_hostname(hostname: str) -> bool:
    try:
        return hostname.casefold() == "localhost" or ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _canonical_origin(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    default_port = 443 if parsed.scheme.casefold() == "https" else 80
    try:
        port = parsed.port or default_port
    except ValueError as error:
        raise ProviderConfigError("基础 URL 的端口无效") from error
    suffix = "" if port == default_port else f":{port}"
    return f"{parsed.scheme.casefold()}://{host}{suffix}"


def public_codex_status(status: dict[str, Any]) -> dict[str, Any]:
    """Return the account status without executable paths or raw CLI output."""
    account = status.get("account") if isinstance(status.get("account"), dict) else {}
    return {
        "installed": bool(status.get("installed")),
        "invokable": bool(status.get("invokable")),
        "available": bool(status.get("available")),
        "loggedIn": bool(status.get("loggedIn")),
        "authenticated": bool(status.get("authenticated")),
        "runtimeAccountDetected": bool(status.get("authenticated")),
        "authMode": str(account.get("type", "")),
        "sameDesktopAccount": None,
        "sameCodexHomeSession": bool(status.get("authenticated")) and str(account.get("type", "")) == "chatgpt",
        "version": str(status.get("version", ""))[:120],
        "account": {
            "type": str(account.get("type", "")),
            "email": str(account.get("email", "")),
            "planType": str(account.get("planType", "")),
        },
        "reason": str(status.get("reason", ""))[:300],
        "transport": str(status.get("transport", "")),
        "models": status.get("models", []) if isinstance(status.get("models"), list) else [],
    }


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi_protect(content: bytes) -> bytes:
    if os.name != "nt":
        raise ProviderConfigError("当前系统不支持 Windows DPAPI，无法安全保存 API Key")
    buffer = ctypes.create_string_buffer(content)
    source = _DataBlob(len(content), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = _DataBlob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        "Math Modeling Agent API key",
        None,
        None,
        None,
        0x1,
        ctypes.byref(output),
    ):
        raise ProviderConfigError(f"Windows DPAPI 加密失败：{ctypes.get_last_error()}")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)


def _dpapi_unprotect(content: bytes) -> bytes:
    if os.name != "nt":
        raise ProviderConfigError("当前系统不支持 Windows DPAPI，无法读取 API Key")
    buffer = ctypes.create_string_buffer(content)
    source = _DataBlob(len(content), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = _DataBlob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(output),
    ):
        raise ProviderConfigError(f"Windows DPAPI 解密失败：{ctypes.get_last_error()}")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)


class ProviderConfigStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.data_root = self.root / ".agent-data"
        self.path = self.data_root / "provider-settings.json"
        self.secret_root = self.data_root / "provider-secrets"
        self._lock = threading.RLock()

    def load_values(self) -> dict[str, str]:
        with self._lock:
            record = self._read_record()
            if not record:
                return {}
            provider = self._normalize_provider(record.get("activeProvider"))
            profile = self._profile(record, provider)
            api_key = self._read_secret(provider)
        return {
            "AGENT_PROVIDER": provider,
            "AGENT_BASE_URL": str(profile.get("baseUrl", "")),
            "AGENT_API_KEY": api_key,
            "AGENT_MODEL": str(profile.get("model", "")),
            "AGENT_TIMEOUT": str(profile.get("timeout", 180)),
            "AGENT_TOOLS": self._env_bool(profile.get("toolsEnabled", True)),
            "AGENT_QUALITY": self._env_bool(profile.get("qualityEnabled", True)),
            "AGENT_QUALITY_THRESHOLD": str(profile.get("qualityThreshold", 82)),
            "AGENT_MAX_REVISIONS": str(profile.get("maxRevisions", 1)),
            "AGENT_MAX_CONCURRENT_RUNS": str(profile.get("maxConcurrentRuns", 2)),
            "AGENT_MAX_QUEUED_RUNS": str(profile.get("maxQueuedRuns", 20)),
            "AGENT_REASONING_EFFORT": str(profile.get("reasoningEffort", "medium")),
            "AGENT_TEXT_VERBOSITY": str(profile.get("textVerbosity", "medium")),
            "AGENT_RESPONSE_STORE": self._env_bool(profile.get("responseStore", False)),
        }

    def config_locked(self) -> bool:
        value = os.environ.get("AGENT_CONFIG_LOCK")
        if value is None:
            env_path = self.root / ".env"
            if env_path.is_file():
                for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, raw_value = line.split("=", 1)
                    if key.strip() == "AGENT_CONFIG_LOCK":
                        value = raw_value.strip().strip("\"'")
                        break
        return str(value or "0").strip().lower() in {"1", "true", "yes", "on"}

    def public_config(self, effective: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            record = self._read_record()
            fallback_provider = (effective or {}).get("provider", "codex-cli")
            active = self._normalize_provider(record.get("activeProvider") if record else fallback_provider)
            profiles: dict[str, dict[str, Any]] = {}
            for provider in PROVIDER_CATALOG:
                profile = self._profile(record, provider)
                profiles[provider] = {
                    **profile,
                    "apiKeyConfigured": self._secret_path(provider).is_file(),
                }
        status = codex_cli_status()
        public_status = public_codex_status(status)
        profiles["codex-cli"]["models"] = status.get("models", [])
        profiles["codex-cli"]["defaultModel"] = next(
            (item.get("id", "") for item in status.get("models", []) if item.get("isDefault")),
            PROVIDER_CATALOG["codex-cli"]["defaultModel"],
        )
        payload = dict(effective or {})
        payload.update(
            {
                "provider": payload.get("provider", active),
                "activeProvider": active,
                "apiKeyConfigured": self._secret_path(active).is_file(),
                "apiKeyStored": self._secret_path(active).is_file(),
                "credentialStorage": "windows-dpapi" if os.name == "nt" else "unavailable",
                "configLocked": self.config_locked(),
                "effectiveConfigSource": "environment" if self.config_locked() else "graphical",
                "profiles": profiles,
                "providerCatalog": [
                    {"id": provider, **details, "profile": profiles[provider]}
                    for provider, details in PROVIDER_CATALOG.items()
                ],
                "codexStatus": public_status,
                "codexLogin": public_status,
                "models": profiles[active].get("models", []),
                "defaultModel": profiles[active].get("defaultModel", profiles[active].get("model", "")),
            }
        )
        return payload

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ProviderConfigError("配置必须是 JSON 对象")
        if self.config_locked():
            raise ProviderConfigError("模型配置已由 AGENT_CONFIG_LOCK 锁定，图形界面为只读")
        provider = self._normalize_provider(payload.get("provider") or payload.get("activeProvider"))
        with self._lock:
            record = self._read_record() or {"version": 1, "activeProvider": provider, "profiles": {}}
            old_profile = self._profile(record, provider)
            profile = self._apply_payload(old_profile, provider, payload)
            profiles = record.get("profiles") if isinstance(record.get("profiles"), dict) else {}
            profiles[provider] = profile
            secret_origins = record.get("secretOrigins") if isinstance(record.get("secretOrigins"), dict) else {}
            api_key = payload.get("apiKey")
            if bool(payload.get("clearApiKey", False)):
                self._secret_path(provider).unlink(missing_ok=True)
                secret_origins.pop(provider, None)
            elif api_key is not None and str(api_key).strip():
                self._write_secret(provider, str(api_key).strip())
                secret_origins[provider] = self._credential_origin(provider, profile)
            elif self._secret_path(provider).is_file():
                old_origin = str(secret_origins.get(provider) or self._credential_origin(provider, old_profile))
                new_origin = self._credential_origin(provider, profile)
                if old_origin != new_origin:
                    raise ProviderConfigError("基础 URL 的主机已改变；为防止旧 API Key 发往新主机，请重新输入密钥")
                secret_origins[provider] = old_origin
            record = {"version": 2, "activeProvider": provider, "profiles": profiles, "secretOrigins": secret_origins}
            self._write_json_atomic(record)
        return self.public_config()

    def preview_values(self, payload: dict[str, Any]) -> dict[str, str]:
        if self.config_locked():
            raise ProviderConfigError("模型配置已由 AGENT_CONFIG_LOCK 锁定；测试只允许使用当前环境配置")
        provider = self._normalize_provider(payload.get("provider") or payload.get("activeProvider"))
        with self._lock:
            record = self._read_record() or {"version": 1, "activeProvider": provider, "profiles": {}}
            old_profile = self._profile(record, provider)
            profile = self._apply_payload(old_profile, provider, payload)
            provided_key = str(payload.get("apiKey", "")).strip()
            if bool(payload.get("clearApiKey", False)):
                api_key = ""
            elif provided_key:
                api_key = provided_key
            else:
                secret_origins = record.get("secretOrigins") if isinstance(record.get("secretOrigins"), dict) else {}
                old_origin = str(secret_origins.get(provider) or self._credential_origin(provider, old_profile))
                new_origin = self._credential_origin(provider, profile)
                if self._secret_path(provider).is_file() and old_origin != new_origin:
                    raise ProviderConfigError("基础 URL 的主机已改变；测试新主机时必须重新输入 API Key")
                api_key = self._read_secret(provider)
        values = {
            "AGENT_PROVIDER": provider,
            "AGENT_BASE_URL": str(profile.get("baseUrl", "")),
            "AGENT_API_KEY": api_key,
            "AGENT_MODEL": str(profile.get("model", "")),
            "AGENT_TIMEOUT": str(profile.get("timeout", 180)),
            "AGENT_TOOLS": self._env_bool(profile.get("toolsEnabled", True)),
            "AGENT_QUALITY": self._env_bool(profile.get("qualityEnabled", True)),
            "AGENT_QUALITY_THRESHOLD": str(profile.get("qualityThreshold", 82)),
            "AGENT_MAX_REVISIONS": str(profile.get("maxRevisions", 1)),
            "AGENT_MAX_CONCURRENT_RUNS": str(profile.get("maxConcurrentRuns", 2)),
            "AGENT_MAX_QUEUED_RUNS": str(profile.get("maxQueuedRuns", 20)),
            "AGENT_REASONING_EFFORT": str(profile.get("reasoningEffort", "medium")),
            "AGENT_TEXT_VERBOSITY": str(profile.get("textVerbosity", "medium")),
            "AGENT_RESPONSE_STORE": self._env_bool(profile.get("responseStore", False)),
        }
        return values

    def _read_record(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProviderConfigError("模型配置文件损坏") from error
        if not isinstance(data, dict):
            raise ProviderConfigError("模型配置文件格式无效")
        return data

    def _profile(self, record: dict[str, Any], provider: str) -> dict[str, Any]:
        details = PROVIDER_CATALOG[provider]
        result = {
            **DEFAULT_PROFILE,
            "baseUrl": details["defaultBaseUrl"],
            "model": details["defaultModel"],
        }
        profiles = record.get("profiles") if isinstance(record, dict) else {}
        saved = profiles.get(provider) if isinstance(profiles, dict) else {}
        if isinstance(saved, dict):
            result.update({key: value for key, value in saved.items() if key in result})
        return result

    def _apply_payload(self, profile: dict[str, Any], provider: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(profile)
        mappings = {
            "baseUrl": "baseUrl",
            "model": "model",
            "timeout": "timeout",
            "toolsEnabled": "toolsEnabled",
            "qualityEnabled": "qualityEnabled",
            "qualityThreshold": "qualityThreshold",
            "maxRevisions": "maxRevisions",
            "maxConcurrentRuns": "maxConcurrentRuns",
            "maxQueuedRuns": "maxQueuedRuns",
            "reasoningEffort": "reasoningEffort",
            "textVerbosity": "textVerbosity",
            "responseStore": "responseStore",
        }
        for source, target in mappings.items():
            if source in payload:
                result[target] = payload[source]
        result["baseUrl"] = str(result.get("baseUrl", "")).strip().rstrip("/")
        result["model"] = str(result.get("model", "")).strip()
        if provider == "codex-cli":
            result["baseUrl"] = ""
            result["model"] = result["model"] or PROVIDER_CATALOG[provider]["defaultModel"]
            result["responseStore"] = False
            result["textVerbosity"] = "medium"
        elif provider == "ollama":
            result["baseUrl"] = result["baseUrl"] or PROVIDER_CATALOG[provider]["defaultBaseUrl"]
        elif not result["baseUrl"]:
            default_url = str(PROVIDER_CATALOG[provider]["defaultBaseUrl"])
            if default_url:
                result["baseUrl"] = default_url
            else:
                raise ProviderConfigError("该提供商必须填写基础 URL")
        if provider != "codex-cli":
            self._validate_base_url(result["baseUrl"])
            self._validate_provider_origin(provider, result["baseUrl"])
        if not result["model"] and provider != "ollama":
            raise ProviderConfigError("模型名称不能为空")

        result["timeout"] = self._clamp_float(result.get("timeout"), 10.0, 600.0, 180.0)
        result["toolsEnabled"] = self._bool(result.get("toolsEnabled"), True)
        result["qualityEnabled"] = self._bool(result.get("qualityEnabled"), True)
        result["responseStore"] = self._bool(result.get("responseStore"), False)
        result["qualityThreshold"] = self._clamp_int(result.get("qualityThreshold"), 60, 95, 82)
        result["maxRevisions"] = self._clamp_int(result.get("maxRevisions"), 0, 2, 1)
        result["maxConcurrentRuns"] = self._clamp_int(result.get("maxConcurrentRuns"), 1, 8, 2)
        result["maxQueuedRuns"] = self._clamp_int(result.get("maxQueuedRuns"), 0, 100, 20)
        effort = str(result.get("reasoningEffort", "medium")).lower()
        allowed_efforts = {"none", "low", "medium", "high", "xhigh", "max"}
        if provider == "codex-cli":
            allowed_efforts.add("ultra")
        result["reasoningEffort"] = effort if effort in allowed_efforts else "medium"
        verbosity = str(result.get("textVerbosity", "medium")).lower()
        result["textVerbosity"] = verbosity if verbosity in {"low", "medium", "high"} else "medium"
        return result

    def _write_secret(self, provider: str, api_key: str) -> None:
        if provider in {"codex-cli", "ollama"}:
            raise ProviderConfigError("该提供商不使用 API Key")
        self.secret_root.mkdir(parents=True, exist_ok=True)
        encrypted = _dpapi_protect(api_key.encode("utf-8"))
        self._write_bytes_atomic(self._secret_path(provider), encrypted)

    def _read_secret(self, provider: str) -> str:
        path = self._secret_path(provider)
        if not path.is_file():
            return ""
        try:
            return _dpapi_unprotect(path.read_bytes()).decode("utf-8")
        except (OSError, UnicodeDecodeError, ProviderConfigError) as error:
            raise ProviderConfigError(f"无法读取 {PROVIDER_CATALOG[provider]['label']} 的 API Key") from error

    def _secret_path(self, provider: str) -> Path:
        return self.secret_root / f"{provider}.bin"

    def _write_json_atomic(self, record: dict[str, Any]) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        content = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
        self._write_bytes_atomic(self.path, content)

    @staticmethod
    def _write_bytes_atomic(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp_path = Path(raw_path)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _normalize_provider(value: Any) -> str:
        provider = str(value or "codex-cli").strip().lower()
        aliases = {
            "codex": "codex-cli",
            "openai": "openai-responses",
            "responses": "openai-responses",
            "auto": "codex-cli",
        }
        provider = aliases.get(provider, provider)
        if provider not in PROVIDER_CATALOG:
            raise ProviderConfigError("未知模型提供商")
        return provider

    @staticmethod
    def _validate_base_url(value: str) -> None:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ProviderConfigError("基础 URL 必须是有效的 HTTP(S) 地址，且不能内嵌账号密码")
        try:
            parsed.port
        except ValueError as error:
            raise ProviderConfigError("基础 URL 的端口无效") from error
        if parsed.query or parsed.fragment:
            raise ProviderConfigError("基础 URL 不能包含查询参数或片段")
        if parsed.scheme == "http":
            try:
                is_loopback = parsed.hostname.casefold() == "localhost" or ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                is_loopback = False
            if not is_loopback:
                raise ProviderConfigError("非本机模型接口必须使用 HTTPS")

    @staticmethod
    def _validate_provider_origin(provider: str, value: str) -> None:
        origin = _canonical_origin(value)
        fixed = {
            "openai-responses": "https://api.openai.com",
            "deepseek": "https://api.deepseek.com",
        }
        if provider in fixed and origin != fixed[provider]:
            raise ProviderConfigError(f"{PROVIDER_CATALOG[provider]['label']} 只允许使用官方接口主机")
        if provider == "ollama":
            hostname = urlparse(value).hostname or ""
            if not _is_loopback_hostname(hostname):
                raise ProviderConfigError("Ollama 仅允许连接本机回环地址")

    @staticmethod
    def _credential_origin(provider: str, profile: dict[str, Any]) -> str:
        if provider in {"codex-cli", "ollama"}:
            return ""
        return _canonical_origin(str(profile.get("baseUrl", "")))

    @staticmethod
    def _clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
        try:
            return max(minimum, min(maximum, int(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp_float(value: Any, minimum: float, maximum: float, default: float) -> float:
        try:
            return max(minimum, min(maximum, float(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() not in {"0", "false", "no", "off"}

    @staticmethod
    def _env_bool(value: Any) -> str:
        return "1" if ProviderConfigStore._bool(value, False) else "0"


def codex_cli_status(configured_path: str = "", *, force: bool = False) -> dict[str, Any]:
    global _CODEX_STATUS_CACHE
    cache_key = configured_path.strip()
    now = time.monotonic()
    with _CODEX_STATUS_LOCK:
        if not force and _CODEX_STATUS_CACHE:
            cached_at, cached_key, cached = _CODEX_STATUS_CACHE
            if cached_key == cache_key and now - cached_at < 15:
                return dict(cached)
        status = _probe_codex_cli(cache_key)
        _CODEX_STATUS_CACHE = (now, cache_key, status)
        return dict(status)


def _probe_codex_cli(configured_path: str) -> dict[str, Any]:
    errors: list[str] = []
    validated_path = ""
    if configured_path:
        try:
            validated_path = _validated_codex_executable(configured_path)
        except ProviderConfigError as error:
            return {
                "installed": False,
                "invokable": False,
                "available": False,
                "loggedIn": False,
                "authenticated": False,
                "sameAccount": None,
                "version": "",
                "account": {},
                "reason": str(error),
                "executable": "",
                "transport": "",
                "models": [],
            }
    try:
        from openai_codex import Codex, CodexConfig

        config = CodexConfig(codex_bin=validated_path or None)
        with Codex(config) as codex:
            account_payload = codex.account(refresh_token=False).model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
            )
            model_payload = codex.models().model_dump(mode="json", by_alias=True, exclude_none=True)
        account = account_payload.get("account") if isinstance(account_payload, dict) else None
        models = model_payload.get("data", model_payload.get("models", [])) if isinstance(model_payload, dict) else []
        public_models = []
        for item in models if isinstance(models, list) else []:
            if not isinstance(item, dict):
                continue
            efforts = item.get("supportedReasoningEfforts", [])
            public_models.append(
                {
                    "id": str(item.get("id", "")),
                    "displayName": str(item.get("displayName", item.get("id", ""))),
                    "isDefault": bool(item.get("isDefault", False)),
                    "defaultReasoningEffort": str(item.get("defaultReasoningEffort", "")),
                    "supportedReasoningEfforts": [
                        str(effort.get("reasoningEffort", ""))
                        for effort in efforts
                        if isinstance(effort, dict) and effort.get("reasoningEffort")
                    ],
                }
            )
        account_type = str(account.get("type", "")) if isinstance(account, dict) else ""
        account_summary = {
            "type": account_type,
            "email": _mask_email(str(account.get("email", ""))) if isinstance(account, dict) else "",
            "planType": str(account.get("planType", "")) if isinstance(account, dict) else "",
        }
        logged_in = bool(account_type)
        return {
            "installed": True,
            "invokable": True,
            "available": logged_in,
            "loggedIn": logged_in,
            "authenticated": logged_in,
            "sameAccount": None,
            "version": "openai-codex SDK 0.144.4",
            "account": account_summary,
            "reason": "" if logged_in else "Codex 运行时尚未登录",
            "executable": validated_path,
            "transport": "app-server-sdk",
            "models": public_models,
        }
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        errors.append(f"openai-codex SDK: {str(error).strip() or type(error).__name__}")

    candidates = _codex_candidates(validated_path)
    for candidate in candidates:
        try:
            version = _run_codex(candidate, ["--version"], timeout=5)
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f"{candidate}: {str(error).strip() or type(error).__name__}")
            continue
        if version.returncode != 0:
            errors.append(f"{candidate}: {(version.stderr or version.stdout).strip()[:180]}")
            continue
        try:
            login = _run_codex(candidate, ["login", "status"], timeout=8)
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f"{candidate}: {str(error).strip() or type(error).__name__}")
            continue
        output = "\n".join(part.strip() for part in (login.stdout, login.stderr) if part.strip())
        logged_in = login.returncode == 0
        return {
            "installed": True,
            "invokable": True,
            "available": logged_in,
            "loggedIn": logged_in,
            "authenticated": logged_in,
            "sameAccount": None,
            "version": (version.stdout or version.stderr).strip()[:120],
            "account": {},
            "reason": "" if logged_in else "Codex CLI 尚未登录",
            "executable": str(candidate),
            "transport": "codex-exec",
            "models": [],
        }
    reason = "未找到可由后端调用的官方 Codex CLI"
    if errors:
        reason += f"；{errors[-1]}"
    return {
        "installed": False,
        "invokable": False,
        "available": False,
        "loggedIn": False,
        "authenticated": False,
        "sameAccount": None,
        "version": "",
        "account": "",
        "reason": reason,
        "executable": "",
        "transport": "",
        "models": [],
    }


def _mask_email(value: str) -> str:
    if "@" not in value:
        return value[:2] + "***" if value else ""
    local, domain = value.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"


def _codex_candidates(configured_path: str) -> list[str]:
    candidates: list[str] = []
    for item in (configured_path, os.environ.get("CODEX_CLI_PATH", ""), shutil.which("codex") or ""):
        if not item:
            continue
        try:
            candidate = _validated_codex_executable(item)
        except ProviderConfigError:
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _run_codex(executable: str, arguments: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    command = [_validated_codex_executable(executable), *arguments]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _validated_codex_executable(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ProviderConfigError("Codex 可执行文件必须是绝对路径")
    if path.is_symlink():
        raise ProviderConfigError("Codex 可执行文件不能是符号链接")
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or resolved.name.casefold() != "codex.exe":
        raise ProviderConfigError("只允许使用官方 codex.exe，拒绝批处理或其他程序")
    if "windowsapps" in {part.casefold() for part in resolved.parts}:
        raise ProviderConfigError("WindowsApps 内部 Codex 组件不能由后端直接调用")
    return str(resolved)
