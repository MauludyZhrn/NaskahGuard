import React, { useEffect, useState } from "react";
import { CheckCircle2, Cpu, HardDrive, ShieldAlert, ShieldCheck } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { BlurFade } from "@/components/ui/blur-fade";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { ModelCatalogItem } from "../types";

export const ModelManagementPage: React.FC = () => {
  const [models, setModels] = useState<ModelCatalogItem[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadModels = () => {
    setLoading(true);
    apiFetch<{ active_model_id: string; models: ModelCatalogItem[] }>("/models")
      .then((res) => {
        setActiveId(res.active_model_id);
        setModels(res.models || []);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadModels();
  }, []);

  const handleVerify = async (id: string) => {
    setError(null);
    setFeedback(null);
    try {
      const res = await apiFetch<{ message: string; verified: boolean }>(`/models/${id}/verify`, { method: "POST" });
      setFeedback(res.message);
      loadModels();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleActivate = async (id: string) => {
    setError(null);
    setFeedback(null);
    try {
      await apiFetch(`/models/${id}/activate`, { method: "POST" });
      setFeedback(`Model '${id}' berhasil diaktifkan.`);
      loadModels();
    } catch (err: any) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-44 w-full" />
        <Skeleton className="h-44 w-full" />
      </div>
    );
  }

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Manajemen Model Deteksi AI"
          description="Kelola model analisis pola tulisan AI secara lokal. Model bawaan berjalan ringan di CPU tanpa GPU maupun biaya API."
          badge={<Badge variant="outline">Aktif: {activeId}</Badge>}
        />

        {feedback && (
          <Alert>
            <CheckCircle2 className="size-4" />
            <AlertTitle>Status Model</AlertTitle>
            <AlertDescription>{feedback}</AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive">
            <ShieldAlert className="size-4" />
            <AlertTitle>Tindakan Belum Dapat Dijalankan</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 gap-4">
          {models.map((m) => (
            <Card key={m.id} className={m.active ? "border-primary/45 shadow-none" : "shadow-none"}>
              <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Cpu className="size-4 text-primary" aria-hidden="true" />
                    <CardTitle className="text-base">{m.name}</CardTitle>
                    {m.active && <Badge variant="default">Aktif</Badge>}
                    <Badge variant="secondary">{m.tier === "BUILTIN_CPU" ? "Bawaan Offline CPU" : "Opsional HuggingFace"}</Badge>
                    <Badge variant={m.installed ? "outline" : "secondary"}>
                      {m.installed ? "Terpasang & Siap" : m.status === "DEPS_MISSING" ? "Paket Opsional Belum Terpasang" : "Belum Diunduh"}
                    </Badge>
                  </div>
                  <CardDescription>{m.family} · Referensi: {m.source_reference}</CardDescription>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Button type="button" variant="outline" size="sm" onClick={() => handleVerify(m.id)}>
                    <ShieldCheck className="size-3.5" data-icon="inline-start" aria-hidden="true" />
                    <span>Verifikasi</span>
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    disabled={Boolean(m.active) || !m.installed}
                    onClick={() => handleActivate(m.id)}
                  >
                    <span>{m.active ? "Sedang Digunakan" : "Aktifkan"}</span>
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                <div className="grid grid-cols-1 gap-3 rounded-md border border-border bg-muted/40 p-3 text-xs sm:grid-cols-3">
                  <div>
                    <span className="text-muted-foreground">Kebutuhan Komputasi:</span>
                    <p className="mt-0.5 font-medium text-foreground">{m.requirements.runtime}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Estimasi Memori / Disk:</span>
                    <p className="mt-0.5 flex items-center gap-1.5 font-medium text-foreground tabular-nums">
                      <HardDrive className="size-3.5 text-muted-foreground" />
                      <span>RAM ~{m.requirements.min_ram_mb} MB · Disk ~{m.requirements.disk_mb} MB</span>
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Dukungan Bahasa Indonesia:</span>
                    <p className="mt-0.5 font-medium text-foreground">{m.indonesian_support}</p>
                  </div>
                </div>

                <div className="flex flex-col gap-1 text-xs text-muted-foreground">
                  <span className="font-semibold text-foreground">Keterbatasan &amp; Catatan Kalibrasi:</span>
                  <ul className="list-disc pl-5 flex flex-col gap-0.5">
                    {m.limitations.map((lim, i) => (
                      <li key={i}>{lim}</li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </BlurFade>
  );
};
