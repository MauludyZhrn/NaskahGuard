import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  BookMarked,
  Bot,
  Database,
  Download,
  FilePlus2,
  FileSearch2,
  FileText,
  Layers,
  Settings,
  ShieldCheck,
  Trash2,
  Upload,
} from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { BlurFade } from "@/components/ui/blur-fade";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NumberTicker } from "@/components/ui/number-ticker";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "../api/client";
import { InfoHint } from "../components/InfoHint";
import { PageHeader } from "../components/PageHeader";
import { AiClassificationBadge, ModeBadge, similarityToneClass } from "../components/StatusBadge";
import { DashboardData } from "../types";

const ACTION_LABELS: Record<string, string> = {
  UPLOAD_DOCUMENT: "Mengunggah naskah baru",
  UPLOAD_SUBMISSION: "Mengunggah naskah baru",
  UPLOAD_CORPUS: "Menambah dokumen ke korpus",
  START_CHECK: "Memulai pemeriksaan dokumen",
  DELETE_DOCUMENT: "Menghapus dokumen dari pustaka",
  UPDATE_SETTINGS: "Memperbarui pengaturan sistem",
  ADD_OAI_REPO: "Mendaftarkan repositori akademik",
  REGISTER_OAI: "Mendaftarkan repositori akademik",
  HARVEST_OAI_REPO: "Mengambil indeks repositori OAI-PMH",
  HARVEST_OAI: "Mengambil indeks repositori OAI-PMH",
  DELETE_OAI_REPO: "Menghapus repositori akademik",
  EXPORT_PDF: "Mengunduh laporan PDF",
  EXPORT_HTML: "Mengunduh laporan HTML",
  EXPORT_JSON: "Mengunduh data laporan JSON",
  PROBE_PROVIDERS: "Memeriksa koneksi penyedia sumber",
};

function ActivityIcon({ action }: { action: string }) {
  if (action.includes("CORPUS")) return <Database className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />;
  if (action.includes("UPLOAD")) return <Upload className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />;
  if (action.includes("EXPORT")) return <Download className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />;
  if (action.includes("DELETE")) return <Trash2 className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />;
  if (action.includes("OAI")) return <BookMarked className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />;
  if (action.includes("SETTINGS")) return <Settings className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />;
  if (action.includes("CHECK")) return <Activity className="size-4 shrink-0 text-primary" aria-hidden="true" />;
  return <ShieldCheck className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />;
}

/** Minimal Tufte editorial tooltip (Rule 10 & 14: serif data typography, calm surface, no heavy shadow). */
const TufteTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-md border border-border bg-card/95 px-3 py-2 text-xs text-card-foreground"
      style={{ fontFamily: "var(--font-serif)" }}
    >
      <div className="mb-1 text-[11px] font-sans text-muted-foreground">{label}</div>
      {payload.map((item: any) => (
        <div key={item.dataKey} className="flex items-center justify-between gap-4 tabular-nums">
          <span className="text-muted-foreground">{item.name}</span>
          <strong className="text-foreground">{Number(item.value ?? 0).toFixed(1)}%</strong>
        </div>
      ))}
    </div>
  );
};

