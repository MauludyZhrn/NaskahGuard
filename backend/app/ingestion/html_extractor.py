"""HTML article text, density-scored main content, and academic metadata extractor."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag

from app.ingestion.pdf import ExtractedDocument, _join_pages


def extract_html_text_and_meta(raw_html: str, *, base_url: str | None = None) -> ExtractedDocument:
    soup = BeautifulSoup(raw_html, "html.parser")

    # Page language from <html lang="..."> or meta
    html_tag = soup.find("html")
    page_lang = None
    if isinstance(html_tag, Tag) and html_tag.get("lang"):
        page_lang = str(html_tag.get("lang")).strip()[:16]

    # Canonical URL & academic meta tags
    canonical = None
    link_canon = soup.find("link", rel=lambda r: r and "canonical" in (r if isinstance(r, list) else [r]))
    if link_canon and link_canon.get("href"):
        raw_canon = str(link_canon["href"]).strip()
        canonical = urljoin(base_url, raw_canon) if base_url else raw_canon

    def _meta(name: str) -> str | None:
        tag = (
            soup.find("meta", attrs={"name": name})
            or soup.find("meta", attrs={"name": name.upper()})
            or soup.find("meta", attrs={"property": name})
        )
        if tag and tag.get("content"):
            return str(tag["content"]).strip()
        return None

    title = (
        _meta("citation_title")
        or _meta("dc.title")
        or _meta("DC.Title")
        or _meta("og:title")
        or (soup.title.get_text(" ", strip=True) if soup.title else None)
    )
    meta_description = (
        _meta("description")
        or _meta("og:description")
        or _meta("citation_abstract")
        or _meta("dc.description")
    )
    authors = [
        str(tag["content"]).strip()
        for tag in soup.find_all("meta", attrs={"name": lambda v: v and str(v).lower() in {"citation_author", "dc.creator"}})
        if tag.get("content")
    ]
    doi = _meta("citation_doi") or _meta("dc.identifier.doi") or _meta("dc.identifier")
    if doi and doi.lower().startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi and doi.lower().startswith("doi:"):
        doi = doi[4:].strip()

    citation_pdf_url = _meta("citation_pdf_url") or _meta("eprints.document_url")
    if citation_pdf_url and base_url:
        citation_pdf_url = urljoin(base_url, citation_pdf_url)

    # Collect outbound / PDF / fulltext source links before decomposing chrome
    source_links: list[str] = []
    if citation_pdf_url:
        source_links.append(citation_pdf_url)
    for a_tag in soup.find_all("a", href=True):
        href = str(a_tag["href"]).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        resolved = urljoin(base_url, href) if base_url else href
        low_href = resolved.lower()
        cls_txt = " ".join(a_tag.get("class") or []).lower()
        anchor_txt = a_tag.get_text(" ", strip=True).lower()
        if (
            low_href.endswith(".pdf")
            or "/article/download/" in low_href
            or "/bitstream/" in low_href
            or "obj_galley" in cls_txt
            or anchor_txt in {"pdf", "download pdf", "unduh pdf", "full text pdf"}
        ):
            if resolved not in source_links:
                source_links.append(resolved)

    # Remove boilerplate elements and hidden prompt-injection / UI containers
    for tag_name in (
        "script", "style", "noscript", "svg", "nav", "header", "footer",
        "aside", "form", "iframe", "button", "template",
    ):
        for el in soup.find_all(tag_name):
            el.decompose()

    noise_tokens = (
        "sidebar", "navbar", "footer", "cookie", "advert", "banner",
        "breadcrumb", "menu", "popup", "modal", "related-articles", "share-buttons",
    )
    for el in list(soup.find_all(True)):
        if getattr(el, "attrs", None) is None:
            continue
        if str(el.get("aria-hidden") or "").lower() == "true":
            el.decompose()
            continue
        style_attr = str(el.get("style") or "").lower().replace(" ", "")
        if "display:none" in style_attr or "visibility:hidden" in style_attr:
            el.decompose()
            continue
        cls = " ".join(el.get("class") or []).lower()
        el_id = str(el.get("id") or "").lower()
        if any(tok in cls or tok in el_id for tok in noise_tokens):
            # Do not accidentally decompose body/article/main if it has a generic class like 'main-menu-wrapper' on body
            if el.name not in {"html", "body", "main", "article"}:
                el.decompose()

    # Density-aware main container selection (prefers <article>, <main>, OJS/DSpace containers, or highest paragraph density)
    explicit_main = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("div", class_=lambda c: c and any(k in " ".join(c if isinstance(c, list) else [c]).lower() for k in ("article-details", "item-page", "ep_summary_content", "entry-content", "post-content")))
    )

    if explicit_main is None:
        best_node = soup.body or soup
        best_score = -1.0
        for cand in (soup.body or soup).find_all(["div", "section"]):
            p_chars = sum(len(p.get_text(" ", strip=True)) for p in cand.find_all("p", recursive=False))
            a_chars = sum(len(a.get_text(" ", strip=True)) for a in cand.find_all("a"))
            total_c = max(1, len(cand.get_text(" ", strip=True)))
            link_density = a_chars / total_c
            score = p_chars * (1.0 - min(0.85, link_density))
            if p_chars >= 160 and score > best_score:
                best_score = score
                best_node = cand
        main_container = best_node
    else:
        main_container = explicit_main

    blocks: list[str] = []
    for node in main_container.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        txt = " ".join(node.get_text(" ", strip=True).split())
        if len(txt) >= 20 or node.name in {"h1", "h2", "h3"}:
            if not blocks or blocks[-1] != txt:
                blocks.append(txt)

    if not blocks:
        fallback = " ".join(main_container.get_text(" ", strip=True).split())
        if fallback:
            blocks = [fallback]

    full_text, pages = _join_pages([(1, "\n\n".join(blocks), False, None)])
    char_len = len(full_text.strip())
    confidence = 0.95 if explicit_main is not None and char_len >= 400 else (0.82 if char_len >= 180 else 0.55)

    return ExtractedDocument(
        text=full_text,
        pages=pages,
        title=title[:500] if title else None,
        authors=authors[:15],
        extraction_method="HTML",
        extraction_confidence=confidence,
        ocr_pages=[],
        extra={
            "canonical_url": canonical,
            "doi": doi,
            "meta_description": meta_description[:600] if meta_description else None,
            "page_language": page_lang,
            "citation_pdf_url": citation_pdf_url,
            "source_links": source_links[:25],
        },
    )


def extract_html(file_path: Path) -> ExtractedDocument:
    raw = file_path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    return extract_html_text_and_meta(text)
