"""Document integrity flag detection and consistent source color palette."""

from __future__ import annotations

from typing import Any

# 12 curated editorial source colors: (solid_badge_hex, pastel_highlight_hex, chip_bg_hex, chip_text_hex)
SOURCE_PALETTE: list[dict[str, str]] = [
    {"badge": "#6E1F2F", "highlight": "#F6DDE2", "chip_bg": "#F7E5E8", "chip_text": "#6E1F2F"},
    {"badge": "#1D4ED8", "highlight": "#DBEAFE", "chip_bg": "#E0ECFF", "chip_text": "#1E40AF"},
    {"badge": "#15803D", "highlight": "#DCFCE7", "chip_bg": "#E2F7E9", "chip_text": "#166534"},
    {"badge": "#7E22CE", "highlight": "#F3E8FF", "chip_bg": "#F3E8FF", "chip_text": "#6B21A8"},
    {"badge": "#B45309", "highlight": "#FEF3C7", "chip_bg": "#FEF3C7", "chip_text": "#92400E"},
    {"badge": "#0F766E", "highlight": "#CCFBF1", "chip_bg": "#D5FAF2", "chip_text": "#115E59"},
    {"badge": "#BE123C", "highlight": "#FFE4E6", "chip_bg": "#FFE4E6", "chip_text": "#9F1239"},
    {"badge": "#4338CA", "highlight": "#E0E7FF", "chip_bg": "#E0E7FF", "chip_text": "#3730A3"},
    {"badge": "#C2410C", "highlight": "#FFEDD5", "chip_bg": "#FFEDD5", "chip_text": "#9A3412"},
    {"badge": "#0369A1", "highlight": "#E0F2FE", "chip_bg": "#E0F2FE", "chip_text": "#075985"},
    {"badge": "#9D174D", "highlight": "#FCE7F3", "chip_bg": "#FCE7F3", "chip_text": "#831843"},
    {"badge": "#3F6212", "highlight": "#ECFCCB", "chip_bg": "#ECFCCB", "chip_text": "#365314"},
]

# Confusable Cyrillic / Greek homoglyphs commonly abused to disguise Latin words
HOMOGLYPH_CHARS = frozenset(
    "\u0410\u0412\u0421\u0415\u041d\u041a\u041c\u041e\u0420\u0422\u0425"  # Cyrillic uppercase lookalikes
    "\u0430\u0435\u043e\u0440\u0441\u0443\u0445\u0456\u0458\u04bb"        # Cyrillic lowercase lookalikes
    "\u0391\u0392\u0395\u0396\u0397\u0399\u039a\u039c\u039d\u039f\u03a1\u03a4\u03a7"  # Greek uppercase
    "\u03bf\u03b1\u03b5\u03b9\u03ba\u03bd\u03c1\u03c4"                    # Greek lowercase
)

ZERO_WIDTH_CHARS = frozenset("\u200b\u200c\u200d\u2060\ufeff")


def color_for_rank(rank: int) -> dict[str, str]:
    idx = max(0, int(rank) - 1) % len(SOURCE_PALETTE)
    return dict(SOURCE_PALETTE[idx])


def classify_source_category(source_type: str | None, provider: str | None) -> tuple[str, str]:
    st = (source_type or "").lower()
    pv = (provider or "").lower()
    if pv in {"openalex", "crossref", "arxiv", "europe_pmc", "pubmed_central", "doaj"} or any(
        k in st for k in ("publication", "journal", "article", "preprint", "paper", "book")
    ):
        return "publication", "Publikasi"
    if pv in {"web", "searxng", "web_search", "playwright", "crawler"} or any(
        k in st for k in ("web", "internet", "url", "html")
    ):
        return "internet", "Internet"
    return "local", "Korpus Lokal"


def compute_source_category_summary(sources: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {"internet": 0.0, "publication": 0.0, "local": 0.0}
    counts = {"internet": 0, "publication": 0, "local": 0}
    for src in sources:
        cat_key, _ = classify_source_category(src.get("source_type"), src.get("provider"))
        totals[cat_key] += float(src.get("contribution_pct") or 0.0)
        counts[cat_key] += 1
    return {
        "internet_pct": round(min(100.0, totals["internet"]), 1),
        "publication_pct": round(min(100.0, totals["publication"]), 1),
        "local_pct": round(min(100.0, totals["local"]), 1),
        "counts": counts,
    }


def extract_active_filters(settings: dict[str, Any] | None) -> list[str]:
    if not isinstance(settings, dict):
        return []
    mapping = [
        ("exclude_bibliography", "Daftar Pustaka / Bibliography"),
        ("exclude_citations", "Sitasi Dalam Teks"),
        ("exclude_quotes", "Kutipan Langsung"),
        ("exclude_toc", "Daftar Isi"),
        ("exclude_cover", "Halaman Sampul"),
        ("exclude_common_phrases", "Frasa Akademik Umum"),
    ]
    return [label for key, label in mapping if settings.get(key)]


def _page_for_offset(pos: int, pages: list[dict[str, Any]]) -> int:
    for p in pages:
        if int(p.get("char_start", 0)) <= pos <= int(p.get("char_end", 0)):
            return int(p.get("number", 1))
    return 1


def detect_integrity_flags(text: str, pages: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Detect genuine character-level anomalies (homoglyph substitution & invisible characters)."""
    if not text:
        return []
    page_list = pages or []
    flags: list[dict[str, Any]] = []

    # 1. Replaced / Homoglyph characters inside Latin words (ignores pure Arabic/Greek/math blocks)
    homoglyph_count = 0
    homoglyph_pages: set[int] = set()
    n = len(text)
    for i, ch in enumerate(text):
        if ch in HOMOGLYPH_CHARS:
            prev_latin = i > 0 and ("A" <= text[i - 1] <= "Z" or "a" <= text[i - 1] <= "z")
            next_latin = i + 1 < n and ("A" <= text[i + 1] <= "Z" or "a" <= text[i + 1] <= "z")
            if prev_latin or next_latin:
                homoglyph_count += 1
                homoglyph_pages.add(_page_for_offset(i, page_list))

    if homoglyph_count > 0:
        flags.append(
            {
                "code": "REPLACED_CHARACTERS",
                "title": "Karakter Terindikasi Penggantian (Homoglyph)",
                "severity": "warning",
                "count": homoglyph_count,
                "pages_count": len(homoglyph_pages),
                "summary": f"{homoglyph_count} karakter mencurigakan pada {len(homoglyph_pages)} halaman.",
                "detail": "Ditemukan huruf dari alfabet lain yang tampak serupa dengan huruf Latin di dalam kata.",
            }
        )

    # 2. Hidden zero-width characters inserted inside Latin words
    hidden_count = 0
    hidden_pages: set[int] = set()
    for i, ch in enumerate(text):
        if ch in ZERO_WIDTH_CHARS:
            prev_latin = i > 0 and text[i - 1].isalpha()
            next_latin = i + 1 < n and text[i + 1].isalpha()
            if prev_latin and next_latin:
                hidden_count += 1
                hidden_pages.add(_page_for_offset(i, page_list))

    if hidden_count >= 3:
        flags.append(
            {
                "code": "HIDDEN_CHARACTERS",
                "title": "Karakter Tak Terlihat di Dalam Kata",
                "severity": "warning",
                "count": hidden_count,
                "pages_count": len(hidden_pages),
                "summary": f"{hidden_count} karakter tak terlihat pada {len(hidden_pages)} halaman.",
                "detail": "Terdapat karakter lebar-nol (zero-width) yang tersisip di tengah kata.",
            }
        )

    return flags
