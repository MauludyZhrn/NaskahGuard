import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  Bot,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  FileSearch2,
  FileText,
  GitBranch,
  Globe,
  Layers,
  ShieldCheck,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";
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
import { NumberTicker } from "@/components/ui/number-ticker";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiFetch, downloadProtectedFile } from "../api/client";
import { InfoHint } from "../components/InfoHint";
import { PageHeader } from "../components/PageHeader";
import { ProcessFlowchart } from "../components/ProcessFlowchart";
import { SimilarityGauge } from "../components/SimilarityGauge";
import { AiClassificationBadge, ModeBadge, similarityToneClass } from "../components/StatusBadge";
import { FullReport, ReportMatch, ReportSource, SourceViewerPayload, ViewerPayload } from "../types";
import { formatDuration, formatMs } from "../utils/format";

const MATCHES_PAGE_SIZE = 15;

const LAYER_LABELS: Record<string, string> = {
  EXACT: "Identik",
  NEAR_EXACT: "Mirip Dekat",
  LEXICAL: "Frasa Terdeteksi",
  SEMANTIC: "Kandidat Kemiripan Makna",
  EXCLUDED: "Dikecualikan",
};

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

  const filteredMatches = useMemo(() => {
    if (!report) return [];
    return report.matches.filter((m) =>
      selectedLayerFilter === "ALL" ? true : m.layer === selectedLayerFilter
    );
  }, [report, selectedLayerFilter]);

  const totalMatchPages = Math.max(1, Math.ceil(filteredMatches.length / MATCHES_PAGE_SIZE));
  const pagedMatches = useMemo(() => {
    const start = (matchesPage - 1) * MATCHES_PAGE_SIZE;
    return filteredMatches.slice(start, start + MATCHES_PAGE_SIZE);
  }, [filteredMatches, matchesPage]);

  const handleSelectSegment = async (matchIds: number[]) => {
    if (!matchIds.length || !report || !checkId) return;
    const mid = matchIds[0];
    setActiveMatchId(mid);
    const matchObj = report.matches.find((m) => m.id === mid);
    if (matchObj && sourceViewer?.source_document_id !== matchObj.source_document_id) {
      try {
        const sv = await apiFetch<SourceViewerPayload>(
          `/checks/${checkId}/sources/${matchObj.source_document_id}/viewer`
        );
        setSourceViewer(sv);
      } catch {
        // Ignore preview error cleanly
      }
    }
  };

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
        <Skeleton className="h-24 w-full" />
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

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <PageHeader
          title={report.document.title || report.document.filename}
          description={`Nomor Laporan ${report.report_number} · ${report.document.word_count.toLocaleString("id-ID")} kata total · Waktu proses ${formatDuration(report.duration_seconds)}`}
          badge={<ModeBadge mode={mode} />}
          actions={
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.pdf`, `${report.report_number}.pdf`)}
              >
                <Download className="size-4" data-icon="inline-start" aria-hidden="true" />
                <span>PDF</span>
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.html`, `${report.report_number}.html`)}
              >
                <Download className="size-4" data-icon="inline-start" aria-hidden="true" />
                <span>HTML</span>
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => downloadProtectedFile(`/checks/${report.check_id}/export.json`, `${report.report_number}.json`)}
              >
                <Download className="size-4" data-icon="inline-start" aria-hidden="true" />
                <span>JSON</span>
              </Button>
            </>
          }
        />

        {/* 5 Plain-Language Questions Summary Card */}
        {report.plain_summary && (
          <Card className="shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Ringkasan Hasil dalam Bahasa Sederhana</CardTitle>
              <CardDescription>
                Jawaban singkat terhadap lima hal utama yang perlu diketahui penulis maupun penelaah naskah.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {[
                { q: "1. Bagaimana tingkat kemiripan dokumen ini?", a: report.plain_summary.similarity_answer },
                { q: "2. Apakah ditemukan bagian mirip sumber?", a: report.plain_summary.sources_answer },
                { q: "3. Apakah terindikasi tulisan AI?", a: report.plain_summary.ai_answer },
                { q: "4. Bagian mana yang perlu diperiksa ulang?", a: report.plain_summary.review_answer },
                { q: "5. Sejauh mana sumber telah diperiksa?", a: report.plain_summary.coverage_answer },
              ].map((item) => (
                <div key={item.q} className="rounded-md border border-border bg-muted/30 p-3 flex flex-col gap-1">
                  <span className="text-xs font-semibold text-foreground">{item.q}</span>
                  <p className="text-xs leading-relaxed text-muted-foreground">{item.a}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Strict Top-Level Separation Between Plagiarism Report and AI Report in COMBINED Mode */}
        {isCombined && hasAiReport && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Layers className="size-4 text-primary" aria-hidden="true" />
              <span>
                Mode Gabungan memisahkan <strong className="text-foreground">Laporan Plagiasi</strong> dan{" "}
                <strong className="text-foreground">Laporan Deteksi AI</strong> secara ketat tanpa menggabungkan angkanya.
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
                <span>Laporan Plagiasi ({simVal.toFixed(1)}%)</span>
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
            {/* Hero Score Card */}
            <Card className="shadow-none">
              <CardContent className="flex flex-col gap-5 p-6 md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-5">
                  <SimilarityGauge
                    value={simVal}
                    level={metrics.operational_category?.level || "-"}
                    thresholdLow={thresholdLow}
                    thresholdHigh={thresholdHigh}
                  />
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-semibold text-foreground">Indeks Kemiripan</span>
                      <InfoHint text="Persentase kata yang cocok pada naskah bersih setelah pengecualian dan pencegahan penghitungan ganda." />
                    </div>
                    <p className={`text-2xl font-bold tabular-nums ${similarityToneClass(simVal)}`}>
                      {simVal.toFixed(1)}%
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Kategori operasional: <strong>{metrics.operational_category?.level || "-"}</strong>
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:min-w-[420px]">
                  <div className="rounded-md border border-border p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">Kata yang Cocok</span>
                      <InfoHint text="Jumlah kata unik pada naskah yang cocok dengan sumber pembanding." />
                    </div>
                    <p className="mt-1 text-lg font-bold tabular-nums">
                      <NumberTicker value={metrics.matched_words ?? 0} />
                    </p>
                  </div>
                  <div className="rounded-md border border-border p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">Kata Diperiksa</span>
                      <InfoHint text="Jumlah kata inti di luar daftar pustaka atau bagian yang dikecualikan." />
                    </div>
                    <p className="mt-1 text-lg font-bold tabular-nums">
                      <NumberTicker value={metrics.eligible_words ?? 0} />
                    </p>
                  </div>
                  <div className="rounded-md border border-border p-3 col-span-2 sm:col-span-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">Sumber Dibandingkan</span>
                      <InfoHint text="Dokumen sumber berteks lengkap yang dibandingkan terhadap naskah." />
                    </div>
                    <p className="mt-1 text-lg font-bold tabular-nums">
                      <NumberTicker value={fulltextCompared} />
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Plagiarism Sub-Tabs */}
            <Tabs value={plagInnerTab} onValueChange={setPlagInnerTab} className="w-full">
              <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1 bg-muted p-1">
                <TabsTrigger value="summary">Ringkasan</TabsTrigger>
                <TabsTrigger value="compare">Bandingkan Teks ({report.matches.length})</TabsTrigger>
                <TabsTrigger value="sources">Sumber Cocok ({report.sources.length})</TabsTrigger>
                <TabsTrigger value="coverage">Cakupan Pemeriksaan</TabsTrigger>
                <TabsTrigger value="analytics">Analitik &amp; Alur</TabsTrigger>
              </TabsList>

              <TabsContent value="summary" className="mt-4 flex flex-col gap-4">
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
                        <span>Dokumen Sumber yang Dibandingkan (Teks Lengkap)</span>
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
                        {report.coverage?.statement || "Sistem hanya menghitung kecocokan dari sumber berteks lengkap yang berhasil diakses."}
                      </p>
                    </CardContent>
                  </Card>
                </div>

                {/* Progressive Disclosure Accordion for Technical Details */}
                <Accordion type="multiple" className="rounded-xl border border-border bg-card px-5">
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
                          Durasi eksekusi: {Object.entries(metrics.stage_timings_ms).map(([k, v]) => `${k}: ${formatMs(v)}`).join(" · ")}
                        </p>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </TabsContent>

              <TabsContent value="compare" className="mt-4 flex flex-col gap-4">
                {viewer ? (
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <Card className="shadow-none">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Naskah yang Diperiksa</CardTitle>
                        <CardDescription>Klik bagian berwarna untuk melihat padanannya di sumber pembanding.</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="viewer-pane">
                          {viewer.segments.map((seg, idx) =>
                            seg.category === "PLAIN" ? (
                              <span key={idx}>{seg.text}</span>
                            ) : (
                              <span
                                key={idx}
                                onClick={() => handleSelectSegment(seg.match_ids)}
                                className={`hl-seg hl-${seg.category} ${
                                  activeMatchId && seg.match_ids.includes(activeMatchId) ? "hl-active" : ""
                                }`}
                                title={LAYER_LABELS[seg.category] || seg.category}
                              >
                                {seg.text}
                              </span>
                            )
                          )}
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
                              if (!sid || !checkId) return;
                              try {
                                const sv = await apiFetch<SourceViewerPayload>(`/checks/${checkId}/sources/${sid}/viewer`);
                                setSourceViewer(sv);
                              } catch {
                                // ignore
                              }
                            }}
                          >
                            {report.sources.map((s) => (
                              <option key={s.source_document_id} value={s.source_document_id}>
                                #{s.rank} — {s.title} ({s.contribution_pct.toFixed(1)}%)
                              </option>
                            ))}
                          </select>
                        )}
                      </CardHeader>
                      <CardContent>
                        {sourceViewer ? (
                          <div className="viewer-pane">
                            {sourceViewer.text}
                          </div>
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
                      <CardDescription>Klik tombol detail pada baris mana pun untuk memeriksa perbandingan lengkap.</CardDescription>
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
                            <TableHead>Jenis</TableHead>
                            <TableHead>Sumber</TableHead>
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
                                <TableCell>
                                  <Badge variant="outline">{LAYER_LABELS[m.layer] || m.layer}</Badge>
                                </TableCell>
                                <TableCell className="max-w-[200px] truncate font-medium">{m.source_title}</TableCell>
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

              <TabsContent value="sources" className="mt-4 flex flex-col gap-4">
                <Card className="shadow-none">
                  <CardHeader>
                    <CardTitle className="text-base">Daftar Sumber yang Cocok</CardTitle>
                    <CardDescription>
                      Kontribusi dihitung secara eksklusif agar satu kalimat tidak pernah dihitung ganda.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>#</TableHead>
                            <TableHead>Judul Sumber &amp; Referensi</TableHead>
                            <TableHead>Tipe</TableHead>
                            <TableHead className="text-right">Kata Cocok</TableHead>
                            <TableHead className="text-right">Kontribusi Sumber</TableHead>
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
                                <TableCell className="tabular-nums">{src.rank}</TableCell>
                                <TableCell className="max-w-[340px]">
                                  <div className="font-medium text-foreground">{src.title}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {src.authors?.join(", ") || "Penulis tidak tercantum"}
                                    {src.year ? ` (${src.year})` : ""}
                                    {src.doi ? ` · DOI: ${src.doi}` : ""}
                                  </div>
                                </TableCell>
                                <TableCell>
                                  <Badge variant="secondary">{src.source_type}</Badge>
                                </TableCell>
                                <TableCell className="text-right tabular-nums">{src.matched_words_exclusive}</TableCell>
                                <TableCell className="text-right font-semibold tabular-nums">
                                  {src.contribution_pct.toFixed(1)}%
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
                                        onClick={() => downloadProtectedFile(`/documents/${src.source_document_id}/file`, src.filename)}
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
                        <div key={idx} className="flex items-center justify-between gap-3 rounded-md border border-border p-3 text-xs">
                          <div className="min-w-0">
                            <p className="truncate font-medium text-foreground">{item.title}</p>
                            <p className="text-muted-foreground">{item.provider} · {item.access_status}</p>
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
                      <p className="mt-1 text-xl font-bold tabular-nums">
                        {report.coverage?.search_coverage?.total_search_queries ?? report.provider_queries.length}
                      </p>
                    </div>
                    <div className="rounded-md border border-border p-3">
                      <span className="text-xs text-muted-foreground">Tautan Unik Ditemukan</span>
                      <p className="mt-1 text-xl font-bold tabular-nums">
                        {report.coverage?.search_coverage?.total_unique_urls_found ?? 0}
                      </p>
                    </div>
                    <div className="rounded-md border border-border p-3">
                      <span className="text-xs text-muted-foreground">Dokumen Diunduh</span>
                      <p className="mt-1 text-xl font-bold tabular-nums">
                        {report.coverage?.search_coverage?.total_fulltext_fetched ?? 0}
                      </p>
                    </div>
                    <div className="rounded-md border border-border p-3">
                      <span className="text-xs text-muted-foreground">Tidak Dapat Diakses</span>
                      <p className="mt-1 text-xl font-bold tabular-nums">
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
                              <TableCell><Badge variant="secondary">{q.status}</Badge></TableCell>
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
                    <CardContent className="h-[240px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={report.analytics.by_chapter} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
                          <XAxis dataKey="chapter" tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                          <RechartsTooltip content={<ChartTooltip />} />
                          <Bar dataKey="similarity_pct" name="Kemiripan (%)" fill="var(--color-primary)" radius={[4, 4, 0, 0]} maxBarSize={36} />
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

                <div className="grid grid-cols-2 gap-3 md:min-w-[300px]">
                  <div className="rounded-md border border-border p-3">
                    <span className="text-xs text-muted-foreground">Tingkat Keyakinan</span>
                    <p className="mt-1 text-sm font-semibold text-foreground">{aiReport.confidence_label}</p>
                  </div>
                  <div className="rounded-md border border-border p-3">
                    <span className="text-xs text-muted-foreground">Bahasa Terdeteksi</span>
                    <p className="mt-1 text-sm font-semibold text-foreground">{aiReport.language.label}</p>
                  </div>
                  <div className="rounded-md border border-border p-3 col-span-2">
                    <span className="text-xs text-muted-foreground">Model Analisis Aktif</span>
                    <p className="mt-0.5 text-xs font-medium text-foreground">{aiReport.model_used}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Signals & Paragraph Highlights */}
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
                              ? "border-destructive/35 bg-destructive/5"
                              : p.classification === "MIXED_UNCERTAIN"
                              ? "border-[color:var(--lexical-border)]/50 bg-[var(--lexical-bg)]/40"
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
              <DialogTitle>Rincian Kecocokan Teks</DialogTitle>
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
