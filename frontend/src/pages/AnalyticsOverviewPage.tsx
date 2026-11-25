import React, { useEffect, useState } from "react";
import { Activity, BarChart3 } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";
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
  const classChart = [
    { name: "Cenderung Manusia", jumlah: aiCounts.HUMAN_LIKELY ?? 0 },
    { name: "Campuran / Ragu", jumlah: aiCounts.MIXED_UNCERTAIN ?? 0 },
    { name: "Terindikasi AI", jumlah: aiCounts.AI_LIKELY ?? 0 },
    { name: "Kurang Bukti", jumlah: aiCounts.INSUFFICIENT_DATA ?? 0 },
  ];

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <PageHeader
          title={isAi ? "Analitik Deteksi Tulisan AI" : "Analitik Pemeriksaan Plagiasi"}
          description={
            isAi
              ? "Statistik sebaran klasifikasi pola penulisan AI secara lokal tanpa mencampurkan skor plagiasi."
              : "Ringkasan agregat indeks kemiripan dan cakupan korpus lokal dari seluruh pemeriksaan selesai."
          }
        />

        {isAi ? (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>Total Dianalisis Pola AI</CardDescription>
                  <CardTitle className="font-serif text-3xl tabular-nums">
                    <NumberTicker value={dash.ai_stats?.total_ai_analyzed ?? 0} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">
                  Gabungan mode Deteksi AI &amp; Laporan Gabungan.
                </CardContent>
              </Card>
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>Rata-rata Indikasi Pola AI</CardDescription>
                  <CardTitle className="font-serif text-3xl tabular-nums">
                    {dash.average_ai_likelihood !== null ? `${dash.average_ai_likelihood.toFixed(1)}%` : "-"}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">
                  Estimasi probabilistik berbasis stilometri &amp; entropi.
                </CardContent>
              </Card>
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>Mode Gabungan Selesai</CardDescription>
                  <CardTitle className="font-serif text-3xl tabular-nums">
                    <NumberTicker value={dash.ai_stats?.total_combined ?? 0} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">
                  Menghasilkan laporan plagiasi dan laporan AI terpisah.
                </CardContent>
              </Card>
            </div>

            <Card className="shadow-none">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Activity className="size-4 text-primary" />
                  <span>Distribusi Klasifikasi Deteksi AI</span>
                </CardTitle>
                <CardDescription>Jumlah dokumen per kategori interpretasi konservatif.</CardDescription>
              </CardHeader>
              <CardContent className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={classChart} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                    <RechartsTooltip />
                    <Bar dataKey="jumlah" name="Jumlah Dokumen" fill="var(--color-primary)" radius={[4, 4, 0, 0]} maxBarSize={44} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>Total Naskah Selesai</CardDescription>
                  <CardTitle className="font-serif text-3xl tabular-nums">
                    <NumberTicker value={dash.total_documents_checked} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">Seluruh dokumen terproses.</CardContent>
              </Card>
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>Rata-rata Indeks Kemiripan</CardDescription>
                  <CardTitle className="font-serif text-3xl tabular-nums">
                    {dash.average_similarity !== null ? `${dash.average_similarity.toFixed(1)}%` : "-"}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">Hanya dari mode Plagiasi &amp; Gabungan.</CardContent>
              </Card>
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>Total Kata di Korpus Lokal</CardDescription>
                  <CardTitle className="font-serif text-3xl tabular-nums">
                    <NumberTicker value={dash.corpus_stats.total_words} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground">
                  {dash.corpus_stats.fulltext_sources_available} sumber teks penuh tersedia.
                </CardContent>
              </Card>
            </div>

            <Card className="shadow-none">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="size-4 text-primary" />
                  <span>Tren Indeks Kemiripan Terbaru</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dash.trend} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
                    <XAxis dataKey="report_number" tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                    <RechartsTooltip />
                    <Bar dataKey="similarity_index" name="Indeks Kemiripan (%)" fill="var(--color-primary)" radius={[4, 4, 0, 0]} maxBarSize={42} />
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
