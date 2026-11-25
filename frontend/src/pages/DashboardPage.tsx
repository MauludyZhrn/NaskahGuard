import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Bot,
  Database,
  FilePlus2,
  FileSearch2,
  FileText,
  Layers,
  ShieldCheck,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
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
  UPLOAD_SUBMISSION: "Mengunggah naskah baru",
  UPLOAD_CORPUS: "Menambah dokumen ke korpus",
  START_CHECK: "Memulai pemeriksaan dokumen",
  DELETE_DOCUMENT: "Menghapus dokumen dari pustaka",
  UPDATE_SETTINGS: "Memperbarui pengaturan sistem",
  REGISTER_OAI: "Menambahkan repositori akademik OAI-PMH",
  HARVEST_OAI: "Mengambil koleksi repositori OAI-PMH",
  PROBE_PROVIDERS: "Memeriksa koneksi penyedia sumber",
};

const ChartTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs text-card-foreground shadow-sm">
      <div className="mb-1 font-semibold">{label}</div>
      {payload.map((item: any) => (
        <div key={item.dataKey} className="flex items-center justify-between gap-4 tabular-nums">
          <span className="text-muted-foreground">{item.name}:</span>
          <span className="font-semibold">{Number(item.value ?? 0).toFixed(1)}%</span>
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

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Ringkasan Pemeriksaan"
          description="Pantau riwayat kemiripan naskah, indikasi pola tulisan AI, serta kesiapan korpus pembanding dalam satu tampilan ringkas."
          actions={
            <>
              <Button variant="outline" asChild>
                <Link to="/models">
                  <Bot className="size-4" data-icon="inline-start" aria-hidden="true" />
                  <span>Manajemen Model</span>
                </Link>
              </Button>
              <Button asChild>
                <Link to="/new-check">
                  <FilePlus2 className="size-4" data-icon="inline-start" aria-hidden="true" />
                  <span>Mulai Pemeriksaan</span>
                </Link>
              </Button>
            </>
          }
        />

        {/* Maximum 4 clean summary KPI cards */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Ringkasan metrik utama">
          <Card className="shadow-none">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardDescription>Total Naskah Selesai</CardDescription>
                <InfoHint text="Jumlah pemeriksaan plagiasi, deteksi AI, maupun gabungan yang telah selesai diproses." />
              </div>
              <CardTitle className="font-serif text-3xl tabular-nums">
                <NumberTicker value={data.total_documents_checked} />
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-xs text-muted-foreground">
                Dari {data.total_submissions} dokumen tersimpan di pustaka.
              </p>
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardDescription>Rata-rata Indeks Kemiripan</CardDescription>
                <InfoHint text="Rata-rata persentase kata yang cocok pada seluruh pemeriksaan plagiasi dan gabungan." />
              </div>
              <CardTitle className="font-serif text-3xl tabular-nums">
                {data.average_similarity !== null ? `${data.average_similarity.toFixed(1)}%` : "-"}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-xs text-muted-foreground">
                Dihitung hanya dari sumber berteks lengkap.
              </p>
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardDescription>Rata-rata Indikasi AI</CardDescription>
                <InfoHint text="Rata-rata skor probabilistik pola penulisan AI pada pemeriksaan mode AI atau Gabungan." />
              </div>
              <CardTitle className="font-serif text-3xl tabular-nums">
                {data.average_ai_likelihood !== null ? `${data.average_ai_likelihood.toFixed(1)}%` : "-"}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-xs text-muted-foreground">
                {data.ai_stats?.total_ai_analyzed ?? 0} dokumen telah dianalisis pola bahasanya.
              </p>
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardDescription>Korpus Pembanding Lokal</CardDescription>
                <InfoHint text="Dokumen referensi lokal serta repositori terbuka yang siap dicocokkan tanpa internet." />
              </div>
              <CardTitle className="font-serif text-3xl tabular-nums">
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

        {/* Trend & Quick Actions */}
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="shadow-none lg:col-span-2">
            <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle className="text-base">Tren Pemeriksaan Terbaru</CardTitle>
                <CardDescription>
                  Perbandingan indeks kemiripan plagiasi dan indikasi AI per laporan selesai.
                </CardDescription>
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
                <span className="inline-flex items-center gap-1.5">
                  <span className="size-2.5 rounded-sm bg-[var(--color-primary)]" />
                  <span>Plagiasi</span>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="size-2.5 rounded-sm bg-[var(--near-border)]" />
                  <span>Indikasi AI</span>
                </span>
              </div>
            </CardHeader>
            <CardContent>
              {data.trend.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-3 rounded-md border border-dashed border-border py-12 text-center">
                  <FileSearch2 className="size-8 text-muted-foreground" aria-hidden="true" />
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium text-foreground">Belum ada riwayat pemeriksaan</p>
                    <p className="text-xs text-muted-foreground">
                      Unggah naskah PDF, DOCX, atau TXT untuk melihat tren hasil di sini.
                    </p>
                  </div>
                  <Button size="sm" asChild>
                    <Link to="/new-check">Mulai Pemeriksaan Pertama</Link>
                  </Button>
                </div>
              ) : (
                <div className="h-[240px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={data.trend.map((t) => ({
                        name: t.report_number,
                        kemiripan: t.similarity_index,
                        ai: t.ai_likelihood_pct ?? 0,
                      }))}
                      margin={{ top: 8, right: 12, left: -16, bottom: 0 }}
                    >
                      <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                      <RechartsTooltip content={<ChartTooltip />} />
                      <Bar dataKey="kemiripan" name="Indeks Kemiripan" fill="var(--color-primary)" radius={[4, 4, 0, 0]} maxBarSize={36} />
                      <Bar dataKey="ai" name="Indikasi AI" fill="var(--near-border)" radius={[4, 4, 0, 0]} maxBarSize={36} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-base">Pilih Alur Pemeriksaan</CardTitle>
              <CardDescription>
                Tiga mode terpisah yang tidak mencampurkan skor plagiasi dan pola AI.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Link
                to="/new-check?mode=PLAGIARISM_ONLY"
                className="flex items-start gap-3 rounded-md border border-border p-3 transition-colors hover:bg-accent"
              >
                <FileSearch2 className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="text-sm font-medium text-foreground">Pemeriksaan Plagiasi</span>
                  <span className="text-xs text-muted-foreground">Bandingkan kata dan kalimat terhadap korpus &amp; sumber terbuka.</span>
                </div>
              </Link>
              <Link
                to="/new-check?mode=AI_ONLY"
                className="flex items-start gap-3 rounded-md border border-border p-3 transition-colors hover:bg-accent"
              >
                <Bot className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="text-sm font-medium text-foreground">Deteksi Tulisan AI</span>
                  <span className="text-xs text-muted-foreground">Analisis ritme bahasa dan entropi paragraf secara lokal.</span>
                </div>
              </Link>
              <Link
                to="/new-check?mode=COMBINED"
                className="flex items-start gap-3 rounded-md border border-primary/35 bg-primary/5 p-3 transition-colors hover:bg-primary/10"
              >
                <Layers className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="text-sm font-medium text-foreground">Pemeriksaan Gabungan</span>
                  <span className="text-xs text-muted-foreground">Laporan plagiasi dan laporan AI dalam dua bagian terpisah.</span>
                </div>
              </Link>
            </CardContent>
          </Card>
        </section>

        {/* Bottom 2 balanced columns */}
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card className="shadow-none">
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <div>
                <CardTitle className="text-base">Laporan Terbaru</CardTitle>
                <CardDescription>Klik laporan untuk membaca detail bagian teks.</CardDescription>
              </div>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/history">
                  <span>Semua</span>
                  <ArrowRight className="size-3.5" data-icon="inline-end" aria-hidden="true" />
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
                    className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2.5 transition-colors hover:bg-accent"
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
                        <span className={`text-sm font-bold tabular-nums ${similarityToneClass(item.similarity_index)}`}>
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

          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-base">Aktivitas Sistem Terbaru</CardTitle>
              <CardDescription>Catatan transparan setiap unggahan dan pemeriksaan.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {data.recent_activity.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">Belum ada aktivitas tercatat.</p>
              ) : (
                data.recent_activity.slice(0, 6).map((act) => (
                  <div
                    key={act.id}
                    className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2.5"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {act.action.includes("CORPUS") ? (
                        <Database className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      ) : act.action.includes("CHECK") ? (
                        <Activity className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      ) : (
                        <ShieldCheck className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      )}
                      <div className="flex flex-col min-w-0">
                        <span className="truncate text-sm font-medium text-foreground">
                          {ACTION_LABELS[act.action] || act.action}
                        </span>
                        <span className="truncate text-xs text-muted-foreground">
                          Oleh {act.actor} · {act.ts ? new Date(act.ts).toLocaleString("id-ID") : "-"}
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
