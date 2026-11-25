"""Standalone institutional HTML report exporter with source-colored margin highlights."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _group_viewer_paragraphs(viewer: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Group viewer segments into paragraphs with deduplicated left-margin source pills."""
    if not viewer or not viewer.get("segments"):
        return []
    paragraphs: list[dict[str, Any]] = [{"segments": [], "badges": []}]
    seen_ranks: set[int] = set()

    for seg in viewer["segments"]:
        raw_text = str(seg.get("text") or "")
        parts = raw_text.split("\n\n")
        for idx, part in enumerate(parts):
            if idx > 0:
                paragraphs.append({"segments": [], "badges": []})
                seen_ranks = set()
            if not part:
                continue
            cur = paragraphs[-1]
            cur["segments"].append(
                {
                    "text": part,
                    "category": seg.get("category", "PLAIN"),
                    "source_rank": seg.get("source_rank"),
                    "source_color": seg.get("source_color"),
                    "source_highlight": seg.get("source_highlight"),
                    "excluded_reason": seg.get("excluded_reason"),
                }
            )
            rank = seg.get("source_rank")
            if rank is not None and seg.get("category") not in {"PLAIN", "EXCLUDED"} and rank not in seen_ranks:
                seen_ranks.add(rank)
                cur["badges"].append(
                    {
                        "rank": rank,
                        "color": seg.get("source_color") or "#6E1F2F",
                    }
                )

    return [p for p in paragraphs if any(s["text"].strip() for s in p["segments"])]


def _format_pct_label(val: float) -> str:
    if 0 < val < 1.0:
        return "<1%"
    return f"{round(val):.0f}%"


def _format_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return "-"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def render_html_bytes(report: dict[str, Any], viewer: dict[str, Any] | None = None) -> bytes:
    tmpl = _env.get_template("report.html")
    doc_info = report.get("document", {})
    html_str = tmpl.render(
        report=report,
        annotated_paragraphs=_group_viewer_paragraphs(viewer),
        download_date=datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        file_size_label=_format_size(doc_info.get("size_bytes")),
        format_pct=_format_pct_label,
    )
    return html_str.encode("utf-8")
