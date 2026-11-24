"""robots.txt compliance checker and safe OA file downloader."""

from __future__ import annotations

from threading import Lock
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

MAX_OA_PDF_BYTES = 25 * 1024 * 1024
DEFAULT_TIMEOUT = 20.0

_robots_lock = Lock()
_robots_cache: dict[str, RobotFileParser | None] = {}


def is_url_allowed(
    url: str,
    user_agent: str,
    client: httpx.Client,
) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    origin = f"{parsed.scheme}://{parsed.netloc}"
    with _robots_lock:
        if origin in _robots_cache:
            rp = _robots_cache[origin]
            return True if rp is None else rp.can_fetch(user_agent, url)

    rp = RobotFileParser()
    robots_url = f"{origin}/robots.txt"
    try:
        resp = client.get(robots_url, headers={"User-Agent": user_agent}, timeout=5.0)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
        elif resp.status_code in {401, 403}:
            rp = None
        else:
            rp = None
    except Exception:
        rp = None

    with _robots_lock:
        _robots_cache[origin] = rp
    return True if rp is None else rp.can_fetch(user_agent, url)


def download_oa_pdf(
    url: str,
    user_agent: str,
    client: httpx.Client,
) -> tuple[bytes | None, str]:
    """Download OA PDF respecting robots.txt, size limit (25 MB), and timeout (20s).

    Returns (bytes_or_none, status_label) where status_label is
    FULL_TEXT_AVAILABLE | ACCESS_DENIED | FETCH_FAILED.
    """
    if not is_url_allowed(url, user_agent, client):
        return None, "ACCESS_DENIED"
    try:
        with client.stream(
            "GET",
            url,
            headers={"User-Agent": user_agent},
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        ) as resp:
            if resp.status_code in {401, 403}:
                return None, "ACCESS_DENIED"
            if resp.status_code >= 400:
                return None, "FETCH_FAILED"
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes(65536):
                total += len(chunk)
                if total > MAX_OA_PDF_BYTES:
                    return None, "FETCH_FAILED"
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data.lstrip()[:5].startswith(b"%PDF-"):
                return None, "FETCH_FAILED"
            return data, "FULL_TEXT_AVAILABLE"
    except Exception:
        return None, "FETCH_FAILED"
