"""Network helpers shared by the scanner, the live agent and infrastructure lookups."""

from __future__ import annotations

import ipaddress
import os
import socket
import ssl
from functools import lru_cache
from urllib.parse import urlsplit

MOBILE_UA = "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


@lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    """Use the operating system's trust store (works behind TLS-inspecting proxies and antivirus)."""
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # truststore missing: fall back to Python's default store
        return ssl.create_default_context()


def _blocked_ip(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def url_error(url: str) -> str | None:
    """Why this URL may not be opened (None if it is allowed)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return "Navigation refused. Only http and https URLs are allowed."
    host = (parts.hostname or "").lower()
    if not host:
        return "Navigation refused. The URL has no host."
    if os.environ.get("RAQIB_ALLOW_PRIVATE") != "1" and _blocked_ip(host):
        return "Navigation refused. Private, loopback and link-local addresses are blocked."
    return None
