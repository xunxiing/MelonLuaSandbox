"""Sandbox-only HTTP. The real game Lua API has no http module.

Exposes:
    status, body = http.request(method, url, body, headers)
    body = http.get(url)
    status, body = http.post(url, body, contentType)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def _header_map(headers: Any) -> dict[str, str]:
    if headers is None:
        return {}
    if isinstance(headers, dict):
        return {str(k): str(v) for k, v in headers.items()}
    if hasattr(headers, "keys"):
        return {str(k): str(headers[k]) for k in headers.keys()}
    return {}


def register_http_backend(lua, g, world):
    def request(method, url, body=None, headers=None):
        verb = str(method or "GET").upper()
        data = None if body is None else str(body).encode("utf-8")
        hdrs = _header_map(headers)
        if data is not None and "Content-Type" not in hdrs:
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(str(url), data=data, headers=hdrs, method=verb)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return int(resp.status), raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raw = exc.read() if exc.fp else b""
            return int(exc.code), raw.decode("utf-8", errors="replace")
        except Exception as exc:
            return 0, str(exc)

    def get(url):
        _status, body = request("GET", url)
        return body

    def post(url, body=None, content_type=None):
        payload = body
        if payload is not None and not isinstance(payload, str):
            payload = json.dumps(payload)
        hdrs = {}
        if content_type:
            hdrs["Content-Type"] = str(content_type)
        return request("POST", url, payload, hdrs)

    g["http"] = lua.table_from(
        {
            "request": request,
            "get": get,
            "post": post,
        }
    )