export const DashboardPage: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DashboardData>("/dashboard")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Gagal memuat ringkasan dasbor</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-20 w-full" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  const trendData = data.trend.map((t) => ({
    name: t.report_number.replace(/^NG-\d{6}/, "#"),
    fullName: t.report_number,
    kemiripan: Number(t.similarity_index ?? 0),
    ai: t.ai_likelihood_pct !== null && t.ai_likelihood_pct !== undefined ? Number(t.ai_likelihood_pct) : null,
  }));
  const hasAiInTrend = trendData.some((d) => d.ai !== null && d.ai > 0);

  return (
    <BlurFade duration={0.18}>
      <div className="flex flex-col gap-6">
        <PageHeader
          eyebrow="Ikhtisar Akademik"
          title="Ringkasan Pemeriksaan"
          description="Pantau tingkat kemiripan naskah, indikasi pola tulisan AI, serta kesiapan korpus lokal secara ringkas dan transparan."
          actions={
            <>
              <Button variant="outline" asChild>
                <Link to="/models">
                  <Bot data-icon="inline-start" aria-hidden="true" />
                  <span>Manajemen Model</span>
                </Link>
              </Button>
              <Button className="rounded-full px-5" asChild>
                <Link to="/new-check">
                  <FilePlus2 data-icon="inline-start" aria-hidden="true" />
                  <span>Mulai Pemeriksaan</span>
                </Link>
              </Button>
            </>
          }
        />

      {/* Maximum 4 clean summary KPI cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Ringkasan metrik utama">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardDescription>Total Naskah Selesai</CardDescription>
                <InfoHint text="Jumlah pemeriksaan plagiasi, deteksi AI, maupun gabungan yang telah selesai diproses." />
              </div>
              <CardTitle className="font-serif text-3xl font-semibold tabular-nums">
                <NumberTicker value={data.total_documents_checked} />
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-xs text-muted-foreground">
                Dari {data.total_submissions} dokumen tersimpan di pustaka.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardDescription>Rata-rata Indeks Kemiripan</CardDescription>
                <InfoHint text="Rata-rata persentase kata yang cocok pada seluruh pemeriksaan plagiasi dan gabungan." />
              </div>
              <CardTitle className="font-serif text-3xl font-semibold tabular-nums text-[color:var(--color-primary-text)]">
                {data.average_similarity !== null ? `${data.average_similarity.toFixed(1)}%` : "-"}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-xs text-muted-foreground">
                Dihitung hanya dari sumber berteks lengkap.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardDescription>Rata-rata Indikasi AI</CardDescription>
                <InfoHint text="Rata-rata skor probabilistik pola penulisan AI pada pemeriksaan mode AI atau Gabungan." />
              </div>
              <CardTitle className="font-serif text-3xl font-semibold tabular-nums">
                {data.average_ai_likelihood !== null ? `${data.average_ai_likelihood.toFixed(1)}%` : "-"}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-xs text-muted-foreground">
                {data.ai_stats?.total_ai_analyzed ?? 0} dokumen telah dianalisis pola bahasanya.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardDescription>Korpus Pembanding Lokal</CardDescription>
                <InfoHint text="Dokumen referensi lokal serta repositori terbuka yang siap dicocokkan tanpa internet." />
              </div>
              <CardTitle className="font-serif text-3xl font-semibold tabular-nums">
                <NumberTicker value={data.corpus_stats.fulltext_sources_available} />
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-xs text-muted-foreground">
                {data.corpus_stats.total_words.toLocaleString("id-ID")} kata terindeks lokal.
              </p>
            </CardContent>
          </Card>
      </section>

      {/* Tufte Trend Chart & Editorial Mode Selector */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle className="font-serif text-lg font-semibold">Tren Pemeriksaan Terbaru</CardTitle>
                <CardDescription>
                  Garis putus-putus menandai rata-rata kemiripan ({data.average_similarity !== null ? `${data.average_similarity.toFixed(1)}%` : "-"}); batang burgundy menandai kemiripan &ge; 30%.
                </CardDescription>
              </div>
              <div className="flex items-center gap-4 text-xs text-muted-foreground shrink-0">
                <span className="inline-flex items-center gap-1.5">
                  <span className="size-2.5 rounded-sm bg-[var(--chart-primary)]" />
                  <span>Plagiasi (&ge;30% / Fokus)</span>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="size-2.5 rounded-sm bg-[var(--chart-muted)]" />
                  <span>{hasAiInTrend ? "Indikasi AI / Normal" : "Kemiripan < 30%"}</span>
                </span>
              </div>
            </CardHeader>
            <CardContent>
              {trendData.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-secondary/40 py-12 text-center">
                  <FileSearch2 className="size-8 text-muted-foreground" aria-hidden="true" />
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium text-foreground">Belum ada riwayat pemeriksaan</p>
                    <p className="text-xs text-muted-foreground">
                      Unggah naskah PDF, DOCX, atau TXT untuk melihat visualisasi tren di sini.
                    </p>
                  </div>
                  <Button size="sm" className="rounded-full" asChild>
                    <Link to="/new-check">Mulai Pemeriksaan Pertama</Link>
                  </Button>
                </div>
              ) : (
                <div
                  className="h-[260px] w-full"
                  role="img"
                  aria-label={`Grafik tren ${trendData.length} laporan terakhir dengan rata-rata kemiripan ${data.average_similarity ?? 0} persen`}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={trendData}
                      margin={{ top: 24, right: 16, left: -14, bottom: 4 }}
                      barGap={4}
                    >
                      <XAxis
                        dataKey="name"
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
                      <RechartsTooltip content={<TufteTooltip />} cursor={{ fill: "var(--primary-soft)" }} />
                      {data.average_similarity !== null && (
                        <ReferenceLine
                          y={data.average_similarity}
                          stroke="var(--chart-ref)"
                          strokeDasharray="3 3"
                          strokeWidth={1}
                        />
                      )}
                      <Bar dataKey="kemiripan" name="Indeks Kemiripan" radius={[3, 3, 0, 0]} maxBarSize={32}>
                        {trendData.map((entry, idx) => (
                          <Cell
                            key={`cell-${idx}`}
                            fill={entry.kemiripan >= 30 || !hasAiInTrend ? "var(--chart-primary)" : "var(--chart-muted)"}
                          />
                        ))}
                        <LabelList
                          dataKey="kemiripan"
                          position="top"
                          fill="var(--text-secondary)"
                          fontSize={11}
                          style={{ fontFamily: "var(--font-serif)" }}
                          formatter={(v: number) => (v > 0 ? `${v.toFixed(0)}%` : "")}
                        />
                      </Bar>
                      {hasAiInTrend && (
                        <Bar dataKey="ai" name="Indikasi AI" fill="var(--chart-secondary)" radius={[3, 3, 0, 0]} maxBarSize={26}>
                          <LabelList
                            dataKey="ai"
                            position="top"
                            fill="var(--text-secondary)"
                            fontSize={11}
                            style={{ fontFamily: "var(--font-serif)" }}
                            formatter={(v: number | null) => (v !== null && v > 0 ? `${v.toFixed(0)}%` : "")}
                          />
                        </Bar>
                      )}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-serif text-lg font-semibold">Pilih Alur Pemeriksaan</CardTitle>
              <CardDescription>
                Tiga mode terpisah yang menjaga skor plagiasi dan pola AI tetap independen.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Link
                to="/new-check?mode=PLAGIARISM_ONLY"
                className="flex items-start gap-3 rounded-lg border border-border bg-background/60 p-3.5 transition-colors hover:border-primary/40 hover:bg-accent/60"
              >
                <FileSearch2 className="mt-0.5 size-4 shrink-0 text-[color:var(--color-primary-text)]" aria-hidden="true" />
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="text-sm font-semibold text-foreground">Pemeriksaan Plagiasi</span>
                  <span className="text-xs text-muted-foreground">Bandingkan kata dan kalimat terhadap korpus &amp; sumber terbuka.</span>
                </div>
              </Link>
              <Link
                to="/new-check?mode=AI_ONLY"
                className="flex items-start gap-3 rounded-lg border border-border bg-background/60 p-3.5 transition-colors hover:border-primary/40 hover:bg-accent/60"
              >
                <Bot className="mt-0.5 size-4 shrink-0 text-[color:var(--color-primary-text)]" aria-hidden="true" />
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="text-sm font-semibold text-foreground">Deteksi Tulisan AI</span>
                  <span className="text-xs text-muted-foreground">Analisis ritme bahasa dan entropi paragraf secara lokal.</span>
                </div>
              </Link>
              <Link
                to="/new-check?mode=COMBINED"
                className="flex items-start gap-3 rounded-lg border border-primary/40 bg-primary/5 p-3.5 transition-colors hover:bg-primary/10"
              >
                <Layers className="mt-0.5 size-4 shrink-0 text-[color:var(--color-primary-text)]" aria-hidden="true" />
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="text-sm font-semibold text-foreground">Pemeriksaan Gabungan</span>
                  <span className="text-xs text-muted-foreground">Laporan plagiasi dan laporan AI dalam dua bagian terpisah.</span>
                </div>
              </Link>
            </CardContent>
          </Card>
        </section>

      {/* Bottom 2 balanced columns */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <div>
                <CardTitle className="font-serif text-lg font-semibold">Laporan Terbaru</CardTitle>
                <CardDescription>Klik laporan untuk membaca detail bagian teks.</CardDescription>
              </div>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/history">
                  <span>Semua</span>
                  <ArrowRight data-icon="inline-end" aria-hidden="true" />
                </Link>
              </Button>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {data.recent_reports.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">Belum ada laporan tersedia.</p>
              ) : (
                data.recent_reports.slice(0, 6).map((item) => (
                  <Link
                    key={item.check_id}
                    to={`/reports/${item.check_id}`}
                    className="flex items-center justify-between gap-3 rounded-lg border border-border/80 bg-background/40 px-3.5 py-2.5 transition-colors hover:border-primary/35 hover:bg-accent/50"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      <div className="flex flex-col min-w-0">
                        <span className="truncate text-sm font-medium text-foreground">{item.title || item.filename}</span>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span className="tabular-nums">{item.report_number}</span>
                          <ModeBadge mode={item.mode} />
                        </div>
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      {item.mode !== "AI_ONLY" && (
                        <span className={`font-serif text-base font-semibold tabular-nums ${similarityToneClass(item.similarity_index)}`}>
                          {item.similarity_index.toFixed(1)}%
                        </span>
                      )}
                      {item.ai_classification && (
                        <AiClassificationBadge
                          classification={item.ai_classification}
                          label={item.ai_likelihood_pct != null ? `AI ${item.ai_likelihood_pct.toFixed(0)}%` : "AI Kurang Data"}
                        />
                      )}
                    </div>
                  </Link>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-serif text-lg font-semibold">Aktivitas Sistem Terbaru</CardTitle>
              <CardDescription>Catatan transparan setiap unggahan, pemeriksaan, dan ekspor laporan.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {data.recent_activity.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">Belum ada aktivitas tercatat.</p>
              ) : (
                data.recent_activity.slice(0, 6).map((act) => (
                  <div
                    key={act.id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-border/80 bg-background/40 px-3.5 py-2.5"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <ActivityIcon action={act.action} />
                      <div className="flex flex-col min-w-0">
                        <span className="truncate text-sm font-medium text-foreground">
                          {ACTION_LABELS[act.action] || "Aktivitas sistem lokal"}
                        </span>
                        <span className="truncate text-xs text-muted-foreground tabular-nums">
                          {act.actor === "127.0.0.1" ? "Pengguna Lokal" : act.actor} ·{" "}
                          {act.ts ? new Date(act.ts).toLocaleString("id-ID") : "-"}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </BlurFade>
  );
};
