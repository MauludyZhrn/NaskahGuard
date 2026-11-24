"""Defense-in-depth SSRF validation, DNS IP checks, redirect validation, and URL canonicalization."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",
    "100.100.100.200",
}

_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}


class SSRFError(ValueError):
    """Raised when a URL fails SSRF safety checks."""


def _is_forbidden_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_url(url: str, *, resolve_dns: bool = True) -> str:
    """Validate URL scheme, hostname, and resolved IP addresses against SSRF."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise SSRFError(f"Skema URL ditolak: {parsed.scheme or 'kosong'}")
    if not parsed.hostname:
        raise SSRFError("Hostname URL tidak valid.")

    host = parsed.hostname.lower().strip(".")
    if host in _BLOCKED_HOSTS or host.endswith((".local", ".internal", ".localhost")):
        raise SSRFError(f"Host internal/terlarang ditolak: {host}")

    # Direct IP literal check
    is_ip_literal = False
    try:
        ipaddress.ip_address(host)
        is_ip_literal = True
    except ValueError:
        is_ip_literal = False

    if is_ip_literal:
        if _is_forbidden_ip(host):
            raise SSRFError(f"Alamat IP privat/loopback/link-local ditolak: {host}")
        return url.strip()

    if resolve_dns:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise SSRFError(f"Gagal melakukan resolusi DNS untuk {host}: {exc}") from exc
        if not infos:
            raise SSRFError(f"Tidak ada alamat IP valid untuk {host}.")
        for info in infos:
            ip_addr = info[4][0]
            if _is_forbidden_ip(ip_addr):
                raise SSRFError(f"Hasil DNS {host} mengarah ke IP terlarang ({ip_addr}).")

    return url.strip()


def canonicalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    kept_params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in _TRACKING_PARAMS]
    query = urlencode(sorted(kept_params))
    return urlunparse((scheme, netloc, path, "", query, ""))
