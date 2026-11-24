import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Download, ExternalLink, FileText, Layers, BarChart3, GitBranch, Table2 } from "lucide-react";
import {
  Bar,
  BarChart,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiFetch, downloadProtectedFile } from "../api/client";
import { ProcessFlowchart } from "../components/ProcessFlowchart";
import { SimilarityGauge } from "../components/SimilarityGauge";
import { FullReport, SourceViewerPayload, ViewerPayload } from "../types";

type TabKey = "overview" | "compare" | "sources" | "analytics" | "flowchart" | "export";

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
    <div style={{ fontFamily: "var(--tufte-serif)", fontSize: 13, color: "var(--text)", background: "var(--surface)", border: "1px solid var(--border)", padding: "6px 8px", borderRadius: 4 }}>
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
  const [error, setError] = useState<string | null>(null);

  const leftPaneRef = useRef<HTMLDivElement>(null);
  const rightPaneRef = useRef<HTMLDivElement>(null);
  const isSyncingRef = useRef(false);

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

  if (error) return <div className="notice notice-warn">Gagal memuat laporan: {error}</div>;
  if (!report) return <div className="card">Memuat detail laporan...</div>;

  const m = report.metrics;
  const op = m.operational_category;
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

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Laporan Kemiripan · {report.report_number}</h2>
          <p className="page-desc">
            Berkas: <strong>{report.document.filename}</strong> ({report.document.file_type.toUpperCase()}, {report.document.page_count} halaman, bahasa: {report.document.language})
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="btn btn-primary" onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.pdf`, `${report.report_number}.pdf`)}>
            <Download size={15} /> Ekspor PDF
          </button>
          <button type="button" className="btn" onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.html`, `${report.report_number}.html`)}>
            <Download size={15} /> HTML
          </button>
          <button type="button" className="btn" onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.json`, `${report.report_number}.json`)}>
            <Download size={15} /> JSON
          </button>
        </div>
      </div>

      <div className="tabs" role="tablist">
        <button type="button" className={`tab-btn ${tab === "overview" ? "active" : ""}`} onClick={() => setTab("overview")}><FileText size={14} style={{ verticalAlign: "text-bottom", marginRight: 5 }} />Ringkasan</button>
        <button type="button" className={`tab-btn ${tab === "compare" ? "active" : ""}`} onClick={() => setTab("compare")}><Layers size={14} style={{ verticalAlign: "text-bottom", marginRight: 5 }} />Perbandingan Dokumen</button>
        <button type="button" className={`tab-btn ${tab === "sources" ? "active" : ""}`} onClick={() => setTab("sources")}><Table2 size={14} style={{ verticalAlign: "text-bottom", marginRight: 5 }} />Sumber ({report.sources.length})</button>
        <button type="button" className={`tab-btn ${tab === "analytics" ? "active" : ""}`} onClick={() => setTab("analytics")}><BarChart3 size={14} style={{ verticalAlign: "text-bottom", marginRight: 5 }} />Analitik</button>
        <button type="button" className={`tab-btn ${tab === "flowchart" ? "active" : ""}`} onClick={() => setTab("flowchart")}><GitBranch size={14} style={{ verticalAlign: "text-bottom", marginRight: 5 }} />Alur Pemeriksaan</button>
        <button type="button" className={`tab-btn ${tab === "export" ? "active" : ""}`} onClick={() => setTab("export")}><Download size={14} style={{ verticalAlign: "text-bottom", marginRight: 5 }} />Ekspor</button>
      </div>

      {tab === "overview" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 16, marginBottom: 16 }}>
            <div className="card" style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
              <SimilarityGauge
                value={m.similarity_index}
                level={op.level}
                thresholdLow={op.threshold_low}
                thresholdHigh={op.threshold_high}
              />
              <div style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", marginTop: 6 }}>
                Raw Similarity: {m.raw_similarity.toFixed(2)}%
              </div>
            </div>

            <div className="card-grid" style={{ marginBottom: 0 }}>
              <div className="card"><div className="stat-label">Kata Diperiksa (Eligible)</div><div className="stat-val">{m.eligible_words.toLocaleString("id-ID")}</div><div style={{ fontSize: 12, color: "var(--text-muted)" }}>Dari {m.total_words.toLocaleString("id-ID")} total kata ({m.excluded_words} dikecualikan)</div></div>
              <div className="card"><div className="stat-label">Kata Cocok Unik</div><div className="stat-val">{m.matched_words.toLocaleString("id-ID")}</div><div style={{ fontSize: 12, color: "var(--text-muted)" }}>Exact: {m.exact_match_pct.toFixed(2)}% · Near: {m.near_exact_match_pct.toFixed(2)}%</div></div>
              <div className="card"><div className="stat-label">Sumber Ditemukan / Full-Text</div><div className="stat-val">{m.sources_found} / {report.coverage.full_text_sources_compared}</div><div style={{ fontSize: 12, color: "var(--text-muted)" }}>Metadata-only: {report.coverage.metadata_only_sources}</div></div>
              <div className="card"><div className="stat-label">Kandidat Leksikal &amp; Semantik</div><div className="stat-val">{m.lexical_candidates_count + m.semantic_candidates_count}</div><div style={{ fontSize: 12, color: "var(--text-muted)" }}>Leksikal: {m.lexical_candidates_count} · Semantik: {m.semantic_candidates_count}</div></div>
              <div className="card"><div className="stat-label">Tingkat Cakupan</div><div className="stat-val" style={{ fontSize: 20 }}>{report.coverage.level}</div><div style={{ fontSize: 12, color: "var(--text-muted)" }}>{report.coverage.external_sources_enabled ? "Korpus lokal + eksternal" : "Korpus lokal saja"}</div></div>
              <div className="card"><div className="stat-label">Waktu Pemeriksaan</div><div className="stat-val" style={{ fontSize: 20 }}>{report.duration_seconds !== null ? `${report.duration_seconds} dtk` : "-"}</div><div style={{ fontSize: 12, color: "var(--text-muted)" }}>Ekstraksi: {report.document.extraction_method} ({Math.round(report.document.extraction_confidence * 100)}%)</div></div>
            </div>
          </div>

          <div className="notice">
            <strong>Kategori Operasional ({op.level}):</strong> {op.disclaimer}
          </div>

          <div className="notice notice-warn">
            <strong>{report.coverage.statement}</strong>
            <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
              {report.coverage.notes.map((n, idx) => <li key={idx}>{n}</li>)}
              {Boolean(report.document.extra?.ocr_warning) && <li>{String(report.document.extra.ocr_warning)}</li>}
              {Boolean(report.document.extra?.page_note) && <li>{String(report.document.extra.page_note)}</li>}
              <li>{m.semantic_status}</li>
            </ul>
          </div>
        </div>
      )}

      {tab === "compare" && viewer && (
        <div>
          <div className="card" style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
              {Object.entries(CATEGORY_LABEL).map(([key, label]) => (
                <label key={key} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                  <input type="checkbox" checked={filters[key]} onChange={(e) => setFilters({ ...filters, [key]: e.target.checked })} />
                  <span className={`badge badge-${key}`}>{label}</span>
                </label>
              ))}
            </div>
            <label style={{ fontSize: 13 }}>
              <input type="checkbox" checked={syncScroll} onChange={(e) => setSyncScroll(e.target.checked)} /> Sinkronisasi gulir panel
            </label>
          </div>

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
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
                <span>Sumber Pembanding: {sourceViewer ? sourceViewer.title : "Pilih sumber / klik bagian highlight"}</span>
                {report.sources.length > 0 && (
                  <select
                    className="input"
                    style={{ width: "auto", padding: "3px 8px", fontSize: 12 }}
                    value={sourceViewer?.source_document_id || ""}
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
                  <span style={{ color: "var(--text-muted)" }}>Belum ada sumber pembanding yang dipilih atau tidak ada kecocokan.</span>
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

      {tab === "sources" && (
        <div>
          <div className="table-wrap" style={{ marginBottom: 18 }}>
            <table>
              <thead>
                <tr>
                  <th>Sumber</th>
                  <th>Tipe</th>
                  <th className="num">Kata cocok</th>
                  <th className="num">Kontribusi</th>
                  <th>Tautan &amp; Aksi</th>
                </tr>
              </thead>
              <tbody>
                {report.sources.length === 0 ? (
                  <tr><td colSpan={5}>Tidak ada sumber yang berkontribusi pada kecocokan.</td></tr>
                ) : (
                  report.sources.map((s) => (
                    <tr key={s.source_document_id}>
                      <td>
                        <strong>#{s.rank} {s.title}</strong>
                        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                          {s.authors.join(", ") || "Penulis tidak tercatat"} {s.year ? `(${s.year})` : ""}
                          {s.doi ? ` · DOI: ${s.doi}` : ""} · Status: {s.access_status}
                        </div>
                      </td>
                      <td>{s.source_type}</td>
                      <td className="num">{s.matched_words_exclusive} <span style={{ fontSize: 11, color: "var(--text-muted)" }}>(total {s.matched_words_total})</span></td>
                      <td className="num"><strong>{s.contribution_pct.toFixed(2)}%</strong></td>
                      <td>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          {s.url && (
                            <a href={s.url} target="_blank" rel="noreferrer" className="btn" style={{ fontSize: 12, minHeight: 30, padding: "4px 8px" }}>
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
              <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>Rincian Cuplikan Kecocokan ({report.matches.length})</h3>
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
                    {report.matches.slice(0, 50).map((item) => (
                      <tr key={item.id}>
                        <td>
                          <span className={`badge badge-${item.layer}`}>{CATEGORY_LABEL[item.layer] || item.layer}</span>
                          {item.excluded_reason && <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>Dikecualikan: {item.excluded_reason}</div>}
                        </td>
                        <td>
                          {item.source_title}
                          {item.src_page && <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Hlm. sumber {item.src_page}</div>}
                        </td>
                        <td style={{ fontSize: 12 }}>{item.sub_excerpt}</td>
                        <td style={{ fontSize: 12 }}>{item.src_excerpt}</td>
                        <td className="num">{item.matched_words}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {report.coverage.metadata_only_items && report.coverage.metadata_only_items.length > 0 && (
            <div className="card" style={{ marginTop: 18 }}>
              <h3 style={{ margin: "0 0 8px", fontSize: 16 }}>Sumber Eksternal Metadata-Only (Tidak Dibandingkan Full-Text)</h3>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                {report.coverage.metadata_only_items.map((item, idx) => (
                  <li key={idx}>
                    <strong>[{item.provider}]</strong> {item.title} {item.year ? `(${item.year})` : ""} {item.doi ? `· DOI: ${item.doi}` : ""} — <code>{item.access_status}</code>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {tab === "analytics" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 18 }}>
          <div className="card">
            <h3 style={{ margin: "0 0 10px", fontSize: 16, fontFamily: "var(--tufte-serif)" }}>Rasio Kata Cocok vs Tidak Cocok</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={wordRatioData} layout="vertical" margin={{ left: 20, right: 40, top: 8, bottom: 8 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={100} tick={{ fontSize: 12, fill: "var(--text-secondary)" }} />
                <Tooltip content={<TufteTooltip />} />
                <Bar dataKey="count" name="Jumlah Kata" fill="#4e79a7" radius={[0, 3, 3, 0]}>
                  <LabelList dataKey="count" position="right" fill="var(--text)" fontSize={12} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h3 style={{ margin: "0 0 10px", fontSize: 16, fontFamily: "var(--tufte-serif)" }}>Komposisi Lapisan Kemiripan (%)</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={layerChartData} layout="vertical" margin={{ left: 20, right: 45, top: 8, bottom: 8 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={90} tick={{ fontSize: 12, fill: "var(--text-secondary)" }} />
                <Tooltip content={<TufteTooltip />} />
                <Bar dataKey="pct" name="Persentase (%)" fill="#e15759" radius={[0, 3, 3, 0]}>
                  <LabelList dataKey="pct" position="right" formatter={(v: any) => `${Number(v).toFixed(2)}%`} fill="var(--text)" fontSize={12} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h3 style={{ margin: "0 0 10px", fontSize: 16, fontFamily: "var(--tufte-serif)" }}>Sumber Penyumbang Teratas (%)</h3>
            {report.sources.length === 0 ? (
              <p style={{ color: "var(--text-muted)" }}>Belum ada sumber yang berkontribusi.</p>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={report.sources.slice(0, 6)} layout="vertical" margin={{ left: 10, right: 45, top: 8, bottom: 8 }}>
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="title" axisLine={false} tickLine={false} width={150} tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
                  <Tooltip content={<TufteTooltip />} />
                  <Bar dataKey="contribution_pct" name="Kontribusi (%)" fill="#2563eb" radius={[0, 3, 3, 0]}>
                    <LabelList dataKey="contribution_pct" position="right" formatter={(v: any) => `${Number(v).toFixed(2)}%`} fill="var(--text)" fontSize={12} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="card">
            <h3 style={{ margin: "0 0 10px", fontSize: 16, fontFamily: "var(--tufte-serif)" }}>Distribusi Kemiripan per Bab / Bagian (%)</h3>
            {report.analytics.by_chapter.length === 0 ? (
              <p style={{ color: "var(--text-muted)" }}>Tidak ada segmen bab terdeteksi.</p>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={report.analytics.by_chapter} margin={{ left: 0, right: 20, top: 18, bottom: 8 }}>
                  <XAxis dataKey="chapter" axisLine={{ stroke: "var(--border)" }} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                  <Tooltip content={<TufteTooltip />} />
                  <Bar dataKey="similarity_pct" name="Kemiripan (%)" fill="#f28e2b" radius={[3, 3, 0, 0]}>
                    <LabelList dataKey="similarity_pct" position="top" formatter={(v: any) => `${Number(v).toFixed(1)}%`} fill="var(--text)" fontSize={11} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="card">
            <h3 style={{ margin: "0 0 10px", fontSize: 16, fontFamily: "var(--tufte-serif)" }}>Distribusi Kemiripan per Halaman (%)</h3>
            {report.analytics.by_page.length === 0 ? (
              <p style={{ color: "var(--text-muted)" }}>Data halaman tidak tersedia.</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={report.analytics.by_page} margin={{ left: 0, right: 20, top: 18, bottom: 8 }}>
                  <XAxis dataKey="page" axisLine={{ stroke: "var(--border)" }} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                  <Tooltip content={<TufteTooltip />} />
                  <Bar dataKey="similarity_pct" name="Kemiripan (%)" fill="#76b7b2" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="card">
            <h3 style={{ margin: "0 0 10px", fontSize: 16, fontFamily: "var(--tufte-serif)" }}>Peta Sebaran Kecocokan Sepanjang Dokumen</h3>
            <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 0 }}>
              Menunjukkan posisi relatif rentang kecocokan dari awal (0%) hingga akhir (100%) dokumen.
            </p>
            <svg width="100%" height="56" viewBox="0 0 500 56" role="img" aria-label="Peta sebaran kecocokan dokumen">
              <rect x="0" y="16" width="500" height="22" rx="4" fill="var(--surface-alt)" stroke="var(--border)" />
              {report.matches.map((item) => {
                const total = Math.max(1, m.total_words);
                const x = (item.sub_token_start / total) * 500;
                const w = Math.max(3, ((item.sub_token_end - item.sub_token_start) / total) * 500);
                const fill =
                  item.layer === "EXACT"
                    ? "#dc2626"
                    : item.layer === "NEAR_EXACT"
                    ? "#ea580c"
                    : item.layer === "LEXICAL"
                    ? "#ca8a04"
                    : "#2563eb";
                return <rect key={item.id} x={x} y="16" width={w} height="22" fill={fill} opacity={item.counted ? 0.85 : 0.35} />;
              })}
            </svg>
          </div>
        </div>
      )}

      {tab === "flowchart" && (
        <div>
          <p className="page-desc" style={{ marginBottom: 14 }}>
            Setiap blok menampilkan jumlah data aktual yang diproses pada tahap pemeriksaan ini.
          </p>
          <ProcessFlowchart stageCounts={report.stage_counts} />
        </div>
      )}

      {tab === "export" && (
        <div className="card">
          <h3 style={{ margin: "0 0 10px", fontSize: 16 }}>Unduh Laporan Pemeriksaan</h3>
          <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
            Nomor Laporan: <strong>{report.report_number}</strong> · Waktu: {report.finished_at || report.created_at}
          </p>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 12 }}>
            <button type="button" className="btn btn-primary" onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.pdf`, `${report.report_number}.pdf`)}>
              <Download size={16} /> Unduh Laporan PDF
            </button>
            <button type="button" className="btn" onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.html`, `${report.report_number}.html`)}>
              <Download size={16} /> Unduh Laporan HTML Mandiri
            </button>
            <button type="button" className="btn" onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.json`, `${report.report_number}.json`)}>
              <Download size={16} /> Unduh Data JSON
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
