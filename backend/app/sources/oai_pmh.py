"""OAI-PMH 2.0 Client, 8-Stage Connection Wizard, and Fault-Tolerant Harvester.

Supports DSpace 7 (/server/oai/request), Legacy DSpace (/oai/request, /dspace-oai/request),
OJS (/index.php/{journal}/oai, /{journal}/oai), EPrints (/cgi/oai2), and general OAI-PMH 2.0
academic repositories with SSRF-safe redirects, metadata format negotiation, resumable pagination,
per-record tracking, and strict separation between metadata and full-text indexing.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse, urlunparse

import defusedxml.ElementTree as ET
import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.service import ingest_validated_upload
from app.ingestion.validators import validate_local_bytes
from app.models import (
    CheckSource,
    Document,
    OAIHarvestLog,
    OAIHarvestRecord,
    OAIHarvestRun,
    OAIRepository,
)
from app.sources.crawler import fetch_public_url
from app.sources.dedup import find_duplicate_source
from app.sources.ssrf import SSRFError, validate_public_url

_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.IGNORECASE)
_ARXIV_ABS_RE = re.compile(r"^https?://(?:export\.)?arxiv\.org/abs/([^\s?#]+)", re.IGNORECASE)
_OJS_GALLEY_RE = re.compile(r"^(https?://[^?#]+/article/)view/(\d+)/(\d+)/?$", re.IGNORECASE)
_CITATION_PDF_RE = re.compile(
    r"""<meta[^>]+name=["']citation_pdf_url["'][^>]+content=["']([^"']+)["']""",
    re.IGNORECASE,
)
_CITATION_PDF_RE_ALT = re.compile(
    r"""<meta[^>]+content=["']([^"']+)["'][^>]+name=["']citation_pdf_url["']""",
    re.IGNORECASE,
)
_HREF_PDF_CANDIDATE_RE = re.compile(
    r"""href=["']([^"']+(?:/bitstream/[^"']+|/bitstreams/[^"']+/content|/article/download/[^"']+|/download/[^"']+|\.pdf(?:\?[^"']*)?))["']""",
    re.IGNORECASE,
)

MAX_REDIRECT_HOPS = 5
PREFERRED_METADATA_PREFIXES = ("oai_dc", "qdc", "oai_etdms", "dim", "mods", "xoai", "arXiv", "didl")

_oai_host_lock = Lock()
_oai_host_last_hit: dict[str, float] = {}

OFFICIAL_REFERENCE_ENDPOINTS: list[dict[str, str]] = [
    {
        "name": "arXiv Public OAI-PMH",
        "base_url": "https://oaipmh.arxiv.org/oai",
        "platform": "arxiv",
        "metadata_prefix": "oai_dc",
        "default_set": "cs",
        "note": "Endpoint OAI-PMH publik resmi arXiv.org untuk pengujian koneksi dan panen open-access.",
    },
    {
        "name": "DOAJ Public OAI-PMH",
        "base_url": "https://doaj.org/oai.article",
        "platform": "other",
        "metadata_prefix": "oai_dc",
        "default_set": "",
        "note": "Endpoint OAI-PMH publik resmi Directory of Open Access Journals (DOAJ).",
    },
]

OAI_ERROR_CATALOG: dict[str, tuple[str, str]] = {
    "badArgument": (
        "Parameter permintaan OAI-PMH tidak valid atau tidak lengkap.",
        "Periksa kembali URL dasar (pastikan tidak mengandung parameter ?verb=... ganda) serta nilai metadataPrefix dan setSpec.",
    ),
    "badVerb": (
        "Perintah (verb) OAI-PMH tidak dikenali oleh server.",
        "Pastikan URL benar-benar mengarah ke endpoint OAI-PMH 2.0, bukan halaman portal utama.",
    ),
    "badResumptionToken": (
        "Token paginasi (resumptionToken) sudah kedaluwarsa atau tidak valid.",
        "Sistem akan menghapus token lama dan memulai ulang paginasi secara bersih dari tanggal terakhir tanpa menghapus data yang sudah tersimpan.",
    ),
    "cannotDisseminateFormat": (
        "Format metadata yang diminta tidak didukung oleh repositori ini.",
        "Gunakan salah satu format metadata yang terdaftar pada hasil ListMetadataFormats (misalnya oai_dc, qdc, dim, atau oai_etdms).",
    ),
    "noRecordsMatch": (
        "Tidak ada rekaman yang cocok dengan filter tanggal atau koleksi (set) saat ini.",
        "Ini normal untuk repositori baru/kosong atau jika belum ada artikel baru sejak panen terakhir. Anda dapat menghapus filter set atau mengatur ulang tanggal panen.",
    ),
    "noSetHierarchy": (
        "Repositori ini tidak menyediakan hierarki koleksi (sets).",
        "Tidak perlu memilih koleksi tertentu; Anda dapat memanen seluruh repositori secara langsung.",
    ),
    "noMetadataFormats": (
        "Repositori tidak melaporkan format metadata yang tersedia.",
        "Hubungi pengelola repositori atau coba verifikasi kembali endpoint OAI-PMH.",
    ),
    "HTML_RESPONSE": (
        "Server mengembalikan halaman web HTML, bukan XML OAI-PMH 2.0.",
        "Gunakan tombol 'Deteksi Otomatis' atau arahkan URL ke path OAI yang benar: /server/oai/request (DSpace 7), /oai/request (DSpace lama), /index.php/{jurnal}/oai (OJS), atau /cgi/oai2 (EPrints).",
    ),
    "XML_PARSE_ERROR": (
        "Respons XML dari repositori rusak atau tidak sesuai standar OAI-PMH.",
        "Periksa apakah server repositori sedang mengalami gangguan atau mengembalikan pesan kesalahan non-XML.",
    ),
    "SSRF_BLOCKED": (
        "URL ditolak oleh pengaman SSRF karena mengarah ke alamat lokal/privat atau skema tidak diizinkan.",
        "Gunakan URL publik http:// atau https:// yang dapat diakses dari internet.",
    ),
    "INVALID_URL": (
        "Format URL endpoint tidak valid.",
        "Masukkan URL lengkap yang diawali http:// atau https://, contoh: https://repository.kampus.ac.id/cgi/oai2.",
    ),
    "HTTP_403": (
        "Akses ditolak oleh server repositori (HTTP 403 Forbidden).",
        "Server mungkin membatasi akses OAI-PMH, memerlukan whitelist IP institusi, atau dilindungi firewall/WAF.",
    ),
    "HTTP_404": (
        "Endpoint OAI-PMH tidak ditemukan pada URL tersebut (HTTP 404 Not Found).",
        "Gunakan 'Deteksi Otomatis' untuk mencoba path standar DSpace 7, DSpace lama, OJS, atau EPrints.",
    ),
    "HTTP_429": (
        "Server repositori membatasi laju permintaan (HTTP 429 Too Many Requests).",
        "Perbesar jeda antar permintaan (rate limit delay) pada pengaturan repositori lalu coba lanjutkan panen.",
    ),
    "HTTP_5XX": (
        "Server repositori mengalami gangguan internal (HTTP 5xx).",
        "Coba uji kembali beberapa saat lagi atau kurangi jumlah rekaman per sesi panen.",
    ),
    "TIMEOUT": (
        "Permintaan ke server repositori melebihi batas waktu (timeout).",
        "Periksa koneksi jaringan, tingkatkan batas waktu (timeout) pada pengaturan repositori, lalu gunakan tombol Lanjutkan.",
    ),
    "DNS_ERROR": (
        "Nama domain repositori tidak dapat ditemukan melalui DNS.",
        "Periksa kembali ejaan domain dan pastikan server kampus sedang aktif.",
    ),
    "CONNECTION_ERROR": (
        "Gagal terhubung ke server repositori.",
        "Pastikan URL benar, sertifikat SSL valid, dan server tidak sedang down.",
    ),
    "REDIRECT_LIMIT": (
        "Terlalu banyak pengalihan (redirect) saat mengakses endpoint.",
        "Masukkan langsung URL tujuan akhir setelah redirect.",
    ),
}


class OAIPMHProtocolError(ValueError):
    """Structured OAI-PMH / transport error carrying Bahasa Indonesia explanation & suggested fix."""

    def __init__(
        self,
        error_code: str,
        message: str | None = None,
        *,
        suggestion: str | None = None,
        http_status: int | None = None,
        raw_detail: str | None = None,
    ) -> None:
        default_msg, default_sug = OAI_ERROR_CATALOG.get(
            error_code,
            (
                f"Terjadi kesalahan OAI-PMH ({error_code}).",
                "Periksa kembali URL endpoint dan log aktivitas untuk detail teknis.",
            ),
        )
        self.error_code = error_code
        self.message = message or default_msg
        self.suggestion = suggestion or default_sug
        self.http_status = http_status
        self.raw_detail = raw_detail or self.message
        super().__init__(f"[{error_code}] {self.message}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "suggestion": self.suggestion,
            "http_status": self.http_status,
            "raw_detail": self.raw_detail,
        }


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def normalize_repo_type(raw: str | None) -> str:
    val = (raw or "").strip().lower()
    mapping = {
        "dspace7": "dspace7",
        "dspace 7": "dspace7",
        "dspace_7": "dspace7",
        "dspace": "dspace_legacy",
        "dspace_legacy": "dspace_legacy",
        "dspace lama": "dspace_legacy",
        "ojs": "ojs",
        "eprints": "eprints",
        "arxiv": "arxiv",
        "oai-pmh": "other",
        "oai_pmh": "other",
        "generic": "other",
        "other": "other",
    }
    return mapping.get(val, "other")


def platform_label(platform: str | None) -> str:
    return {
        "dspace7": "DSpace 7",
        "dspace_legacy": "DSpace Lama",
        "dspace": "DSpace",
        "ojs": "OJS",
        "eprints": "EPrints",
        "arxiv": "arXiv OAI-PMH",
        "other": "OAI-PMH Umum",
    }.get((platform or "").lower(), "OAI-PMH Umum")


def clean_oai_base_url(raw_url: str) -> tuple[str, bool]:
    """Return (cleaned_base_url, changed) without mutating user's input silently.

    Strips surrounding whitespace and OAI-PMH query verbs (?verb=Identify etc.) so the base URL
    can be cleanly reused for subsequent OAI requests.
    """
    trimmed = (raw_url or "").strip()
    if not trimmed:
        return "", False
    parsed = urlparse(trimmed)
    if not parsed.scheme:
        return trimmed, False
    q_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    oai_params = {"verb", "metadataprefix", "set", "from", "until", "resumptiontoken", "identifier"}
    kept = [(k, v) for k, v in q_pairs if k.lower() not in oai_params]
    new_query = "&".join(f"{k}={v}" for k, v in kept)
    cleaned = urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", new_query, ""))
    # Keep root slash only when path was empty; remove trailing ? if query stripped
    if not parsed.path and cleaned.endswith("/"):
        cleaned = cleaned[:-1]
    return cleaned, cleaned != trimmed


def detect_platform_from_url(url: str, identify_info: dict[str, str] | None = None) -> str:
    low = (url or "").lower()
    parsed = urlparse(low)
    path = parsed.path or ""
    host = parsed.hostname or ""

    if "arxiv.org" in host:
        return "arxiv"
    if "/server/oai/request" in path:
        return "dspace7"
    if "/dspace-oai/request" in path or "/oai/request" in path:
        return "dspace_legacy"
    if "/cgi/oai2" in path or "/cgi/oai" in path:
        return "eprints"
    if "/index.php/" in path and path.rstrip("/").endswith("/oai"):
        return "ojs"
    if re.search(r"/[^/]+/oai/?$", path):
        # Could be OJS /{journal}/oai or generic /oai
        if not path.rstrip("/").endswith("/server/oai"):
            return "ojs"

    if identify_info:
        blob = " ".join(str(v) for v in identify_info.values()).lower()
        if "dspace 7" in blob or "/server/oai/request" in blob:
            return "dspace7"
        if "dspace" in blob:
            return "dspace_legacy"
        if "eprints" in blob:
            return "eprints"
        if "open journal systems" in blob or "pkp" in blob or "ojs" in blob:
            return "ojs"
        if "arxiv" in blob:
            return "arxiv"

    return "other"


def suggest_oai_candidates(raw_url: str) -> list[dict[str, str]]:
    """Build ordered non-destructive OAI-PMH endpoint candidates from a user-supplied URL."""
    cleaned, _ = clean_oai_base_url(raw_url)
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return []

    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = (parsed.path or "").rstrip("/")
    seen: set[str] = set()
    candidates: list[dict[str, str]] = []

    def _add(url: str, platform_hint: str, reason: str) -> None:
        if url not in seen:
            seen.add(url)
            candidates.append({"url": url, "platform_hint": platform_hint, "reason": reason})

    # 1. Exact cleaned URL first
    if cleaned:
        _add(cleaned, detect_platform_from_url(cleaned), "URL yang dimasukkan pengguna")

    # 2. If user pasted an OJS journal landing URL (e.g. /index.php/alafaq or /alafaq)
    if path and not path.endswith(("/oai", "/oai2", "/request")):
        _add(f"{origin}{path}/oai", "ojs", "Pola OJS berdasarkan path jurnal")

    # 3. Standard academic platform endpoints
    _add(f"{origin}/server/oai/request", "dspace7", "Standar endpoint DSpace 7")
    _add(f"{origin}/oai/request", "dspace_legacy", "Standar endpoint DSpace lama")
    _add(f"{origin}/dspace-oai/request", "dspace_legacy", "Alternatif endpoint DSpace lama")
    _add(f"{origin}/cgi/oai2", "eprints", "Standar endpoint EPrints")
    _add(f"{origin}/index.php/index/oai", "ojs", "Standar endpoint OJS multi-jurnal")
    _add(f"{origin}/oai", "other", "Endpoint OAI-PMH umum")

    return candidates


def _respect_oai_delay(url: str, delay_sec: float) -> None:
    if delay_sec <= 0:
        return
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return
    with _oai_host_lock:
        now = time.monotonic()
        last = _oai_host_last_hit.get(host, 0.0)
        wait = delay_sec - (now - last)
        if wait > 0:
            time.sleep(min(wait, 5.0))
        _oai_host_last_hit[host] = time.monotonic()


def _is_pdf_candidate_url(url: str) -> bool:
    low = url.lower()
    path = urlparse(low).path or ""
    if path.endswith(".pdf") or ".pdf?" in low:
        return True
    if "/server/api/core/bitstreams/" in path and "/content" in path:
        return True
    if "/bitstream/" in path:
        return True
    if "/article/download/" in path:
        return True
    if "/pdf/" in path and ("arxiv.org" in low or "/download" in path):
        return True
    return False


def _derive_pdf_urls_from_landing(url: str) -> list[str]:
    """Derive direct open-access PDF URLs for well-known open repositories (e.g. arXiv)."""
    derived: list[str] = []
    m_arxiv = _ARXIV_ABS_RE.match(url.strip())
    if m_arxiv:
        arxiv_id = m_arxiv.group(1).strip("/")
        derived.append(f"https://arxiv.org/pdf/{arxiv_id}.pdf")
    return derived


@dataclass
class OAIRecord:
    identifier: str
    datestamp: str | None
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    doc_type: str | None = None
    subjects: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    pdf_urls: list[str] = field(default_factory=list)
    rights: str | None = None
    description: str | None = None
    deleted: bool = False
    set_specs: list[str] = field(default_factory=list)


class OAIPMHClient:
    """Standards-compliant OAI-PMH 2.0 client with defusedxml, SSRF-safe redirects, and structured errors."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        resolve_dns: bool = True,
        timeout_sec: float = 20.0,
        rate_limit_delay_sec: float = 0.0,
    ) -> None:
        self._external_client = client
        self.resolve_dns = resolve_dns
        self.timeout_sec = max(3.0, float(timeout_sec))
        self.rate_limit_delay_sec = max(0.0, float(rate_limit_delay_sec))

    def _safe_http_get(
        self,
        url: str,
        params: dict[str, str] | None = None,
    ) -> tuple[httpx.Response, str, list[str]]:
        """Perform HTTP GET with hop-by-hop SSRF validation across redirects."""
        try:
            current_url = validate_public_url(url, resolve_dns=self.resolve_dns)
        except SSRFError as exc:
            err_msg = str(exc)
            if "DNS" in err_msg:
                raise OAIPMHProtocolError("DNS_ERROR", err_msg, raw_detail=err_msg) from exc
            if "Skema URL" in err_msg or "Hostname URL" in err_msg:
                raise OAIPMHProtocolError("INVALID_URL", err_msg, raw_detail=err_msg) from exc
            raise OAIPMHProtocolError("SSRF_BLOCKED", err_msg, raw_detail=err_msg) from exc

        ua = f"NaskahGuard-OAI/1.0 (mailto:{get_settings().CONTACT_EMAIL})"
        headers = {
            "User-Agent": ua,
            "Accept": "application/xml, text/xml;q=0.9, */*;q=0.5",
        }
        client = self._external_client or httpx.Client(timeout=self.timeout_sec)
        redirect_chain: list[str] = []
        current_params = params

        try:
            for _hop in range(MAX_REDIRECT_HOPS + 1):
                if self._external_client is None and self.rate_limit_delay_sec > 0:
                    _respect_oai_delay(current_url, self.rate_limit_delay_sec)

                try:
                    resp = client.get(
                        current_url,
                        params=current_params,
                        headers=headers,
                        follow_redirects=False,
                        timeout=self.timeout_sec,
                    )
                except httpx.TimeoutException as exc:
                    raise OAIPMHProtocolError("TIMEOUT", raw_detail=str(exc)) from exc
                except httpx.ConnectError as exc:
                    low = str(exc).lower()
                    if "getaddrinfo" in low or "name or service not known" in low or "nodename" in low:
                        raise OAIPMHProtocolError("DNS_ERROR", raw_detail=str(exc)) from exc
                    raise OAIPMHProtocolError("CONNECTION_ERROR", raw_detail=str(exc)) from exc
                except httpx.HTTPError as exc:
                    raise OAIPMHProtocolError("CONNECTION_ERROR", raw_detail=str(exc)) from exc

                if resp.status_code in {301, 302, 303, 307, 308}:
                    location = resp.headers.get("location")
                    if not location:
                        break
                    next_url = urljoin(current_url, location.strip())
                    # Re-validate redirect target against SSRF!
                    try:
                        next_url = validate_public_url(next_url, resolve_dns=self.resolve_dns)
                    except SSRFError as exc:
                        raise OAIPMHProtocolError(
                            "SSRF_BLOCKED",
                            f"Redirect diarahkan ke alamat terlarang: {exc}",
                            http_status=resp.status_code,
                            raw_detail=str(exc),
                        ) from exc
                    redirect_chain.append(f"{resp.status_code} -> {next_url}")
                    current_url = next_url
                    # Preserve query params ONLY if the redirect Location did not already carry them
                    if urlparse(next_url).query:
                        current_params = None
                    continue

                return resp, current_url, redirect_chain

            raise OAIPMHProtocolError("REDIRECT_LIMIT", http_status=310)
        finally:
            if self._external_client is None:
                client.close()

    def _get_with_meta(
        self,
        base_url: str,
        params: dict[str, str],
    ) -> tuple[ET.Element, int, str, list[str]]:
        resp, final_url, redirect_chain = self._safe_http_get(base_url, params=params)
        status_code = resp.status_code

        if status_code == 403:
            raise OAIPMHProtocolError("HTTP_403", http_status=403, raw_detail=resp.text[:300])
        if status_code == 404:
            raise OAIPMHProtocolError("HTTP_404", http_status=404, raw_detail=resp.text[:300])
        if status_code == 429:
            raise OAIPMHProtocolError("HTTP_429", http_status=429, raw_detail=resp.text[:300])
        if status_code >= 500:
            raise OAIPMHProtocolError(
                "HTTP_5XX",
                f"Server repositori mengembalikan kesalahan HTTP {status_code}.",
                http_status=status_code,
                raw_detail=resp.text[:300],
            )
        if status_code >= 400:
            raise OAIPMHProtocolError(
                "HTTP_ERROR",
                f"Server repositori menolak permintaan (HTTP {status_code}).",
                http_status=status_code,
                raw_detail=resp.text[:300],
            )

        body = (resp.text or "").lstrip("\ufeff \t\r\n")
        content_type = (resp.headers.get("content-type") or "").lower()
        low_head = body[:400].lower()

        if (
            "text/html" in content_type
            or low_head.startswith("<!doctype html")
            or low_head.startswith("<html")
            or ("<head>" in low_head and "<oai-pmh" not in low_head)
        ):
            raise OAIPMHProtocolError(
                "HTML_RESPONSE",
                http_status=status_code,
                raw_detail=f"Content-Type: {content_type}; preview: {body[:160]}",
            )

        if not body:
            raise OAIPMHProtocolError(
                "XML_PARSE_ERROR",
                "Server mengembalikan respons kosong tanpa XML OAI-PMH.",
                http_status=status_code,
            )

        try:
            root = ET.fromstring(body)
        except Exception as exc:
            raise OAIPMHProtocolError(
                "XML_PARSE_ERROR",
                f"Respons tidak dapat dibaca sebagai XML OAI-PMH yang valid: {exc}",
                http_status=status_code,
                raw_detail=body[:240],
            ) from exc

        if _local(root.tag).lower() != "oai-pmh":
            raise OAIPMHProtocolError(
                "XML_PARSE_ERROR",
                f"Elemen akar XML adalah <{_local(root.tag)}>, bukan <OAI-PMH>.",
                suggestion="Pastikan URL mengarah langsung ke endpoint OAI-PMH 2.0.",
                http_status=status_code,
            )

        for child in root:
            if _local(child.tag) == "error":
                code = child.attrib.get("code", "unknown").strip() or "unknown"
                server_msg = (child.text or "").strip()
                default_msg, default_sug = OAI_ERROR_CATALOG.get(
                    code,
                    (f"OAI-PMH error ({code}): {server_msg}", "Periksa kembali konfigurasi endpoint repositori."),
                )
                full_msg = f"{default_msg} ({server_msg})" if server_msg else default_msg
                raise OAIPMHProtocolError(
                    code,
                    full_msg,
                    suggestion=default_sug,
                    http_status=status_code,
                    raw_detail=server_msg or code,
                )

        return root, status_code, final_url, redirect_chain

    def _get(self, base_url: str, params: dict[str, str]) -> ET.Element:
        root, _sc, _final_url, _redirects = self._get_with_meta(base_url, params)
        return root

    def identify(self, base_url: str) -> dict[str, str]:
        root = self._get(base_url, {"verb": "Identify"})
        return self._parse_identify(root)

    @staticmethod
    def _parse_identify(root: ET.Element) -> dict[str, str]:
        info: dict[str, str] = {}
        wanted = {
            "repositoryName",
            "baseURL",
            "protocolVersion",
            "earliestDatestamp",
            "deletedRecord",
            "granularity",
            "adminEmail",
            "description",
        }
        for el in root.iter():
            ln = _local(el.tag)
            if ln in wanted and el.text and el.text.strip():
                if ln not in info:
                    info[ln] = el.text.strip()
        return info

    def list_metadata_formats(self, base_url: str) -> list[str]:
        root = self._get(base_url, {"verb": "ListMetadataFormats"})
        return self._parse_metadata_formats(root)

    @staticmethod
    def _parse_metadata_formats(root: ET.Element) -> list[str]:
        formats: list[str] = []
        for el in root.iter():
            if _local(el.tag) == "metadataPrefix" and el.text:
                prefix = el.text.strip()
                if prefix and prefix not in formats:
                    formats.append(prefix)
        return formats

    def list_sets(self, base_url: str, *, max_sets: int = 100) -> list[dict[str, str]]:
        root = self._get(base_url, {"verb": "ListSets"})
        return self._parse_sets(root, max_sets=max_sets)

    @staticmethod
    def _parse_sets(root: ET.Element, *, max_sets: int = 100) -> list[dict[str, str]]:
        sets: list[dict[str, str]] = []
        seen: set[str] = set()
        for s_el in root.iter():
            if _local(s_el.tag) == "set":
                spec = ""
                name = ""
                for c in s_el:
                    cln = _local(c.tag)
                    if cln == "setSpec" and c.text:
                        spec = c.text.strip()
                    elif cln == "setName" and c.text:
                        name = c.text.strip()
                if spec and spec not in seen:
                    seen.add(spec)
                    sets.append({"setSpec": spec, "setName": name or spec})
                    if len(sets) >= max_sets:
                        break
        return sets

    @staticmethod
    def _parse_record(rec_el: ET.Element, *, include_deleted: bool = False) -> OAIRecord | None:
        identifier = ""
        datestamp = None
        deleted = False
        set_specs: list[str] = []
        titles: list[str] = []
        authors: list[str] = []
        dates: list[str] = []
        raw_links: list[str] = []
        rights: list[str] = []
        descriptions: list[str] = []
        doc_types: list[str] = []
        subjects: list[str] = []

        # Parse header cleanly first
        header_el = None
        metadata_el = None
        for child in rec_el:
            cln = _local(child.tag)
            if cln == "header":
                header_el = child
            elif cln == "metadata":
                metadata_el = child

        if header_el is not None:
            if header_el.attrib.get("status", "").lower() == "deleted":
                deleted = True
            for h_el in header_el.iter():
                hln = _local(h_el.tag)
                if hln == "identifier" and h_el.text and not identifier:
                    identifier = h_el.text.strip()
                elif hln == "datestamp" and h_el.text and datestamp is None:
                    datestamp = h_el.text.strip()
                elif hln == "setSpec" and h_el.text:
                    sp = h_el.text.strip()
                    if sp and sp not in set_specs:
                        set_specs.append(sp)

        if not identifier:
            return None

        if deleted:
            if include_deleted:
                return OAIRecord(
                    identifier=identifier,
                    datestamp=datestamp,
                    title=identifier,
                    deleted=True,
                    set_specs=set_specs,
                )
            return None

        if metadata_el is not None:
            for el in metadata_el.iter():
                ln = _local(el.tag).lower()
                text_val = (el.text or "").strip()

                # Capture attribute-based links used in DIDL, MODS, XOAI, EPrints
                for attr_name in ("ref", "href", "url"):
                    attr_val = (el.attrib.get(attr_name) or "").strip()
                    if attr_val.startswith(("http://", "https://")):
                        raw_links.append(attr_val)

                # Handle DSpace DIM (<dim:field mdschema="dc" element="title">...)
                if ln == "field" and el.attrib.get("element"):
                    dim_elem = el.attrib.get("element", "").lower()
                    dim_qual = el.attrib.get("qualifier", "").lower()
                    if text_val:
                        if dim_elem == "title":
                            titles.append(" ".join(text_val.split()))
                        elif dim_elem in {"contributor", "creator"} and dim_qual in {"", "author"}:
                            authors.append(" ".join(text_val.split()))
                        elif dim_elem == "date":
                            dates.append(text_val)
                        elif dim_elem in {"identifier", "relation"}:
                            raw_links.append(text_val)
                        elif dim_elem == "rights":
                            rights.append(text_val)
                        elif dim_elem == "description":
                            descriptions.append(" ".join(text_val.split()))
                        elif dim_elem == "type":
                            doc_types.append(" ".join(text_val.split()))
                        elif dim_elem == "subject":
                            subjects.append(" ".join(text_val.split()))
                    continue

                if not text_val:
                    continue

                if ln in {"title", "titleinfo"}:
                    titles.append(" ".join(text_val.split()))
                elif ln in {"creator", "author", "keyname"}:
                    authors.append(" ".join(text_val.split()))
                elif ln in {"date", "created", "issued", "dateissued"}:
                    dates.append(text_val)
                elif ln in {"identifier", "relation", "url", "id", "uri"}:
                    raw_links.append(text_val)
                elif ln in {"rights", "license", "accesscondition"}:
                    rights.append(text_val)
                elif ln in {"description", "abstract"}:
                    descriptions.append(" ".join(text_val.split()))
                elif ln in {"type", "genre"}:
                    doc_types.append(" ".join(text_val.split()))
                elif ln in {"subject", "topic"}:
                    subjects.append(" ".join(text_val.split()))

        year = None
        for d in dates:
            m_yr = re.search(r"\b(19\d{2}|20\d{2})\b", d)
            if m_yr:
                year = int(m_yr.group(1))
                break

        doi = None
        urls: list[str] = []
        pdf_urls: list[str] = []

        # Also check oai_identifier for arXiv IDs (e.g., oai:arXiv.org:2301.00001)
        m_oai_arxiv = re.match(r"^oai:arxiv\.org:([^\s]+)$", identifier, re.IGNORECASE)
        if m_oai_arxiv:
            arxiv_id = m_oai_arxiv.group(1)
            raw_links.append(f"https://arxiv.org/abs/{arxiv_id}")
            raw_links.append(f"https://arxiv.org/pdf/{arxiv_id}.pdf")

        for val in raw_links:
            m_doi = _DOI_RE.search(val)
            if m_doi and not doi:
                doi = m_doi.group(1).rstrip(".,;)")
            if val.startswith(("http://", "https://")):
                if val not in urls:
                    urls.append(val)
                if _is_pdf_candidate_url(val):
                    if val not in pdf_urls:
                        pdf_urls.append(val)
                for derived in _derive_pdf_urls_from_landing(val):
                    if derived not in pdf_urls:
                        pdf_urls.append(derived)

        return OAIRecord(
            identifier=identifier,
            datestamp=datestamp,
            title=(titles[0] if titles else identifier)[:500],
            authors=authors[:10],
            year=year,
            doi=doi,
            doc_type=doc_types[0][:120] if doc_types else None,
            subjects=subjects[:10],
            urls=urls,
            pdf_urls=pdf_urls,
            rights=rights[0][:250] if rights else None,
            description=descriptions[0][:1000] if descriptions else None,
            deleted=False,
            set_specs=set_specs,
        )

    def list_records(
        self,
        base_url: str,
        *,
        metadata_prefix: str = "oai_dc",
        from_datestamp: str | None = None,
        until_datestamp: str | None = None,
        set_spec: str | None = None,
        resumption_token: str | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[OAIRecord], str | None]:
        params: dict[str, str] = {"verb": "ListRecords"}
        if resumption_token:
            params["resumptionToken"] = resumption_token
        else:
            params["metadataPrefix"] = metadata_prefix
            if from_datestamp:
                params["from"] = from_datestamp
            if until_datestamp:
                params["until"] = until_datestamp
            if set_spec:
                params["set"] = set_spec

        root = self._get(base_url, params)
        records: list[OAIRecord] = []
        next_token: str | None = None
        for el in root.iter():
            ln = _local(el.tag)
            if ln == "record":
                parsed = self._parse_record(el, include_deleted=include_deleted)
                if parsed is not None:
                    records.append(parsed)
            elif ln == "resumptionToken":
                tok = (el.text or "").strip()
                next_token = tok or None
        return records, next_token

    def get_record(self, base_url: str, identifier: str, metadata_prefix: str = "oai_dc") -> OAIRecord | None:
        root = self._get(base_url, {"verb": "GetRecord", "identifier": identifier, "metadataPrefix": metadata_prefix})
        for el in root.iter():
            if _local(el.tag) == "record":
                return self._parse_record(el, include_deleted=False)
        return None


def negotiate_metadata_prefix(preferred: str | None, supported: list[str]) -> str:
    if not supported:
        return (preferred or "oai_dc").strip() or "oai_dc"
    if preferred and preferred in supported:
        return preferred
    for cand in PREFERRED_METADATA_PREFIXES:
        if cand in supported:
            return cand
    return supported[0]


def auto_detect_oai_endpoint(
    raw_url: str,
    *,
    client: httpx.Client | None = None,
    resolve_dns: bool = True,
    timeout_sec: float = 12.0,
) -> dict[str, Any]:
    """Probe standard DSpace 7, legacy DSpace, OJS, and EPrints OAI-PMH paths without mutating DB."""
    candidates = suggest_oai_candidates(raw_url)
    if not candidates:
        return {
            "found": False,
            "input_url": raw_url,
            "detected_url": None,
            "platform_detected": "other",
            "identified_name": None,
            "attempts": [],
            "message": "Format URL tidak valid. Pastikan URL diawali http:// atau https://.",
        }

    oai = OAIPMHClient(client=client, resolve_dns=resolve_dns, timeout_sec=timeout_sec, rate_limit_delay_sec=0.0)
    attempts: list[dict[str, Any]] = []

    for cand in candidates[:7]:
        cand_url = cand["url"]
        try:
            root, status_code, final_url, redirects = oai._get_with_meta(cand_url, {"verb": "Identify"})
            ident = oai._parse_identify(root)
            effective_url, _ = clean_oai_base_url(ident.get("baseURL") or final_url)
            # Only adopt identify baseURL if it passes SSRF check; otherwise keep verified final_url
            try:
                validate_public_url(effective_url, resolve_dns=False)
            except SSRFError:
                effective_url = final_url
            platform = detect_platform_from_url(effective_url, ident)
            attempts.append(
                {
                    "url": cand_url,
                    "status": "PASS",
                    "http_status": status_code,
                    "platform_hint": platform,
                    "message": f"Berhasil teridentifikasi sebagai {ident.get('repositoryName') or 'Endpoint OAI-PMH'}.",
                    "redirects": redirects,
                }
            )
            return {
                "found": True,
                "input_url": raw_url,
                "detected_url": final_url,
                "identified_base_url": ident.get("baseURL"),
                "platform_detected": platform,
                "platform_label": platform_label(platform),
                "identified_name": ident.get("repositoryName"),
                "identify": ident,
                "attempts": attempts,
                "message": f"Endpoint OAI-PMH ditemukan ({platform_label(platform)}): {final_url}",
            }
        except OAIPMHProtocolError as exc:
            attempts.append(
                {
                    "url": cand_url,
                    "status": "FAIL",
                    "http_status": exc.http_status,
                    "error_code": exc.error_code,
                    "message": exc.message,
                }
            )
            # If SSRF or DNS failed on the origin host itself, stop probing other paths on the same host
            if exc.error_code in {"SSRF_BLOCKED", "DNS_ERROR", "INVALID_URL"}:
                break

    return {
        "found": False,
        "input_url": raw_url,
        "detected_url": None,
        "platform_detected": detect_platform_from_url(raw_url),
        "identified_name": None,
        "attempts": attempts,
        "message": "Tidak ditemukan endpoint OAI-PMH aktif pada jalur standar (DSpace 7, DSpace lama, OJS, EPrints). Anda tetap dapat memasukkan URL endpoint manual.",
    }


def _make_stage(
    step: int,
    key: str,
    title: str,
    status: str,
    *,
    http_status: int | None = None,
    error_code: str | None = None,
    message: str = "",
    suggestion: str | None = None,
    duration_ms: int = 0,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "step": step,
        "key": key,
        "title": title,
        "status": status,  # PASS | WARN | FAIL | SKIP
        "http_status": http_status,
        "error_code": error_code,
        "message": message,
        "suggestion": suggestion,
        "duration_ms": duration_ms,
        "data": data or {},
    }


def run_connection_wizard(
    base_url: str,
    *,
    metadata_prefix: str | None = "oai_dc",
    set_spec: str | None = None,
    probe_pdf: bool = False,
    client: httpx.Client | None = None,
    resolve_dns: bool = True,
    timeout_sec: float = 20.0,
) -> dict[str, Any]:
    """Run the full 8-stage OAI-PMH Connection Test Wizard.

    Stages:
      1. URL validation
      2. HTTP connectivity
      3. OAI-PMH Identify
      4. ListMetadataFormats
      5. ListSets
      6. Test ListRecords
      7. Metadata validation
      8. Full-text URL discovery
    """
    stages: list[dict[str, Any]] = []
    cleaned_url, url_cleaned_changed = clean_oai_base_url(base_url)
    effective_url = cleaned_url or (base_url or "").strip()
    oai = OAIPMHClient(client=client, resolve_dns=resolve_dns, timeout_sec=timeout_sec, rate_limit_delay_sec=0.0)

    platform_detected = detect_platform_from_url(effective_url)
    identify_info: dict[str, str] = {}
    supported_formats: list[str] = []
    available_sets: list[dict[str, str]] = []
    recommended_prefix = (metadata_prefix or "oai_dc").strip() or "oai_dc"
    sample_records: list[dict[str, Any]] = []

    def _skip_remaining(from_step: int, reason: str) -> None:
        defs = [
            (2, "http_connectivity", "Konektivitas HTTP"),
            (3, "identify", "OAI-PMH Identify"),
            (4, "list_metadata_formats", "ListMetadataFormats"),
            (5, "list_sets", "ListSets (Koleksi)"),
            (6, "test_list_records", "Uji ListRecords"),
            (7, "metadata_validation", "Validasi Metadata"),
            (8, "fulltext_url_discovery", "Deteksi URL Full-Text"),
        ]
        for st_num, st_key, st_title in defs:
            if st_num >= from_step:
                stages.append(_make_stage(st_num, st_key, st_title, "SKIP", message=reason))

    # --- Stage 1: URL Validation ---
    t0 = time.monotonic()
    try:
        validated = validate_public_url(effective_url, resolve_dns=resolve_dns)
        effective_url = validated
        msg = f"URL publik valid ({platform_label(platform_detected)})."
        if url_cleaned_changed:
            msg += f" Parameter query OAI sementara dibersihkan menjadi {effective_url} untuk pengujian."
        stages.append(
            _make_stage(
                1,
                "url_validation",
                "Validasi URL & Keamanan SSRF",
                "PASS",
                message=msg,
                duration_ms=int((time.monotonic() - t0) * 1000),
                data={
                    "input_url": base_url,
                    "tested_url": effective_url,
                    "url_cleaned_changed": url_cleaned_changed,
                    "platform_hint": platform_detected,
                },
            )
        )
    except SSRFError as exc:
        err_str = str(exc)
        err_code = "DNS_ERROR" if "DNS" in err_str else ("INVALID_URL" if "Skema" in err_str or "Hostname" in err_str else "SSRF_BLOCKED")
        _, sug = OAI_ERROR_CATALOG.get(err_code, ("", "Periksa kembali format dan domain URL."))
        stages.append(
            _make_stage(
                1,
                "url_validation",
                "Validasi URL & Keamanan SSRF",
                "FAIL",
                error_code=err_code,
                message=err_str,
                suggestion=sug,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        )
        _skip_remaining(2, "Dilewati karena validasi URL gagal.")
        return _finalize_wizard_report(
            base_url, effective_url, platform_detected, identify_info, recommended_prefix,
            supported_formats, available_sets, sample_records, stages
        )

    # --- Stage 2 & 3: HTTP Connectivity + OAI-PMH Identify ---
    t1 = time.monotonic()
    try:
        root_ident, http_status, final_url, redirect_chain = oai._get_with_meta(effective_url, {"verb": "Identify"})
        dur_ms = int((time.monotonic() - t1) * 1000)
        cleaned_final, _ = clean_oai_base_url(final_url)
        effective_url = cleaned_final or final_url
        redir_note = f" (melalui {len(redirect_chain)} redirect aman)" if redirect_chain else ""
        stages.append(
            _make_stage(
                2,
                "http_connectivity",
                "Konektivitas HTTP",
                "PASS",
                http_status=http_status,
                message=f"Server merespons HTTP {http_status}{redir_note}.",
                duration_ms=dur_ms,
                data={"final_url": effective_url, "redirects": redirect_chain},
            )
        )
        identify_info = oai._parse_identify(root_ident)
        platform_detected = detect_platform_from_url(effective_url, identify_info)
        repo_name = identify_info.get("repositoryName") or "Tanpa Nama"
        proto_v = identify_info.get("protocolVersion") or "2.0"
        stages.append(
            _make_stage(
                3,
                "identify",
                "OAI-PMH Identify",
                "PASS",
                http_status=http_status,
                message=f"Teridentifikasi: {repo_name} (OAI-PMH v{proto_v}, platform {platform_label(platform_detected)}).",
                duration_ms=dur_ms,
                data={"identify": identify_info, "platform_detected": platform_detected},
            )
        )
    except OAIPMHProtocolError as exc:
        dur_ms = int((time.monotonic() - t1) * 1000)
        if (
            exc.http_status is not None
            and 200 <= exc.http_status < 300
            and exc.error_code not in {"SSRF_BLOCKED", "REDIRECT_LIMIT"}
        ):
            # HTTP reachable (2xx), but XML / OAI-PMH Identify failed (e.g., HTML_RESPONSE)
            stages.append(
                _make_stage(
                    2,
                    "http_connectivity",
                    "Konektivitas HTTP",
                    "PASS",
                    http_status=exc.http_status,
                    message=f"Server dapat dihubungi (HTTP {exc.http_status}).",
                    duration_ms=dur_ms,
                )
            )
            stages.append(
                _make_stage(
                    3,
                    "identify",
                    "OAI-PMH Identify",
                    "FAIL",
                    http_status=exc.http_status,
                    error_code=exc.error_code,
                    message=exc.message,
                    suggestion=exc.suggestion,
                    duration_ms=dur_ms,
                )
            )
            _skip_remaining(4, "Dilewati karena verifikasi Identify OAI-PMH gagal.")
        else:
            stages.append(
                _make_stage(
                    2,
                    "http_connectivity",
                    "Konektivitas HTTP",
                    "FAIL",
                    http_status=exc.http_status,
                    error_code=exc.error_code,
                    message=exc.message,
                    suggestion=exc.suggestion,
                    duration_ms=dur_ms,
                )
            )
            _skip_remaining(3, "Dilewati karena konektivitas HTTP gagal.")
        return _finalize_wizard_report(
            base_url, effective_url, platform_detected, identify_info, recommended_prefix,
            supported_formats, available_sets, sample_records, stages
        )

    # --- Stage 4: ListMetadataFormats ---
    t4 = time.monotonic()
    try:
        root_fmt, sc4, _, _ = oai._get_with_meta(effective_url, {"verb": "ListMetadataFormats"})
        supported_formats = oai._parse_metadata_formats(root_fmt)
        recommended_prefix = negotiate_metadata_prefix(metadata_prefix, supported_formats)
        if metadata_prefix and supported_formats and metadata_prefix not in supported_formats:
            stages.append(
                _make_stage(
                    4,
                    "list_metadata_formats",
                    "ListMetadataFormats",
                    "WARN",
                    http_status=sc4,
                    error_code="cannotDisseminateFormat",
                    message=f"Format '{metadata_prefix}' tidak tersedia. Format didukung: {', '.join(supported_formats)}. Dialihkan otomatis ke '{recommended_prefix}'.",
                    suggestion=f"Simpan format metadata '{recommended_prefix}' agar panen berjalan lancar.",
                    duration_ms=int((time.monotonic() - t4) * 1000),
                    data={"formats": supported_formats, "recommended_prefix": recommended_prefix},
                )
            )
        else:
            stages.append(
                _make_stage(
                    4,
                    "list_metadata_formats",
                    "ListMetadataFormats",
                    "PASS",
                    http_status=sc4,
                    message=f"Ditemukan {len(supported_formats)} format metadata ({', '.join(supported_formats[:6])}). Menggunakan '{recommended_prefix}'.",
                    duration_ms=int((time.monotonic() - t4) * 1000),
                    data={"formats": supported_formats, "recommended_prefix": recommended_prefix},
                )
            )
    except OAIPMHProtocolError as exc:
        stages.append(
            _make_stage(
                4,
                "list_metadata_formats",
                "ListMetadataFormats",
                "FAIL",
                http_status=exc.http_status,
                error_code=exc.error_code,
                message=exc.message,
                suggestion=exc.suggestion,
                duration_ms=int((time.monotonic() - t4) * 1000),
            )
        )

    # --- Stage 5: ListSets ---
    t5 = time.monotonic()
    try:
        root_sets, sc5, _, _ = oai._get_with_meta(effective_url, {"verb": "ListSets"})
        available_sets = oai._parse_sets(root_sets, max_sets=100)
        stages.append(
            _make_stage(
                5,
                "list_sets",
                "ListSets (Koleksi)",
                "PASS",
                http_status=sc5,
                message=f"Ditemukan {len(available_sets)} koleksi/set yang dapat dipilih.",
                duration_ms=int((time.monotonic() - t5) * 1000),
                data={"sets_count": len(available_sets), "sample_sets": available_sets[:10]},
            )
        )
    except OAIPMHProtocolError as exc:
        if exc.error_code == "noSetHierarchy":
            stages.append(
                _make_stage(
                    5,
                    "list_sets",
                    "ListSets (Koleksi)",
                    "WARN",
                    http_status=exc.http_status,
                    error_code=exc.error_code,
                    message=exc.message,
                    suggestion=exc.suggestion,
                    duration_ms=int((time.monotonic() - t5) * 1000),
                    data={"sets_count": 0},
                )
            )
        else:
            stages.append(
                _make_stage(
                    5,
                    "list_sets",
                    "ListSets (Koleksi)",
                    "WARN",
                    http_status=exc.http_status,
                    error_code=exc.error_code,
                    message=exc.message,
                    suggestion=exc.suggestion,
                    duration_ms=int((time.monotonic() - t5) * 1000),
                )
            )

    # --- Stage 6: Test ListRecords ---
    t6 = time.monotonic()
    parsed_records: list[OAIRecord] = []
    deleted_count = 0
    has_resumption_token = False
    try:
        params6: dict[str, str] = {"verb": "ListRecords", "metadataPrefix": recommended_prefix}
        if set_spec:
            params6["set"] = set_spec
        root_rec, sc6, _, _ = oai._get_with_meta(effective_url, params6)
        for el in root_rec.iter():
            ln = _local(el.tag)
            if ln == "record":
                rec = oai._parse_record(el, include_deleted=True)
                if rec is not None:
                    if rec.deleted:
                        deleted_count += 1
                    else:
                        parsed_records.append(rec)
            elif ln == "resumptionToken" and (el.text or "").strip():
                has_resumption_token = True
        stages.append(
            _make_stage(
                6,
                "test_list_records",
                "Uji ListRecords",
                "PASS" if parsed_records else "WARN",
                http_status=sc6,
                message=(
                    f"Berhasil mengambil {len(parsed_records)} rekaman aktif"
                    + (f" ({deleted_count} dihapus)" if deleted_count else "")
                    + (" dengan dukungan paginasi resumptionToken." if has_resumption_token else ".")
                ),
                suggestion=None if parsed_records else "Seluruh entri pada halaman pertama berstatus dihapus (deleted).",
                duration_ms=int((time.monotonic() - t6) * 1000),
                data={
                    "active_records": len(parsed_records),
                    "deleted_records": deleted_count,
                    "has_resumption_token": has_resumption_token,
                    "metadata_prefix_used": recommended_prefix,
                },
            )
        )
    except OAIPMHProtocolError as exc:
        if exc.error_code == "noRecordsMatch":
            stages.append(
                _make_stage(
                    6,
                    "test_list_records",
                    "Uji ListRecords",
                    "WARN",
                    http_status=exc.http_status,
                    error_code=exc.error_code,
                    message=exc.message,
                    suggestion=exc.suggestion,
                    duration_ms=int((time.monotonic() - t6) * 1000),
                    data={"active_records": 0},
                )
            )
            stages.append(
                _make_stage(
                    7,
                    "metadata_validation",
                    "Validasi Metadata",
                    "WARN",
                    message="Belum ada rekaman metadata untuk divalidasi pada filter saat ini.",
                )
            )
            stages.append(
                _make_stage(
                    8,
                    "fulltext_url_discovery",
                    "Deteksi URL Full-Text",
                    "WARN",
                    message="Belum ada rekaman untuk diperiksa ketersediaan URL full-text.",
                )
            )
            return _finalize_wizard_report(
                base_url, effective_url, platform_detected, identify_info, recommended_prefix,
                supported_formats, available_sets, sample_records, stages
            )
        stages.append(
            _make_stage(
                6,
                "test_list_records",
                "Uji ListRecords",
                "FAIL",
                http_status=exc.http_status,
                error_code=exc.error_code,
                message=exc.message,
                suggestion=exc.suggestion,
                duration_ms=int((time.monotonic() - t6) * 1000),
            )
        )
        _skip_remaining(7, "Dilewati karena uji ListRecords gagal.")
        return _finalize_wizard_report(
            base_url, effective_url, platform_detected, identify_info, recommended_prefix,
            supported_formats, available_sets, sample_records, stages
        )

    # --- Stage 7: Metadata Validation & Sample Preview ---
    t7 = time.monotonic()
    with_title = sum(1 for r in parsed_records if r.title and r.title != r.identifier)
    with_authors = sum(1 for r in parsed_records if r.authors)
    with_year = sum(1 for r in parsed_records if r.year is not None)
    with_doi = sum(1 for r in parsed_records if r.doi)

    for rec in parsed_records[:5]:
        sample_records.append(
            {
                "identifier": rec.identifier,
                "datestamp": rec.datestamp,
                "title": rec.title,
                "authors": rec.authors,
                "year": rec.year,
                "doi": rec.doi,
                "rights": rec.rights,
                "urls": rec.urls[:3],
                "pdf_urls": rec.pdf_urls[:3],
                "set_specs": rec.set_specs[:5],
            }
        )

    meta_ok = len(parsed_records) > 0 and with_title > 0
    stages.append(
        _make_stage(
            7,
            "metadata_validation",
            "Validasi Metadata",
            "PASS" if meta_ok else "WARN",
            message=(
                f"Dari {len(parsed_records)} sampel: {with_title} memiliki judul, "
                f"{with_authors} penulis, {with_year} tahun terbit, {with_doi} DOI."
            ),
            suggestion=None if meta_ok else "Metadata judul kosong pada sampel awal; periksa format metadata lain.",
            duration_ms=int((time.monotonic() - t7) * 1000),
            data={
                "checked": len(parsed_records),
                "with_title": with_title,
                "with_authors": with_authors,
                "with_year": with_year,
                "with_doi": with_doi,
            },
        )
    )

    # --- Stage 8: Full-Text URL Discovery ---
    t8 = time.monotonic()
    with_pdf = [r for r in parsed_records if r.pdf_urls]
    with_landing = [r for r in parsed_records if r.urls]
    probed_status: int | None = None
    probe_note = ""

    if probe_pdf and with_pdf:
        first_pdf = with_pdf[0].pdf_urls[0]
        try:
            resp_probe, _final_pdf, _ = oai._safe_http_get(first_pdf)
            probed_status = resp_probe.status_code
            if 200 <= resp_probe.status_code < 300:
                probe_note = f" Sampel PDF dapat diakses langsung (HTTP {resp_probe.status_code})."
            else:
                probe_note = f" Sampel PDF merespons HTTP {resp_probe.status_code} (mungkin perlu izin/akses terbatas)."
        except OAIPMHProtocolError as exc:
            probe_note = f" Uji akses sampel PDF gagal ({exc.error_code})."

    if with_pdf:
        stages.append(
            _make_stage(
                8,
                "fulltext_url_discovery",
                "Deteksi URL Full-Text",
                "PASS",
                http_status=probed_status,
                message=f"Ditemukan URL PDF langsung pada {len(with_pdf)} dari {len(parsed_records)} sampel rekaman.{probe_note}",
                duration_ms=int((time.monotonic() - t8) * 1000),
                data={
                    "records_with_pdf_url": len(with_pdf),
                    "records_with_landing_url": len(with_landing),
                    "sample_pdf_urls": [r.pdf_urls[0] for r in with_pdf[:3]],
                },
            )
        )
    elif with_landing:
        stages.append(
            _make_stage(
                8,
                "fulltext_url_discovery",
                "Deteksi URL Full-Text",
                "WARN",
                message=(
                    f"Tidak ada tautan .pdf langsung di XML OAI, namun ditemukan {len(with_landing)} URL halaman artikel. "
                    "Saat panen, NaskahGuard akan mencoba mendeteksi tautan PDF publik (citation_pdf_url) secara otomatis."
                ),
                suggestion="Metadata tetap dapat disimpan, dan hanya dokumen yang benar-benar memiliki full-text publik yang akan diindeks ke korpus pembanding.",
                duration_ms=int((time.monotonic() - t8) * 1000),
                data={
                    "records_with_pdf_url": 0,
                    "records_with_landing_url": len(with_landing),
                },
            )
        )
    else:
        stages.append(
            _make_stage(
                8,
                "fulltext_url_discovery",
                "Deteksi URL Full-Text",
                "WARN",
                message="Repositori ini hanya mengekspor metadata tanpa URL PDF maupun halaman artikel pada sampel awal.",
                suggestion="Metadata tidak akan pernah dianggap sebagai full-text. Pertimbangkan mengganti format metadata (mis. dim/xoai/oai_etdms) jika tersedia.",
                duration_ms=int((time.monotonic() - t8) * 1000),
                data={"records_with_pdf_url": 0, "records_with_landing_url": 0},
            )
        )

    return _finalize_wizard_report(
        base_url, effective_url, platform_detected, identify_info, recommended_prefix,
        supported_formats, available_sets, sample_records, stages
    )


def _finalize_wizard_report(
    input_url: str,
    effective_url: str,
    platform_detected: str,
    identify_info: dict[str, str],
    recommended_prefix: str,
    supported_formats: list[str],
    available_sets: list[dict[str, str]],
    sample_records: list[dict[str, Any]],
    stages: list[dict[str, Any]],
) -> dict[str, Any]:
    fail_count = sum(1 for s in stages if s["status"] == "FAIL")
    warn_count = sum(1 for s in stages if s["status"] == "WARN")
    pass_count = sum(1 for s in stages if s["status"] == "PASS")

    # Core stages 1, 2, 3 must pass for READY/PARTIAL
    core_ok = all(s["status"] == "PASS" for s in stages if s["step"] in {1, 2, 3})
    if fail_count == 0 and warn_count == 0:
        overall_status = "READY"
    elif core_ok and fail_count == 0:
        overall_status = "PARTIAL"
    else:
        overall_status = "FAILED"

    return {
        "ok": core_ok and fail_count == 0,
        "overall_status": overall_status,
        "summary_counts": {"pass": pass_count, "warn": warn_count, "fail": fail_count},
        "input_url": input_url,
        "effective_url": effective_url,
        "platform_detected": platform_detected,
        "platform_label": platform_label(platform_detected),
        "identified_name": identify_info.get("repositoryName"),
        "identify": identify_info,
        "recommended_prefix": recommended_prefix,
        "supported_formats": supported_formats,
        "available_sets": available_sets,
        "sample_records": sample_records,
        "stages": stages,
        "tested_at": datetime.now(timezone.utc).isoformat(),
    }


def preview_oai_records(
    base_url: str,
    *,
    metadata_prefix: str = "oai_dc",
    set_spec: str | None = None,
    limit: int = 5,
    client: httpx.Client | None = None,
    resolve_dns: bool = True,
    timeout_sec: float = 20.0,
) -> dict[str, Any]:
    """Fetch a small sample of metadata records without modifying the local corpus."""
    oai = OAIPMHClient(client=client, resolve_dns=resolve_dns, timeout_sec=timeout_sec)
    records, next_token = oai.list_records(
        base_url,
        metadata_prefix=metadata_prefix,
        set_spec=set_spec or None,
        include_deleted=False,
    )
    return {
        "metadata_prefix": metadata_prefix,
        "set_spec": set_spec,
        "has_more": bool(next_token),
        "count": len(records[:limit]),
        "records": [
            {
                "identifier": r.identifier,
                "datestamp": r.datestamp,
                "title": r.title,
                "authors": r.authors,
                "year": r.year,
                "doi": r.doi,
                "rights": r.rights,
                "urls": r.urls[:3],
                "pdf_urls": r.pdf_urls[:3],
                "set_specs": r.set_specs[:5],
            }
            for r in records[:limit]
        ],
    }


def _log_oai(
    db: Session,
    repo_id: str,
    stage: str,
    message: str,
    *,
    level: str = "INFO",
    http_status: int | None = None,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        OAIHarvestLog(
            repository_id=repo_id,
            level=level,
            stage=stage,
            http_status=http_status,
            error_code=error_code,
            message=message,
            details=details,
        )
    )


def _discover_pdf_from_landing_page(
    landing_urls: list[str],
    *,
    oai: OAIPMHClient,
) -> list[str]:
    """Inspect public OJS/DSpace/EPrints landing or galley URLs for open-access PDF links."""
    found: list[str] = []
    # Check OJS galley pattern (/article/view/{article_id}/{galley_id}) -> candidate /article/download/...
    for lu in landing_urls:
        m_ojs = _OJS_GALLEY_RE.match(lu.strip())
        if m_ojs:
            dl_cand = f"{m_ojs.group(1)}download/{m_ojs.group(2)}/{m_ojs.group(3)}"
            try:
                validate_public_url(dl_cand, resolve_dns=oai.resolve_dns)
                if dl_cand not in found:
                    found.append(dl_cand)
            except Exception:
                pass

    for lu in landing_urls[:2]:
        try:
            resp, final_url, _ = oai._safe_http_get(lu)
            if resp.status_code != 200:
                continue
            ct = (resp.headers.get("content-type") or "").lower()
            if "application/pdf" in ct or resp.content[:5] == b"%PDF-":
                if final_url not in found:
                    found.append(final_url)
                continue
            html = resp.text[:98304]
            m = _CITATION_PDF_RE.search(html) or _CITATION_PDF_RE_ALT.search(html)
            if m:
                candidate = urljoin(final_url, m.group(1).strip())
                validate_public_url(candidate, resolve_dns=oai.resolve_dns)
                if candidate not in found:
                    found.append(candidate)
            for hm in _HREF_PDF_CANDIDATE_RE.finditer(html):
                href_raw = hm.group(1).strip().replace("&amp;", "&")
                candidate = urljoin(final_url, href_raw)
                try:
                    validate_public_url(candidate, resolve_dns=oai.resolve_dns)
                except Exception:
                    continue
                if candidate not in found:
                    found.append(candidate)
                if len(found) >= 3:
                    break
        except Exception:
            continue
    return found


def _record_matches_filters(
    rec: OAIRecord,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
    keyword_filter: str | None = None,
    doc_type_filter: str | None = None,
) -> bool:
    """Apply Phase 10.4 record-level filtering (year range, keyword, document type)."""
    if year_from is not None:
        if rec.year is None or rec.year < year_from:
            return False
    if year_to is not None:
        if rec.year is None or rec.year > year_to:
            return False

    if keyword_filter and keyword_filter.strip():
        terms = [t.strip().lower() for t in re.split(r"[,;\s]+", keyword_filter.strip()) if t.strip()]
        hay = " ".join([rec.title or "", rec.description or "", " ".join(rec.subjects or [])]).lower()
        if not any(term in hay for term in terms):
            return False

    if doc_type_filter and doc_type_filter.strip():
        dt_needle = doc_type_filter.strip().lower()
        dt_hay = " ".join(
            [rec.doc_type or "", " ".join(rec.set_specs or []), rec.title or ""]
        ).lower()
        # Handle Indonesian/English common synonyms cleanly
        synonym_groups = {
            "skripsi": ("skripsi", "undergraduate thesis", "bachelor", "tugas akhir"),
            "tesis": ("tesis", "master thesis", "magister"),
            "disertasi": ("disertasi", "doctoral", "dissertation"),
            "artikel": ("artikel", "article", "journal", "jurnal", "info:eu-repo/semantics/article"),
            "prosiding": ("prosiding", "conference", "proceeding"),
            "buku": ("buku", "book", "monograph"),
        }
        accepted = synonym_groups.get(dt_needle, (dt_needle,))
        if not any(tok in dt_hay for tok in accepted):
            return False

    return True


def _sync_repo_counters(db: Session, repo: OAIRepository) -> None:
    """Recompute accurate persistent funnel counters from oai_harvest_records."""
    rows = db.query(OAIHarvestRecord).filter(OAIHarvestRecord.repository_id == repo.id).all()
    if not rows:
        return
    non_deleted = [r for r in rows if not r.deleted]
    repo.records_harvested = len(non_deleted)
    repo.metadata_saved_count = len(non_deleted)
    repo.pdf_urls_found_count = sum(1 for r in non_deleted if r.pdf_urls and len(r.pdf_urls) > 0)
    repo.pdf_accessible_count = sum(
        1 for r in non_deleted if r.status in {"FULLTEXT_EXTRACTED", "INDEXED"}
    )
    repo.fulltext_extracted_count = sum(
        1 for r in non_deleted if r.status in {"FULLTEXT_EXTRACTED", "INDEXED"}
    )
    repo.fulltext_indexed = sum(1 for r in non_deleted if r.status == "INDEXED" and r.document_id)
    repo.failed_records_count = sum(
        1 for r in non_deleted if r.status in {"FAILED", "PDF_INACCESSIBLE"}
    )


def get_repository_funnel(db: Session, repo: OAIRepository) -> dict[str, int]:
    """Return the transparent 7-stage funnel for a repository."""
    doc_ids = [
        row[0]
        for row in db.query(OAIHarvestRecord.document_id)
        .filter(
            OAIHarvestRecord.repository_id == repo.id,
            OAIHarvestRecord.document_id.isnot(None),
        )
        .distinct()
        .all()
        if row[0]
    ]
    compared_count = 0
    if doc_ids:
        compared_count = (
            db.query(func.count(func.distinct(CheckSource.source_document_id)))
            .filter(CheckSource.source_document_id.in_(doc_ids))
            .scalar()
            or 0
        )
    else:
        # Also account for legacy docs indexed with provider == f"oai:{repo.name}"
        legacy_ids = [
            row[0]
            for row in db.query(Document.id).filter(Document.provider == f"oai:{repo.name}").all()
        ]
        if legacy_ids:
            compared_count = (
                db.query(func.count(func.distinct(CheckSource.source_document_id)))
                .filter(CheckSource.source_document_id.in_(legacy_ids))
                .scalar()
                or 0
            )

    return {
        "metadata_found": repo.records_harvested,
        "metadata_saved": repo.metadata_saved_count or repo.records_harvested,
        "pdf_urls_found": repo.pdf_urls_found_count,
        "pdf_accessible": repo.pdf_accessible_count,
        "fulltext_extracted": repo.fulltext_extracted_count,
        "document_indexed": repo.fulltext_indexed,
        "document_compared": int(compared_count),
        "failed_records": repo.failed_records_count,
    }


def _acquire_and_index_record(
    db: Session,
    repo: OAIRepository,
    hrec: OAIHarvestRecord,
    *,
    oai: OAIPMHClient,
    client: httpx.Client | None,
    resolve_dns: bool,
    download_pdfs: bool,
    allow_download: bool = True,
) -> tuple[bool, bool, str | None]:
    """Attempt PDF acquisition & local indexing for one OAIHarvestRecord.

    Returns (pdf_accessible, indexed_ok, last_error_code).
    Strictly never treats metadata-only records as full-text.
    """
    settings = get_settings()
    pdf_urls: list[str] = list(hrec.pdf_urls or [])
    landing_urls: list[str] = list(hrec.landing_urls or [])
    primary_url = pdf_urls[0] if pdf_urls else (landing_urls[0] if landing_urls else None)

    # Check duplicate BEFORE downloading PDF
    dup = find_duplicate_source(
        db,
        doi=hrec.doi,
        url=primary_url,
        title=hrec.title,
    )
    if dup is not None:
        hrec.status = "DUPLICATE"
        hrec.document_id = dup.id
        hrec.error_code = None
        hrec.error_message = "Sumber sudah ada di korpus lokal (DOI/URL/judul cocok)."
        hrec.updated_at = datetime.now(timezone.utc)
        return False, False, None

    if not download_pdfs or not allow_download:
        hrec.status = "PDF_FOUND" if pdf_urls else "METADATA_SAVED"
        hrec.error_code = None
        hrec.error_message = (
            "Batas maksimum unduhan PDF per sesi tercapai; metadata tetap disimpan."
            if (download_pdfs and not allow_download and pdf_urls)
            else None
        )
        hrec.updated_at = datetime.now(timezone.utc)
        return False, False, None

    # If no direct PDF URL in XML, check public landing / galley URLs
    if not pdf_urls and landing_urls:
        discovered = _discover_pdf_from_landing_page(landing_urls, oai=oai)
        if discovered:
            pdf_urls.extend(discovered)
            hrec.pdf_urls = pdf_urls
            primary_url = primary_url or pdf_urls[0]

    if not pdf_urls:
        hrec.status = "METADATA_SAVED"
        hrec.error_code = None
        hrec.error_message = None
        hrec.updated_at = datetime.now(timezone.utc)
        return False, False, None

    last_err_code: str | None = None
    last_err_msg: str | None = None

    for pdf_url in pdf_urls[:3]:
        crawl = fetch_public_url(
            pdf_url,
            client=client,
            enable_browser_crawler=False,
            max_bytes=settings.MAX_EXTERNAL_DOWNLOAD_MB * 1024 * 1024,
            resolve_dns=resolve_dns,
        )
        if crawl.status == "FULLTEXT_FETCHED" and crawl.raw_bytes and crawl.file_type:
            # Guard against HTML login/paywall/viewer pages masquerading as PDF
            if crawl.file_type == "html":
                last_err_code = "PDF_INACCESSIBLE"
                last_err_msg = "Tautan mengembalikan halaman HTML, bukan berkas PDF full-text."
                continue
            try:
                val = validate_local_bytes(
                    f"oai_{repo.repo_type}.{crawl.file_type}",
                    crawl.raw_bytes,
                    settings.max_upload_bytes,
                    allow_web_formats=True,
                )
                doc_dup = find_duplicate_source(
                    db,
                    file_hash=val.file_hash,
                    doi=hrec.doi,
                    url=primary_url,
                    canonical_url=crawl.canonical_url or primary_url,
                    title=hrec.title,
                )
                if doc_dup is not None:
                    hrec.status = "DUPLICATE"
                    hrec.document_id = doc_dup.id
                    hrec.error_code = None
                    hrec.error_message = "Konten berkas sama dengan dokumen yang sudah diindeks."
                    hrec.updated_at = datetime.now(timezone.utc)
                    return True, False, None

                provenance_extra = {
                    "repository_id": repo.id,
                    "repository_name": repo.name,
                    "university": repo.identified_name or repo.name,
                    "oai_base_url": repo.base_url,
                    "oai_identifier": hrec.oai_identifier,
                    "oai_set_spec": hrec.set_spec,
                    "doc_type": hrec.doc_type,
                    "platform": repo.platform_detected or repo.repo_type,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                }
                doc = ingest_validated_upload(
                    db,
                    val,
                    role="CORPUS",
                    title=hrec.title or hrec.oai_identifier,
                    authors=hrec.authors or [],
                    year=hrec.year,
                    doi=hrec.doi,
                    url=primary_url,
                    canonical_url=crawl.canonical_url or primary_url,
                    license_name=hrec.rights,
                    indexing_status="FULLTEXT_INDEXED",
                    source_type=f"oai_{repo.repo_type}",
                    access_status="INDEXED_LOCALLY",
                    provider=f"oai:{repo.name}",
                    external_id=hrec.oai_identifier,
                    extra_metadata=provenance_extra,
                )
                hrec.status = "INDEXED"
                hrec.document_id = doc.id
                hrec.error_code = None
                hrec.error_message = None
                hrec.updated_at = datetime.now(timezone.utc)
                return True, True, None
            except Exception as exc:
                last_err_code = "EXTRACTION_FAILED"
                last_err_msg = f"Gagal mengekstrak atau mengindeks berkas: {exc}"
                continue
        elif crawl.status == "ACCESS_RESTRICTED":
            last_err_code = "PDF_INACCESSIBLE"
            last_err_msg = crawl.error or f"Akses berkas ditolak (HTTP {crawl.http_status or 403})."
        else:
            last_err_code = "PDF_INACCESSIBLE"
            last_err_msg = crawl.error or f"Gagal mengunduh PDF (HTTP {crawl.http_status or '-'})."

    hrec.status = "PDF_INACCESSIBLE" if last_err_code == "PDF_INACCESSIBLE" else "FAILED"
    hrec.error_code = last_err_code or "PDF_INACCESSIBLE"
    hrec.error_message = last_err_msg
    hrec.updated_at = datetime.now(timezone.utc)
    return False, False, hrec.error_code


def harvest_oai_repository(
    db: Session,
    repo: OAIRepository,
    *,
    max_records: int = 20,
    max_downloads: int | None = None,
    download_pdfs: bool = True,
    resume: bool = False,
    reset_cursor: bool = False,
    incremental: bool = True,
    set_spec: str | None = None,
    metadata_prefix: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    keyword_filter: str | None = None,
    doc_type_filter: str | None = None,
    trigger_mode: str = "MANUAL",
    client: httpx.Client | None = None,
    resolve_dns: bool = True,
) -> dict[str, Any]:
    """Fault-tolerant, resumable OAI-PMH 2.0 harvester with Phase 10.4 filters, download limits, and run history."""
    oai = OAIPMHClient(
        client=client,
        resolve_dns=resolve_dns,
        timeout_sec=float(repo.request_timeout_sec or 20),
        rate_limit_delay_sec=float(repo.rate_limit_delay_sec or 0.0) if client is None else 0.0,
    )

    if reset_cursor or not incremental:
        repo.resumption_token = None
        if reset_cursor:
            repo.last_datestamp = None

    effective_set = set_spec if set_spec is not None else repo.selected_set
    effective_prefix = (metadata_prefix or repo.metadata_prefix or "oai_dc").strip()
    eff_year_from = year_from if year_from is not None else repo.year_from
    eff_year_to = year_to if year_to is not None else repo.year_to
    eff_keyword = keyword_filter if keyword_filter is not None else repo.keyword_filter
    eff_doc_type = doc_type_filter if doc_type_filter is not None else repo.doc_type_filter
    eff_max_downloads = (
        max_downloads
        if max_downloads is not None
        else (repo.max_downloads if repo.max_downloads is not None else max_records)
    )
    eff_max_downloads = max(0, min(eff_max_downloads, max_records))

    # Bound scanned records so broad filters cannot scan an unbounded repository indefinitely
    max_scan_budget = max(max_records * 5, 100)

    run_row = OAIHarvestRun(
        repository_id=repo.id,
        trigger_mode="RESUME" if (resume and trigger_mode == "MANUAL") else trigger_mode,
        status="RUNNING",
        set_spec=effective_set or None,
        metadata_prefix=effective_prefix,
        filters_snapshot={
            "year_from": eff_year_from,
            "year_to": eff_year_to,
            "keyword_filter": eff_keyword,
            "doc_type_filter": eff_doc_type,
            "max_records": max_records,
            "max_downloads": eff_max_downloads,
            "incremental": incremental,
        },
        started_at=datetime.now(timezone.utc),
    )
    db.add(run_row)

    repo.status = "HARVESTING"
    repo.harvest_state = "RUNNING"
    repo.last_error = None
    repo.updated_at = datetime.now(timezone.utc)
    _log_oai(
        db,
        repo.id,
        "HARVEST_START",
        f"Memulai panen {run_row.trigger_mode} (maks {max_records} rekaman, maks {eff_max_downloads} unduhan PDF, format {effective_prefix}"
        + (f", koleksi {effective_set}" if effective_set else "")
        + (f", tahun {eff_year_from or '*'}–{eff_year_to or '*'}" if (eff_year_from or eff_year_to) else "")
        + (f", kata kunci '{eff_keyword}'" if eff_keyword else "")
        + (f", jenis '{eff_doc_type}'" if eff_doc_type else "")
        + ").",
    )
    db.commit()

    run_scanned = 0
    run_matched = 0
    run_harvested = 0
    run_indexed = 0
    run_downloads_attempted = 0
    run_metadata_only = 0
    run_duplicates = 0
    run_deleted = 0
    run_failed = 0
    run_pdf_found = 0
    run_pdf_accessible = 0
    pages_fetched = 0
    paused = False
    latest_ds = repo.last_datestamp

    try:
        ident = oai.identify(repo.base_url)
        if ident.get("repositoryName"):
            repo.identified_name = ident["repositoryName"][:500]
        repo.platform_detected = detect_platform_from_url(repo.base_url, ident)

        try:
            fmts = oai.list_metadata_formats(repo.base_url)
            if fmts:
                repo.supported_formats = fmts
                negotiated = negotiate_metadata_prefix(effective_prefix, fmts)
                if negotiated != effective_prefix:
                    _log_oai(
                        db,
                        repo.id,
                        "FORMAT_NEGOTIATION",
                        f"Format '{effective_prefix}' tidak tersedia; beralih otomatis ke '{negotiated}'.",
                        level="WARN",
                        error_code="cannotDisseminateFormat",
                    )
                    effective_prefix = negotiated
                    repo.metadata_prefix = negotiated
                    run_row.metadata_prefix = negotiated
        except OAIPMHProtocolError:
            pass

        db.commit()

        token: str | None = repo.resumption_token if resume else None
        first_page = not bool(token)
        token_retried = False
        has_filters = bool(eff_year_from or eff_year_to or eff_keyword or eff_doc_type)

        # Compute OAI 'from' datestamp: incremental last_datestamp OR explicit year_from
        from_ds = repo.last_datestamp if (incremental and first_page and not token) else None
        if not from_ds and eff_year_from and not token:
            from_ds = f"{eff_year_from:04d}-01-01"

        while run_harvested < max_records and run_scanned < max_scan_budget:
            db.refresh(repo)
            if repo.harvest_state == "PAUSED":
                paused = True
                _log_oai(
                    db,
                    repo.id,
                    "HARVEST_PAUSED",
                    f"Panen dijeda setelah {run_harvested} rekaman. Progres dan token tersimpan untuk dilanjutkan.",
                )
                break

            try:
                recs, next_token = oai.list_records(
                    repo.base_url,
                    metadata_prefix=effective_prefix,
                    from_datestamp=from_ds if (first_page and not token) else None,
                    set_spec=effective_set if (first_page and not token) else None,
                    resumption_token=token,
                    include_deleted=True,
                )
            except OAIPMHProtocolError as exc:
                if exc.error_code == "noRecordsMatch":
                    _log_oai(
                        db,
                        repo.id,
                        "LIST_RECORDS",
                        "Tidak ada rekaman baru yang cocok (noRecordsMatch). Panen diselesaikan tanpa error.",
                        level="INFO",
                        http_status=exc.http_status,
                        error_code="noRecordsMatch",
                    )
                    repo.resumption_token = None
                    break
                if exc.error_code == "badResumptionToken" and token and not token_retried:
                    token_retried = True
                    _log_oai(
                        db,
                        repo.id,
                        "TOKEN_RECOVERY",
                        "resumptionToken kedaluwarsa (badResumptionToken). Menghapus token lama dan melanjutkan dari datestamp terakhir.",
                        level="WARN",
                        http_status=exc.http_status,
                        error_code="badResumptionToken",
                    )
                    token = None
                    repo.resumption_token = None
                    first_page = True
                    db.commit()
                    continue
                raise

            first_page = False
            pages_fetched += 1

            if not recs:
                repo.resumption_token = None
                break

            for rec in recs:
                if run_harvested >= max_records:
                    break
                run_scanned += 1

                if rec.datestamp and (latest_ds is None or rec.datestamp > latest_ds):
                    latest_ds = rec.datestamp

                existing_rec = (
                    db.query(OAIHarvestRecord)
                    .filter(
                        OAIHarvestRecord.repository_id == repo.id,
                        OAIHarvestRecord.oai_identifier == rec.identifier,
                    )
                    .first()
                )

                if rec.deleted:
                    run_deleted += 1
                    if existing_rec is None:
                        db.add(
                            OAIHarvestRecord(
                                repository_id=repo.id,
                                oai_identifier=rec.identifier,
                                datestamp=rec.datestamp,
                                set_spec=rec.set_specs[0] if rec.set_specs else effective_set,
                                metadata_prefix=effective_prefix,
                                deleted=True,
                                title=rec.identifier,
                                status="DELETED",
                            )
                        )
                    else:
                        existing_rec.deleted = True
                        existing_rec.status = "DELETED"
                        existing_rec.datestamp = rec.datestamp
                        existing_rec.updated_at = datetime.now(timezone.utc)
                    continue

                if has_filters and not _record_matches_filters(
                    rec,
                    year_from=eff_year_from,
                    year_to=eff_year_to,
                    keyword_filter=eff_keyword,
                    doc_type_filter=eff_doc_type,
                ):
                    continue

                run_matched += 1
                run_harvested += 1
                if rec.pdf_urls:
                    run_pdf_found += 1

                if existing_rec is None:
                    hrec = OAIHarvestRecord(
                        repository_id=repo.id,
                        oai_identifier=rec.identifier,
                        datestamp=rec.datestamp,
                        set_spec=rec.set_specs[0] if rec.set_specs else effective_set,
                        metadata_prefix=effective_prefix,
                        deleted=False,
                        title=rec.title,
                        authors=rec.authors,
                        year=rec.year,
                        doi=rec.doi,
                        doc_type=rec.doc_type,
                        subjects=rec.subjects,
                        rights=rec.rights,
                        landing_urls=rec.urls,
                        pdf_urls=rec.pdf_urls,
                        status="METADATA_SAVED",
                    )
                    db.add(hrec)
                    db.flush()
                else:
                    hrec = existing_rec
                    hrec.datestamp = rec.datestamp or hrec.datestamp
                    hrec.title = rec.title or hrec.title
                    hrec.authors = rec.authors or hrec.authors
                    hrec.year = rec.year or hrec.year
                    hrec.doi = rec.doi or hrec.doi
                    hrec.doc_type = rec.doc_type or hrec.doc_type
                    hrec.subjects = rec.subjects or hrec.subjects
                    hrec.rights = rec.rights or hrec.rights
                    hrec.landing_urls = rec.urls or hrec.landing_urls
                    hrec.pdf_urls = rec.pdf_urls or hrec.pdf_urls
                    hrec.attempts += 1
                    hrec.updated_at = datetime.now(timezone.utc)

                    if hrec.status == "INDEXED" and hrec.document_id:
                        run_duplicates += 1
                        continue

                can_download = download_pdfs and (run_downloads_attempted < eff_max_downloads)
                had_candidate_dl = bool(hrec.pdf_urls or hrec.landing_urls)
                pdf_acc, idx_ok, _err_code = _acquire_and_index_record(
                    db,
                    repo,
                    hrec,
                    oai=oai,
                    client=client,
                    resolve_dns=resolve_dns,
                    download_pdfs=download_pdfs,
                    allow_download=can_download,
                )
                if can_download and had_candidate_dl and hrec.status != "DUPLICATE" and (hrec.pdf_urls or pdf_acc):
                    run_downloads_attempted += 1

                if pdf_acc:
                    run_pdf_accessible += 1
                if idx_ok:
                    run_indexed += 1
                elif hrec.status == "DUPLICATE":
                    run_duplicates += 1
                elif hrec.status in {"FAILED", "PDF_INACCESSIBLE"}:
                    run_failed += 1
                    run_metadata_only += 1
                else:
                    run_metadata_only += 1

            token = next_token
            repo.resumption_token = next_token
            repo.last_datestamp = latest_ds
            _sync_repo_counters(db, repo)
            run_row.records_scanned = run_scanned
            run_row.records_matched_filter = run_matched
            run_row.records_harvested = run_harvested
            run_row.fulltext_indexed = run_indexed
            run_row.metadata_only = run_metadata_only
            run_row.failed_records = run_failed
            run_row.duplicates_skipped = run_duplicates
            _log_oai(
                db,
                repo.id,
                "PAGE_COMPLETE",
                f"Halaman {pages_fetched} selesai: {run_scanned} dipindai, {run_harvested} cocok & disimpan, {run_indexed} full-text diindeks.",
                details={
                    "page": pages_fetched,
                    "has_next_token": bool(next_token),
                    "run_scanned": run_scanned,
                    "run_harvested": run_harvested,
                    "run_indexed": run_indexed,
                },
            )
            db.commit()

            if not token:
                break

        now_utc = datetime.now(timezone.utc)
        repo.last_harvested_at = now_utc
        repo.last_datestamp = latest_ds
        if repo.schedule_enabled:
            repo.next_scheduled_at = now_utc + timedelta(hours=max(1, int(repo.schedule_interval_hours or 24)))
        _sync_repo_counters(db, repo)
        if paused:
            repo.status = "PAUSED"
            repo.harvest_state = "PAUSED"
            run_row.status = "PAUSED"
        else:
            repo.status = "VERIFIED"
            repo.harvest_state = "COMPLETED"
            run_row.status = "COMPLETED"
            if run_harvested < max_records and not repo.resumption_token:
                repo.resumption_token = None
        run_row.records_scanned = run_scanned
        run_row.records_matched_filter = run_matched
        run_row.records_harvested = run_harvested
        run_row.fulltext_indexed = run_indexed
        run_row.metadata_only = run_metadata_only
        run_row.failed_records = run_failed
        run_row.duplicates_skipped = run_duplicates
        run_row.finished_at = now_utc
        repo.updated_at = now_utc
        _log_oai(
            db,
            repo.id,
            "HARVEST_DONE",
            (
                f"Panen selesai ({repo.harvest_state}): {run_harvested} rekaman disimpan "
                f"(dari {run_scanned} dipindai), {run_indexed} full-text diindeks, "
                f"{run_metadata_only} metadata saja, {run_duplicates} duplikat, {run_failed} gagal PDF."
            ),
        )
        db.commit()
    except Exception as exc:
        err_code = exc.error_code if isinstance(exc, OAIPMHProtocolError) else "HARVEST_ERROR"
        http_st = exc.http_status if isinstance(exc, OAIPMHProtocolError) else None
        now_utc = datetime.now(timezone.utc)
        _sync_repo_counters(db, repo)
        repo.last_datestamp = latest_ds
        repo.status = "ERROR"
        repo.harvest_state = "ERROR"
        repo.last_error = str(exc)
        repo.updated_at = now_utc
        run_row.status = "ERROR"
        run_row.records_scanned = run_scanned
        run_row.records_matched_filter = run_matched
        run_row.records_harvested = run_harvested
        run_row.fulltext_indexed = run_indexed
        run_row.metadata_only = run_metadata_only
        run_row.failed_records = run_failed
        run_row.duplicates_skipped = run_duplicates
        run_row.error_message = str(exc)
        run_row.finished_at = now_utc
        _log_oai(
            db,
            repo.id,
            "HARVEST_ERROR",
            str(exc),
            level="ERROR",
            http_status=http_st,
            error_code=err_code,
            details={"run_harvested_before_error": run_harvested, "resumption_token_saved": bool(repo.resumption_token)},
        )
        db.commit()
        raise

    return {
        "run_id": run_row.id,
        "repository": repo.name,
        "records_scanned": run_scanned,
        "records_matched_filter": run_matched,
        "records_harvested": run_harvested,
        "records_seen": run_harvested,
        "fulltext_indexed": run_indexed,
        "metadata_only": run_metadata_only,
        "pdf_urls_found": run_pdf_found,
        "pdf_accessible": run_pdf_accessible,
        "duplicates_skipped": run_duplicates,
        "deleted_skipped": run_deleted,
        "failed_records": run_failed,
        "pages_fetched": pages_fetched,
        "has_more": bool(repo.resumption_token),
        "harvest_state": repo.harvest_state,
        "status": repo.status,
    }


def retry_failed_oai_records(
    db: Session,
    repo: OAIRepository,
    *,
    limit: int = 20,
    client: httpx.Client | None = None,
    resolve_dns: bool = True,
) -> dict[str, Any]:
    """Retry PDF acquisition and indexing for FAILED / PDF_INACCESSIBLE records of a repository."""
    oai = OAIPMHClient(
        client=client,
        resolve_dns=resolve_dns,
        timeout_sec=float(repo.request_timeout_sec or 20),
        rate_limit_delay_sec=float(repo.rate_limit_delay_sec or 0.0) if client is None else 0.0,
    )
    rows = (
        db.query(OAIHarvestRecord)
        .filter(
            OAIHarvestRecord.repository_id == repo.id,
            OAIHarvestRecord.status.in_(["FAILED", "PDF_INACCESSIBLE"]),
            OAIHarvestRecord.deleted.is_(False),
        )
        .order_by(OAIHarvestRecord.updated_at.asc())
        .limit(limit)
        .all()
    )

    retried = 0
    recovered = 0
    still_failed = 0
    duplicates = 0

    for hrec in rows:
        retried += 1
        hrec.attempts += 1
        _pdf_acc, idx_ok, _err = _acquire_and_index_record(
            db,
            repo,
            hrec,
            oai=oai,
            client=client,
            resolve_dns=resolve_dns,
            download_pdfs=True,
        )
        if idx_ok:
            recovered += 1
        elif hrec.status == "DUPLICATE":
            duplicates += 1
        else:
            still_failed += 1

    _sync_repo_counters(db, repo)
    repo.updated_at = datetime.now(timezone.utc)
    _log_oai(
        db,
        repo.id,
        "RETRY_FAILED",
        f"Percobaan ulang selesai: {retried} dicoba, {recovered} berhasil diindeks, {duplicates} duplikat, {still_failed} masih gagal.",
    )
    db.commit()

    return {
        "retried": retried,
        "recovered_indexed": recovered,
        "duplicates": duplicates,
        "still_failed": still_failed,
    }
