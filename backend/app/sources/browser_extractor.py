"""Modular BrowserExtractor interface and isolated adapters (Phase 9).

Guarantees strict browser isolation:
- Never accesses personal browser profiles, cookies, saved passwords, or history.
- Uses fresh ephemeral BrowserContext per extraction with zero shared storage_state.
- Enforces SSRF protection, redirect validation, robots.txt, domain crawl delay, and size limits.
- Never bypasses CAPTCHA, authentication, or paywalls.
"""

from __future__ import annotations

import abc
import asyncio
import importlib.util
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings
from app.ingestion.html_extractor import extract_html_text_and_meta
from app.ingestion.language import detect_language
from app.sources.crawler import fetch_public_url
from app.sources.ssrf import canonicalize_url


@dataclass
class BrowserExtractionResult:
    requested_url: str
    final_url: str | None = None
    canonical_url: str | None = None
    http_status: int | None = None
    page_title: str | None = None
    meta_description: str | None = None
    main_content: str = ""
    page_language: str | None = None
    source_links: list[str] = field(default_factory=list)
    retrieval_time_ms: int = 0
    extraction_method: str = "HTTP_STATIC"
    extraction_confidence: float = 0.0
    error_status: str | None = None
    status: str = "CRAWL_FAILED"  # FULLTEXT_FETCHED | ACCESS_RESTRICTED | CRAWL_FAILED
    raw_bytes: bytes | None = None
    file_type: str | None = None
    authors: list[str] = field(default_factory=list)
    doi: str | None = None
    used_playwright: bool = False


class BrowserExtractor(abc.ABC):
    """Unified async interface for safe public-web & academic page extraction."""

    @abc.abstractmethod
    async def extract(self, url: str) -> BrowserExtractionResult:
        """Extract main content, metadata, and canonical links from a public URL."""

    @abc.abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Verify whether the underlying browser/HTTP engine is operational."""


class IsolatedPlaywrightExtractor(BrowserExtractor):
    """Production BrowserExtractor combining fast HTTP streaming + isolated Playwright Chromium fallback."""

    def __init__(
        self,
        *,
        enable_browser: bool = True,
        max_bytes: int | None = None,
        resolve_dns: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        self.enable_browser = enable_browser
        self.max_bytes = max_bytes
        self.resolve_dns = resolve_dns
        self.client = client

    def extract_sync(self, url: str) -> BrowserExtractionResult:
        t0 = time.perf_counter()
        crawl = fetch_public_url(
            url,
            client=self.client,
            enable_browser_crawler=self.enable_browser,
            max_bytes=self.max_bytes,
            resolve_dns=self.resolve_dns,
            follow_oa_pdf_meta=True,
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if crawl.status != "FULLTEXT_FETCHED" or not crawl.raw_bytes:
            return BrowserExtractionResult(
                requested_url=url,
                final_url=crawl.final_url,
                canonical_url=crawl.canonical_url,
                http_status=crawl.http_status,
                retrieval_time_ms=elapsed_ms,
                extraction_method="PLAYWRIGHT_ISOLATED" if crawl.used_playwright else "HTTP_STATIC",
                extraction_confidence=0.0,
                error_status=crawl.error or crawl.status,
                status=crawl.status,
                used_playwright=crawl.used_playwright,
            )

        if crawl.file_type == "html":
            html_str = crawl.raw_bytes.decode("utf-8", errors="replace")
            doc = extract_html_text_and_meta(html_str, base_url=crawl.final_url or url)
            lang = doc.extra.get("page_language") or (detect_language(doc.text) if doc.text.strip() else None)
            return BrowserExtractionResult(
                requested_url=url,
                final_url=crawl.final_url or url,
                canonical_url=doc.extra.get("canonical_url") or crawl.canonical_url or canonicalize_url(crawl.final_url or url),
                http_status=crawl.http_status or 200,
                page_title=doc.title or crawl.title,
                meta_description=doc.extra.get("meta_description"),
                main_content=doc.text,
                page_language=lang,
                source_links=list(doc.extra.get("source_links") or []),
                retrieval_time_ms=elapsed_ms,
                extraction_method="PLAYWRIGHT_ISOLATED" if crawl.used_playwright else "HTTP_STATIC",
                extraction_confidence=doc.extraction_confidence,
                error_status=None,
                status="FULLTEXT_FETCHED",
                raw_bytes=crawl.raw_bytes,
                file_type="html",
                authors=doc.authors or crawl.authors,
                doi=doc.extra.get("doi") or crawl.doi,
                used_playwright=crawl.used_playwright,
            )

        # Binary PDF or JATS/TEI XML payload
        method = "PDF_BINARY" if crawl.file_type == "pdf" else "XML_STRUCTURED"
        return BrowserExtractionResult(
            requested_url=url,
            final_url=crawl.final_url or url,
            canonical_url=crawl.canonical_url or canonicalize_url(crawl.final_url or url),
            http_status=crawl.http_status or 200,
            page_title=crawl.title,
            meta_description=crawl.meta_description,
            main_content="",
            page_language=crawl.page_language,
            source_links=crawl.source_links,
            retrieval_time_ms=elapsed_ms,
            extraction_method=method,
            extraction_confidence=0.98,
            error_status=None,
            status="FULLTEXT_FETCHED",
            raw_bytes=crawl.raw_bytes,
            file_type=crawl.file_type,
            authors=crawl.authors,
            doi=crawl.doi,
            used_playwright=crawl.used_playwright,
        )

    async def extract(self, url: str) -> BrowserExtractionResult:
        return await asyncio.to_thread(self.extract_sync, url)

    def health_check_sync(self) -> dict[str, Any]:
        settings = get_settings()
        pw_spec = importlib.util.find_spec("playwright")
        if pw_spec is None:
            return {
                "engine": "playwright_chromium",
                "configured": False,
                "reachable": False,
                "isolated_context": True,
                "message": "Paket playwright belum terpasang.",
            }
        if not settings.PLAYWRIGHT_ENABLED:
            return {
                "engine": "playwright_chromium",
                "configured": True,
                "reachable": False,
                "isolated_context": True,
                "message": "Playwright terpasang tetapi PLAYWRIGHT_ENABLED=false.",
            }
        t0 = time.perf_counter()
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(storage_state=None, java_script_enabled=True, accept_downloads=False)
                page = ctx.new_page()
                page.set_content("<html><head><title>NG Health</title></head><body><main><p>Isolated browser ready.</p></main></body></html>")
                ok = page.title() == "NG Health"
                ctx.close()
                browser.close()
            ms = int((time.perf_counter() - t0) * 1000)
            return {
                "engine": "playwright_chromium",
                "configured": True,
                "reachable": bool(ok),
                "isolated_context": True,
                "latency_ms": ms,
                "message": f"Chromium headless terisolasi siap ({ms} ms).",
            }
        except Exception as exc:
            return {
                "engine": "playwright_chromium",
                "configured": True,
                "reachable": False,
                "isolated_context": True,
                "message": f"Gagal meluncurkan Chromium headless: {exc}",
            }

    async def health_check(self) -> dict[str, Any]:
        return await asyncio.to_thread(self.health_check_sync)
