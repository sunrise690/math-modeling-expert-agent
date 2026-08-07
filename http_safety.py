from __future__ import annotations

import re
import urllib.error
import urllib.request
from typing import Any


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Treat redirects as errors so credentials never follow to another origin."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def urlopen_no_redirect(request: urllib.request.Request, *, timeout: float):
    opener = urllib.request.build_opener(NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def safe_http_error(error: urllib.error.HTTPError, label: str = "上游接口") -> str:
    request_id = ""
    headers = getattr(error, "headers", None)
    if headers is not None:
        for name in ("x-request-id", "request-id", "x-amzn-requestid", "cf-ray"):
            value = str(headers.get(name, "")).strip()
            if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value):
                request_id = value
                break
    suffix = f"（request id: {request_id}）" if request_id else ""
    return f"{label}返回 HTTP {int(error.code)}{suffix}"


def scrub_diagnostic(text: str, *secrets: str, limit: int = 300) -> str:
    cleaned = str(text or "")
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "***")
    cleaned = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer ***", cleaned)
    cleaned = re.sub(r"(?i)(api[_ -]?key|token|secret)(\s*[:=]\s*)[^\s,;]+", r"\1\2***", cleaned)
    cleaned = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "sk-***", cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned[:limit]
