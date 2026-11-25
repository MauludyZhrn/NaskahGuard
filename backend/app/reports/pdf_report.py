"""Institutional editorial PDF report exporter for NaskahGuard.

Structure modeled on academic integrity reports (in NaskahGuard's Ivory Burgundy
editorial style & Bahasa Indonesia):
  - Page 1: Cover Page (Title, Document Details, Right Ivory Stat Card)
  - Page 2: Ringkasan Integritas (Overall %, Active Filters, Category Breakdown, Integrity Flags)
  - Page 3+: Daftar Sumber Utama (Numbered colored pills + category chips + right-aligned %)
  - Annotated Manuscript Pages:
      * If source file is PDF on disk: preserves original PDF pages via PyMuPDF with
        translucent source-colored highlights, left-margin numbered badges, and uniform
        running NaskahGuard headers/footers.
      * Otherwise (DOCX/TXT/HTML): renders paginated annotated paragraphs with left-margin
        colored numbered pills and pastel highlights via ReportLab.
  - Optional Separate Section: Deteksi Pola Tulisan AI (strictly isolated from plagiarism score).
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import get_settings
from app.ingestion.validators import resolve_safe_storage_path
from app.reports.integrity_flags import color_for_rank

# Editorial Ivory Burgundy Palette
COL_BURGUNDY = colors.HexColor("#6E1F2F")
COL_INK = colors.HexColor("#1B1416")
COL_MUTED = colors.HexColor("#5E544F")
COL_TAUPE = colors.HexColor("#9A8F89")
COL_IVORY = colors.HexColor("#F8F5F0")
COL_SAND = colors.HexColor("#F3ECE4")
COL_BORDER = colors.HexColor("#E0D7CB")
COL_LINE = colors.HexColor("#EAE2D7")


def _safe_pdf_text(text: Any) -> str:
    """Sanitize characters outside cp1252 so ReportLab standard fonts never crash."""
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
    s = s.encode("cp1252", errors="replace").decode("cp1252")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _hex_to_rgb01(hex_str: str) -> tuple[float, float, float]:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def _format_pct(val: float) -> str:
    if 0 < val < 1.0:
        return "<1%"
    return f"{round(val):.0f}%"


def _format_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return "-"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def _format_dt(iso_str: str | None) -> str:
    if not iso_str:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return str(iso_str)


class SourcePillFlowable(Flowable):
    """Draws a rounded colored rank pill + optional soft category chip cleanly."""

    def __init__(
        self,
        rank: int,
        badge_hex: str,
        category_label: str = "",
        chip_bg_hex: str = "#EDE6DD",
        chip_text_hex: str = "#1B1416",
    ) -> None:
        super().__init__()
        self.rank = rank
        self.badge_hex = badge_hex
        self.category_label = category_label
        self.chip_bg_hex = chip_bg_hex
        self.chip_text_hex = chip_text_hex
        self.pill_w = 24
        self.pill_h = 14
        self.chip_w = max(56, len(category_label) * 5.2 + 14) if category_label else 0
        self.width = self.pill_w + (8 + self.chip_w if category_label else 0)
        self.height = self.pill_h

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        # Rank pill
        c.setFillColor(colors.HexColor(self.badge_hex))
        c.roundRect(0, 0, self.pill_w, self.pill_h, 7, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(self.pill_w / 2.0, 4.2, str(self.rank))
        # Category chip
        if self.category_label:
            x0 = self.pill_w + 6
            c.setFillColor(colors.HexColor(self.chip_bg_hex))
            c.roundRect(x0, 0, self.chip_w, self.pill_h, 7, fill=1, stroke=0)
            c.setFillColor(colors.HexColor(self.chip_text_hex))
            c.setFont("Helvetica-Bold", 7.5)
            c.drawCentredString(x0 + self.chip_w / 2.0, 4.2, _safe_pdf_text(self.category_label))
        c.restoreState()


class MarginBadgeStack(Flowable):
    """Vertical stack of small rounded numbered source badges for the left margin gutter."""

    def __init__(self, badges: list[tuple[int, str]]) -> None:
        super().__init__()
        self.badges = badges[:6]
        self.width = 22
        self.height = max(14, len(self.badges) * 16)

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        y = self.height - 13
        for rank, hex_col in self.badges:
            c.setFillColor(colors.HexColor(hex_col))
            c.roundRect(0, y, 20, 12, 6, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(10, y + 3.4, str(rank))
            y -= 15
        c.restoreState()


def _group_viewer_paragraphs(viewer: dict[str, Any] | None) -> list[dict[str, Any]]:
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
                }
            )
            rank = seg.get("source_rank")
            if rank is not None and seg.get("category") not in {"PLAIN", "EXCLUDED"} and rank not in seen_ranks:
                seen_ranks.add(rank)
                cur["badges"].append((int(rank), str(seg.get("source_color") or "#6E1F2F")))
    return [p for p in paragraphs if any(s["text"].strip() for s in p["segments"])]


def _build_front_matter_pdf(
    report: dict[str, Any],
    viewer: dict[str, Any] | None,
    include_text_pages: bool,
) -> tuple[bytes, list[str]]:
    """Build Cover Page, Ringkasan Integritas, Top Sources, optional text pages, and AI page."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.1 * cm,
        bottomMargin=1.9 * cm,
        title=f"Laporan Integritas {report.get('report_number', '')}",
    )

    styles = getSampleStyleSheet()
    eyebrow_style = ParagraphStyle(
        "NGEyebrow",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=COL_BURGUNDY,
        spaceAfter=6,
    )
    cover_title_style = ParagraphStyle(
        "NGCoverTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=24,
        textColor=COL_INK,
        spaceAfter=10,
    )
    h2_style = ParagraphStyle(
        "NGH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=COL_INK,
        spaceBefore=12,
        spaceAfter=6,
    )
    score_big_style = ParagraphStyle(
        "NGScoreBig",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=COL_INK,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "NGBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=13.5,
        textColor=COL_INK,
    )
    muted_style = ParagraphStyle(
        "NGMuted",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.3,
        leading=12,
        textColor=COL_MUTED,
    )
    label_style = ParagraphStyle(
        "NGLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.8,
        leading=10.5,
        textColor=COL_TAUPE,
        spaceBefore=6,
    )
    val_style = ParagraphStyle(
        "NGVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.8,
        leading=12,
        textColor=COL_INK,
    )
    stat_style = ParagraphStyle(
        "NGStat",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=16,
        textColor=COL_INK,
    )

    metrics = report.get("metrics", {})
    doc_info = report.get("document", {})
    sources = report.get("sources", [])
    active_filters = report.get("active_filters", [])
    source_cats = report.get("source_categories", {})
    integrity_flags = report.get("integrity_flags", [])
    ai_rep = report.get("ai_report")
    mode = report.get("mode", "PLAGIARISM_ONLY")

    mode_labels = {
        "PLAGIARISM_ONLY": "Pemeriksaan Plagiasi",
        "AI_ONLY": "Deteksi Tulisan AI",
        "COMBINED": "Pemeriksaan Gabungan (Plagiasi + AI Terpisah)",
    }

    story: list[Any] = []
    page_sections: dict[int, str] = {}
    page_count_ref = [0]

    # Track exact section name per 1-based page number directly from canvas during flowable draw
    current_section = ["Sampul Laporan"]

    class _SectionMarker(Flowable):
        def __init__(self, label: str) -> None:
            super().__init__()
            self.label = label
            self.width = 0
            self.height = 0

        def draw(self) -> None:
            current_section[0] = self.label
            pno = int(self.canv.getPageNumber())
            page_sections[pno] = self.label

    def _on_page(canvas, _doc):
        pno = int(canvas.getPageNumber())
        page_count_ref[0] = max(page_count_ref[0], pno)
        page_sections.setdefault(pno, current_section[0])

    # ================= PAGE 1: COVER PAGE =================
    story.append(_SectionMarker("Sampul Laporan"))
    story.append(Spacer(1, 3.6 * cm))
    story.append(Paragraph("LAPORAN PEMERIKSAAN INTEGRITAS NASKAH", eyebrow_style))
    story.append(Paragraph(_safe_pdf_text(doc_info.get("title") or doc_info.get("filename")), cover_title_style))

    authors_list = doc_info.get("authors") or []
    if authors_list:
        story.append(Paragraph(_safe_pdf_text("Penulis: " + ", ".join(authors_list)), muted_style))
    story.append(Paragraph(_safe_pdf_text(f"Mode Pemeriksaan: {mode_labels.get(mode, mode)}"), muted_style))
    story.append(Paragraph(_safe_pdf_text(f"Platform: {report.get('app_name', 'NaskahGuard')} (Lokal & Open-Source)"), muted_style))
    story.append(Spacer(1, 0.9 * cm))
    story.append(HRFlowable(width="100%", thickness=0.6, color=COL_BORDER, spaceAfter=14))

    story.append(Paragraph("Detail Dokumen", h2_style))
    left_details = [
        Paragraph("Nomor Laporan", label_style),
        Paragraph(_safe_pdf_text(report.get("report_number")), val_style),
        Paragraph("Tanggal Pemeriksaan", label_style),
        Paragraph(_safe_pdf_text(_format_dt(report.get("finished_at") or report.get("created_at"))), val_style),
        Paragraph("Tanggal Unduh", label_style),
        Paragraph(_safe_pdf_text(datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")), val_style),
        Paragraph("Nama Berkas", label_style),
        Paragraph(_safe_pdf_text(doc_info.get("filename")), val_style),
        Paragraph("Ukuran Berkas", label_style),
        Paragraph(_safe_pdf_text(_format_size(doc_info.get("size_bytes"))), val_style),
    ]
    char_cnt = int(doc_info.get("character_count") or 0)
    right_box = Table(
        [
            [Paragraph(f"{int(doc_info.get('page_count') or 1):,} Halaman", stat_style)],
            [Paragraph(f"{int(doc_info.get('word_count') or 0):,} Kata", stat_style)],
            [Paragraph(f"{char_cnt:,} Karakter", stat_style)],
        ],
        colWidths=[5.4 * cm],
    )
    right_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COL_IVORY),
                ("BOX", (0, 0), (-1, -1), 0.6, COL_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (0, 0), 12),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
                ("TOPPADDING", (0, 1), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -2), 3),
            ]
        )
    )
    details_tbl = Table([[left_details, right_box]], colWidths=[11.0 * cm, 5.8 * cm])
    details_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(details_tbl)

    # ================= PAGE 2: RINGKASAN INTEGRITAS =================
    story.append(PageBreak())
    story.append(_SectionMarker("Ringkasan Integritas"))

    if mode != "AI_ONLY":
        si_val = float(metrics.get("similarity_index", 0.0))
        si_int = f"{si_val:.1f}%" if si_val % 1 != 0 else f"{int(si_val)}%"
        story.append(
            Paragraph(
                f'<font color="#6E1F2F">{si_int}</font> &nbsp; Kemiripan Keseluruhan',
                score_big_style,
            )
        )
        story.append(
            Paragraph(
                _safe_pdf_text(
                    f"Total gabungan kecocokan unik: {int(metrics.get('matched_words', 0)):,} dari "
                    f"{int(metrics.get('eligible_words', 0)):,} kata inti yang diperiksa (tanpa penghitungan ganda)."
                ),
                muted_style,
            )
        )
        story.append(Spacer(1, 0.45 * cm))

        story.append(Paragraph("Bagian yang Dikecualikan", h2_style))
        if active_filters:
            for flt in active_filters:
                story.append(Paragraph(f"- &nbsp; {_safe_pdf_text(flt)}", body_style))
        else:
            story.append(Paragraph("Tidak ada pengecualian bagian yang diaktifkan.", muted_style))
        story.append(Spacer(1, 0.35 * cm))
        story.append(HRFlowable(width="100%", thickness=0.6, color=COL_BORDER, spaceAfter=10))

        story.append(Paragraph("Ringkasan Sumber per Kategori", h2_style))
        cat_rows = [
            [
                Paragraph(f"<b>{source_cats.get('internet_pct', 0):.1f}%</b>", body_style),
                Paragraph("Sumber Internet &amp; Halaman Web Terbuka", body_style),
            ],
            [
                Paragraph(f"<b>{source_cats.get('publication_pct', 0):.1f}%</b>", body_style),
                Paragraph("Publikasi Ilmiah &amp; Jurnal Terbuka", body_style),
            ],
            [
                Paragraph(f"<b>{source_cats.get('local_pct', 0):.1f}%</b>", body_style),
                Paragraph("Korpus Lokal &amp; Repositori Institusi", body_style),
            ],
        ]
        cat_tbl = Table(cat_rows, colWidths=[2.2 * cm, 14.6 * cm])
        cat_tbl.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(cat_tbl)
        story.append(Spacer(1, 0.35 * cm))
        story.append(HRFlowable(width="100%", thickness=0.6, color=COL_BORDER, spaceAfter=10))

    # Integrity Flags Block
    story.append(Paragraph("Tanda Integritas", h2_style))
    flag_items: list[Any] = []
    if integrity_flags:
        flag_items.append(Paragraph(f"<b>{len(integrity_flags)} Tanda Integritas untuk Ditinjau</b>", body_style))
        flag_items.append(Spacer(1, 4))
        for fl in integrity_flags:
            flag_items.append(
                Paragraph(
                    f'<font color="#6E1F2F"><b>[!]</b></font> &nbsp;<b>{_safe_pdf_text(fl["title"])}</b><br/>'
                    f'<font color="#5E544F">{_safe_pdf_text(fl["summary"])} {_safe_pdf_text(fl["detail"])}</font>',
                    muted_style,
                )
            )
            flag_items.append(Spacer(1, 5))
    else:
        flag_items.append(
            Paragraph(
                "<b>0 Anomali Karakter Terdeteksi</b><br/>"
                '<font color="#5E544F">Tidak ditemukan karakter pengganti (homoglyph) atau karakter tak terlihat yang disisipkan pada kata Latin.</font>',
                muted_style,
            )
        )

    if isinstance(ai_rep, dict):
        ai_pct = ai_rep.get("ai_likelihood_pct")
        ai_score_str = f"{ai_pct:.1f}%" if ai_pct is not None else "Tidak Cukup Bukti"
        flag_items.append(Spacer(1, 6))
        flag_items.append(
            Paragraph(
                f'<b>Indikasi Pola Tulisan AI (Terpisah): {ai_score_str}</b><br/>'
                f'<font color="#5E544F">Klasifikasi: {_safe_pdf_text(ai_rep.get("classification_label", "-"))} '
                f'(Keyakinan: {_safe_pdf_text(ai_rep.get("confidence_label", "-"))}). Bersifat probabilistik, bukan vonis.</font>',
                muted_style,
            )
        )

    callout_box = Table(
        [
            [
                Paragraph(
                    "Algoritma NaskahGuard menelaah dokumen secara lokal untuk menemukan kecocokan sumber dan inkonsistensi penulisan.<br/><br/>"
                    "Tanda integritas atau skor kemiripan bukan bukti otomatis pelanggaran akademik, melainkan titik fokus untuk peninjauan manusia.",
                    muted_style,
                )
            ]
        ],
        colWidths=[7.4 * cm],
    )
    callout_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COL_SAND),
                ("BOX", (0, 0), (-1, -1), 0.6, COL_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    flag_tbl = Table([[flag_items, callout_box]], colWidths=[9.0 * cm, 7.8 * cm])
    flag_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(flag_tbl)

    # ================= PAGE 3+: DAFTAR SUMBER UTAMA BERWARNA =================
    if mode != "AI_ONLY" and sources:
        story.append(PageBreak())
        story.append(_SectionMarker("Daftar Sumber Utama"))
        story.append(Paragraph("Daftar Sumber Utama", h2_style))
        story.append(
            Paragraph(
                "Sumber dengan tingkat kecocokan tertinggi pada naskah. Setiap bagian teks yang tumpang tindih hanya dihitung satu kali pada sumber peringkat tertinggi.",
                muted_style,
            )
        )
        story.append(Spacer(1, 0.35 * cm))

        for src in sources:
            rank = int(src.get("rank") or 1)
            pal = color_for_rank(rank)
            pill = SourcePillFlowable(
                rank=rank,
                badge_hex=src.get("color_hex") or pal["badge"],
                category_label=src.get("category_label") or "Sumber",
                chip_bg_hex=src.get("chip_bg_hex") or pal["chip_bg"],
                chip_text_hex=src.get("chip_text_hex") or pal["chip_text"],
            )
            title_txt = _safe_pdf_text(src.get("title") or src.get("filename"))
            authors_str = ", ".join(src.get("authors") or [])
            sub_meta = " · ".join(
                p for p in [authors_str, str(src["year"]) if src.get("year") else "", src.get("doi") or ""] if p
            )
            left_cell = [pill, Spacer(1, 4), Paragraph(f"<b>{title_txt}</b>", body_style)]
            if sub_meta:
                left_cell.append(Paragraph(_safe_pdf_text(sub_meta), muted_style))

            pct_str = _format_pct(float(src.get("contribution_pct") or 0.0))
            row_tbl = Table(
                [[left_cell, Paragraph(f"<b>{pct_str}</b>", ParagraphStyle("PctR", parent=body_style, alignment=2))]],
                colWidths=[14.6 * cm, 2.2 * cm],
            )
            row_tbl.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.5, COL_LINE),
                    ]
                )
            )
            story.append(row_tbl)

    # ================= OPTIONAL SEPARATE AI WRITING SECTION =================
    if isinstance(ai_rep, dict):
        story.append(PageBreak())
        story.append(_SectionMarker("Laporan Deteksi Tulisan AI"))
        story.append(Paragraph("LAPORAN TERPISAH — DETEKSI POLA TULISAN AI", eyebrow_style))
        story.append(
            Paragraph(
                f"Dokumen dianalisis: <b>{_safe_pdf_text(doc_info.get('title') or doc_info.get('filename'))}</b>",
                muted_style,
            )
        )
        story.append(Spacer(1, 0.15 * cm))
        ai_pct = ai_rep.get("ai_likelihood_pct")
        score_disp = f"{ai_pct:.1f}%" if ai_pct is not None else "Tidak Cukup Bukti"
        story.append(
            Paragraph(
                f'<font color="#6E1F2F">{score_disp}</font> &nbsp; {_safe_pdf_text(ai_rep.get("classification_label", "-"))}',
                score_big_style,
            )
        )
        cal_info = ai_rep.get("calibration") or {}
        conf_lbl = _safe_pdf_text(ai_rep.get("confidence_label", "-"))
        unc_val = ai_rep.get("uncertainty_pct")
        unc_txt = f" · Ketidakpastian +/-{unc_val:.1f}%" if unc_val is not None else ""
        cal_txt = (
            f" · Kalibrasi: T={cal_info.get('temperature', 1.3)}"
            if cal_info.get("calibrated")
            else ""
        )
        story.append(Paragraph(f"Tingkat Keyakinan: <b>{conf_lbl}</b>{unc_txt}{cal_txt}", muted_style))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(_safe_pdf_text(ai_rep.get("summary_id", "")), body_style))
        story.append(Spacer(1, 0.25 * cm))

        paras = ai_rep.get("paragraphs") or []
        ps = ai_rep.get("paragraph_summary") or {
            "total_paragraphs": len(paras),
            "ai_likely_count": sum(1 for p in paras if p.get("classification") == "AI_LIKELY"),
            "human_likely_count": sum(1 for p in paras if p.get("classification") == "HUMAN_LIKELY"),
            "uncertain_count": sum(1 for p in paras if p.get("classification") == "MIXED_UNCERTAIN"),
            "insufficient_count": sum(1 for p in paras if p.get("classification") == "INSUFFICIENT_DATA"),
        }
        ai_stat_tbl = Table(
            [
                [
                    Paragraph("<b>Total Paragraf</b>", muted_style),
                    Paragraph("<b>Indikasi AI</b>", muted_style),
                    Paragraph("<b>Indikasi Manusia</b>", muted_style),
                    Paragraph("<b>Tidak Pasti / Pendek</b>", muted_style),
                ],
                [
                    Paragraph(f"<b>{ps.get('total_paragraphs', 0)}</b>", stat_style),
                    Paragraph(f'<font color="#6E1F2F"><b>{ps.get("ai_likely_count", 0)}</b></font>', stat_style),
                    Paragraph(f'<font color="#15803D"><b>{ps.get("human_likely_count", 0)}</b></font>', stat_style),
                    Paragraph(f"<b>{int(ps.get('uncertain_count', 0)) + int(ps.get('insufficient_count', 0))}</b>", stat_style),
                ],
            ],
            colWidths=[4.2 * cm, 4.2 * cm, 4.2 * cm, 4.2 * cm],
        )
        ai_stat_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), COL_IVORY),
                    ("BOX", (0, 0), (-1, -1), 0.6, COL_BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, COL_BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(ai_stat_tbl)
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph(f"<i>Catatan Penting: {_safe_pdf_text(ai_rep.get('disclaimer', ''))}</i>", muted_style))
        lims = ai_rep.get("limitations") or []
        if lims:
            story.append(Spacer(1, 0.15 * cm))
            story.append(
                Paragraph(
                    "Keterbatasan Deteksi: " + " ".join(_safe_pdf_text(x) for x in lims[:3]),
                    muted_style,
                )
            )
        story.append(Spacer(1, 0.3 * cm))
        story.append(HRFlowable(width="100%", thickness=0.6, color=COL_BORDER, spaceAfter=8))

        if paras:
            story.append(Paragraph("Highlight & Ringkasan Analisis per Paragraf", h2_style))
            p_rows = [["Prg", "Kata", "Klasifikasi", "Indikasi AI", "Cuplikan & Alasan"]]
            row_styles = [
                ("BACKGROUND", (0, 0), (-1, 0), COL_IVORY),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, COL_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
            for r_idx, p in enumerate(paras[:30], start=1):
                pct_p = f"{p['ai_likelihood_pct']:.1f}%" if p.get("ai_likelihood_pct") is not None else "-"
                reason = (p.get("reasons") or ["-"])[0]
                excerpt_p = _safe_pdf_text(str(p.get("text") or "")[:120])
                cls_code = p.get("classification")
                if cls_code == "AI_LIKELY":
                    row_styles.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#FBF0F2")))
                elif cls_code == "MIXED_UNCERTAIN":
                    row_styles.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#FEF8EC")))
                elif cls_code == "HUMAN_LIKELY":
                    row_styles.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F1FAF4")))
                p_rows.append(
                    [
                        str(int(p.get("paragraph_index", 0)) + 1),
                        str(p.get("word_count", 0)),
                        Paragraph(_safe_pdf_text(p.get("classification_label", "-")), muted_style),
                        pct_p,
                        Paragraph(f'"{excerpt_p}..."<br/><font color="#5E544F">{_safe_pdf_text(reason[:140])}</font>', muted_style),
                    ]
                )
            t_ai = Table(p_rows, colWidths=[1.0 * cm, 1.2 * cm, 3.4 * cm, 1.9 * cm, 9.3 * cm])
            t_ai.setStyle(TableStyle(row_styles))
            story.append(t_ai)

    # ================= ANNOTATED MANUSCRIPT TEXT PAGES (FOR NON-PDF / FALLBACK) =================
    if include_text_pages and mode != "AI_ONLY":
        annotated = _group_viewer_paragraphs(viewer)
        if annotated:
            story.append(PageBreak())
            story.append(_SectionMarker("Naskah Berpenanda"))
            story.append(Paragraph("Naskah Lengkap dengan Penanda Sumber", h2_style))
            story.append(
                Paragraph(
                    "Nomor berwarna di margin kiri menunjukkan peringkat sumber pada Daftar Sumber Utama yang cocok dengan sorotan paragraf terkait.",
                    muted_style,
                )
            )
            story.append(Spacer(1, 0.3 * cm))

            for para in annotated:
                chunks: list[str] = []
                for seg in para["segments"]:
                    esc = _safe_pdf_text(seg["text"]).replace("\n", "<br/>")
                    cat = seg.get("category", "PLAIN")
                    hl = seg.get("source_highlight")
                    if cat not in {"PLAIN", "EXCLUDED"} and hl:
                        chunks.append(f'<font backColor="{hl}">{esc}</font>')
                    elif cat == "EXCLUDED":
                        chunks.append(f'<font color="#8A807A">{esc}</font>')
                    else:
                        chunks.append(esc)
                para_flow = Paragraph("".join(chunks), ParagraphStyle("NGDocText", parent=body_style, fontSize=9.3, leading=14.2))
                gutter_cell: Any = MarginBadgeStack(para["badges"]) if para["badges"] else Spacer(1, 1)
                p_tbl = Table([[gutter_cell, para_flow]], colWidths=[1.1 * cm, 15.7 * cm])
                p_tbl.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                story.append(p_tbl)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    total_front = max(page_count_ref[0], max(page_sections.keys(), default=1))
    section_labels: list[str] = []
    last_lbl = "Sampul Laporan"
    for pno in range(1, total_front + 1):
        if pno in page_sections:
            last_lbl = page_sections[pno]
        section_labels.append(last_lbl)
    return buf.getvalue(), section_labels


def _annotate_original_pdf_pages(
    pdf_path: Path,
    report: dict[str, Any],
) -> tuple[bytes, int] | None:
    """Render original uploaded PDF inside framed A4 pages with source-colored highlights & left-margin badges."""
    try:
        import fitz
    except Exception:
        return None

    try:
        src_pdf = fitz.open(str(pdf_path))
    except Exception:
        return None

    out_pdf = fitz.open()
    matches = [m for m in (report.get("matches") or []) if m.get("source_rank") is not None and not m.get("excluded_reason")]

    # Precompute short search phrases per match (3-7 words) so PyMuPDF locates them cleanly on original pages
    match_phrases: list[tuple[int, str, str, list[str]]] = []
    for m in matches:
        rank = int(m["source_rank"])
        pal = color_for_rank(rank)
        badge_hex = m.get("source_color") or pal["badge"]
        hl_hex = m.get("source_highlight") or pal["highlight"]
        excerpt = " ".join(str(m.get("sub_excerpt") or "").split())
        words = excerpt.split()
        if len(words) < 3:
            continue
        phrases: list[str] = []
        step = 6
        for i in range(0, min(len(words), 36), step):
            chunk = " ".join(words[i : i + 6])
            if len(chunk) >= 14:
                phrases.append(chunk)
        if phrases:
            match_phrases.append((rank, badge_hex, hl_hex, phrases))

    a4_w, a4_h = 595.28, 841.89
    gutter_left = 44.0
    margin_right = 24.0
    margin_top = 46.0
    margin_bottom = 42.0
    target_box = fitz.Rect(gutter_left, margin_top, a4_w - margin_right, a4_h - margin_bottom)

    try:
        for pno in range(len(src_pdf)):
            orig_page = src_pdf[pno]
            orig_rect = orig_page.rect
            new_page = out_pdf.new_page(width=a4_w, height=a4_h)

            scale = min(target_box.width / max(1.0, orig_rect.width), target_box.height / max(1.0, orig_rect.height))
            draw_w = orig_rect.width * scale
            draw_h = orig_rect.height * scale
            dx = target_box.x0 + (target_box.width - draw_w) / 2.0
            dy = target_box.y0 + (target_box.height - draw_h) / 2.0
            dest_rect = fitz.Rect(dx, dy, dx + draw_w, dy + draw_h)

            new_page.show_pdf_page(dest_rect, src_pdf, pno)

            # Find matched excerpts on this page & overlay translucent source highlights + left-margin rank pills
            placed_badges: list[tuple[float, int, str]] = []
            for rank, badge_hex, hl_hex, phrases in match_phrases:
                hl_rgb = _hex_to_rgb01(hl_hex)
                page_rects: list[fitz.Rect] = []
                for ph in phrases:
                    found = orig_page.search_for(ph)
                    if found:
                        page_rects.extend(found[:4])
                if not page_rects:
                    continue
                first_y = None
                for r in page_rects:
                    mapped = fitz.Rect(
                        dx + (r.x0 - orig_rect.x0) * scale,
                        dy + (r.y0 - orig_rect.y0) * scale,
                        dx + (r.x1 - orig_rect.x0) * scale,
                        dy + (r.y1 - orig_rect.y0) * scale,
                    )
                    new_page.draw_rect(mapped, color=None, fill=hl_rgb, fill_opacity=0.38, overlay=True)
                    if first_y is None or mapped.y0 < first_y:
                        first_y = mapped.y0
                if first_y is not None:
                    placed_badges.append((first_y, rank, badge_hex))

            # Draw deduplicated non-overlapping numbered colored pills in the left margin gutter
            placed_badges.sort(key=lambda item: (round(item[0] / 12.0), item[1]))
            last_y = -999.0
            seen_cluster: set[tuple[int, int]] = set()
            for y_pos, rank, badge_hex in placed_badges:
                bucket = (int(y_pos // 16), rank)
                if bucket in seen_cluster:
                    continue
                seen_cluster.add(bucket)
                draw_y = max(y_pos, last_y + 15.0)
                if draw_y > a4_h - margin_bottom - 14:
                    continue
                last_y = draw_y
                pill_rect = fitz.Rect(13.0, draw_y, 35.0, draw_y + 13.0)
                new_page.draw_rect(pill_rect, color=None, fill=_hex_to_rgb01(badge_hex), radius=0.42, overlay=True)
                rank_txt = str(rank)
                tw = fitz.get_text_length(rank_txt, fontname="hebo", fontsize=7.6)
                new_page.insert_text(
                    (24.0 - tw / 2.0, draw_y + 9.2),
                    rank_txt,
                    fontsize=7.6,
                    fontname="hebo",
                    color=(1, 1, 1),
                    overlay=True,
                )

        annotated_bytes = out_pdf.tobytes()
        count = len(out_pdf)
        return annotated_bytes, count
    finally:
        src_pdf.close()
        out_pdf.close()


def _stamp_running_headers_and_footers(
    merged_pdf_bytes: bytes,
    section_labels: list[str],
    app_name: str,
    report_number: str,
) -> bytes:
    """Stamp uniform crisp running headers & footers ('Halaman X dari Y') on every page."""
    try:
        import fitz
    except Exception:
        return merged_pdf_bytes

    pdf = fitz.open(stream=merged_pdf_bytes, filetype="pdf")
    total_pages = len(pdf)
    burgundy_rgb = _hex_to_rgb01("#6E1F2F")
    muted_rgb = _hex_to_rgb01("#5E544F")
    line_rgb = _hex_to_rgb01("#E0D7CB")

    try:
        for idx, page in enumerate(pdf):
            sec = section_labels[idx] if idx < len(section_labels) else "Naskah Berpenanda"
            w = page.rect.width
            h = page.rect.height

            # Top header
            page.insert_text((36, 28), _safe_pdf_text(app_name), fontsize=9.5, fontname="hebo", color=burgundy_rgb)
            page.insert_text(
                (118, 28),
                f"Halaman {idx + 1} dari {total_pages} - {_safe_pdf_text(sec)}",
                fontsize=7.8,
                fontname="helv",
                color=muted_rgb,
            )
            page.insert_textbox(
                fitz.Rect(w - 220, 19, w - 36, 34),
                f"No. Laporan {_safe_pdf_text(report_number)}",
                fontsize=7.8,
                fontname="helv",
                color=muted_rgb,
                align=fitz.TEXT_ALIGN_RIGHT,
            )
            page.draw_line((36, 36), (w - 36, 36), color=line_rgb, width=0.6)

            # Bottom footer
            page.draw_line((36, h - 34), (w - 36, h - 34), color=line_rgb, width=0.6)
            page.insert_text((36, h - 22), _safe_pdf_text(app_name), fontsize=8.5, fontname="hebo", color=burgundy_rgb)
            page.insert_text(
                (118, h - 22),
                f"Halaman {idx + 1} dari {total_pages} - {_safe_pdf_text(sec)}",
                fontsize=7.5,
                fontname="helv",
                color=muted_rgb,
            )
            page.insert_textbox(
                fitz.Rect(w - 220, h - 30, w - 36, h - 14),
                f"No. Laporan {_safe_pdf_text(report_number)}",
                fontsize=7.5,
                fontname="helv",
                color=muted_rgb,
                align=fitz.TEXT_ALIGN_RIGHT,
            )

        return pdf.tobytes()
    finally:
        pdf.close()


def render_pdf_bytes(report: dict[str, Any], viewer: dict[str, Any] | None = None) -> bytes:
    """Render institutional PDF report, overlaying original PDF pages when available."""
    doc_info = report.get("document", {})
    mode = report.get("mode", "PLAGIARISM_ONLY")
    annotated_orig: tuple[bytes, int] | None = None

    if mode != "AI_ONLY" and str(doc_info.get("file_type") or "").lower() == "pdf" and doc_info.get("stored_name"):
        try:
            settings = get_settings()
            pdf_path = resolve_safe_storage_path(settings.storage_path, "uploads", str(doc_info["stored_name"]))
            if pdf_path.exists():
                annotated_orig = _annotate_original_pdf_pages(pdf_path, report)
        except Exception:
            annotated_orig = None

    front_bytes, front_labels = _build_front_matter_pdf(
        report,
        viewer=viewer,
        include_text_pages=(annotated_orig is None),
    )

    merged_bytes = front_bytes
    all_labels = list(front_labels)

    if annotated_orig is not None:
        orig_bytes, orig_count = annotated_orig
        try:
            import fitz

            merged = fitz.open(stream=front_bytes, filetype="pdf")
            orig_doc = fitz.open(stream=orig_bytes, filetype="pdf")
            merged.insert_pdf(orig_doc)
            merged_bytes = merged.tobytes()
            all_labels.extend(["Naskah Berpenanda"] * orig_count)
            merged.close()
            orig_doc.close()
        except Exception:
            pass

    return _stamp_running_headers_and_footers(
        merged_bytes,
        section_labels=all_labels,
        app_name=str(report.get("app_name") or "NaskahGuard"),
        report_number=str(report.get("report_number") or "-"),
    )
