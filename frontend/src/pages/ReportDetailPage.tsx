import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  AlertTriangle,
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Database,
  Download,
  ExternalLink,
  FileSearch2,
  FileText,
  Filter,
  Globe,
  Layers,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { BlurFade } from "@/components/ui/blur-fade";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiFetch, downloadProtectedFile } from "../api/client";
import { InfoHint } from "../components/InfoHint";
import { ProcessFlowchart } from "../components/ProcessFlowchart";
import { SimilarityGauge } from "../components/SimilarityGauge";
import { AiClassificationBadge, ModeBadge, similarityToneClass } from "../components/StatusBadge";
import {
  FullReport,
  ReportMatch,
  ReportSource,
  SourceViewerPayload,
  ViewerPayload,
  ViewerSegment,
} from "../types";
import { formatDuration, formatMs } from "../utils/format";

const MATCHES_PAGE_SIZE = 15;

const LAYER_LABELS: Record<string, string> = {
  EXACT: "Identik",
  NEAR_EXACT: "Mirip Dekat",
  LEXICAL: "Frasa Terdeteksi",
  SEMANTIC: "Kandidat Kemiripan Makna",
  EXCLUDED: "Dikecualikan",
};

const FALLBACK_PALETTE = [
  "#6E1F2F",
  "#1D4ED8",
  "#15803D",
  "#7E22CE",
  "#B45309",
  "#0F766E",
  "#BE123C",
  "#4338CA",
];

function formatContributionPct(pct: number): string {
  if (pct > 0 && pct < 1) return "<1%";
  return `${pct.toFixed(1)}%`;
}

function formatBytes(sizeBytes?: number): string {
  if (!sizeBytes || sizeBytes <= 0) return "-";
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDateId(iso?: string | null): string {
  if (!iso) return "-";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  return dt.toLocaleString("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function pillColor(rank?: number | null, explicit?: string | null): string {
  if (explicit) return explicit;
  if (!rank || rank < 1) return FALLBACK_PALETTE[0];
  return FALLBACK_PALETTE[(rank - 1) % FALLBACK_PALETTE.length];
}

interface AnnotatedParaChunk {
  text: string;
  category: ViewerSegment["category"];
  match_ids: number[];
  source_rank?: number | null;
  source_color?: string | null;
  excluded_reason?: string | null;
}

interface AnnotatedParaRow {
  id: number;
  pills: Array<{ rank: number; color: string; firstMatchId: number | null }>;
  chunks: AnnotatedParaChunk[];
}

function groupSegmentsIntoParagraphs(segments: ViewerSegment[]): AnnotatedParaRow[] {
  const rows: AnnotatedParaRow[] = [];
  let currentChunks: AnnotatedParaChunk[] = [];
  let rowId = 0;

  const flushRow = () => {
    if (!currentChunks.length) return;
    const seenRanks = new Map<number, { rank: number; color: string; firstMatchId: number | null }>();
    for (const ch of currentChunks) {
      if (ch.category !== "PLAIN" && ch.category !== "EXCLUDED" && ch.source_rank) {
        if (!seenRanks.has(ch.source_rank)) {
          seenRanks.set(ch.source_rank, {
            rank: ch.source_rank,
            color: pillColor(ch.source_rank, ch.source_color),
            firstMatchId: ch.match_ids[0] ?? null,
          });
        }
      }
    }
    const hasNonWhitespace = currentChunks.some((c) => c.text.trim().length > 0);
    if (hasNonWhitespace) {
      rows.push({
        id: rowId++,
        pills: Array.from(seenRanks.values()).sort((a, b) => a.rank - b.rank),
        chunks: currentChunks,
      });
    }
    currentChunks = [];
  };

  for (const seg of segments) {
    const parts = seg.text.split("\n");
    parts.forEach((part, idx) => {
      if (part.length > 0) {
        currentChunks.push({
          text: part,
          category: seg.category,
          match_ids: seg.match_ids,
          source_rank: seg.source_rank,
          source_color: seg.source_color,
          excluded_reason: seg.excluded_reason,
        });
      }
      if (idx < parts.length - 1) {
        flushRow();
      }
    });
  }
  flushRow();
  return rows;
}

const ChartTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs text-card-foreground shadow-sm">
      <div className="mb-1 font-semibold">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="tabular-nums">
          {p.name}: <strong>{Number(p.value).toLocaleString("id-ID")}</strong>
        </div>
      ))}
    </div>
  );
};

