"""Standalone HTML report exporter using Jinja2 + inline SVG charts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.reports.charts_svg import svg_layer_breakdown_bar, svg_top_sources_bar

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_html_bytes(report: dict[str, Any]) -> bytes:
    tmpl = _env.get_template("report.html")
    html_str = tmpl.render(
        report=report,
        layer_svg=svg_layer_breakdown_bar(report.get("metrics", {})),
        sources_svg=svg_top_sources_bar(report.get("sources", [])),
    )
    return html_str.encode("utf-8")
