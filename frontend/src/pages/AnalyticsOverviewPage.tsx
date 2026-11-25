import React, { useEffect, useState } from "react";
import { Activity, BarChart3 } from "lucide-react";
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NumberTicker } from "@/components/ui/number-ticker";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { DashboardData } from "../types";

interface AnalyticsProps {
  focusMode?: "plagiarism" | "ai";
}

const TufteTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-md border border-border bg-card/95 px-3 py-2 text-xs text-card-foreground"
      style={{ fontFamily: "var(--font-serif)" }}
    >
      <div className="mb-1 text-[11px] font-sans text-muted-foreground">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="tabular-nums">
          {p.name}: <strong>{Number(p.value ?? 0).toLocaleString("id-ID")}</strong>
        </div>
      ))}
    </div>
  );
};

export const AnalyticsOverviewPage: React.FC<AnalyticsProps> = ({ focusMode = "plagiarism" }) => {
  const [dash, setDash] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DashboardData>("/dashboard")
      .then(setDash)
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Gagal memuat analitik</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!dash) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const isAi = focusMode === "ai";
  const aiCounts = dash.ai_stats?.classification_counts || {};
  // Tufte horizontal bar chart: sorted descending by value with direct labels, hidden X-axis, zero gridlines
  const classChart = [
    { name: "Cenderung Manusia", jumlah: aiCounts.HUMAN_LIKELY ?? 0, highlight: false },
    { name: "Campuran / Ragu", jumlah: aiCounts.MIXED_UNCERTAIN ?? 0, highlight: false },
    { name: "Terindikasi Pola AI", jumlah: aiCounts.AI_LIKELY ?? 0, highlight: true },
    { name: "Tidak Cukup Bukti", jumlah: aiCounts.INSUFFICIENT_DATA ?? 0, highlight: false },
  ].sort((a, b) => b.jumlah - a.jumlah);

  return (
    <BlurFade duration={0.22}>
      <div className="flex flex-col gap-6">
        <PageHeader
          eyebrow={isAi ? "Analitik Probabilistik AI" : "Analitik Kemiripan"}
          title={isAi ? "Analitik Deteksi Tulisan AI" : "Analitik Pemeriksaan Plagiasi"}
          description={
            isAi
              ? "Sebaran klasifikasi pola penulisan AI secara lokal tanpa mencampurkan skor plagiasi."
              : "Ringkasan agregat indeks kemiripan dan cakupan korpus lokal dari seluruh pemeriksaan selesai."
          }
        />

        {isAi ? (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Dianalisis Pola AI</CardDescription>
                  <CardTitle className="font-serif text-3xl font-semibold tabular-nums">
                    <NumberTicker value={dash.ai_stats?.total_ai_analyzed ?? 0} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">
                  Gabungan mode Deteksi AI &amp; Laporan Gabungan.
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Rata-rata Indikasi Pola AI</CardDescription>
                  <CardTitle className="font-serif text-3xl font-semibold tabular-nums text-[color:var(--color-primary-text)]">
                    {dash.average_ai_likelihood !== null ? `${dash.average_ai_likelihood.toFixed(1)}%` : "-"}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">
                  Estimasi probabilistik berbasis stilometri &amp; entropi.
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Mode Gabungan Selesai</CardDescription>
                  <CardTitle className="font-serif text-3xl font-semibold tabular-nums">
                    <NumberTicker value={dash.ai_stats?.total_combined ?? 0} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">
                  Menghasilkan laporan plagiasi dan laporan AI terpisah.
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 font-serif text-lg font-semibold">
                  <Activity className="size-4 text-[color:var(--color-primary-text)]" aria-hidden="true" />
                  <span>Distribusi Klasifikasi Deteksi AI</span>
                </CardTitle>
                <CardDescription>Diurutkan berdasarkan jumlah dokumen dengan label nilai langsung.</CardDescription>
              </CardHeader>
              <CardContent className="h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={classChart} layout="vertical" margin={{ top: 8, right: 56, left: 16, bottom: 8 }}>
                    <XAxis type="number" hide />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={148}
                      tickLine={false}
                      axisLine={false}
                      tick={{ fontSize: 13, fill: "var(--text)", fontFamily: "var(--font-serif)" }}
                    />
                    <RechartsTooltip content={<TufteTooltip />} cursor={{ fill: "var(--primary-soft)" }} />
                    <Bar dataKey="jumlah" name="Jumlah Dokumen" barSize={22} radius={[0, 3, 3, 0]}>
                      {classChart.map((entry, idx) => (
                        <Cell
                          key={`ai-cell-${idx}`}
                          fill={entry.highlight ? "var(--chart-primary)" : "var(--chart-muted)"}
                        />
                      ))}
                      <LabelList
                        dataKey="jumlah"
                        position="right"
                        fill="var(--text-secondary)"
                        fontSize={12}
                        style={{ fontFamily: "var(--font-serif)" }}
                        formatter={(v: number) => `${v} dok`}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Naskah Selesai</CardDescription>
                  <CardTitle className="font-serif text-3xl font-semibold tabular-nums">
                    <NumberTicker value={dash.total_documents_checked} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">Seluruh dokumen terproses.</CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Rata-rata Indeks Kemiripan</CardDescription>
                  <CardTitle className="font-serif text-3xl font-semibold tabular-nums text-[color:var(--color-primary-text)]">
                    {dash.average_similarity !== null ? `${dash.average_similarity.toFixed(1)}%` : "-"}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">Hanya dari mode Plagiasi &amp; Gabungan.</CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Kata di Korpus Lokal</CardDescription>
                  <CardTitle className="font-serif text-3xl font-semibold tabular-nums">
                    <NumberTicker value={dash.corpus_stats.total_words} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">
                  {dash.corpus_stats.fulltext_sources_available} sumber teks penuh tersedia.
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 font-serif text-lg font-semibold">
                  <BarChart3 className="size-4 text-[color:var(--color-primary-text)]" aria-hidden="true" />
                  <span>Tren Indeks Kemiripan Terbaru</span>
                </CardTitle>
                <CardDescription>Batang burgundy menandai naskah di atas ambang perhatian 30%.</CardDescription>
              </CardHeader>
              <CardContent className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dash.trend} margin={{ top: 24, right: 16, left: -12, bottom: 4 }}>
                    <XAxis
                      dataKey="report_number"
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
                    {dash.average_similarity !== null && (
                      <ReferenceLine
                        y={dash.average_similarity}
                        stroke="var(--chart-ref)"
                        strokeDasharray="3 3"
                        label={{
                          value: `Rata-rata ${dash.average_similarity.toFixed(1)}%`,
                          position: "insideTopRight",
                          fill: "var(--text-secondary)",
                          fontSize: 11,
                          fontFamily: "var(--font-serif)",
                        }}
                      />
                    )}
                    <Bar dataKey="similarity_index" name="Indeks Kemiripan (%)" radius={[3, 3, 0, 0]} maxBarSize={38}>
                      {dash.trend.map((entry, idx) => (
                        <Cell
                          key={`plag-cell-${idx}`}
                          fill={entry.similarity_index >= 30 ? "var(--chart-primary)" : "var(--chart-muted)"}
                        />
                      ))}
                      <LabelList
                        dataKey="similarity_index"
                        position="top"
                        fill="var(--text-secondary)"
                        fontSize={11}
                        style={{ fontFamily: "var(--font-serif)" }}
                        formatter={(v: number) => `${v.toFixed(1)}%`}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </BlurFade>
  );
};