export const ReportDetailPage: React.FC = () => {
  const { checkId } = useParams<{ checkId: string }>();
  const [report, setReport] = useState<FullReport | null>(null);
  const [viewer, setViewer] = useState<ViewerPayload | null>(null);
  const [sourceViewer, setSourceViewer] = useState<SourceViewerPayload | null>(null);
  const [activeMatchId, setActiveMatchId] = useState<number | null>(null);
  const [selectedSourceRank, setSelectedSourceRank] = useState<number | null>(null);
  const [selectedLayerFilter, setSelectedLayerFilter] = useState<string>("ALL");
  const [matchesPage, setMatchesPage] = useState(1);
  const [sectionTab, setSectionTab] = useState<"plagiarism" | "ai">("plagiarism");
  const [plagInnerTab, setPlagInnerTab] = useState("summary");
  const [selectedEvidence, setSelectedEvidence] = useState<ReportMatch | null>(null);
  const [selectedAiParaIdx, setSelectedAiParaIdx] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!checkId) return;
    setError(null);
    Promise.all([
      apiFetch<FullReport>(`/checks/${checkId}/report`),
      apiFetch<ViewerPayload>(`/checks/${checkId}/viewer`).catch(() => null),
    ])
      .then(async ([rep, vw]) => {
        setReport(rep);
        setViewer(vw);
        if (rep.mode === "AI_ONLY") {
          setSectionTab("ai");
        } else {
          setSectionTab("plagiarism");
        }
        if (rep.sources?.length) {
          try {
            const sv = await apiFetch<SourceViewerPayload>(
              `/checks/${checkId}/sources/${rep.sources[0].source_document_id}/viewer`
            );
            setSourceViewer(sv);
          } catch {
            // Optional if source preview unavailable
          }
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [checkId]);

  const annotatedParagraphs = useMemo(() => {
    if (!viewer?.segments?.length) return [];
    return groupSegmentsIntoParagraphs(viewer.segments);
  }, [viewer]);

  const filteredMatches = useMemo(() => {
    if (!report) return [];
    return report.matches.filter((m) => {
      if (selectedLayerFilter !== "ALL" && m.layer !== selectedLayerFilter) return false;
      if (selectedSourceRank !== null && m.source_rank !== selectedSourceRank) return false;
      return true;
    });
  }, [report, selectedLayerFilter, selectedSourceRank]);

  const totalMatchPages = Math.max(1, Math.ceil(filteredMatches.length / MATCHES_PAGE_SIZE));
  const pagedMatches = useMemo(() => {
    const start = (matchesPage - 1) * MATCHES_PAGE_SIZE;
    return filteredMatches.slice(start, start + MATCHES_PAGE_SIZE);
  }, [filteredMatches, matchesPage]);

  const loadSourceById = async (sourceDocId: string) => {
    if (!checkId) return;
    try {
      const sv = await apiFetch<SourceViewerPayload>(`/checks/${checkId}/sources/${sourceDocId}/viewer`);
      setSourceViewer(sv);
    } catch {
      // Ignore preview error cleanly
    }
  };

  const handleSelectSegment = async (matchIds: number[], rank?: number | null) => {
    if (!matchIds.length || !report || !checkId) return;
    const mid = matchIds[0];
    setActiveMatchId(mid);
    if (rank) setSelectedSourceRank(rank);
    const matchObj = report.matches.find((m) => m.id === mid);
    if (matchObj && sourceViewer?.source_document_id !== matchObj.source_document_id) {
      await loadSourceById(matchObj.source_document_id);
    }
  };

  const handleJumpToSource = async (src: ReportSource) => {
    setSelectedSourceRank(src.rank);
    setPlagInnerTab("compare");
    const firstMatch = report?.matches.find((m) => m.source_document_id === src.source_document_id);
    if (firstMatch) setActiveMatchId(firstMatch.id);
    await loadSourceById(src.source_document_id);
  };

  const renderedSourceText = useMemo(() => {
    if (!sourceViewer) return null;
    const text = sourceViewer.text || "";
    const highlights = (sourceViewer.highlights || [])
      .filter((h) => h.src_char_end > h.src_char_start)
      .sort((a, b) => a.src_char_start - b.src_char_start);
    if (!highlights.length) return text;

    const activeSrc = report?.sources.find((s) => s.source_document_id === sourceViewer.source_document_id);
    const srcColor = pillColor(activeSrc?.rank, activeSrc?.color_hex);

    const nodes: React.ReactNode[] = [];
    let cursor = 0;
    highlights.forEach((h, i) => {
      const start = Math.max(cursor, Math.min(h.src_char_start, text.length));
      const end = Math.max(start, Math.min(h.src_char_end, text.length));
      if (start > cursor) {
        nodes.push(<span key={`p-${i}`}>{text.slice(cursor, start)}</span>);
      }
      if (end > start) {
        const isCurrent = activeMatchId === h.match_id;
        nodes.push(
          <span
            key={`h-${h.match_id}-${i}`}
            className={`hl-seg hl-source-tinted ${isCurrent ? "hl-active" : ""}`}
            style={{ ["--src-color" as any]: srcColor }}
          >
            {text.slice(start, end)}
          </span>
        );
      }
      cursor = Math.max(cursor, end);
    });
    if (cursor < text.length) {
      nodes.push(<span key="tail">{text.slice(cursor)}</span>);
    }
    return nodes;
  }, [sourceViewer, activeMatchId, report?.sources]);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Gagal memuat laporan pemeriksaan</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!report) {
    return (
      <div className="flex flex-col gap-5">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-44 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  const mode = report.mode || "PLAGIARISM_ONLY";
  const isCombined = mode === "COMBINED";
  const hasAiReport = Boolean(report.ai_report);
  const metrics = report.metrics || ({} as FullReport["metrics"]);
  const simVal = Number(metrics.similarity_index ?? 0);
  const thresholdLow = metrics.operational_category?.threshold_low ?? 15;
  const thresholdHigh = metrics.operational_category?.threshold_high ?? 30;
  const fulltextCompared =
    report.coverage?.source_metrics?.fulltext_compared ??
    report.coverage?.full_text_sources_compared ??
    0;
  const metadataOnlyCount =
    report.coverage?.source_metrics?.metadata_only_sources ??
    report.coverage?.metadata_only_sources ??
    0;
  const aiReport = report.ai_report;
  const activeFilters = report.active_filters || [];
  const integrityFlags = report.integrity_flags || [];
  const srcCat = report.source_categories || {
    internet_pct: 0,
    publication_pct: 0,
    local_pct: 0,
    counts: { internet: 0, publication: 0, local: 0 },
  };

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        {/* Institutional Cover / Document Details Card */}
        <Card className="shadow-none overflow-hidden">
          <CardContent className="p-6">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex min-w-0 flex-1 flex-col gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
                    Laporan Integritas Naskah
                  </span>
                  <span className="text-muted-foreground">·</span>
                  <span className="text-xs font-medium tabular-nums text-muted-foreground">
                    {report.report_number}
                  </span>
                  <ModeBadge mode={mode} />
                </div>

                <h1 className="font-serif text-2xl font-bold leading-snug tracking-tight text-foreground sm:text-[26px]">
                  {report.document.title || report.document.filename}
                </h1>

                <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <FileText className="size-3.5 text-primary/70" aria-hidden="true" />
                    <strong className="font-medium text-foreground">{report.document.filename}</strong>
                  </span>
                  {report.document.size_bytes ? (
                    <span className="tabular-nums">Ukuran: {formatBytes(report.document.size_bytes)}</span>
                  ) : null}
                  <span>Selesai: {formatDateId(report.finished_at || report.created_at)}</span>
                  <span>Durasi: {formatDuration(report.duration_seconds)}</span>
                  <span className="inline-flex items-center gap-1">
                    Ekstraksi:{" "}
                    <strong className="font-medium text-foreground">
                      {report.document.extraction_method === "OCR"
                        ? `OCR (${report.document.ocr_pages?.length || 0} hlm)`
                        : report.document.extraction_method === "MIXED"
                        ? `Teks + OCR (${report.document.ocr_pages?.length || 0} hlm)`
                        : report.document.extraction_method === "OCR_UNAVAILABLE"
                        ? "Pindaian (OCR Nonaktif)"
                        : "Teks Langsung"}
                    </strong>
                    {typeof report.document.extraction_confidence === "number" ? (
                      <span className="tabular-nums">
                        ({Math.round(report.document.extraction_confidence * 100)}%)
                      </span>
                    ) : null}
                  </span>
                </div>
              </div>

              <div className="flex flex-col gap-3 sm:items-end">
                {/* Export Actions */}
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="default"
                    size="sm"
                    onClick={() =>
                      downloadProtectedFile(`/checks/${report.check_id}/export.pdf`, `${report.report_number}.pdf`)
                    }
                  >
                    <Download className="size-3.5" data-icon="inline-start" aria-hidden="true" />
                    <span>Unduh PDF</span>
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      downloadProtectedFile(`/checks/${report.check_id}/export.html`, `${report.report_number}.html`)
                    }
                  >
                    <Download className="size-3.5" data-icon="inline-start" aria-hidden="true" />
                    <span>HTML</span>
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      downloadProtectedFile(`/checks/${report.check_id}/export.json`, `${report.report_number}.json`)
                    }
                  >
                    <Download className="size-3.5" data-icon="inline-start" aria-hidden="true" />
                    <span>JSON</span>
                  </Button>
                </div>

                {/* Institutional Page · Word · Character Strip */}
                <div className="grid grid-cols-3 divide-x divide-border rounded-lg border border-border bg-muted/40 text-center">
                  <div className="px-3.5 py-2">
                    <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground">Halaman</div>
                    <div className="font-serif text-base font-bold tabular-nums text-foreground">
                      {(report.document.page_count || 1).toLocaleString("id-ID")}
                    </div>
                  </div>
                  <div className="px-3.5 py-2">
                    <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground">Kata</div>
                    <div className="font-serif text-base font-bold tabular-nums text-foreground">
                      {(report.document.word_count || 0).toLocaleString("id-ID")}
                    </div>
                  </div>
                  <div className="px-3.5 py-2">
                    <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground">Karakter</div>
                    <div className="font-serif text-base font-bold tabular-nums text-foreground">
                      {(report.document.character_count || 0).toLocaleString("id-ID")}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Strict Top-Level Separation Between Plagiarism Report and AI Report in COMBINED Mode */}
        {isCombined && hasAiReport && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-3.5">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Layers className="size-4 text-primary" aria-hidden="true" />
              <span>
                Mode Gabungan memisahkan <strong className="text-foreground">Laporan Kemiripan Naskah</strong> dan{" "}
                <strong className="text-foreground">Laporan Deteksi Tulisan AI</strong> secara ketat tanpa menggabungkan skornya.
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant={sectionTab === "plagiarism" ? "default" : "outline"}
                onClick={() => setSectionTab("plagiarism")}
              >
                <FileSearch2 className="size-3.5" data-icon="inline-start" aria-hidden="true" />
                <span>Laporan Kemiripan ({simVal.toFixed(1)}%)</span>
              </Button>
              <Button
                type="button"
                size="sm"
                variant={sectionTab === "ai" ? "default" : "outline"}
                onClick={() => setSectionTab("ai")}
              >
                <Bot className="size-3.5" data-icon="inline-start" aria-hidden="true" />
                <span>
                  Laporan Deteksi AI (
                  {aiReport?.score_available && aiReport.ai_likelihood_pct !== null
                    ? `${aiReport.ai_likelihood_pct.toFixed(1)}%`
                    : "Kurang Bukti"}
                  )
                </span>
              </Button>
            </div>
          </div>
        )}

        {/* ================== SECTION A: PLAGIARISM REPORT ================== */}
        {mode !== "AI_ONLY" && (sectionTab === "plagiarism" || !isCombined) && (
          <div className="flex flex-col gap-6">
            {/* Ringkasan Integritas Institutional Panel */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
              {/* Overall Similarity & Active Exclusions */}
              <Card className="shadow-none lg:col-span-5">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                    Kemiripan Keseluruhan
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="flex items-center gap-5">
                    <SimilarityGauge
                      value={simVal}
                      level={metrics.operational_category?.level || "-"}
                      thresholdLow={thresholdLow}
                      thresholdHigh={thresholdHigh}
                    />
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-1.5">
                        <span className={`font-serif text-4xl font-bold tabular-nums ${similarityToneClass(simVal)}`}>
                          {simVal.toFixed(1)}%
                        </span>
                        <InfoHint text="Persentase kata unik pada naskah bersih yang cocok dengan sumber pembanding tanpa penghitungan ganda." />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        <strong className="text-foreground">{(metrics.matched_words ?? 0).toLocaleString("id-ID")}</strong> dari{" "}
                        <strong className="text-foreground">{(metrics.eligible_words ?? 0).toLocaleString("id-ID")}</strong> kata diperiksa
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Kategori: <strong className="text-foreground">{metrics.operational_category?.level || "-"}</strong>
                      </p>
                    </div>
                  </div>

                  {/* Active Filters / Exclusions */}
                  <div className="rounded-lg border border-border bg-muted/35 p-3">
                    <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                      <Filter className="size-3.5 text-primary/75" aria-hidden="true" />
                      <span>Bagian yang Dikecualikan</span>
                    </div>
                    {activeFilters.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {activeFilters.map((f) => (
                          <Badge key={f} variant="secondary" className="text-[11px] font-normal">
                            {f}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground">Seluruh bagian naskah diperiksa tanpa pengecualian.</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Source Categories Breakdown */}
              <Card className="shadow-none lg:col-span-4">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                    Kelompok Sumber Cocok
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Kontribusi eksklusif berdasarkan jenis sumber ({fulltextCompared} dokumen teks lengkap dibandingkan).
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3.5 pt-1">
                  {[
                    {
                      label: "Sumber Internet",
                      pct: srcCat.internet_pct,
                      count: srcCat.counts?.internet ?? 0,
                      icon: Globe,
                      barColor: "#1D4ED8",
                    },
                    {
                      label: "Publikasi Ilmiah",
                      pct: srcCat.publication_pct,
                      count: srcCat.counts?.publication ?? 0,
                      icon: BookOpen,
                      barColor: "#6E1F2F",
                    },
                    {
                      label: "Korpus Lokal",
                      pct: srcCat.local_pct,
                      count: srcCat.counts?.local ?? 0,
                      icon: Database,
                      barColor: "#15803D",
                    },
                  ].map((row) => {
                    const Icon = row.icon;
                    return (
                      <div key={row.label} className="flex flex-col gap-1.5">
                        <div className="flex items-center justify-between text-xs">
                          <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
                            <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
                            {row.label}
                            <span className="text-muted-foreground font-normal">({row.count})</span>
                          </span>
                          <span className="font-semibold tabular-nums text-foreground">
                            {formatContributionPct(row.pct)}
                          </span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${Math.min(100, Math.max(row.pct > 0 ? 3 : 0, row.pct))}%`,
                              backgroundColor: row.barColor,
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>

              {/* Integrity Flags Card */}
              <Card className="shadow-none lg:col-span-3">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                    {integrityFlags.length > 0 ? (
                      <ShieldAlert className="size-4 text-amber-600" aria-hidden="true" />
                    ) : (
                      <ShieldCheck className="size-4 text-emerald-700" aria-hidden="true" />
                    )}
                    <span>Tanda Integritas</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2.5">
                  {integrityFlags.length === 0 ? (
                    <div className="rounded-lg border border-border bg-muted/35 p-3">
                      <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                        <CheckCircle2 className="size-4 text-emerald-700 shrink-0" aria-hidden="true" />
                        <span>Tidak Ada Anomali Karakter</span>
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        Tidak terdeteksi penggantian huruf (homoglyph) maupun karakter lebar-nol tersembunyi di dalam kata.
                      </p>
                    </div>
                  ) : (
                    <>
                      {integrityFlags.map((flag) => (
                        <div
                          key={flag.code}
                          className="rounded-lg border border-amber-500/35 bg-amber-500/10 p-3 flex flex-col gap-1"
                        >
                          <span className="text-xs font-semibold text-foreground">{flag.title}</span>
                          <span className="text-xs font-medium text-amber-800 dark:text-amber-300">{flag.summary}</span>
                          <span className="text-[11px] leading-relaxed text-muted-foreground">{flag.detail}</span>
                        </div>
                      ))}
                      <p className="rounded-md bg-muted/50 px-2.5 py-2 text-[11px] leading-relaxed text-muted-foreground">
                        Tanda integritas bersifat indikatif. Tinjauan manusia tetap diperlukan untuk memverifikasi konteks penulisan.
                      </p>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Plagiarism Sub-Tabs */}
            <Tabs value={plagInnerTab} onValueChange={setPlagInnerTab} className="w-full">
              <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1 bg-muted p-1">
                <TabsTrigger value="summary">Ringkasan &amp; Sumber Utama</TabsTrigger>
                <TabsTrigger value="compare">Naskah Berpenanda ({report.matches.length})</TabsTrigger>
                <TabsTrigger value="sources">Daftar Sumber Lengkap ({report.sources.length})</TabsTrigger>
                <TabsTrigger value="coverage">Cakupan Pemeriksaan</TabsTrigger>
                <TabsTrigger value="analytics">Analitik &amp; Alur</TabsTrigger>
              </TabsList>

              <TabsContent value="summary" className="mt-4 flex flex-col gap-5">
                {/* Top Sources Colored Ranked List */}
                <Card className="shadow-none">
                  <CardHeader className="flex flex-row items-center justify-between gap-3 pb-3">
                    <div>
                      <CardTitle className="text-base">Daftar Sumber Utama</CardTitle>
                      <CardDescription>
                        Nomor dan warna sumber sama dengan penanda pada Naskah Berpenanda serta laporan PDF. Klik sumber untuk langsung meninjau padanan teks.
                      </CardDescription>
                    </div>
                    {report.sources.length > 6 && (
                      <Button type="button" variant="outline" size="sm" onClick={() => setPlagInnerTab("sources")}>
                        Lihat semua ({report.sources.length})
                      </Button>
                    )}
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    {report.sources.length === 0 ? (
                      <div className="rounded-md border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
                        Tidak ditemukan sumber dengan kecocokan teks pada sesi pemeriksaan ini.
                      </div>
                    ) : (
                      report.sources.slice(0, 8).map((src) => {
                        const badgeHex = pillColor(src.rank, src.color_hex);
                        return (
                          <div
                            key={src.source_document_id}
                            onClick={() => handleJumpToSource(src)}
                            className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-border bg-card px-3.5 py-2.5 transition-colors hover:bg-accent/50"
                          >
                            <div className="flex min-w-0 items-center gap-3">
                              <span className="source-rank-pill shrink-0" style={{ backgroundColor: badgeHex }}>
                                {src.rank}
                              </span>
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="truncate text-sm font-medium text-foreground">{src.title}</span>
                                  <span
                                    className="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10.5px] font-medium"
                                    style={{
                                      backgroundColor: src.chip_bg_hex || "var(--muted)",
                                      color: src.chip_text_hex || "var(--foreground)",
                                    }}
                                  >
                                    {src.category_label || src.source_type}
                                  </span>
                                </div>
                                <p className="truncate text-xs text-muted-foreground">
                                  {src.authors?.length ? src.authors.join(", ") : src.provider || "Korpus Lokal"}
                                  {src.year ? ` (${src.year})` : ""}
                                  {src.doi ? ` · DOI: ${src.doi}` : ""}
                                  {` · ${src.matched_words_exclusive} kata unik`}
                                </p>
                              </div>
                            </div>
                            <span className="shrink-0 font-serif text-base font-bold tabular-nums text-foreground">
                              {formatContributionPct(src.contribution_pct)}
                            </span>
                          </div>
                        );
                      })
                    )}
                  </CardContent>
                </Card>

                {/* Layer Breakdown + Plain Summary */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Card className="shadow-none">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">Rincian Lapisan Kemiripan</CardTitle>
                      <CardDescription>Setiap kata hanya dihitung paling tinggi satu kali (tanpa hitung ganda).</CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-3 text-sm">
                      <div className="flex items-center justify-between border-b border-border pb-2">
                        <span>Kecocokan Identik</span>
                        <strong className="tabular-nums">{(metrics.exact_match_pct ?? 0).toFixed(1)}%</strong>
                      </div>
                      <div className="flex items-center justify-between border-b border-border pb-2">
                        <span>Kemiripan Mendekati Identik (Suntingan Ringan)</span>
                        <strong className="tabular-nums">{(metrics.near_exact_match_pct ?? 0).toFixed(1)}%</strong>
                      </div>
                      <div className="flex items-center justify-between border-b border-border pb-2">
                        <span>Kemiripan Frasa (Leksikal)</span>
                        <strong className="tabular-nums">{(metrics.lexical_match_pct ?? 0).toFixed(1)}%</strong>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Kandidat Kemiripan Makna (Tinjauan Manusia)</span>
                        <strong className="tabular-nums">{metrics.semantic_candidates_count ?? 0} bagian</strong>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="shadow-none">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">Cakupan Sumber Pembanding</CardTitle>
                      <CardDescription>Status nyata keterjangkauan sumber yang diperiksa pada sesi ini.</CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-3 text-sm">
                      <div className="flex items-center justify-between border-b border-border pb-2">
                        <span>Dokumen Sumber Dibandingkan (Teks Lengkap)</span>
                        <strong className="tabular-nums">{fulltextCompared}</strong>
                      </div>
                      <div className="flex items-center justify-between border-b border-border pb-2">
                        <span>Sumber Terbukti Cocok</span>
                        <strong className="tabular-nums">{report.sources.length}</strong>
                      </div>
                      <div className="flex items-center justify-between border-b border-border pb-2">
                        <span>Hanya Informasi Referensi (Tanpa Isi Penuh)</span>
                        <strong className="tabular-nums">{metadataOnlyCount}</strong>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {report.coverage?.statement ||
                          "Sistem hanya menghitung kecocokan dari sumber berteks lengkap yang berhasil diakses."}
                      </p>
                    </CardContent>
                  </Card>
                </div>

                {/* Plain-Language 5-Point Interpretation + Formula Disclosure */}
                <Accordion type="multiple" className="rounded-xl border border-border bg-card px-5">
                  {report.plain_summary && (
                    <AccordionItem value="plain">
                      <AccordionTrigger className="hover:no-underline text-sm font-semibold">
                        Ringkasan Interpretasi Bahasa Sederhana (5 Pertanyaan Utama)
                      </AccordionTrigger>
                      <AccordionContent className="pb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                        {[
                          { q: "1. Tingkat kemiripan dokumen", a: report.plain_summary.similarity_answer },
                          { q: "2. Sumber pembanding yang cocok", a: report.plain_summary.sources_answer },
                          { q: "3. Indikasi pola tulisan AI", a: report.plain_summary.ai_answer },
                          { q: "4. Bagian yang perlu ditinjau", a: report.plain_summary.review_answer },
                          { q: "5. Cakupan pemeriksaan sumber", a: report.plain_summary.coverage_answer },
                        ].map((item) => (
                          <div key={item.q} className="rounded-md border border-border bg-muted/30 p-3 flex flex-col gap-1">
                            <span className="text-xs font-semibold text-foreground">{item.q}</span>
                            <p className="text-xs leading-relaxed text-muted-foreground">{item.a}</p>
                          </div>
                        ))}
                      </AccordionContent>
                    </AccordionItem>
                  )}
                  <AccordionItem value="formula" className="border-b-0">
                    <AccordionTrigger className="hover:no-underline text-sm font-semibold">
                      Detail Rumus Penghitungan Skor &amp; Durasi Tahapan
                    </AccordionTrigger>
                    <AccordionContent className="pb-4 text-xs leading-relaxed text-muted-foreground flex flex-col gap-2">
                      <p>
                        Rumus transparan: <code>(Kata Cocok Unik / Jumlah Kata Diperiksa) × 100%</code>.
                      </p>
                      <p>
                        Total kata awal: <strong>{metrics.total_words ?? 0}</strong> · Kata dikecualikan:{" "}
                        <strong>{metrics.excluded_words ?? 0}</strong> · Kata unik terhitung:{" "}
                        <strong>{metrics.matched_words ?? 0}</strong>.
                      </p>
                      {metrics.stage_timings_ms && (
                        <p className="tabular-nums">
                          Durasi eksekusi:{" "}
                          {Object.entries(metrics.stage_timings_ms)
                            .map(([k, v]) => `${k}: ${formatMs(v)}`)
                            .join(" · ")}
                        </p>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </TabsContent>

              {/* ================== ANNOTATED MANUSCRIPT COMPARISON TAB ================== */}
              <TabsContent value="compare" className="mt-4 flex flex-col gap-4">
                {/* Interactive Colored Source Legend Strip */}
                {report.sources.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card px-3.5 py-2.5">
                    <span className="text-xs font-semibold text-muted-foreground mr-1">Filter Sumber:</span>
                    <Button
                      type="button"
                      size="sm"
                      variant={selectedSourceRank === null ? "default" : "outline"}
                      className="h-7 px-2.5 text-xs"
                      onClick={() => {
                        setSelectedSourceRank(null);
                        setMatchesPage(1);
                      }}
                    >
                      Semua
                    </Button>
                    {report.sources.slice(0, 10).map((src) => {
                      const active = selectedSourceRank === src.rank;
                      const bgHex = pillColor(src.rank, src.color_hex);
                      return (
                        <button
                          key={src.source_document_id}
                          type="button"
                          onClick={() => {
                            setSelectedSourceRank(active ? null : src.rank);
                            setMatchesPage(1);
                            loadSourceById(src.source_document_id);
                          }}
                          className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors ${
                            active
                              ? "border-primary bg-primary/10 text-foreground font-semibold"
                              : "border-border bg-background text-muted-foreground hover:bg-accent"
                          }`}
                        >
                          <span
                            className="inline-flex size-4 items-center justify-center rounded text-[10px] font-bold text-white"
                            style={{ backgroundColor: bgHex }}
                          >
                            {src.rank}
                          </span>
                          <span className="max-w-[140px] truncate">{src.title}</span>
                          <span className="tabular-nums opacity-75">{formatContributionPct(src.contribution_pct)}</span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {viewer ? (
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <Card className="shadow-none">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Naskah Berpenanda</CardTitle>
                        <CardDescription>
                          Nomor di tepi kiri sesuai daftar sumber. Klik sorotan warna untuk menyinkronkan sumber pembanding.
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="viewer-pane viewer-annotated">
                          {annotatedParagraphs.map((row) => (
                            <div key={row.id} className="viewer-para-row">
                              <div className="viewer-gutter">
                                {row.pills.map((p) => (
                                  <button
                                    key={p.rank}
                                    type="button"
                                    className="viewer-margin-pill"
                                    style={{ backgroundColor: p.color }}
                                    title={`Sumber #${p.rank}`}
                                    onClick={() => {
                                      const src = report.sources.find((s) => s.rank === p.rank);
                                      if (src) {
                                        setSelectedSourceRank(src.rank);
                                        if (p.firstMatchId) setActiveMatchId(p.firstMatchId);
                                        loadSourceById(src.source_document_id);
                                      }
                                    }}
                                  >
                                    {p.rank}
                                  </button>
                                ))}
                              </div>
                              <p className="viewer-para-text">
                                {row.chunks.map((seg, idx) => {
                                  if (seg.category === "PLAIN") {
                                    return <span key={idx}>{seg.text}</span>;
                                  }
                                  if (seg.category === "EXCLUDED") {
                                    return (
                                      <span
                                        key={idx}
                                        className="hl-seg hl-EXCLUDED"
                                        title={`Dikecualikan: ${seg.excluded_reason || "aturan pengecualian"}`}
                                      >
                                        {seg.text}
                                      </span>
                                    );
                                  }
                                  const isDimmed =
                                    selectedSourceRank !== null &&
                                    seg.source_rank !== null &&
                                    seg.source_rank !== selectedSourceRank;
                                  const srcHex = pillColor(seg.source_rank, seg.source_color);
                                  return (
                                    <span
                                      key={idx}
                                      onClick={() => handleSelectSegment(seg.match_ids, seg.source_rank)}
                                      className={`hl-seg hl-source-tinted ${
                                        activeMatchId && seg.match_ids.includes(activeMatchId) ? "hl-active" : ""
                                      } ${isDimmed ? "opacity-35" : ""}`}
                                      style={{ ["--src-color" as any]: srcHex }}
                                      title={`${seg.source_rank ? `Sumber #${seg.source_rank} · ` : ""}${
                                        LAYER_LABELS[seg.category] || seg.category
                                      }`}
                                    >
                                      {seg.text}
                                    </span>
                                  );
                                })}
                              </p>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="shadow-none">
                      <CardHeader className="pb-2 flex flex-col gap-2">
                        <CardTitle className="text-sm">Sumber Pembanding Terkait</CardTitle>
                        {report.sources.length > 0 && (
                          <select
                            className="h-9 rounded-md border border-input bg-background px-3 text-xs text-foreground"
                            value={sourceViewer?.source_document_id || ""}
                            onChange={async (e) => {
                              const sid = e.target.value;
                              if (!sid) return;
                              await loadSourceById(sid);
                            }}
                          >
                            {report.sources.map((s) => (
                              <option key={s.source_document_id} value={s.source_document_id}>
                                #{s.rank} — {s.title} ({formatContributionPct(s.contribution_pct)})
                              </option>
                            ))}
                          </select>
                        )}
                      </CardHeader>
                      <CardContent>
                        {sourceViewer ? (
                          <div className="viewer-pane">{renderedSourceText}</div>
                        ) : (
                          <div className="flex h-[540px] items-center justify-center rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                            Tidak ada sumber berteks lengkap yang cocok untuk ditampilkan.
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                ) : (
                  <Alert>
                    <AlertTitle>Pratinjau teks tidak tersedia</AlertTitle>
                    <AlertDescription>Berkas hasil ekstraksi belum tersedia untuk dokumen ini.</AlertDescription>
                  </Alert>
                )}

                {/* Paginated Evidence Table */}
                <Card className="shadow-none">
                  <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <CardTitle className="text-base">Daftar Bukti Kecocokan</CardTitle>
                      <CardDescription>Klik tombol rincian pada baris mana pun untuk memeriksa perbandingan lengkap.</CardDescription>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {["ALL", "EXACT", "NEAR_EXACT", "LEXICAL", "SEMANTIC"].map((layerKey) => (
                        <Button
                          key={layerKey}
                          type="button"
                          size="sm"
                          variant={selectedLayerFilter === layerKey ? "default" : "outline"}
                          onClick={() => {
                            setSelectedLayerFilter(layerKey);
                            setMatchesPage(1);
                          }}
                        >
                          {layerKey === "ALL" ? "Semua" : LAYER_LABELS[layerKey] || layerKey}
                        </Button>
                      ))}
                    </div>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Sumber</TableHead>
                            <TableHead>Jenis</TableHead>
                            <TableHead>Cuplikan Naskah</TableHead>
                            <TableHead className="text-right">Kata</TableHead>
                            <TableHead className="text-right">Bukti</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {pagedMatches.length === 0 ? (
                            <TableRow>
                              <TableCell colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                                Tidak ada kecocokan untuk filter ini.
                              </TableCell>
                            </TableRow>
                          ) : (
                            pagedMatches.map((m) => (
                              <TableRow key={m.id}>
                                <TableCell className="max-w-[230px]">
                                  <div className="flex items-center gap-2">
                                    {m.source_rank ? (
                                      <span
                                        className="source-rank-pill shrink-0"
                                        style={{ backgroundColor: pillColor(m.source_rank, m.source_color) }}
                                      >
                                        {m.source_rank}
                                      </span>
                                    ) : null}
                                    <span className="truncate font-medium text-foreground">{m.source_title}</span>
                                  </div>
                                </TableCell>
                                <TableCell>
                                  <Badge variant="outline">{LAYER_LABELS[m.layer] || m.layer}</Badge>
                                </TableCell>
                                <TableCell className="max-w-[320px] truncate text-xs text-muted-foreground">
                                  {m.sub_excerpt}
                                </TableCell>
                                <TableCell className="text-right tabular-nums">{m.matched_words}</TableCell>
                                <TableCell className="text-right">
                                  <Button type="button" size="sm" variant="ghost" onClick={() => setSelectedEvidence(m)}>
                                    Rincian
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))
                          )}
                        </TableBody>
                      </Table>
                    </div>
                    {totalMatchPages > 1 && (
                      <div className="flex items-center justify-between border-t border-border px-4 py-3 text-xs text-muted-foreground">
                        <span>
                          Halaman {matchesPage} dari {totalMatchPages}
                        </span>
                        <div className="flex items-center gap-1">
                          <Button
                            type="button"
                            size="icon"
                            variant="outline"
                            className="size-8"
                            disabled={matchesPage <= 1}
                            onClick={() => setMatchesPage((p) => p - 1)}
                          >
                            <ChevronLeft className="size-4" />
                          </Button>
                          <Button
                            type="button"
                            size="icon"
                            variant="outline"
                            className="size-8"
                            disabled={matchesPage >= totalMatchPages}
                            onClick={() => setMatchesPage((p) => p + 1)}
                          >
                            <ChevronRight className="size-4" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* ================== FULL COLORED SOURCES TAB ================== */}
              <TabsContent value="sources" className="mt-4 flex flex-col gap-4">
                <Card className="shadow-none">
                  <CardHeader>
                    <CardTitle className="text-base">Daftar Lengkap Sumber yang Cocok</CardTitle>
                    <CardDescription>
                      Kontribusi dihitung secara eksklusif agar satu kalimat tidak pernah dihitung ganda.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-12">#</TableHead>
                            <TableHead>Judul Sumber &amp; Referensi</TableHead>
                            <TableHead>Kategori</TableHead>
                            <TableHead className="text-right">Kata Cocok</TableHead>
                            <TableHead className="text-right">Kontribusi</TableHead>
                            <TableHead className="text-right">Akses</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {report.sources.length === 0 ? (
                            <TableRow>
                              <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">
                                Tidak ada sumber yang cocok.
                              </TableCell>
                            </TableRow>
                          ) : (
                            report.sources.map((src: ReportSource) => (
                              <TableRow key={src.source_document_id}>
                                <TableCell>
                                  <span
                                    className="source-rank-pill"
                                    style={{ backgroundColor: pillColor(src.rank, src.color_hex) }}
                                  >
                                    {src.rank}
                                  </span>
                                </TableCell>
                                <TableCell className="max-w-[360px]">
                                  <button
                                    type="button"
                                    onClick={() => handleJumpToSource(src)}
                                    className="text-left font-medium text-foreground hover:text-primary hover:underline"
                                  >
                                    {src.title}
                                  </button>
                                  <div className="text-xs text-muted-foreground">
                                    {src.authors?.join(", ") || "Penulis tidak tercantum"}
                                    {src.year ? ` (${src.year})` : ""}
                                    {src.doi ? ` · DOI: ${src.doi}` : ""}
                                  </div>
                                </TableCell>
                                <TableCell>
                                  <span
                                    className="inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium"
                                    style={{
                                      backgroundColor: src.chip_bg_hex || "var(--muted)",
                                      color: src.chip_text_hex || "var(--foreground)",
                                    }}
                                  >
                                    {src.category_label || src.source_type}
                                  </span>
                                </TableCell>
                                <TableCell className="text-right tabular-nums">{src.matched_words_exclusive}</TableCell>
                                <TableCell className="text-right font-serif font-bold tabular-nums">
                                  {formatContributionPct(src.contribution_pct)}
                                </TableCell>
                                <TableCell className="text-right">
                                  <div className="flex justify-end gap-1">
                                    {src.url && (
                                      <Button size="sm" variant="outline" asChild>
                                        <a href={src.url} target="_blank" rel="noreferrer">
                                          <ExternalLink className="size-3.5" data-icon="inline-start" />
                                          <span>Tautan</span>
                                        </a>
                                      </Button>
                                    )}
                                    {src.can_download_file && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() =>
                                          downloadProtectedFile(`/documents/${src.source_document_id}/file`, src.filename)
                                        }
                                      >
                                        <Download className="size-3.5" />
                                      </Button>
                                    )}
                                  </div>
                                </TableCell>
                              </TableRow>
                            ))
                          )}
                        </TableBody>
                      </Table>
                    </div>
                  </CardContent>
                </Card>

                {report.coverage?.metadata_only_items && report.coverage.metadata_only_items.length > 0 && (
                  <Card className="shadow-none">
                    <CardHeader>
                      <CardTitle className="text-base">Hanya Informasi Referensi (Belum Bisa Dibandingkan)</CardTitle>
                      <CardDescription>
                        Sumber berikut tidak menyediakan isi artikel terbuka sehingga tidak dapat dicocokkan kata per kata.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-2">
                      {report.coverage.metadata_only_items.slice(0, 10).map((item, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between gap-3 rounded-md border border-border p-3 text-xs"
                        >
                          <div className="min-w-0">
                            <p className="truncate font-medium text-foreground">{item.title}</p>
                            <p className="text-muted-foreground">
                              {item.provider} · {item.access_status}
                            </p>
                          </div>
                          {item.url && (
                            <Button size="sm" variant="ghost" asChild>
                              <a href={item.url} target="_blank" rel="noreferrer">
                                <ExternalLink className="size-3.5" />
                              </a>
                            </Button>
                          )}
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="coverage" className="mt-4 flex flex-col gap-4">
                <Card className="shadow-none">
                  <CardHeader>
                    <CardTitle className="text-base">Ringkasan Penelusuran Sumber</CardTitle>
                    <CardDescription>
                      {report.coverage?.search_coverage?.coverage_disclaimer ||
                        "Menampilkan jumlah kueri, tautan yang diperiksa, dan dokumen teks lengkap yang berhasil diunduh."}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <div className="rounded-md border border-border p-3">
                      <span className="text-xs text-muted-foreground">Kueri Pencarian</span>
                      <p className="mt-1 font-serif text-xl font-bold tabular-nums">
                        {report.coverage?.search_coverage?.total_search_queries ?? report.provider_queries.length}
                      </p>
                    </div>
                    <div className="rounded-md border border-border p-3">
                      <span className="text-xs text-muted-foreground">Tautan Unik Ditemukan</span>
                      <p className="mt-1 font-serif text-xl font-bold tabular-nums">
                        {report.coverage?.search_coverage?.total_unique_urls_found ?? 0}
                      </p>
                    </div>
                    <div className="rounded-md border border-border p-3">
                      <span className="text-xs text-muted-foreground">Dokumen Diunduh</span>
                      <p className="mt-1 font-serif text-xl font-bold tabular-nums">
                        {report.coverage?.search_coverage?.total_fulltext_fetched ?? 0}
                      </p>
                    </div>
                    <div className="rounded-md border border-border p-3">
                      <span className="text-xs text-muted-foreground">Tidak Dapat Diakses</span>
                      <p className="mt-1 font-serif text-xl font-bold tabular-nums">
                        {report.coverage?.search_coverage?.total_inaccessible_sources ?? 0}
                      </p>
                    </div>
                  </CardContent>
                </Card>

                {report.provider_queries.length > 0 && (
                  <Card className="shadow-none">
                    <CardHeader>
                      <CardTitle className="text-base">Log Kueri Sumber Eksternal</CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Penyedia</TableHead>
                            <TableHead>Kueri</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="text-right">Hasil</TableHead>
                            <TableHead className="text-right">Waktu</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {report.provider_queries.map((q, i) => (
                            <TableRow key={i}>
                              <TableCell className="font-medium">{q.provider}</TableCell>
                              <TableCell className="max-w-[340px] truncate text-xs text-muted-foreground">{q.query}</TableCell>
                              <TableCell>
                                <Badge variant="secondary">{q.status}</Badge>
                              </TableCell>
                              <TableCell className="text-right tabular-nums">{q.result_count}</TableCell>
                              <TableCell className="text-right tabular-nums text-xs">{formatMs(q.duration_ms)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="analytics" className="mt-4 flex flex-col gap-6">
                {report.analytics?.by_chapter?.length > 0 && (
                  <Card className="shadow-none">
                    <CardHeader>
                      <CardTitle className="text-base">Sebaran Kemiripan per Bagian Dokumen</CardTitle>
                    </CardHeader>
                    <CardContent className="h-[260px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={report.analytics.by_chapter} margin={{ top: 24, right: 16, left: -12, bottom: 4 }}>
                          <XAxis
                            dataKey="chapter"
                            tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                            tickLine={false}
                            axisLine={{ stroke: "var(--chart-axis)", strokeWidth: 0.75 }}
                            dy={6}
                          />
                          <YAxis
                            domain={[0, 112]}
                            ticks={[0, 25, 50, 75, 100]}
                            tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(v) => `${v}%`}
                          />
                          <RechartsTooltip content={<ChartTooltip />} cursor={{ fill: "var(--primary-soft)" }} />
                          <Bar dataKey="similarity_pct" name="Kemiripan (%)" radius={[3, 3, 0, 0]} maxBarSize={36}>
                            {report.analytics.by_chapter.map((ch, idx) => (
                              <Cell
                                key={`ch-${idx}`}
                                fill={ch.similarity_pct >= 30 ? "var(--chart-primary)" : "var(--chart-muted)"}
                              />
                            ))}
                            <LabelList
                              dataKey="similarity_pct"
                              position="top"
                              fill="var(--text-secondary)"
                              fontSize={11}
                              style={{ fontFamily: "var(--font-serif)" }}
                              formatter={(v: number) => `${v.toFixed(0)}%`}
                            />
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}

                <Card className="shadow-none">
                  <CardHeader>
                    <CardTitle className="text-base">Alur Pemeriksaan 12 Tahap</CardTitle>
                    <CardDescription>Data jumlah kata dan sumber aktual pada setiap langkah pemrosesan.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ProcessFlowchart stageCounts={report.stage_counts || {}} />
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        )}

        {/* ================== SECTION B: AI WRITING REPORT (STRICTLY ISOLATED) ================== */}
        {aiReport && (mode === "AI_ONLY" || sectionTab === "ai") && (
          <div className="flex flex-col gap-6">
            <Alert>
              <AlertTriangle className="size-4" />
              <AlertTitle>Catatan Interpretasi Wajib</AlertTitle>
              <AlertDescription>{aiReport.disclaimer}</AlertDescription>
            </Alert>

            <Card className="shadow-none">
              <CardContent className="flex flex-col gap-5 p-6 md:flex-row md:items-center md:justify-between">
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">Indikasi Pola Tulisan AI</span>
                    <InfoHint text="Estimasi statistik keseragaman kalimat, entropi kosakata, dan penanda gaya LLM. Bukan angka kemiripan plagiasi." />
                    <AiClassificationBadge
                      classification={aiReport.classification}
                      label={aiReport.classification_label}
                    />
                  </div>

                  {aiReport.score_available && aiReport.ai_likelihood_pct !== null ? (
                    <div className="flex items-baseline gap-3">
                      <span className="font-serif text-4xl font-bold tabular-nums text-foreground">
                        {aiReport.ai_likelihood_pct.toFixed(1)}%
                      </span>
                      {aiReport.uncertainty_pct !== null && (
                        <span className="text-xs text-muted-foreground tabular-nums">
                          Ketidakpastian ±{aiReport.uncertainty_pct.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="font-serif text-2xl font-bold text-muted-foreground">
                      Tidak Cukup Bukti ({aiReport.word_count} / {aiReport.min_words_required} kata minimum)
                    </span>
                  )}
                  <p className="max-w-2xl text-sm text-muted-foreground">{aiReport.summary_id}</p>
                </div>

                <div className="grid grid-cols-2 gap-3 md:min-w-[320px]">
                  <div className="rounded-md border border-border p-3">
                    <span className="text-xs text-muted-foreground">Tingkat Keyakinan</span>
                    <p className="mt-1 text-sm font-semibold text-foreground">{aiReport.confidence_label}</p>
                    {aiReport.calibration?.calibrated && (
                      <p className="mt-0.5 text-[11px] text-muted-foreground tabular-nums">
                        Terkalibrasi (T={aiReport.calibration.temperature})
                      </p>
                    )}
                  </div>
                  <div className="rounded-md border border-border p-3">
                    <span className="text-xs text-muted-foreground">Bahasa Terdeteksi</span>
                    <p className="mt-1 text-sm font-semibold text-foreground">{aiReport.language.label}</p>
                  </div>
                  <div className="rounded-md border border-border p-3 col-span-2">
                    <span className="text-xs text-muted-foreground">Dokumen &amp; Model Aktif</span>
                    <p className="mt-0.5 truncate text-xs font-medium text-foreground">
                      {report.document.title || report.document.filename} · {aiReport.model_used}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Clear Paragraph Classification Summary Tiles */}
            {(() => {
              const ps = aiReport.paragraph_summary || {
                total_paragraphs: aiReport.paragraphs.length,
                ai_likely_count: aiReport.paragraphs.filter((p) => p.classification === "AI_LIKELY").length,
                human_likely_count: aiReport.paragraphs.filter((p) => p.classification === "HUMAN_LIKELY").length,
                uncertain_count: aiReport.paragraphs.filter((p) => p.classification === "MIXED_UNCERTAIN").length,
                insufficient_count: aiReport.paragraphs.filter((p) => p.classification === "INSUFFICIENT_DATA").length,
              };
              return (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Card className="shadow-none">
                    <CardContent className="p-4">
                      <span className="text-xs text-muted-foreground">Jumlah Paragraf</span>
                      <p className="mt-1 font-serif text-2xl font-bold tabular-nums text-foreground">
                        {ps.total_paragraphs}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="shadow-none">
                    <CardContent className="p-4">
                      <span className="text-xs text-muted-foreground">Paragraf Indikasi AI</span>
                      <p className="mt-1 font-serif text-2xl font-bold tabular-nums text-primary">
                        {ps.ai_likely_count}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="shadow-none">
                    <CardContent className="p-4">
                      <span className="text-xs text-muted-foreground">Paragraf Indikasi Manusia</span>
                      <p className="mt-1 font-serif text-2xl font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
                        {ps.human_likely_count}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="shadow-none">
                    <CardContent className="p-4">
                      <span className="text-xs text-muted-foreground">Tidak Pasti / Singkat</span>
                      <p className="mt-1 font-serif text-2xl font-bold tabular-nums text-amber-700 dark:text-amber-400">
                        {ps.uncertain_count + ps.insufficient_count}
                      </p>
                    </CardContent>
                  </Card>
                </div>
              );
            })()}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <Card className="shadow-none lg:col-span-2">
                <CardHeader>
                  <CardTitle className="text-base">Analisis per Paragraf</CardTitle>
                  <CardDescription>
                    Paragraf ditandai bila pola gaya bahasanya menyerupai keluaran model bahasa. Klik paragraf untuk membaca penjelasannya.
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  {aiReport.paragraphs.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Tidak ada paragraf yang cukup panjang untuk dianalisis.</p>
                  ) : (
                    aiReport.paragraphs.map((p) => {
                      const active = selectedAiParaIdx === p.paragraph_index;
                      return (
                        <div
                          key={p.paragraph_index}
                          onClick={() => setSelectedAiParaIdx(active ? null : p.paragraph_index)}
                          className={`rounded-lg border p-4 transition-colors cursor-pointer ${
                            active
                              ? "border-primary bg-primary/5"
                              : p.classification === "AI_LIKELY"
                              ? "border-destructive/40 bg-destructive/5"
                              : p.classification === "MIXED_UNCERTAIN"
                              ? "border-amber-500/40 bg-amber-500/5"
                              : p.classification === "HUMAN_LIKELY"
                              ? "border-emerald-600/30 bg-emerald-500/5"
                              : "border-border bg-card hover:bg-accent/40"
                          }`}
                        >
                          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2 text-xs">
                              <span className="font-semibold text-foreground">Paragraf {p.paragraph_index + 1}</span>
                              <span className="text-muted-foreground tabular-nums">({p.word_count} kata)</span>
                              <AiClassificationBadge
                                classification={p.classification}
                                label={p.classification_label}
                              />
                            </div>
                            {p.ai_likelihood_pct !== null && (
                              <span className="text-xs font-bold tabular-nums text-foreground">
                                {p.ai_likelihood_pct.toFixed(1)}%
                              </span>
                            )}
                          </div>
                          <p className="font-serif text-[14.5px] leading-relaxed text-foreground">{p.text}</p>
                          {p.reasons.length > 0 && (
                            <div className="mt-2.5 flex flex-col gap-1 border-t border-border/60 pt-2 text-xs text-muted-foreground">
                              {p.reasons.map((r, i) => (
                                <span key={i}>• {r}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </CardContent>
              </Card>

              <div className="flex flex-col gap-4">
                <Card className="shadow-none">
                  <CardHeader>
                    <CardTitle className="text-base">Sinyal Utama Penilaian</CardTitle>
                    <CardDescription>Faktor kebahasaan paling berpengaruh pada dokumen ini.</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    {aiReport.signals.length === 0 ? (
                      <p className="text-xs text-muted-foreground">Tidak cukup kata untuk mengekstrak sinyal stabil.</p>
                    ) : (
                      aiReport.signals.map((sig) => (
                        <div key={sig.key} className="rounded-md border border-border p-3 flex flex-col gap-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold text-foreground">{sig.title}</span>
                            <Badge variant={sig.direction === "ai" ? "destructive" : "secondary"} className="text-[10px]">
                              {sig.direction === "ai" ? "Arah AI" : sig.direction === "human" ? "Arah Manusia" : "Netral"}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground leading-relaxed">{sig.detail}</p>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>

                <Card className="shadow-none">
                  <CardHeader>
                    <CardTitle className="text-base">Keterbatasan Analisis</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="list-disc pl-4 flex flex-col gap-1.5 text-xs text-muted-foreground leading-relaxed">
                      {aiReport.limitations.map((lim, i) => (
                        <li key={i}>{lim}</li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        )}

        {/* Evidence Detail Modal */}
        <Dialog open={Boolean(selectedEvidence)} onOpenChange={(open) => !open && setSelectedEvidence(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {selectedEvidence?.source_rank ? (
                  <span
                    className="source-rank-pill"
                    style={{ backgroundColor: pillColor(selectedEvidence.source_rank, selectedEvidence.source_color) }}
                  >
                    {selectedEvidence.source_rank}
                  </span>
                ) : null}
                <span>Rincian Kecocokan Teks</span>
              </DialogTitle>
              <DialogDescription>
                {selectedEvidence?.source_title} ({selectedEvidence ? LAYER_LABELS[selectedEvidence.layer] : ""})
              </DialogDescription>
            </DialogHeader>
            {selectedEvidence && (
              <div className="flex flex-col gap-4 text-sm">
                <div className="rounded-md border border-border bg-muted/40 p-3">
                  <p className="mb-1 text-xs font-semibold text-muted-foreground">Teks pada Naskah Anda:</p>
                  <p className="font-serif leading-relaxed text-foreground">{selectedEvidence.sub_excerpt}</p>
                </div>
                <div className="rounded-md border border-border bg-muted/40 p-3">
                  <p className="mb-1 text-xs font-semibold text-muted-foreground">Teks pada Sumber Pembanding:</p>
                  <p className="font-serif leading-relaxed text-foreground">{selectedEvidence.src_excerpt}</p>
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Kata cocok: {selectedEvidence.matched_words}</span>
                  <span>
                    {selectedEvidence.counted
                      ? "Dihitung ke dalam Indeks Kemiripan"
                      : `Tidak dihitung: ${selectedEvidence.excluded_reason || "tumpang tindih"}`}
                  </span>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </BlurFade>
  );
};
