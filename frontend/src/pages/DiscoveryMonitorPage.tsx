import React, { useEffect, useState } from "react";
import { Activity, Globe, RefreshCw } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { BlurFade } from "@/components/ui/blur-fade";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiFetch } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { ProviderHealthItem, SourceAcquisitionItem } from "../types";
import { formatMs } from "../utils/format";

interface MonitorResponse {
  summary: {
    total_queries: number;
    failed_queries: number;
    total_acquisitions: number;
    status_counts: Record<string, number>;
  };
  recent_checks: Array<{ id: string; report_number: string; status: string }>;
  queries: Array<{
    id: number;
    provider: string;
    query: string;
    status: string;
    result_count: number;
    duration_ms: number;
  }>;
  acquisitions: SourceAcquisitionItem[];
}

export const DiscoveryMonitorPage: React.FC = () => {
  const [data, setData] = useState<MonitorResponse | null>(null);
  const [providers, setProviders] = useState<ProviderHealthItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [probing, setProbing] = useState(false);
  const [diagMsg, setDiagMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      apiFetch<MonitorResponse>("/providers/monitor"),
      apiFetch<{ providers: ProviderHealthItem[] }>("/providers"),
    ])
      .then(([mon, prov]) => {
        setData(mon);
        setProviders(prov.providers || []);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const runProbe = async () => {
    setProbing(true);
    setDiagMsg(null);
    setError(null);
    try {
      const res = await apiFetch<{ providers: ProviderHealthItem[]; checked_at: string }>("/providers/diagnostics", {
        method: "POST",
      });
      setProviders(res.providers || []);
      setDiagMsg(`Koneksi langsung ke penyedia terbuka diperiksa pada ${new Date(res.checked_at).toLocaleTimeString("id-ID")}.`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setProbing(false);
    }
  };

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Monitor Penemuan Sumber"
          description="Pantau kueri pencarian eksternal, unduhan teks penuh sumber terbuka, serta status koneksi penyedia jurnal ilmiah."
          actions={
            <Button type="button" variant="outline" disabled={probing} onClick={runProbe}>
              <RefreshCw className={`size-4 ${probing ? "animate-spin" : ""}`} data-icon="inline-start" aria-hidden="true" />
              <span>{probing ? "Memeriksa Koneksi..." : "Uji Koneksi Langsung"}</span>
            </Button>
          }
        />

        {diagMsg && (
          <Alert>
            <Activity className="size-4" />
            <AlertTitle>Hasil Uji Koneksi</AlertTitle>
            <AlertDescription>{diagMsg}</AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Gagal memuat monitor penemuan</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {providers.map((p) => {
            const label = !p.configured
              ? "Perlu Konfigurasi"
              : p.reachable === true
              ? "Terhubung (Terverifikasi)"
              : p.reachable === false
              ? "Tidak Terjangkau"
              : "Siap (Belum Diuji Live)";
            return (
              <Card key={p.id} className="shadow-none">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-sm">{p.name}</CardTitle>
                    <Badge variant={p.reachable === false ? "destructive" : p.reachable === true ? "default" : "secondary"}>
                      {label}
                    </Badge>
                  </div>
                  <CardDescription>{p.type} · {p.full_text_capable ? "Mendukung Teks Penuh" : "Hanya Referensi"}</CardDescription>
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground flex justify-between tabular-nums">
                  <span>Permintaan: {p.request_count}</span>
                  <span>Hasil: {p.result_count}</span>
                </CardContent>
              </Card>
            );
          })}
        </div>

        <Card className="shadow-none">
          <CardHeader>
            <CardTitle className="text-base">Log Akuisisi Sumber Terbaru</CardTitle>
            <CardDescription>Daftar tautan artikel terbuka yang dicoba diakses dalam pemeriksaan terakhir.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {loading || !data ? (
              <div className="p-6"><Skeleton className="h-32 w-full" /></div>
            ) : data.acquisitions.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
                <Globe className="size-8 text-muted-foreground" aria-hidden="true" />
                <p className="text-sm font-medium text-foreground">Belum ada log pengambilan sumber web</p>
                <p className="text-xs text-muted-foreground">Aktifkan Pencarian Internet Terbuka pada Pemeriksaan Baru untuk mengisi monitor ini.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Penyedia</TableHead>
                      <TableHead>Judul</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Durasi</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.acquisitions.slice(0, 20).map((acq) => (
                      <TableRow key={acq.id}>
                        <TableCell className="font-medium">{acq.provider}</TableCell>
                        <TableCell className="max-w-[340px] truncate">{acq.title}</TableCell>
                        <TableCell><Badge variant="outline">{acq.status}</Badge></TableCell>
                        <TableCell className="text-right text-xs tabular-nums">{formatMs(acq.duration_ms)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </BlurFade>
  );
};
