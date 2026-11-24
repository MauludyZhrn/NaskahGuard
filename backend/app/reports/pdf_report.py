"""PDF report exporter powered by ReportLab (platypus + reportlab.graphics)."""

from __future__ import annotations

import io
from typing import Any

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _safe_pdf_text(text: Any) -> str:
    """Sanitize characters outside WinAnsi/cp1252 so ReportLab standard fonts never fail."""
    s = str(text if text is not None else "")
    replacements = {
        "≥": ">=",
        "≤": "<=",
        "→": "->",
        "←": "<-",
        "≠": "!=",
        "×": "x",
        "•": "-",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    # Escape XML entities for ReportLab Paragraph
    s = s.encode("cp1252", errors="replace").decode("cp1252")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_visual_summary(metrics: dict[str, Any], sources: list[dict[str, Any]]) -> Drawing:
    drawing = Drawing(460, 155)
    matched = max(0, int(metrics.get("matched_words", 0)))
    unmatched = max(0, int(metrics.get("unmatched_eligible_words", 0)))
    if matched == 0 and unmatched == 0:
        unmatched = 1

    # Left: Matched vs Unmatched Pie
    drawing.add(String(10, 140, "Rasio Kata Cocok vs Tidak Cocok", fontName="Helvetica-Bold", fontSize=9))
    pie = Pie()
    pie.x = 25
    pie.y = 20
    pie.width = 95
    pie.height = 95
    pie.data = [matched, unmatched]
    pie.labels = [f"Cocok ({matched})", f"Tidak ({unmatched})"]
    pie.slices[0].fillColor = colors.HexColor("#dc2626")
    pie.slices[1].fillColor = colors.HexColor("#cbd5e1")
    pie.simpleLabels = 1
    drawing.add(pie)

    # Right: Layer breakdown horizontal bar
    drawing.add(String(190, 140, "Komposisi Lapisan (%)", fontName="Helvetica-Bold", fontSize=9))
    exact = float(metrics.get("exact_match_pct", 0.0))
    near = float(metrics.get("near_exact_match_pct", 0.0))
    lex = float(metrics.get("lexical_match_pct", 0.0))
    bc = HorizontalBarChart()
    bc.x = 250
    bc.y = 30
    bc.height = 90
    bc.width = 190
    bc.data = [[exact, near, lex]]
    bc.categoryAxis.categoryNames = ["Exact", "Near-Exact", "Lexical"]
    bc.categoryAxis.labels.fontSize = 8
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = max(10.0, exact, near, lex) * 1.15
    bc.bars[0].fillColor = colors.HexColor("#2563eb")
    drawing.add(bc)
    return drawing


def render_pdf_bytes(report: dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=f"Laporan Kemiripan {report.get('report_number', '')}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("NGTitle", parent=styles["Heading1"], fontSize=16, spaceAfter=6)
    h2_style = ParagraphStyle("NGH2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    body_style = ParagraphStyle("NGBody", parent=styles["Normal"], fontSize=9, leading=13)
    small_style = ParagraphStyle("NGSmall", parent=styles["Normal"], fontSize=8, leading=11, textColor=colors.HexColor("#334155"))

    story: list[Any] = []
    metrics = report.get("metrics", {})
    coverage = report.get("coverage", {})
    doc_info = report.get("document", {})
    sources = report.get("sources", [])
    matches = report.get("matches", [])
    stage_counts = report.get("stage_counts", {})

    # 1. Identitas Pemeriksaan & Dokumen
    story.append(Paragraph(_safe_pdf_text(f"{report.get('app_name', 'NaskahGuard')} - Laporan Pemeriksaan Kemiripan"), title_style))
    meta_rows = [
        ["Nomor Laporan", _safe_pdf_text(report.get("report_number")), "Waktu Selesai", _safe_pdf_text(report.get("finished_at") or report.get("created_at"))],
        ["Nama Berkas", _safe_pdf_text(doc_info.get("filename")), "Judul Dokumen", _safe_pdf_text(doc_info.get("title"))],
        ["Tipe / Bahasa", _safe_pdf_text(f"{str(doc_info.get('file_type', '')).upper()} / {doc_info.get('language', '-')}"), "Ekstraksi / Halaman", _safe_pdf_text(f"{doc_info.get('extraction_method', '-')} ({doc_info.get('page_count', 1)} hlm)")],
    ]
    t_meta = Table(meta_rows, colWidths=[3.2 * cm, 5.5 * cm, 3.3 * cm, 5.2 * cm])
    t_meta.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f8fafc")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # 2. Similarity Index & Rincian Persentase
    story.append(Paragraph("Ringkasan Similarity Index & Rincian Persentase", h2_style))
    si_val = float(metrics.get("similarity_index", 0.0))
    op_cat = metrics.get("operational_category", {})
    story.append(
        Paragraph(
            _safe_pdf_text(
                f"Similarity Index (Adjusted): <b>{si_val:.2f}%</b> | "
                f"Raw Similarity: {float(metrics.get('raw_similarity', 0.0)):.2f}% | "
                f"Kategori Operasional: <b>{op_cat.get('level', '-')}</b>"
            ),
            body_style,
        )
    )
    story.append(
        Paragraph(
            _safe_pdf_text(
                f"Exact Match: {float(metrics.get('exact_match_pct', 0.0)):.2f}% | "
                f"Near-Exact Match: {float(metrics.get('near_exact_match_pct', 0.0)):.2f}% | "
                f"Lexical: {float(metrics.get('lexical_match_pct', 0.0)):.2f}% | "
                f"Kandidat Semantik: {metrics.get('semantic_candidates_count', 0)} segmen"
            ),
            body_style,
        )
    )
    story.append(Paragraph(_safe_pdf_text(op_cat.get("disclaimer", "")), small_style))
    story.append(Spacer(1, 6))

    # 3. Metodologi Perhitungan
    story.append(Paragraph("Metodologi Perhitungan", h2_style))
    story.append(
        Paragraph(
            _safe_pdf_text(
                f"SI = (Unique Matched Eligible Words / Total Eligible Words) x 100% = "
                f"({metrics.get('matched_words', 0)} / {metrics.get('eligible_words', 0)}) x 100%. "
                f"Kata yang tumpang tindih antar sumber hanya dihitung sekali menggunakan atribusi eksklusif. "
                f"Total kata: {metrics.get('total_words', 0)}, kata dikecualikan: {metrics.get('excluded_words', 0)}."
            ),
            body_style,
        )
    )
    story.append(Spacer(1, 8))

    # 4. Ringkasan Visual
    story.append(_build_visual_summary(metrics, sources))
    story.append(Spacer(1, 6))

    # 5. Daftar Sumber
    story.append(Paragraph("Daftar Sumber Cocok", h2_style))
    src_rows = [["#", "Judul Sumber", "Tipe & Status", "Kata Eksklusif", "Kontribusi"]]
    for s in sources:
        src_rows.append(
            [
                str(s.get("rank", "")),
                Paragraph(_safe_pdf_text(f"{s.get('title', '')} ({s.get('year') or '-'})"), small_style),
                _safe_pdf_text(f"{s.get('source_type', '')}\n{s.get('access_status', '')}"),
                str(s.get("matched_words_exclusive", 0)),
                f"{float(s.get('contribution_pct', 0.0)):.2f}%",
            ]
        )
    if len(src_rows) == 1:
        src_rows.append(["-", "Tidak ada sumber cocok dalam cakupan yang diperiksa.", "-", "0", "0.00%"])
    t_src = Table(src_rows, colWidths=[0.8 * cm, 7.6 * cm, 3.8 * cm, 2.5 * cm, 2.5 * cm])
    t_src.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_src)
    story.append(Spacer(1, 8))

    # 6. Contoh Teks Cocok (max 20)
    story.append(Paragraph("Contoh Teks yang Cocok (Maks. 20 Passage)", h2_style))
    m_rows = [["Lapisan", "Sumber", "Cuplikan Dokumen", "Kata"]]
    for m in matches[:20]:
        m_rows.append(
            [
                _safe_pdf_text(m.get("layer", "")),
                Paragraph(_safe_pdf_text(m.get("source_title", "")), small_style),
                Paragraph(_safe_pdf_text((m.get("sub_excerpt") or "")[:240]), small_style),
                str(m.get("matched_words", 0)),
            ]
        )
    if len(m_rows) == 1:
        m_rows.append(["-", "Tidak ada kecocokan teks yang ditemukan.", "-", "0"])
    t_m = Table(m_rows, colWidths=[2.2 * cm, 4.5 * cm, 9.0 * cm, 1.5 * cm])
    t_m.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_m)
    story.append(Spacer(1, 8))

    # 7. Ringkasan Tahap Alur Pemeriksaan
    story.append(Paragraph("Alur Pemeriksaan (Jumlah Data Aktual)", h2_style))
    st_rows = [["Tahap", "Data Aktual"]]
    for k, v in stage_counts.items():
        st_rows.append([_safe_pdf_text(k), Paragraph(_safe_pdf_text(v), small_style)])
    t_st = Table(st_rows, colWidths=[4.2 * cm, 13.0 * cm])
    t_st.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_st)
    story.append(Spacer(1, 8))

    # 8. Pernyataan Cakupan & Keterbatasan
    story.append(Paragraph("Pernyataan Cakupan & Keterbatasan Sistem", h2_style))
    story.append(Paragraph(_safe_pdf_text(coverage.get("statement", "")), body_style))
    for note in coverage.get("notes", []):
        story.append(Paragraph(_safe_pdf_text(f"- {note}"), small_style))
    story.append(
        Paragraph(
            _safe_pdf_text(
                "- NaskahGuard tidak mengklaim identik dengan Turnitin/iThenticate dan tidak memiliki akses ke basis data tertutup penerbit."
            ),
            small_style,
        )
    )

    doc.build(story)
    return buf.getvalue()
