import React, { useEffect, useState } from "react";
import { CheckCircle2, Save } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { BlurFade } from "@/components/ui/blur-fade";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { apiFetch } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { CheckSettings } from "../types";

interface SettingsPayload {
  default_exclusions: CheckSettings;
  threshold_low: number;
  threshold_high: number;
  system: {
    app_name: string;
    pdf_backend: string;
    retention_days: number;
    ocr_available: boolean;
    ocr_message: string;
    semantic_enabled: boolean;
    semantic_available: boolean;
    semantic_message: string;
  };
}

export const SettingsPage: React.FC = () => {
  const [payload, setPayload] = useState<SettingsPayload | null>(null);
  const [tokenInput, setTokenInput] = useState(() => localStorage.getItem("ng_api_token") || "");
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<SettingsPayload>("/settings")
      .then(setPayload)
      .catch((err: Error) => setError(err.message));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!payload) return;
    setError(null);
    setSavedMsg(null);
    localStorage.setItem("ng_api_token", tokenInput.trim());
    try {
      const updated = await apiFetch<SettingsPayload>("/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          default_exclusions: payload.default_exclusions,
          threshold_low: payload.threshold_low,
          threshold_high: payload.threshold_high,
        }),
      });
      setPayload(updated);
      setSavedMsg("Pengaturan berhasil disimpan.");
    } catch (err: any) {
      setError(err.message);
    }
  };

  if (!payload) {
    if (error) {
      return (
        <Alert variant="destructive">
          <AlertTitle>Gagal memuat pengaturan</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      );
    }
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-60 w-full" />
      </div>
    );
  }

  const ex = payload.default_exclusions;

  return (
    <BlurFade duration={0.2}>
      <form onSubmit={handleSave} className="flex flex-col gap-6">
        <PageHeader
          title="Pengaturan Aplikasi"
          description="Atur pengecualian default, batas kategori persentase kemiripan, dan lihat kesiapan modul lokal."
          actions={
            <Button type="submit">
              <Save className="size-4" data-icon="inline-start" aria-hidden="true" />
              <span>Simpan Pengaturan</span>
            </Button>
          }
        />

        {savedMsg && (
          <Alert>
            <CheckCircle2 className="size-4" />
            <AlertTitle>Tersimpan</AlertTitle>
            <AlertDescription>{savedMsg}</AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Gagal menyimpan</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-base">Pengecualian Bawaan Pemeriksaan</CardTitle>
              <CardDescription>Pengaturan awal yang otomatis terpilih saat membuka halaman Pemeriksaan Baru.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {[
                {
                  key: "exclude_bibliography",
                  label: "Kecualikan Daftar Pustaka / Bibliography",
                  hint: "Daftar Pustaka, Bibliography, Bibliografi, References, Works Cited",
                },
                { key: "exclude_citations", label: "Kecualikan Sitasi Dalam Teks" },
                { key: "exclude_quotes", label: "Kecualikan Kutipan Langsung" },
                { key: "exclude_toc", label: "Kecualikan Daftar Isi" },
                { key: "exclude_common_phrases", label: "Kecualikan Frasa Akademik Umum" },
              ].map((item) => (
                <div key={item.key} className="flex items-center justify-between gap-3">
                  <div className="flex flex-col gap-0.5">
                    <Label htmlFor={`set-${item.key}`} className="font-normal cursor-pointer">{item.label}</Label>
                    {"hint" in item && item.hint ? (
                      <span className="text-[11px] text-muted-foreground">{item.hint}</span>
                    ) : null}
                  </div>
                  <Switch
                    id={`set-${item.key}`}
                    checked={Boolean((ex as any)[item.key])}
                    onCheckedChange={(val) =>
                      setPayload({
                        ...payload,
                        default_exclusions: { ...ex, [item.key]: val },
                      })
                    }
                  />
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-base">Ambang Batas &amp; Token Lokal</CardTitle>
              <CardDescription>Digunakan untuk mengelompokkan kategori Indeks Kemiripan rendah, sedang, dan tinggi.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="th-low">Batas Bawah (%)</Label>
                  <Input
                    id="th-low"
                    type="number"
                    min={1}
                    max={90}
                    value={payload.threshold_low}
                    onChange={(e) => setPayload({ ...payload, threshold_low: Number(e.target.value) })}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="th-high">Batas Atas (%)</Label>
                  <Input
                    id="th-high"
                    type="number"
                    min={5}
                    max={99}
                    value={payload.threshold_high}
                    onChange={(e) => setPayload({ ...payload, threshold_high: Number(e.target.value) })}
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="api-token">Token Akses API Lokal (Opsional)</Label>
                <Input
                  id="api-token"
                  type="password"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  placeholder="Kosongkan bila berjalan pada mode localhost tunggal"
                />
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="shadow-none">
          <CardHeader>
            <CardTitle className="text-base">Status Komponen Lokal</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 text-xs sm:grid-cols-3">
            <div className="rounded-md border border-border p-3 flex flex-col gap-1">
              <span className="text-muted-foreground">Pembaca PDF</span>
              <span className="font-semibold text-foreground uppercase">{payload.system.pdf_backend}</span>
            </div>
            <div className="rounded-md border border-border p-3 flex flex-col gap-1">
              <span className="text-muted-foreground">OCR Dokumen Pindaian</span>
              <div>
                <Badge variant={payload.system.ocr_available ? "default" : "secondary"}>
                  {payload.system.ocr_available ? "Tersedia" : "Tidak Aktif"}
                </Badge>
              </div>
              {payload.system.ocr_message && (
                <span className="text-[11px] text-muted-foreground">{payload.system.ocr_message}</span>
              )}
            </div>
            <div className="rounded-md border border-border p-3 flex flex-col gap-1">
              <span className="text-muted-foreground">Kemiripan Makna Lokal</span>
              <div>
                <Badge variant={payload.system.semantic_available ? "default" : "secondary"}>
                  {payload.system.semantic_message}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </form>
    </BlurFade>
  );
};
