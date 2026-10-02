import http.client
import ipaddress
import json
import socket
import ssl
import time
from urllib.parse import urlsplit

from app.config import settings
from app.llm import ProviderError

SCENARIOS = {
    "rag": {"status": "degraded", "web": "ok", "rag": "unavailable", "index": "not_ready"},
    "cache": {"status": "degraded", "database": "ok", "redis": "unavailable"},
    "unknown": {"status": "unknown", "reason": "insufficient_evidence"},
}


def public_addresses(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ProviderError("health_address_forbidden")
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    """Connect only to the addresses just checked, with TLS hostname verification intact."""

    def connect(self):
        addresses = public_addresses(self.host, self.port)
        family, socktype, proto, _, address = addresses[0]
        raw = socket.socket(family, socktype, proto)
        raw.settimeout(self.timeout)
        try:
            raw.connect(address)
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def read_health(target_id):
    url = settings().health_targets.get(target_id)
    if not url:
        raise ProviderError("health_target_forbidden")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ProviderError("health_target_invalid")
    started = time.monotonic()
    connection = PinnedHTTPS(parsed.hostname, port=parsed.port or 443, timeout=5)
    try:
        connection.request("GET", parsed.path or "/", headers={"Accept": "application/json"})
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise ProviderError("health_redirect_forbidden")
        data = response.read(65537)
        if len(data) > 65536:
            raise ProviderError("health_response_too_large")
        try:
            payload = json.loads(data)
        except ValueError:
            payload = {}
        allowed = {}
        if isinstance(payload, dict):
            for key in ["status", "database", "redis", "rag", "index", "web"]:
                value = payload.get(key)
                if isinstance(value, (str, bool, int)):
                    allowed[key] = str(value)[:100]
        return {
            "mode": "live",
            "http_status": response.status,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "fields": allowed,
        }
    except (OSError, http.client.HTTPException):
        raise ProviderError("health_unavailable", retryable=True) from None
    finally:
        connection.close()


def execute_tool(name, mode, scenario, target_id, is_admin):
    if name == "simulate_health" and mode == "sandbox":
        return {"mode": "sandbox", "simulated": True, "fields": SCENARIOS[scenario]}
    if name == "read_health" and mode == "live" and is_admin:
        return read_health(target_id)
    raise ProviderError("tool_forbidden")
