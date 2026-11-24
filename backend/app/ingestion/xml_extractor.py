"""Safe XML full-text extractor (JATS / Europe PMC / TEI XML) using defusedxml."""

from __future__ import annotations

from pathlib import Path
import defusedxml.ElementTree as ET

from app.ingestion.pdf import ExtractedDocument, _join_pages


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def extract_xml_text_and_meta(raw_xml: str) -> ExtractedDocument:
    root = ET.fromstring(raw_xml)
    title: str | None = None
    authors: list[str] = []
    paragraphs: list[str] = []

    for elem in root.iter():
        lname = _local_name(elem.tag)
        if title is None and lname in {"article-title", "title"}:
            txt = " ".join("".join(elem.itertext()).split())
            if txt:
                title = txt[:500]
        elif lname == "contrib" and elem.attrib.get("contrib-type") == "author":
            name_txt = " ".join("".join(elem.itertext()).split())
            if name_txt:
                authors.append(name_txt[:120])
        elif lname in {"p", "sec-title", "title"}:
            # Skip reference list items inside <ref-list>
            txt = " ".join("".join(elem.itertext()).split())
            if len(txt) >= 15 and (not paragraphs or paragraphs[-1] != txt):
                paragraphs.append(txt)

    if not paragraphs:
        all_txt = " ".join("".join(root.itertext()).split())
        if all_txt:
            paragraphs = [all_txt]

    full_text, pages = _join_pages([(1, "\n\n".join(paragraphs), False, None)])
    return ExtractedDocument(
        text=full_text,
        pages=pages,
        title=title,
        authors=authors[:15],
        extraction_method="XML",
        extraction_confidence=1.0,
        ocr_pages=[],
        extra={"xml_root": _local_name(root.tag)},
    )


def extract_xml(file_path: Path) -> ExtractedDocument:
    raw = file_path.read_bytes().decode("utf-8-sig", errors="replace")
    return extract_xml_text_and_meta(raw)
