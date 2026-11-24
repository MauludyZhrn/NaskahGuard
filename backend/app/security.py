"""Security, auth, rate limiting, and host/URL safety utilities."""

from __future__ import annotations

import hashlib
import ipaddress
import time
from collections import defaultdict, deque
from threading import Lock
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower().strip("[]")
    if normalized in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_startup_security(settings: Settings) -> None:
    if not is_loopback_host(settings.HOST) and not settings.API_TOKEN.strip():
        raise RuntimeError(
            "Keamanan: HOST bukan alamat loopback sementara API_TOKEN kosong. "
            "Atur NG_API_TOKEN sebelum menjalankan aplikasi di antarmuka jaringan non-lokal."
        )
    if settings.NOPLAG_ENGINE_URL.strip():
        validate_loopback_url(settings.NOPLAG_ENGINE_URL)


def validate_loopback_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL Noplag Engine tidak valid.")
    if not is_loopback_host(parsed.hostname):
        raise ValueError(
            f"NOPLAG_ENGINE_URL ditolak ({parsed.hostname}): hanya host loopback yang diizinkan."
        )
    return url.rstrip("/")


def get_actor_label(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]
        return f"{ip}:tok-{digest}"
    return ip


def require_auth(request: Request, settings: Settings = Depends(get_settings)) -> str:
    actor = get_actor_label(request)
    token = settings.API_TOKEN.strip()
    if not token:
        return actor
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Otentikasi Bearer token diperlukan.",
        )
    provided = auth_header[7:].strip()
    if provided != token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token otentikasi tidak valid.",
        )
    return actor


class SlidingWindowRateLimiter:
    """Simple thread-safe sliding-window rate limiter per client IP."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit_per_min: int) -> None:
        if limit_per_min <= 0:
            return
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            q = self._hits[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit_per_min:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Terlalu banyak permintaan dalam 1 menit. Silakan coba lagi sebentar.",
                )
            q.append(now)


rate_limiter = SlidingWindowRateLimiter()


def enforce_rate_limit(request: Request, settings: Settings = Depends(get_settings)) -> None:
    ip = request.client.host if request.client else "unknown"
    rate_limiter.check(ip, settings.RATE_LIMIT_PER_MIN)
