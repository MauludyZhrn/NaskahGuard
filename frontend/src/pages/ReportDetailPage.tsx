import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Download,
  ExternalLink,
  FileText,
  Layers,
  BarChart3,
  GitBranch,
  Table2,
  Globe,
  ShieldCheck,
  Calculator,
  ChevronsUpDown,
  Info,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  Bar,
  BarChart,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { BlurFade } from "@/components/ui/blur-fade";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { NumberTicker } from "@/components/ui/number-ticker";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, downloadProtectedFile } from "../api/client";
import { ProcessFlowchart } from "../components/ProcessFlowchart";
import { SimilarityGauge } from "../components/SimilarityGauge";
import { FullReport, ReportSource, SourceViewerPayload, ViewerPayload } from "../types";
import { formatDuration, formatMs } from "../utils/format";

type TabKey = "overview" | "compare" | "sources" | "evidence" | "coverage" | "analytics" | "flowchart" | "export";

const ALL_ACCORDION_KEYS = ["formula", "sources_metrics", "coverage_notes", "timings"];
const DEFAULT_ACCORDION_KEYS = ["formula", "sources_metrics"];
const MATCHES_PAGE_SIZE = 15;

const CATEGORY_LABEL: Record<string, string> = {
  EXACT: "Exact",
  NEAR_EXACT: "Near-Exact",
  LEXICAL: "Lexical",
  SEMANTIC: "Kandidat Semantik",
  EXCLUDED: "Dikecualikan",
};

const TufteTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        fontFamily: "var(--font-serif)",
        fontSize: 13,
        color: "var(--text)",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        padding: "6px 10px",
        borderRadius: 6,
      }}
    >
      <div style={{ color: "var(--text-secondary)", fontSize: 11 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey}>
          {p.name}: <strong>{Number(p.value).toLocaleString("id-ID")}</strong>
        </div>
      ))}
    </div>
  );
};

