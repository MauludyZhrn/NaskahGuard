"""Inline SVG chart generators (Tufte-inspired) for standalone HTML reports."""

from __future__ import annotations

import html
from typing import Any


def svg_layer_breakdown_bar(metrics: dict[str, Any]) -> str:
    exact = float(metrics.get("exact_match_pct", 0.0))
    near = float(metrics.get("near_exact_match_pct", 0.0))
    lex = float(metrics.get("lexical_match_pct", 0.0))
    rows = [
        ("Exact Match", exact, "#dc2626"),
        ("Near-Exact", near, "#ea580c"),
        ("Lexical (Kandidat/Ekstra)", lex, "#ca8a04"),
    ]
    max_val = max([r[1] for r in rows] + [10.0])
    svg_rows = []
    y = 14
    for label, val, color in rows:
        bar_w = max(2.0, (val / max_val) * 260.0) if val > 0 else 0.0
        svg_rows.append(
            f'<text x="4" y="{y + 12}" font-size="11" fill="#334155" font-family="system-ui,sans-serif">{html.escape(label)}</text>'
            f'<rect x="155" y="{y}" width="{bar_w:.1f}" height="15" rx="2" fill="{color}" />'
            f'<text x="{162 + bar_w:.1f}" y="{y + 12}" font-size="11" font-weight="600" fill="#0f172a" font-family="system-ui,sans-serif">{val:.2f}%</text>'
        )
        y += 28
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 490 105" width="100%" height="105">'
        + "".join(svg_rows)
        + "</svg>"
    )


def svg_top_sources_bar(sources: list[dict[str, Any]]) -> str:
    top = sources[:6]
    if not top:
        return '<p style="color:#64748b;font-size:13px;">Tidak ada sumber yang berkontribusi pada indeks kemiripan.</p>'
    max_val = max([float(s.get("contribution_pct", 0.0)) for s in top] + [5.0])
    height = 18 + len(top) * 28
    rows = []
    y = 12
    for s in top:
        title = (s.get("title") or "Sumber")[:28]
        val = float(s.get("contribution_pct", 0.0))
        bar_w = max(2.0, (val / max_val) * 230.0) if val > 0 else 0.0
        rows.append(
            f'<text x="4" y="{y + 12}" font-size="11" fill="#334155" font-family="system-ui,sans-serif">{html.escape(title)}</text>'
            f'<rect x="195" y="{y}" width="{bar_w:.1f}" height="14" rx="2" fill="#2563eb" />'
            f'<text x="{202 + bar_w:.1f}" y="{y + 12}" font-size="11" font-weight="600" fill="#0f172a" font-family="system-ui,sans-serif">{val:.2f}%</text>'
        )
        y += 28
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 {height}" width="100%" height="{height}">'
        + "".join(rows)
        + "</svg>"
    )
