import os
import re
import sys
import time
import socket
import ipaddress
import subprocess
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from flask import Flask, Blueprint, jsonify, request

_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}\Z)(?!-)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)\Z"
)


def _get_client_ip() -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


@dataclass
class RateLimitConfig:
    window_seconds: int = 60
    max_requests: int = 30


class InMemoryFixedWindowRateLimiter:
    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._counters: Dict[Tuple[str, int], int] = {}

    def allow(self, key: str) -> bool:
        now = int(time.time())
        window_id = now // self._config.window_seconds
        k = (key, window_id)
        with self._lock:
            self._counters[k] = self._counters.get(k, 0) + 1
            # Best-effort cleanup of old windows
            for (ck, wid) in list(self._counters.keys()):
                if wid < window_id - 2:
                    self._counters.pop((ck, wid), None)
            return self._counters[k] <= self._config.max_requests


def _require_bearer_token() -> bool:
    expected = os.environ.get("PING_API_TOKEN", "").strip()
    if not expected:
        return True
    auth = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not auth.startswith(prefix):
        return False
    return auth[len(prefix) :].strip() == expected


def _normalize_host(host: str) -> str:
    host = (host or "").strip()
    if not host:
        raise ValueError("host is required")
    if len(host) > 253:
        raise ValueError("host is too long")
    if any(c in host for c in ("\x00", "\r", "\n", "\t", " ", "/", "\\", "@", "#", "?")):
        raise ValueError("invalid host format")

    # Strip trailing dot (absolute FQDN)
    if host.endswith("."):
        host = host[:-1]

    # If it's an IP literal, validate and return it
    try:
        ip = ipaddress.ip_address(host)
        return str(ip)
    except ValueError:
        pass

    # IDNA normalize for internationalized hostnames
    try:
        host_idna = host.encode("idna").decode("ascii")
    except Exception as e:
        raise ValueError("invalid hostname") from e

    if host_idna.lower() in {"localhost"} or host_idna.lower().endswith(".local"):
        raise ValueError("hostname not allowed")

    if not _HOSTNAME_RE.match(host_idna):
        raise ValueError("invalid hostname")

    return host_idna


def _is_public_ip(ip: ipaddress._BaseAddress) -> bool:
    # ipaddress.is_global is a good baseline; add explicit denylists.
    if not ip.is_global:
        return False
    if ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local:
        return False
    if ip.version == 4:
        # Block common sensitive ranges even if edge-cases slip through.
        if ip in ipaddress.ip_network("169.254.0.0/16"):  # link-local
            return False
        if ip in ipaddress.ip_network("127.0.0.0/8"):
            return False
        if ip in ipaddress.ip_network("0.0.0.0/8"):
            return False
    else:
        if ip in ipaddress.ip_network("::1/128"):
            return False
        if ip in ipaddress.ip_network("fe80::/10"):  # link-local
            return False
        if ip in ipaddress.ip_network("fc00::/7"):  # ULA
            return False
    return True


def _resolve_public_ips(host: str) -> List[str]:
    # If host is already an IP literal
    try:
        ip = ipaddress.ip_address(host)
        if not _is_public_ip(ip):
            raise PermissionError("target is not a public address")
        return [str(ip)]
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError("unable to resolve host") from e

    ips: List[str] = []
    for family, _, _, _, sockaddr in infos:
        if family == socket.AF_INET:
            ip_str = sockaddr[0]
        elif family == socket.AF_INET6:
            ip_str = sockaddr[0]
        else:
            continue
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if not _is_public_ip(ip_obj):
            raise PermissionError("hostname resolves to a non-public address")
        ips.append(str(ip_obj))

    ips = sorted(set(ips))
    if not ips:
        raise ValueError("no usable addresses found for host")
    return ips


def _build_ping_command(host: str) -> List[str]:
    ping_bin = os.environ.get("PING_BINARY", "ping")
    if sys.platform.startswith("win"):
        return [ping_bin, "-n", "3", "-w", "2000", host]
    if sys.platform == "darwin":
        # macOS: -W is timeout in milliseconds (per probe)
        return [ping_bin, "-n", "-c", "3", "-W", "2000", host]
    # Linux (iputils): -W is timeout in seconds (per reply)
    return [ping_bin, "-n", "-c", "3", "-W", "2", host]


def _truncate(s: str, max_len: int = 32768) -> str:
    if s is None:
        return ""
    if len(s) <= max_len:
        return s
    return s[:max_len] + "\n...[truncated]"


def create_app() -> Flask:
    app = Flask(__name__)
    api = Blueprint("api", __name__)
    limiter = InMemoryFixedWindowRateLimiter(
        RateLimitConfig(
            window_seconds=int(os.environ.get("PING_RATE_WINDOW_SECONDS", "60")),
            max_requests=int(os.environ.get("PING_RATE_MAX_REQUESTS", "30")),
        )
    )

    @api.post("/api/tools/ping")
    def ping_tool():
        if not _require_bearer_token():
            return jsonify({"error": "unauthorized"}), 401

        client_ip = _get_client_ip()
        if not limiter.allow(client_ip):
            return jsonify({"error": "rate_limited"}), 429

        payload = request.get_json(silent=True) or {}
        host_in = payload.get("host", "")
        try:
            host = _normalize_host(host_in)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        try:
            resolved_ips = _resolve_public_ips(host)
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        cmd = _build_ping_command(host)
        started = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=int(os.environ.get("PING_TIMEOUT_SECONDS", "10")),
                check=False,
            )
            duration_ms = int((time.time() - started) * 1000)
            output = (proc.stdout or "") + (proc.stderr or "")
            return (
                jsonify(
                    {
                        "host": host,
                        "resolved_ips": resolved_ips,
                        "exit_code": proc.returncode,
                        "success": proc.returncode == 0,
                        "duration_ms": duration_ms,
                        "output": _truncate(output),
                    }
                ),
                200,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - started) * 1000)
            return (
                jsonify(
                    {
                        "host": host,
                        "resolved_ips": resolved_ips,
                        "success": False,
                        "duration_ms": duration_ms,
                        "error": "ping timed out",
                    }
                ),
                504,
            )
        except FileNotFoundError:
            return jsonify({"error": "ping binary not found on server"}), 500

    app.register_blueprint(api)

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True}), 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
