"""Public-web & academic URL acquisition crawler (HTTP first + isolated Playwright Chromium fallback)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from urllib.parse import urljoin, urlparse

import httpx

from app.config import get_settings
from app.ingestion.html_extractor import extract_html_text_and_meta
from app.sources.robots import is_url_allowed
from app.sources.ssrf import SSRFError, canonicalize_url, validate_public_url

_domain_lock = Lock()
_domain_last_hit: dict[str, float] = {}


@dataclass
class CrawlResult:
    status: str  # FULLTEXT_FETCHED | ACCESS_RESTRICTED | CRAWL_FAILED
    raw_bytes: bytes | None = None
    file_type: str | None = None  # pdf | html | xml | txt
    final_url: str | None = None
    canonical_url: str | None = None
    http_status: int | None = None
    title: str | None = None
    meta_description: str | None = None
    page_language: str | None = None
    source_links: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    doi: str | None = None
    license_name: str | None = None
    used_playwright: bool = False
    error: str | None = None


def _respect_domain_delay(url: str, delay_sec: float) -> None:
    if delay_sec <= 0:
        return
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return
    with _domain_lock:
        now = time.monotonic()
        last = _domain_last_hit.get(host, 0.0)
        wait = delay_sec - (now - last)
        if wait > 0:
            time.sleep(min(wait, 5.0))
        _domain_last_hit[host] = time.monotonic()


def _needs_playwright_rendering(html_text: str, extracted_chars: int) -> bool:
    low = html_text.lower()
    if extracted_chars < 180:
        return True
    if ("__next_data__" in low or 'id="root"' in low or 'id="app"' in low) and extracted_chars < 500:
        return True
    if "enable javascript" in low or "please turn on javascript" in low:
        return True
    return False


def _fetch_with_playwright(
    url: str,
    user_agent: str,
    timeout_sec: int,
    resolve_dns: bool,
) -> tuple[str | None, str | None, str | None]:
    """Render public web page using an isolated ephemeral Chromium context (zero personal profile/cookies/history)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, None, "Playwright belum terpasang."

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Strictly isolated ephemeral context: storage_state=None, zero personal profile/cookies/passwords
            context = browser.new_context(
                storage_state=None,
                user_agent=user_agent,
                ignore_https_errors=False,
                java_script_enabled=True,
                accept_downloads=False,
            )
            page = context.new_page()

            def _route_guard(route):
                req_url = route.request.url
                if req_url.startswith(("data:", "blob:")):
                    route.abort()
                    return
                try:
                    validate_public_url(req_url, resolve_dns=resolve_dns)
                except SSRFError:
                    route.abort()
                    return
                if route.request.resource_type in {"image", "media", "font"}:
                    route.abort()
                    return
                route.continue_()

            page.route("**/*", _route_guard)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=min(4500, timeout_sec * 450))
            except Exception:
                pass
            html_content = page.content()
            final_url = page.url
            context.close()
            browser.close()
            return html_content, final_url, None
    except Exception as exc:
        return None, None, f"Playwright gagal merender halaman: {exc}"