export const ReportDetailPage: React.FC = () => {
  const { checkId } = useParams<{ checkId: string }>();
  const [tab, setTab] = useState<TabKey>("overview");
  const [report, setReport] = useState<FullReport | null>(null);
  const [viewer, setViewer] = useState<ViewerPayload | null>(null);
  const [sourceViewer, setSourceViewer] = useState<SourceViewerPayload | null>(null);
  const [activeMatchId, setActiveMatchId] = useState<number | null>(null);
  const [syncScroll, setSyncScroll] = useState(true);
  const [filters, setFilters] = useState<Record<string, boolean>>({
    EXACT: true,
    NEAR_EXACT: true,
    LEXICAL: true,
    SEMANTIC: true,
    EXCLUDED: true,
  });
  const [openAccordions, setOpenAccordions] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem("ng_report_open_accordions");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch {
      // ignore invalid storage
    }
    return DEFAULT_ACCORDION_KEYS;
  });
  const [matchesPage, setMatchesPage] = useState(1);
  const [matchLayerFilter, setMatchLayerFilter] = useState<string>("ALL");
  const [selectedSourceModal, setSelectedSourceModal] = useState<ReportSource | null>(null);
  const [error, setError] = useState<string | null>(null);

  const leftPaneRef = useRef<HTMLDivElement>(null);
  const rightPaneRef = useRef<HTMLDivElement>(null);
  const isSyncingRef = useRef(false);

  useEffect(() => {
    try {
      localStorage.setItem("ng_report_open_accordions", JSON.stringify(openAccordions));
    } catch {
      // ignore storage quota errors
    }
  }, [openAccordions]);

  useEffect(() => {
    if (!checkId) return;
    Promise.all([
      apiFetch<FullReport>(`/checks/${checkId}/report`),
      apiFetch<ViewerPayload>(`/checks/${checkId}/viewer`),
    ])
      .then(([rep, vw]) => {
        setReport(rep);
        setViewer(vw);
        if (rep.sources.length > 0) {
          apiFetch<SourceViewerPayload>(`/checks/${checkId}/sources/${rep.sources[0].source_document_id}/viewer`)
            .then(setSourceViewer)
            .catch(() => undefined);
        }
      })
      .catch((e) => setError(e.message));
  }, [checkId]);

  const handleSelectHighlight = async (matchIds: number[]) => {
    if (!report || !checkId || matchIds.length === 0) return;
    const mid = matchIds[0];
    setActiveMatchId(mid);
    const m = report.matches.find((item) => item.id === mid);
    if (!m) return;
    if (!sourceViewer || sourceViewer.source_document_id !== m.source_document_id) {
      const sv = await apiFetch<SourceViewerPayload>(`/checks/${checkId}/sources/${m.source_document_id}/viewer`);
      setSourceViewer(sv);
      setTimeout(() => {
        const el = rightPaneRef.current?.querySelector(`[data-src-match="${mid}"]`);
        el?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 80);
    } else {
      const el = rightPaneRef.current?.querySelector(`[data-src-match="${mid}"]`);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  const handleScrollPane = (side: "left" | "right") => {
    if (!syncScroll || isSyncingRef.current) return;
    const srcEl = side === "left" ? leftPaneRef.current : rightPaneRef.current;
    const dstEl = side === "left" ? rightPaneRef.current : leftPaneRef.current;
    if (!srcEl || !dstEl) return;
    const ratio = srcEl.scrollTop / Math.max(1, srcEl.scrollHeight - srcEl.clientHeight);
    isSyncingRef.current = true;
    dstEl.scrollTop = ratio * Math.max(0, dstEl.scrollHeight - dstEl.clientHeight);
    requestAnimationFrame(() => {
      isSyncingRef.current = false;
    });
  };

  const sourceSpans = useMemo(() => {
    if (!sourceViewer) return [];
    const text = sourceViewer.text;
    if (!text) return [];
    const hls = [...sourceViewer.highlights].sort((a, b) => a.src_char_start - b.src_char_start);
    const out: Array<{ key: string; text: string; layer?: string; matchId?: number }> = [];
    let cursor = 0;
    for (const h of hls) {
      const s = Math.max(cursor, Math.min(h.src_char_start, text.length));
      const e = Math.max(s, Math.min(h.src_char_end, text.length));
      if (s > cursor) out.push({ key: `p-${cursor}`, text: text.slice(cursor, s) });
      if (e > s) out.push({ key: `m-${h.match_id}-${s}`, text: text.slice(s, e), layer: h.layer, matchId: h.match_id });
      cursor = Math.max(cursor, e);
    }
    if (cursor < text.length) out.push({ key: `p-end`, text: text.slice(cursor) });
    return out;
  }, [sourceViewer]);

  const filteredMatches = useMemo(() => {
    if (!report) return [];
    if (matchLayerFilter === "ALL") return report.matches;
    return report.matches.filter((item) => item.layer === matchLayerFilter);
  }, [report, matchLayerFilter]);

  if (error) {
    return (
      <Alert variant="destructive" className="mb-4">
        <AlertTitle>Gagal memuat laporan</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (!report) {
    return (
      <div className="card">
        <Skeleton className="h-7 w-64 mb-4" />
        <Skeleton className="h-44 w-full" />
      </div>
    );
  }

  const m = report.metrics;
  const op = m.operational_category;
  const se = m.score_explanation;
  const sm = report.coverage.source_metrics;
  const sc = report.coverage.search_coverage;
  const timings = m.stage_timings_ms || {};

  const exactWords = se?.exact_match_words ?? se?.exact_words ?? 0;
  const nearWords = se?.near_exact_match_words ?? se?.near_exact_words ?? 0;
  const diffExplain =
    se?.raw_vs_adjusted_reason ||
    se?.raw_vs_adjusted_diff_reason ||
    "Raw Similarity menghitung seluruh kata cocok terhadap total kata dokumen sebelum pengecualian; Adjusted Similarity menghitung kata cocok unik pada bagian dokumen yang eligible.";

  // Explicit 9-category Source Transparency (Fix 4 — never mixed)
  const sourceTransparencyItems = [
    {
      label: "Hasil Pencarian Provider",
      sub: "Respons metadata mentah",
      val: sm?.search_results_count ?? sc?.total_provider_responses ?? 0,
    },
    {
      label: "URL Unik Ditemukan",
      sub: "Setelah kanonisasi URL",
      val: sm?.total_urls_found ?? sc?.total_unique_urls_found ?? 0,
    },
    {
      label: "Metadata-Only",
      sub: "Tidak memiliki teks penuh",
      val: sm?.metadata_only_sources ?? report.coverage.metadata_only_sources,
    },
    {
      label: "Full-Text Berhasil Diunduh",
      sub: "PDF / HTML / XML publik",
      val: sm?.fulltext_downloaded ?? sc?.total_fulltext_fetched ?? 0,
    },
    {
      label: "Full-Text Terindeks",
      sub: "Masuk indeks lokal",
      val: sm?.fulltext_indexed ?? sc?.total_fulltext_indexed ?? 0,
    },
    {
      label: "Full-Text Dibandingkan",
      sub: "Kandidat diperiksa penuh",
      val: sm?.fulltext_compared ?? report.coverage.full_text_sources_compared,
    },
    {
      label: "Sumber Cocok Terverifikasi",
      sub: "Berkontribusi pada skor",
      val: sm?.verified_contributing_sources ?? m.sources_found,
    },
    {
      label: "Sumber Dibatasi Akses",
      sub: "HTTP 401/403 / robots.txt",
      val: sm?.inaccessible_sources ?? report.coverage.access_denied_sources,
    },
    {
      label: "Gagal Akuisisi",
      sub: "Timeout / gagal ekstraksi",
      val: sm?.failed_acquisitions ?? report.coverage.fetch_failed_sources,
    },
  ];

  const layerChartData = [
    { name: "Exact", pct: m.exact_match_pct },
    { name: "Near-Exact", pct: m.near_exact_match_pct },
    { name: "Lexical", pct: m.lexical_match_pct },
  ];
  const wordRatioData = [
    { name: "Kata Cocok", count: m.matched_words },
    { name: "Tidak Cocok", count: m.unmatched_eligible_words },
    { name: "Dikecualikan", count: m.excluded_words },
  ];

  const tabItems: Array<{ key: TabKey; label: string; icon: React.ComponentType<{ size?: number | string }> }> = [
    { key: "overview", label: "Ringkasan", icon: FileText },
    { key: "compare", label: "Perbandingan Dokumen", icon: Layers },
    { key: "sources", label: `Sumber Cocok (${report.sources.length})`, icon: Table2 },
    { key: "evidence", label: "Bukti Internet", icon: Globe },
    { key: "coverage", label: "Cakupan Pencarian", icon: ShieldCheck },
    { key: "analytics", label: "Analitik", icon: BarChart3 },
    { key: "flowchart", label: "Alur Pemeriksaan", icon: GitBranch },
    { key: "export", label: "Ekspor", icon: Download },
  ];

  const availableKeys = Object.keys(timings).length > 0 ? ALL_ACCORDION_KEYS : ALL_ACCORDION_KEYS.filter((k) => k !== "timings");
  const allExpanded = availableKeys.every((k) => openAccordions.includes(k));
  const totalMatchPages = Math.max(1, Math.ceil(filteredMatches.length / MATCHES_PAGE_SIZE));
  const pagedMatches = filteredMatches.slice((matchesPage - 1) * MATCHES_PAGE_SIZE, matchesPage * MATCHES_PAGE_SIZE);

  return (
    <BlurFade duration={0.22}>
      <div>
        {/* Header Bersih */}
        <div className="page-header">
          <div>
            <h2 className="page-title">Laporan Kemiripan · {report.report_number}</h2>
            <p className="page-desc">
              <strong>{report.document.filename}</strong> · {report.document.file_type.toUpperCase()} ·{" "}
              {report.document.page_count} halaman · Bahasa: {report.document.language} · Durasi:{" "}
              <strong>{formatDuration(report.duration_seconds)}</strong>
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.pdf`, `${report.report_number}.pdf`)}
            >
              <Download size={15} /> PDF
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.html`, `${report.report_number}.html`)}
            >
              <Download size={15} /> HTML
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.json`, `${report.report_number}.json`)}
            >
              <Download size={15} /> JSON
            </button>
          </div>
        </div>

        {/* Fix 1: Strictly Mutual-Exclusive Navigation (Mobile Select <= 640px, Desktop/Tablet Tabs > 640px) */}
        <div className="mobile-tab-select">
          <select
            className="input"
            value={tab}
            onChange={(e) => setTab(e.target.value as TabKey)}
            aria-label="Pilih bagian laporan"
          >
            {tabItems.map((t) => (
              <option key={t.key} value={t.key}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        <div className="tabs-bar" role="tablist" aria-label="Navigasi bagian laporan">
          {tabItems.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.key}
                type="button"
                role="tab"
                aria-selected={tab === t.key}
                className={`tab-btn ${tab === t.key ? "active" : ""}`}
                onClick={() => setTab(t.key)}
              >
                <Icon size={14} />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* TAB 1: RINGKASAN */}
        {tab === "overview" && (
          <div>
            {/* Fix 2: Proportional Similarity Summary Layout (Always stays visible above accordions) */}
            <div className="report-summary-shell">
              {/* Area Kiri: Similarity Index, Operational Category, Raw & Adjusted Similarity */}
              <div className="card report-score-card">
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <SimilarityGauge
                    value={m.similarity_index}
                    level={op.level}
                    thresholdLow={op.threshold_low}
                    thresholdHigh={op.threshold_high}
                  />
                  <div style={{ minWidth: 0 }}>
                    <div className="stat-label">Similarity Index</div>
                    <div style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.15 }} className="num">
                      <NumberTicker value={m.similarity_index} decimalPlaces={2} />%
                    </div>
                    <div style={{ marginTop: 6 }}>
                      <span
                        className={`badge ${
                          op.level === "Tinggi"
                            ? "badge-EXACT"
                            : op.level === "Sedang"
                            ? "badge-NEAR_EXACT"
                            : "badge-SUCCESS"
                        }`}
                      >
                        Kategori: {op.level}
                      </span>
                    </div>
                  </div>
                </div>

                <Separator />

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div style={{ padding: "8px 10px", background: "var(--surface-alt)", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 600 }}>ADJUSTED SIMILARITY</div>
                    <div className="num" style={{ fontSize: 16, fontWeight: 700, marginTop: 2 }}>
                      {m.adjusted_similarity.toFixed(2)}%
                    </div>
                  </div>
                  <div style={{ padding: "8px 10px", background: "var(--surface-alt)", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 600 }}>RAW SIMILARITY</div>
                    <div className="num" style={{ fontSize: 16, fontWeight: 700, marginTop: 2 }}>
                      {m.raw_similarity.toFixed(2)}%
                    </div>
                  </div>
                </div>
              </div>

              {/* Area Kanan: Eligible Words, Unique Matched Words, Contributing Sources, Full-Text Compared */}
              <div className="report-kpi-quad">
                <div className="card">
                  <div className="stat-label">Kata Diperiksa (Eligible)</div>
                  <div className="stat-val">
                    <NumberTicker value={m.eligible_words} />
                  </div>
                  <div className="stat-sub">
                    Total {m.total_words.toLocaleString("id-ID")} · Dikecualikan {m.excluded_words.toLocaleString("id-ID")}
                  </div>
                </div>
                <div className="card">
                  <div className="stat-label">Kata Cocok Unik</div>
                  <div className="stat-val">
                    <NumberTicker value={m.matched_words} />
                  </div>
                  <div className="stat-sub">
                    Exact {m.exact_match_pct.toFixed(2)}% · Near-Exact {m.near_exact_match_pct.toFixed(2)}%
                  </div>
                </div>
                <div className="card">
                  <div className="stat-label">Sumber Berkontribusi</div>
                  <div className="stat-val">
                    <NumberTicker value={m.sources_found} />
                  </div>
                  <div className="stat-sub">
                    Sumber terverifikasi menyumbang kecocokan
                  </div>
                </div>
                <div className="card">
                  <div className="stat-label">Full-Text Dibandingkan</div>
                  <div className="stat-val">
                    <NumberTicker value={report.coverage.full_text_sources_compared} />
                  </div>
                  <div className="stat-sub">
                    Cakupan: {report.coverage.level} ({report.coverage.metadata_only_sources} metadata-only)
                  </div>
                </div>
              </div>
            </div>

            <div className="notice" style={{ marginBottom: 14 }}>
              <strong>Kategori Operasional ({op.level}):</strong> {op.disclaimer}
            </div>

            {/* Fix 5: Expand All / Collapse All + Persistent Individual Accordion State */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>
                Detail perhitungan &amp; transparansi sumber (ringkasan skor utama tetap terlihat di atas)
              </span>
              <button
                type="button"
                className="btn"
                onClick={() => setOpenAccordions(allExpanded ? [] : availableKeys)}
                style={{ fontSize: 12.5 }}
              >
                <ChevronsUpDown size={14} />
                <span>{allExpanded ? "Ciutkan Semua Bagian" : "Perluas Semua Bagian"}</span>
              </button>
            </div>

            <Accordion
              type="multiple"
              value={openAccordions}
              onValueChange={setOpenAccordions}
              className="flex flex-col gap-3"
            >
              {/* Fix 3: Penjelasan Perhitungan Similarity */}
              <AccordionItem value="formula" className="card p-0 overflow-hidden">
                <AccordionTrigger className="px-4 py-3.5 hover:no-underline hover:bg-muted/40">
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
                    <Calculator size={16} /> Penjelasan Perhitungan Similarity (Bagaimana skor dihitung?)
                  </span>
                </AccordionTrigger>
                <AccordionContent className="px-4 pb-4 pt-3 border-t" style={{ borderColor: "var(--border)" }}>
                  <div style={{ fontSize: 13.5, lineHeight: 1.65 }}>
                    <div style={{ marginBottom: 8 }}>
                      <strong>Rumus Similarity Index (Adjusted):</strong>{" "}
                      <code>
                        {se?.adjusted_formula ||
                          se?.formula ||
                          `${m.matched_words} / ${m.eligible_words} × 100% = ${m.adjusted_similarity.toFixed(2)}%`}
                      </code>
                    </div>
                    <div style={{ marginBottom: 8 }}>
                      <strong>Rumus Raw Similarity:</strong>{" "}
                      <code>
                        {se?.raw_formula ||
                          `${m.raw_matched_words} / ${m.total_words} × 100% = ${m.raw_similarity.toFixed(2)}%`}
                      </code>
                    </div>
                    <div style={{ marginBottom: 10 }}>
                      <strong>Penjelasan Raw vs Adjusted:</strong> {diffExplain}
                    </div>
                    {se?.rounding_note && (
                      <div className="notice" style={{ marginBottom: 10, padding: "8px 12px", fontSize: 12.5 }}>
                        <strong>Catatan Presisi Pembulatan:</strong> {se.rounding_note}
                      </div>
                    )}

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(155px, 1fr))",
                        gap: 10,
                        marginTop: 10,
                        marginBottom: 14,
                      }}
                    >
                      <div style={{ padding: 10, background: "var(--surface-alt)", borderRadius: "var(--radius-sm)" }}>
                        <div className="stat-label">Eligible Words</div>
                        <div className="num" style={{ fontSize: 16, fontWeight: 700 }}>{m.eligible_words.toLocaleString("id-ID")}</div>
                      </div>
                      <div style={{ padding: 10, background: "var(--surface-alt)", borderRadius: "var(--radius-sm)" }}>
                        <div className="stat-label">Matched Words Unik</div>
                        <div className="num" style={{ fontSize: 16, fontWeight: 700 }}>{m.matched_words.toLocaleString("id-ID")}</div>
                      </div>
                      <div style={{ padding: 10, background: "var(--surface-alt)", borderRadius: "var(--radius-sm)" }}>
                        <div className="stat-label">Exact Match</div>
                        <div className="num" style={{ fontSize: 16, fontWeight: 700 }}>
                          {exactWords.toLocaleString("id-ID")} ({m.exact_match_pct.toFixed(2)}%)
                        </div>
                      </div>
                      <div style={{ padding: 10, background: "var(--surface-alt)", borderRadius: "var(--radius-sm)" }}>
                        <div className="stat-label">Near-Exact Match</div>
                        <div className="num" style={{ fontSize: 16, fontWeight: 700 }}>
                          {nearWords.toLocaleString("id-ID")} ({m.near_exact_match_pct.toFixed(2)}%)
                        </div>
                      </div>
                      <div style={{ padding: 10, background: "var(--surface-alt)", borderRadius: "var(--radius-sm)" }}>
                        <div className="stat-label">Excluded Words</div>
                        <div className="num" style={{ fontSize: 16, fontWeight: 700 }}>{m.excluded_words.toLocaleString("id-ID")}</div>
                      </div>
                      <div style={{ padding: 10, background: "var(--surface-alt)", borderRadius: "var(--radius-sm)" }}>
                        <div className="stat-label">Resolusi Overlap</div>
                        <div className="num" style={{ fontSize: 16, fontWeight: 700 }}>
                          {(se?.overlap_tokens_removed ?? 0).toLocaleString("id-ID")} token
                        </div>
                      </div>
                    </div>

                    {report.sources.length > 0 && (
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                          Kontribusi Eksklusif per Sumber (Tanpa Penghitungan Ganda)
                        </div>
                        <div className="table-wrap">
                          <table>
                            <thead>
                              <tr>
                                <th>Sumber</th>
                                <th className="num">Kata Eksklusif</th>
                                <th className="num">Total Kata Cocok</th>
                                <th className="num">Kontribusi SI</th>
                              </tr>
                            </thead>
                            <tbody>
                              {report.sources.slice(0, 8).map((s) => (
                                <tr key={s.source_document_id}>
                                  <td>
                                    <strong>#{s.rank}</strong> {s.title}
                                  </td>
                                  <td className="num">{s.matched_words_exclusive}</td>
                                  <td className="num">{s.matched_words_total}</td>
                                  <td className="num">
                                    <strong>{s.contribution_pct.toFixed(2)}%</strong>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* Fix 4: 9 Separated Source Transparency Categories */}
              <AccordionItem value="sources_metrics" className="card p-0 overflow-hidden">
                <AccordionTrigger className="px-4 py-3.5 hover:no-underline hover:bg-muted/40">
                  <span style={{ fontWeight: 600 }}>Transparansi Kategori Sumber (9 Metrik Terpisah)</span>
                </AccordionTrigger>
                <AccordionContent className="px-4 pb-4 pt-3 border-t" style={{ borderColor: "var(--border)" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 10 }}>
                    {sourceTransparencyItems.map((item) => (
                      <div
                        key={item.label}
                        style={{
                          padding: "10px 12px",
                          background: "var(--surface-alt)",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--border)",
                        }}
                      >
                        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)" }}>{item.label}</div>
                        <div className="num" style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }}>
                          {item.val.toLocaleString("id-ID")}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{item.sub}</div>
                      </div>
                    ))}
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* Catatan Cakupan & Ekstraksi */}
              <AccordionItem value="coverage_notes" className="card p-0 overflow-hidden">
                <AccordionTrigger className="px-4 py-3.5 hover:no-underline hover:bg-muted/40">
                  <span style={{ fontWeight: 600 }}>Pernyataan Cakupan &amp; Catatan Ekstraksi</span>
                </AccordionTrigger>
                <AccordionContent className="px-4 pb-4 pt-3 border-t" style={{ borderColor: "var(--border)" }}>
                  <div style={{ fontSize: 13.5 }}>
                    <p style={{ marginTop: 0, fontWeight: 600 }}>{report.coverage.statement}</p>
                    <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
                      {report.coverage.notes.map((n, idx) => (
                        <li key={idx}>{n}</li>
                      ))}
                      {Boolean(report.document.extra?.ocr_warning) && <li>{String(report.document.extra.ocr_warning)}</li>}
                      {Boolean(report.document.extra?.page_note) && <li>{String(report.document.extra.page_note)}</li>}
                      <li>
                        Metode ekstraksi: <code>{report.document.extraction_method}</code> (kepercayaan{" "}
                        {Math.round(report.document.extraction_confidence * 100)}%)
                      </li>
                      <li>{m.semantic_status}</li>
                    </ul>
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* Waktu Tahapan Pipeline */}
              {Object.keys(timings).length > 0 && (
                <AccordionItem value="timings" className="card p-0 overflow-hidden">
                  <AccordionTrigger className="px-4 py-3.5 hover:no-underline hover:bg-muted/40">
                    <span style={{ fontWeight: 600 }}>Rincian Waktu Pemrosesan per Tahap</span>
                  </AccordionTrigger>
                  <AccordionContent className="px-4 pb-4 pt-3 border-t" style={{ borderColor: "var(--border)" }}>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Tahap Pipeline</th>
                            <th className="num">Durasi Aktual</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(timings).map(([k, v]) => (
                            <tr key={k}>
                              <td>
                                <code>{k}</code>
                              </td>
                              <td className="num">{formatMs(v)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              )}
            </Accordion>
          </div>
        )}

        {/* TAB 2: PERBANDINGAN DOKUMEN (Fix 6: Sticky Toolbar + Side-by-Side Viewer) */}
        {tab === "compare" && viewer && (
          <div>
            <div className="viewer-toolbar-sticky">
              <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
                {Object.entries(CATEGORY_LABEL).map(([key, label]) => (
                  <label key={key} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={filters[key]}
                      onChange={(e) => setFilters({ ...filters, [key]: e.target.checked })}
                    />
                    <span className={`badge badge-${key}`}>{label}</span>
                  </label>
                ))}
              </div>
              <label style={{ fontSize: 13, cursor: "pointer" }}>
                <input type="checkbox" checked={syncScroll} onChange={(e) => setSyncScroll(e.target.checked)} /> Sinkronisasi gulir panel
              </label>
            </div>

            {activeMatchId !== null &&
              (() => {
                const activeMatch = report.matches.find((item) => item.id === activeMatchId);
                if (!activeMatch) return null;
                return (
                  <div
                    className="notice"
                    style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", justifyContent: "space-between" }}
                  >
                    <div>
                      <span className={`badge badge-${activeMatch.layer}`} style={{ marginRight: 8 }}>
                        {CATEGORY_LABEL[activeMatch.layer] || activeMatch.layer}
                      </span>
                      <strong>{activeMatch.source_title}</strong>
                      {activeMatch.src_page ? ` · Hlm. sumber ${activeMatch.src_page}` : ""}
                      {activeMatch.excluded_reason ? ` · Dikecualikan (${activeMatch.excluded_reason})` : ""}
                    </div>
                    <div className="num" style={{ fontSize: 13 }}>
                      {activeMatch.matched_words} kata cocok · Skor {Math.round(activeMatch.score * 100)}%
                    </div>
                  </div>
                );
              })()}

            <div className="split-viewer">
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Dokumen Asli: {report.document.filename} ({viewer.pages.length} halaman)
                </div>
                <div className="viewer-pane" ref={leftPaneRef} onScroll={() => handleScrollPane("left")}>
                  {viewer.segments.map((seg, i) => {
                    const showHl = seg.category !== "PLAIN" && filters[seg.category];
                    if (!showHl) return <span key={i}>{seg.text}</span>;
                    const isActive = activeMatchId !== null && seg.match_ids.includes(activeMatchId);
                    return (
                      <span
                        key={i}
                        className={`hl-seg hl-${seg.category} ${isActive ? "hl-active" : ""}`}
                        title={`${CATEGORY_LABEL[seg.category] || seg.category}${seg.excluded_reason ? ` (${seg.excluded_reason})` : ""}`}
                        onClick={() => handleSelectHighlight(seg.match_ids)}
                      >
                        {seg.text}
                      </span>
                    );
                  })}
                </div>
              </div>

              <div>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    marginBottom: 6,
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 8,
                    flexWrap: "wrap",
                    alignItems: "center",
                  }}
                >
                  <span>Sumber Pembanding: {sourceViewer ? sourceViewer.title : "Pilih sumber / klik highlight"}</span>
                  {report.sources.length > 0 && (
                    <select
                      className="input"
                      style={{ width: "auto", padding: "3px 8px", fontSize: 12 }}
                      value={sourceViewer?.source_document_id || ""}
                      aria-label="Pilih sumber pembanding"
                      onChange={async (e) => {
                        const sv = await apiFetch<SourceViewerPayload>(`/checks/${report.check_id}/sources/${e.target.value}/viewer`);
                        setSourceViewer(sv);
                      }}
                    >
                      {report.sources.map((s) => (
                        <option key={s.source_document_id} value={s.source_document_id}>
                          #{s.rank} {s.title} ({s.contribution_pct.toFixed(2)}%)
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <div className="viewer-pane" ref={rightPaneRef} onScroll={() => handleScrollPane("right")}>
                  {!sourceViewer ? (
                    <span style={{ color: "var(--text-muted)" }}>
                      Belum ada sumber pembanding yang dipilih atau tidak ada kecocokan.
                    </span>
                  ) : (
                    sourceSpans.map((sp) =>
                      sp.layer ? (
                        <span
                          key={sp.key}
                          data-src-match={sp.matchId}
                          className={`hl-seg hl-${sp.layer} ${activeMatchId === sp.matchId ? "hl-active" : ""}`}
                        >
                          {sp.text}
                        </span>
                      ) : (
                        <span key={sp.key}>{sp.text}</span>
                      )
                    )
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: SUMBER COCOK (Fix 6: Source Details Modal + Paginated Match Table) */}
        {tab === "sources" && (
          <div>
            <div className="table-wrap" style={{ marginBottom: 18 }}>
              <table>
                <thead>
                  <tr>
                    <th>Sumber</th>
                    <th>Tipe / Provider</th>
                    <th className="num">Kata Eksklusif</th>
                    <th className="num">Kontribusi</th>
                    <th>Tautan &amp; Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {report.sources.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ color: "var(--text-muted)" }}>
                        Tidak ada sumber yang berkontribusi pada kecocokan.
                      </td>
                    </tr>
                  ) : (
                    report.sources.map((s) => (
                      <tr key={s.source_document_id}>
                        <td>
                          <strong>
                            #{s.rank} {s.title}
                          </strong>
                          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                            {s.authors.join(", ") || "Penulis tidak tercatat"} {s.year ? `(${s.year})` : ""}
                            {s.doi ? ` · DOI: ${s.doi}` : ""} · Status: {s.access_status}
                          </div>
                        </td>
                        <td>
                          <div>{s.source_type}</div>
                          <div style={{ fontSize: 11.5, color: "var(--text-muted)" }}>{s.provider}</div>
                        </td>
                        <td className="num">
                          {s.matched_words_exclusive}{" "}
                          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>(total {s.matched_words_total})</span>
                        </td>
                        <td className="num">
                          <strong>{s.contribution_pct.toFixed(2)}%</strong>
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            <button
                              type="button"
                              className="btn"
                              style={{ fontSize: 12, minHeight: 30, padding: "4px 8px" }}
                              onClick={() => setSelectedSourceModal(s)}
                            >
                              <Info size={12} /> Detail
                            </button>
                            {s.url && (
                              <a
                                href={s.url}
                                target="_blank"
                                rel="noreferrer"
                                className="btn"
                                style={{ fontSize: 12, minHeight: 30, padding: "4px 8px" }}
                              >
                                <ExternalLink size={12} /> Tautan
                              </a>
                            )}
                            {s.can_download_file && (
                              <button
                                type="button"
                                className="btn"
                                style={{ fontSize: 12, minHeight: 30, padding: "4px 8px" }}
                                onClick={() => downloadProtectedFile(`/documents/${s.source_document_id}/file`, s.filename)}
                              >
                                <Download size={12} /> Berkas
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {report.matches.length > 0 && (
              <div className="card">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 10,
                    marginBottom: 12,
                  }}
                >
                  <h3 className="section-title" style={{ margin: 0 }}>
                    Rincian Cuplikan Kecocokan ({filteredMatches.length})
                  </h3>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <select
                      className="input"
                      style={{ width: "auto", padding: "5px 10px", fontSize: 12.5 }}
                      value={matchLayerFilter}
                      aria-label="Filter lapisan kecocokan"
                      onChange={(e) => {
                        setMatchLayerFilter(e.target.value);
                        setMatchesPage(1);
                      }}
                    >
                      <option value="ALL">Semua Lapisan ({report.matches.length})</option>
                      <option value="EXACT">Exact</option>
                      <option value="NEAR_EXACT">Near-Exact</option>
                      <option value="LEXICAL">Lexical</option>
                      <option value="SEMANTIC">Kandidat Semantik</option>
                    </select>
                  </div>
                </div>

                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Lapisan</th>
                        <th>Sumber</th>
                        <th>Cuplikan Dokumen</th>
                        <th>Cuplikan Sumber</th>
                        <th className="num">Kata</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagedMatches.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <span className={`badge badge-${item.layer}`}>{CATEGORY_LABEL[item.layer] || item.layer}</span>
                            {item.excluded_reason && (
                              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                                Dikecualikan: {item.excluded_reason}
                              </div>
                            )}
                          </td>
                          <td>
                            <strong>{item.source_title}</strong>
                            {item.src_page && <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Hlm. sumber {item.src_page}</div>}
                          </td>
                          <td style={{ fontSize: 12.5 }}>{item.sub_excerpt}</td>
                          <td style={{ fontSize: 12.5 }}>{item.src_excerpt}</td>
                          <td className="num">{item.matched_words}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {totalMatchPages > 1 && (
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginTop: 12,
                      fontSize: 13,
                    }}
                  >
                    <span style={{ color: "var(--text-muted)" }}>
                      Halaman {matchesPage} dari {totalMatchPages}
                    </span>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        type="button"
                        className="btn"
                        disabled={matchesPage <= 1}
                        onClick={() => setMatchesPage((p) => Math.max(1, p - 1))}
                      >
                        <ChevronLeft size={14} /> Sebelumnya
                      </button>
                      <button
                        type="button"
                        className="btn"
                        disabled={matchesPage >= totalMatchPages}
                        onClick={() => setMatchesPage((p) => Math.min(totalMatchPages, p + 1))}
                      >
                        Berikutnya <ChevronRight size={14} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {report.coverage.metadata_only_items && report.coverage.metadata_only_items.length > 0 && (
              <div className="card" style={{ marginTop: 18 }}>
                <h3 className="section-title">Sumber Eksternal Metadata-Only (Tidak Dibandingkan Full-Text)</h3>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                  {report.coverage.metadata_only_items.map((item, idx) => (
                    <li key={idx}>
                      <strong>[{item.provider}]</strong> {item.title} {item.year ? `(${item.year})` : ""}{" "}
                      {item.doi ? `· DOI: ${item.doi}` : ""} — <code>{item.access_status}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* TAB 4: BUKTI INTERNET */}
        {tab === "evidence" && (
          <div>
            <div className="card" style={{ marginBottom: 18 }}>
              <h3 className="section-title">Bukti Akuisisi Sumber Internet &amp; Akademik ({report.acquisitions?.length || 0})</h3>
              {!report.acquisitions || report.acquisitions.length === 0 ? (
                <div className="empty-state">
                  <Globe size={24} color="var(--text-muted)" />
                  <div style={{ fontWeight: 600 }}>Tidak ada pencarian eksternal</div>
                  <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                    Pemeriksaan ini dijalankan terhadap korpus sumber lokal saja.
                  </div>
                </div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Provider &amp; Kueri</th>
                        <th>Sumber &amp; URL Asli</th>
                        <th>Format / Metode</th>
                        <th>Status Akuisisi</th>
                        <th className="num">Durasi</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.acquisitions.map((acq) => (
                        <tr key={acq.id}>
                          <td>
                            <strong>{acq.provider}</strong>
                            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{acq.query}</div>
                          </td>
                          <td>
                            <strong>{acq.title}</strong>
                            {acq.source_url && (
                              <div style={{ fontSize: 12 }}>
                                <a href={acq.source_url} target="_blank" rel="noreferrer">
                                  {acq.source_url.slice(0, 70)}
                                  {acq.source_url.length > 70 ? "..." : ""} <ExternalLink size={11} />
                                </a>
                              </div>
                            )}
                            {acq.doi && <div style={{ fontSize: 11, color: "var(--text-muted)" }}>DOI: {acq.doi}</div>}
                            {acq.error && <div style={{ fontSize: 11, color: "var(--exact-text)" }}>{acq.error}</div>}
                          </td>
                          <td>
                            {acq.file_type ? acq.file_type.toUpperCase() : "-"} · {acq.used_playwright ? "Playwright" : "HTTP"}
                          </td>
                          <td>
                            <span className="badge badge-SEMANTIC">{acq.status}</span>
                          </td>
                          <td className="num">{formatMs(acq.duration_ms)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="card">
              <h3 className="section-title">Riwayat Kueri Provider ({report.provider_queries.length})</h3>
              {report.provider_queries.length === 0 ? (
                <p style={{ color: "var(--text-muted)", fontSize: 14, margin: 0 }}>Tidak ada kueri ke provider eksternal.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Provider</th>
                        <th>Kueri</th>
                        <th>Status</th>
                        <th className="num">Hasil</th>
                        <th className="num">HTTP</th>
                        <th className="num">Durasi</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.provider_queries.map((pq, idx) => (
                        <tr key={idx}>
                          <td>
                            <strong>{pq.provider}</strong>
                          </td>
                          <td style={{ fontSize: 13 }}>{pq.query}</td>
                          <td>
                            {pq.status}
                            {pq.error ? ` (${pq.error})` : ""}
                          </td>
                          <td className="num">{pq.result_count}</td>
                          <td className="num">{pq.http_status ?? "-"}</td>
                          <td className="num">{formatMs(pq.duration_ms)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 5: CAKUPAN PENCARIAN */}
        {tab === "coverage" && (
          <div>
            <div className="notice" style={{ marginBottom: 16 }}>
              <strong>{report.coverage.statement}</strong>
              <p style={{ margin: "6px 0 0" }}>
                {sc?.coverage_disclaimer ||
                  "Cakupan menunjukkan sumber yang berhasil diakses dalam pemeriksaan ini, bukan seluruh dokumen di internet."}
              </p>
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <h3 className="section-title">Rincian Transparansi Sumber (9 Kategori Terpisah)</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 10 }}>
                {sourceTransparencyItems.map((item) => (
                  <div
                    key={item.label}
                    style={{
                      padding: "10px 12px",
                      background: "var(--surface-alt)",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 600 }}>{item.label}</div>
                    <div className="num" style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }}>
                      {item.val.toLocaleString("id-ID")}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{item.sub}</div>
                  </div>
                ))}
              </div>
            </div>

            {sc?.indicators && (
              <div className="card" style={{ marginBottom: 16 }}>
                <h3 className="section-title">Indikator Cakupan Sumber</h3>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, lineHeight: 1.8 }}>
                  <li><strong>Cakupan Korpus Lokal:</strong> {sc.indicators.local_corpus_coverage}</li>
                  <li><strong>Cakupan Database Akademik:</strong> {sc.indicators.academic_database_coverage}</li>
                  <li><strong>Cakupan Web Publik:</strong> {sc.indicators.public_web_coverage}</li>
                  <li><strong>Ketersediaan Full-Text:</strong> {sc.indicators.fulltext_availability}</li>
                  <li><strong>Cakupan Pencarian Eksternal:</strong> {sc.indicators.external_search_coverage}</li>
                  {sc.providers_failed.length > 0 && (
                    <li style={{ color: "var(--exact-text)" }}>
                      <strong>Provider Gagal:</strong> {sc.providers_failed.join(", ")}
                    </li>
                  )}
                </ul>
              </div>
            )}

            {sc?.generated_queries && sc.generated_queries.length > 0 && (
              <div className="card">
                <h3 className="section-title">Kueri Cerdas yang Dikirim ke Provider</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Kueri</th>
                        <th>Jenis</th>
                        <th>Bab / Bagian</th>
                        <th className="num">Skor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sc.generated_queries.map((gq, i) => (
                        <tr key={i}>
                          <td>
                            <code>{gq.query}</code>
                          </td>
                          <td>{gq.kind}</td>
                          <td>{gq.chapter}</td>
                          <td className="num">{gq.score.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 6: ANALITIK */}
        {tab === "analytics" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 16 }}>
            <div className="card">
              <h3 className="section-title" style={{ fontFamily: "var(--font-serif)" }}>
                Rasio Kata Cocok vs Tidak Cocok
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={wordRatioData} layout="vertical" margin={{ left: 20, right: 40, top: 8, bottom: 8 }}>
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={100} tick={{ fontSize: 12, fill: "var(--text-secondary)" }} />
                  <Tooltip content={<TufteTooltip />} />
                  <Bar dataKey="count" name="Jumlah Kata" fill="#1E3A5F" radius={[0, 3, 3, 0]}>
                    <LabelList dataKey="count" position="right" fill="var(--text)" fontSize={12} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="card">
              <h3 className="section-title" style={{ fontFamily: "var(--font-serif)" }}>
                Komposisi Lapisan Kemiripan (%)
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={layerChartData} layout="vertical" margin={{ left: 20, right: 45, top: 8, bottom: 8 }}>
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={90} tick={{ fontSize: 12, fill: "var(--text-secondary)" }} />
                  <Tooltip content={<TufteTooltip />} />
                  <Bar dataKey="pct" name="Persentase (%)" fill="#B45309" radius={[0, 3, 3, 0]}>
                    <LabelList dataKey="pct" position="right" formatter={(v: any) => `${Number(v).toFixed(2)}%`} fill="var(--text)" fontSize={12} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="card">
              <h3 className="section-title" style={{ fontFamily: "var(--font-serif)" }}>
                Sumber Penyumbang Teratas (%)
              </h3>
              {report.sources.length === 0 ? (
                <p style={{ color: "var(--text-muted)" }}>Belum ada sumber yang berkontribusi.</p>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={report.sources.slice(0, 6)} layout="vertical" margin={{ left: 10, right: 45, top: 8, bottom: 8 }}>
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="title" axisLine={false} tickLine={false} width={140} tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
                    <Tooltip content={<TufteTooltip />} />
                    <Bar dataKey="contribution_pct" name="Kontribusi (%)" fill="#2563EB" radius={[0, 3, 3, 0]}>
                      <LabelList dataKey="contribution_pct" position="right" formatter={(v: any) => `${Number(v).toFixed(2)}%`} fill="var(--text)" fontSize={12} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="card">
              <h3 className="section-title" style={{ fontFamily: "var(--font-serif)" }}>
                Distribusi Kemiripan per Bab / Bagian (%)
              </h3>
              {report.analytics.by_chapter.length === 0 ? (
                <p style={{ color: "var(--text-muted)" }}>Tidak ada segmen bab terdeteksi.</p>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={report.analytics.by_chapter} margin={{ left: 0, right: 20, top: 18, bottom: 8 }}>
                    <XAxis dataKey="chapter" axisLine={{ stroke: "var(--border)" }} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                    <Tooltip content={<TufteTooltip />} />
                    <Bar dataKey="similarity_pct" name="Kemiripan (%)" fill="#EA580C" radius={[3, 3, 0, 0]}>
                      <LabelList dataKey="similarity_pct" position="top" formatter={(v: any) => `${Number(v).toFixed(1)}%`} fill="var(--text)" fontSize={11} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="card">
              <h3 className="section-title" style={{ fontFamily: "var(--font-serif)" }}>
                Distribusi Kemiripan per Halaman (%)
              </h3>
              {report.analytics.by_page.length === 0 ? (
                <p style={{ color: "var(--text-muted)" }}>Data halaman tidak tersedia.</p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={report.analytics.by_page} margin={{ left: 0, right: 20, top: 18, bottom: 8 }}>
                    <XAxis dataKey="page" axisLine={{ stroke: "var(--border)" }} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                    <Tooltip content={<TufteTooltip />} />
                    <Bar dataKey="similarity_pct" name="Kemiripan (%)" fill="#0F766E" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="card">
              <h3 className="section-title" style={{ fontFamily: "var(--font-serif)" }}>
                Peta Sebaran Kecocokan Sepanjang Dokumen
              </h3>
              <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 0 }}>
                Posisi relatif rentang kecocokan dari awal (0%) hingga akhir (100%) dokumen.
              </p>
              <svg width="100%" height="56" viewBox="0 0 500 56" role="img" aria-label="Peta sebaran kecocokan dokumen">
                <rect x="0" y="16" width="500" height="22" rx="4" fill="var(--surface-alt)" stroke="var(--border)" />
                {report.matches.map((item) => {
                  const total = Math.max(1, m.total_words);
                  const x = (item.sub_token_start / total) * 500;
                  const w = Math.max(3, ((item.sub_token_end - item.sub_token_start) / total) * 500);
                  const fill =
                    item.layer === "EXACT"
                      ? "#DC2626"
                      : item.layer === "NEAR_EXACT"
                      ? "#EA580C"
                      : item.layer === "LEXICAL"
                      ? "#CA8A04"
                      : "#2563EB";
                  return <rect key={item.id} x={x} y="16" width={w} height="22" fill={fill} opacity={item.counted ? 0.85 : 0.35} />;
                })}
              </svg>
            </div>
          </div>
        )}

        {/* TAB 7: ALUR PEMERIKSAAN */}
        {tab === "flowchart" && (
          <div>
            <p className="page-desc" style={{ marginBottom: 14 }}>
              Setiap blok menampilkan jumlah data aktual yang diproses pada tahap pemeriksaan ini.
            </p>
            <ProcessFlowchart stageCounts={report.stage_counts} />
          </div>
        )}

        {/* TAB 8: EKSPOR */}
        {tab === "export" && (
          <div className="card">
            <h3 className="section-title">Unduh Laporan Pemeriksaan</h3>
            <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
              Nomor Laporan: <strong>{report.report_number}</strong> · Durasi:{" "}
              <strong>{formatDuration(report.duration_seconds)}</strong> · Selesai: {report.finished_at || report.created_at}
            </p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 12 }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.pdf`, `${report.report_number}.pdf`)}
              >
                <Download size={16} /> Unduh Laporan PDF
              </button>
              <button
                type="button"
                className="btn"
                onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.html`, `${report.report_number}.html`)}
              >
                <Download size={16} /> Unduh Laporan HTML Mandiri
              </button>
              <button
                type="button"
                className="btn"
                onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.json`, `${report.report_number}.json`)}
              >
                <Download size={16} /> Unduh Data JSON
              </button>
            </div>
          </div>
        )}

        {/* Dialog Detail Sumber (Fix 6 — Accessible shadcn Dialog with Title & Description) */}
        <Dialog open={selectedSourceModal !== null} onOpenChange={(open) => !open && setSelectedSourceModal(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                #{selectedSourceModal?.rank} {selectedSourceModal?.title}
              </DialogTitle>
              <DialogDescription>
                Rincian atribusi, metadata sumber, dan rincian lapisan kecocokan terverifikasi.
              </DialogDescription>
            </DialogHeader>
            {selectedSourceModal && (
              <div style={{ fontSize: 13.5, display: "flex", flexDirection: "column", gap: 8 }}>
                <div>
                  <strong>Penulis:</strong> {selectedSourceModal.authors.join(", ") || "Tidak tercatat"}
                </div>
                <div>
                  <strong>Tahun / Tipe:</strong> {selectedSourceModal.year || "-"} · {selectedSourceModal.source_type} ({selectedSourceModal.provider})
                </div>
                {selectedSourceModal.doi && (
                  <div>
                    <strong>DOI:</strong> <code>{selectedSourceModal.doi}</code>
                  </div>
                )}
                {selectedSourceModal.license && (
                  <div>
                    <strong>Lisensi:</strong> {selectedSourceModal.license}
                  </div>
                )}
                <div>
                  <strong>Kontribusi Eksklusif:</strong> {selectedSourceModal.matched_words_exclusive} kata (
                  {selectedSourceModal.contribution_pct.toFixed(2)}%) · Total cocok: {selectedSourceModal.matched_words_total} kata
                </div>
                <div>
                  <strong>Rincian per Lapisan:</strong> Exact {selectedSourceModal.layers.EXACT || 0} kata · Near-Exact{" "}
                  {selectedSourceModal.layers.NEAR_EXACT || 0} kata · Lexical {selectedSourceModal.layers.LEXICAL || 0} kata
                </div>
                {selectedSourceModal.canonical_url && (
                  <div style={{ wordBreak: "break-all" }}>
                    <strong>URL Kanonis:</strong>{" "}
                    <a href={selectedSourceModal.canonical_url} target="_blank" rel="noreferrer">
                      {selectedSourceModal.canonical_url}
                    </a>
                  </div>
                )}
                {selectedSourceModal.alternate_urls && selectedSourceModal.alternate_urls.length > 1 && (
                  <div>
                    <strong>URL Alternatif Terdeduplikasi ({selectedSourceModal.alternate_urls.length}):</strong>
                    <ul style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: 12 }}>
                      {selectedSourceModal.alternate_urls.map((u, idx) => (
                        <li key={idx} style={{ wordBreak: "break-all" }}>
                          {u}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </BlurFade>
  );
};