def fetch_public_url(
    url: str,
    *,
    client: httpx.Client | None = None,
    enable_browser_crawler: bool = False,
    max_bytes: int | None = None,
    resolve_dns: bool = True,
    max_redirects: int = 5,
    follow_oa_pdf_meta: bool = True,
    _depth: int = 0,
) -> CrawlResult:
    """Safely fetch PDF, XML, or HTML from a public URL with SSRF, robots.txt, backoff, OA PDF link follow, and Playwright fallback."""
    settings = get_settings()
    limit_bytes = max_bytes or (settings.MAX_EXTERNAL_DOWNLOAD_MB * 1024 * 1024)
    timeout_sec = settings.CRAWL_TIMEOUT_SEC
    user_agent = f"NaskahGuard/0.1 (mailto:{settings.CONTACT_EMAIL})"

    try:
        current_url = validate_public_url(url, resolve_dns=resolve_dns)
    except SSRFError as exc:
        return CrawlResult(status="ACCESS_RESTRICTED", error=str(exc))

    own_client = client is None
    http = client or httpx.Client(timeout=float(timeout_sec))
    try:
        if client is None:
            _respect_domain_delay(current_url, settings.CRAWL_DOMAIN_DELAY_SEC)

        if not is_url_allowed(current_url, user_agent, http):
            return CrawlResult(status="ACCESS_RESTRICTED", final_url=current_url, error="Dilarang oleh robots.txt.")

        resp_bytes: bytes | None = None
        content_type = ""
        final_url = current_url
        final_status = 0

        for _hop in range(max_redirects + 1):
            last_exc: Exception | None = None
            resp_status = 0
            resp_headers: dict[str, str] = {}
            hop_redirect: str | None = None

            for attempt in range(3):
                try:
                    with http.stream(
                        "GET",
                        final_url,
                        headers={"User-Agent": user_agent, "Accept": "application/pdf, text/html, application/xml, */*;q=0.8"},
                        timeout=float(timeout_sec),
                        follow_redirects=False,
                    ) as resp:
                        resp_status = resp.status_code
                        final_status = resp_status
                        resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                        if resp_status in {301, 302, 303, 307, 308} and "location" in resp_headers:
                            hop_redirect = urljoin(final_url, resp_headers["location"])
                            break
                        if resp_status in {429, 503} and attempt < 2:
                            time.sleep(0.5 * (2**attempt))
                            continue
                        if resp_status in {401, 403, 451}:
                            return CrawlResult(
                                status="ACCESS_RESTRICTED",
                                final_url=final_url,
                                http_status=resp_status,
                                error=f"Akses ditolak HTTP {resp_status}.",
                            )
                        if resp_status >= 400:
                            return CrawlResult(
                                status="CRAWL_FAILED",
                                final_url=final_url,
                                http_status=resp_status,
                                error=f"Gagal mengambil URL (HTTP {resp_status}).",
                            )

                        chunks: list[bytes] = []
                        total = 0
                        for chunk in resp.iter_bytes(65536):
                            total += len(chunk)
                            if total > limit_bytes:
                                return CrawlResult(
                                    status="CRAWL_FAILED",
                                    final_url=final_url,
                                    http_status=resp_status,
                                    error="Ukuran dokumen melebihi batas maksimum.",
                                )
                            chunks.append(chunk)
                        resp_bytes = b"".join(chunks)
                        content_type = resp_headers.get("content-type", "").lower()
                        break
                except Exception as exc:
                    last_exc = exc
                    if attempt < 2:
                        time.sleep(0.4 * (2**attempt))
                    continue

            if hop_redirect is not None:
                try:
                    final_url = validate_public_url(hop_redirect, resolve_dns=resolve_dns)
                except SSRFError as exc:
                    return CrawlResult(status="ACCESS_RESTRICTED", final_url=final_url, error=f"Redirect ditolak: {exc}")
                continue

            if resp_bytes is None:
                return CrawlResult(
                    status="CRAWL_FAILED",
                    final_url=final_url,
                    http_status=final_status or None,
                    error=str(last_exc or "Gagal mengunduh konten."),
                )
            break
        else:
            return CrawlResult(status="CRAWL_FAILED", final_url=final_url, error="Terlalu banyak redirect.")

        canon = canonicalize_url(final_url)

        # Classify PDF vs XML vs HTML
        if resp_bytes.lstrip()[:5].startswith(b"%PDF-") or "application/pdf" in content_type:
            return CrawlResult(
                status="FULLTEXT_FETCHED",
                raw_bytes=resp_bytes,
                file_type="pdf",
                final_url=final_url,
                canonical_url=canon,
                http_status=final_status or 200,
            )

        if "xml" in content_type or resp_bytes.lstrip()[:60].startswith((b"<?xml", b"<article", b"<TEI")):
            return CrawlResult(
                status="FULLTEXT_FETCHED",
                raw_bytes=resp_bytes,
                file_type="xml",
                final_url=final_url,
                canonical_url=canon,
                http_status=final_status or 200,
            )

        # HTML path (with optional Playwright fallback when JS-rendered + legal OA citation_pdf_url follow)
        html_str = resp_bytes.decode("utf-8", errors="replace")
        extracted = extract_html_text_and_meta(html_str, base_url=final_url)
        used_pw = False

        if (
            enable_browser_crawler
            and settings.PLAYWRIGHT_ENABLED
            and client is None
            and _needs_playwright_rendering(html_str, len(extracted.text.strip()))
        ):
            pw_html, pw_url, pw_err = _fetch_with_playwright(
                final_url,
                user_agent,
                timeout_sec,
                resolve_dns=resolve_dns,
            )
            if pw_html:
                effective_base = pw_url or final_url
                pw_extracted = extract_html_text_and_meta(pw_html, base_url=effective_base)
                if len(pw_extracted.text.strip()) > len(extracted.text.strip()):
                    html_str = pw_html
                    extracted = pw_extracted
                    resp_bytes = pw_html.encode("utf-8")
                    if pw_url:
                        final_url = pw_url
                        canon = canonicalize_url(pw_url)
                    used_pw = True
            elif pw_err and len(extracted.text.strip()) < 60:
                return CrawlResult(
                    status="CRAWL_FAILED",
                    final_url=final_url,
                    http_status=final_status or None,
                    error=pw_err,
                    used_playwright=True,
                )

        # If this is an OJS / DSpace / repository landing page (abstract only < 1200 chars) exposing a legal OA PDF URL, fetch the PDF!
        pdf_meta_url = extracted.extra.get("citation_pdf_url")
        if (
            follow_oa_pdf_meta
            and _depth == 0
            and pdf_meta_url
            and len(extracted.text.strip()) < 1200
        ):
            pdf_res = fetch_public_url(
                str(pdf_meta_url),
                client=http,
                enable_browser_crawler=False,
                max_bytes=limit_bytes,
                resolve_dns=resolve_dns,
                max_redirects=max_redirects,
                follow_oa_pdf_meta=False,
                _depth=1,
            )
            if pdf_res.status == "FULLTEXT_FETCHED" and pdf_res.file_type == "pdf" and pdf_res.raw_bytes:
                pdf_res.title = extracted.title
                pdf_res.authors = extracted.authors
                pdf_res.doi = extracted.extra.get("doi")
                pdf_res.meta_description = extracted.extra.get("meta_description")
                pdf_res.page_language = extracted.extra.get("page_language")
                pdf_res.source_links = list(extracted.extra.get("source_links") or [])
                pdf_res.canonical_url = extracted.extra.get("canonical_url") or canon
                pdf_res.used_playwright = used_pw
                return pdf_res

        if len(extracted.text.strip()) < 80:
            return CrawlResult(
                status="CRAWL_FAILED",
                final_url=final_url,
                canonical_url=canon,
                http_status=final_status or None,
                error="Teks artikel bermakna tidak ditemukan pada halaman.",
                used_playwright=used_pw,
            )

        resolved_canon = extracted.extra.get("canonical_url")
        return CrawlResult(
            status="FULLTEXT_FETCHED",
            raw_bytes=resp_bytes,
            file_type="html",
            final_url=final_url,
            canonical_url=canonicalize_url(resolved_canon) if resolved_canon else canon,
            http_status=final_status or 200,
            title=extracted.title,
            meta_description=extracted.extra.get("meta_description"),
            page_language=extracted.extra.get("page_language"),
            source_links=list(extracted.extra.get("source_links") or []),
            authors=extracted.authors,
            doi=extracted.extra.get("doi"),
            used_playwright=used_pw,
        )
    finally:
        if own_client:
            http.close()
