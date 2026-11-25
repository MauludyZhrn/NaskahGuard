import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Bot,
  CheckCircle2,
  FileSearch2,
  FileText,
  Globe,
  Layers,
  Play,
  SlidersHorizontal,
  UploadCloud,
} from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { BlurFade } from "@/components/ui/blur-fade";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { apiFetch } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { CheckMode, CheckSettings, CheckSummary, DocumentItem, ModelCatalogItem } from "../types";

const MODE_OPTIONS: Array<{
  mode: CheckMode;
  title: string;
  subtitle: string;
  detail: string;
  badge?: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  {
    mode: "PLAGIARISM_ONLY",
    title: "Pemeriksaan Plagiasi",
    subtitle: "Cocokkan isi naskah terhadap korpus lokal & sumber ilmiah.",
    detail: "Menghitung Indeks Kemiripan dan sumber yang cocok tanpa skor AI.",
    icon: FileSearch2,
  },
  {
    mode: "AI_ONLY",
    title: "Deteksi Tulisan AI",
    subtitle: "Analisis pola bahasa, ritme kalimat, & entropi tulisan.",
    detail: "Berjalan luring di CPU lokal. Bersifat probabilistik (bukan vonis).",
    icon: Bot,
  },
  {
    mode: "COMBINED",
    title: "Pemeriksaan Gabungan",
    subtitle: "Jalankan Plagiasi dan Deteksi AI sekaligus dalam satu unggahan.",
    detail: "Hasil plagiasi dan hasil AI disajikan dalam dua laporan terpisah.",
    badge: "Direkomendasikan",
    icon: Layers,
  },
];

const DEFAULT_SETTINGS: CheckSettings = {
  check_mode: "COMBINED",
  ai_model_id: "ng-id-stylo-lm-v1",
  exclude_bibliography: true,
  exclude_quotes: false,
  exclude_citations: true,
  exclude_cover: false,
  exclude_toc: true,
  exclude_common_phrases: true,
  min_match_words: 8,
  include_lexical_in_index: false,
  include_local_corpus: true,
  use_external_sources: false,
  enable_academic_search: true,
  enable_web_search: false,
  enable_oai_sources: true,
  enable_fulltext_download: true,
  enable_browser_crawler: false,
  search_intensity: "BALANCED",
  max_search_queries: 24,
  max_crawled_urls: 12,
  max_download_mb: 25,
  search_language: "all",
  external_providers: ["openalex", "europe_pmc", "arxiv", "crossref"],
  compare_with_previous_submissions: false,
  add_to_corpus_after_check: false,
  use_noplag_engine: false,
};

export const NewCheckPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const initialModeParam = searchParams.get("mode") as CheckMode | null;
  const initialMode: CheckMode =
    initialModeParam && ["PLAGIARISM_ONLY", "AI_ONLY", "COMBINED"].includes(initialModeParam)
      ? initialModeParam
      : "COMBINED";

  const [mode, setMode] = useState<CheckMode>(initialMode);
  const [file, setFile] = useState<File | null>(null);
  const [titleInput, setTitleInput] = useState("");
  const [dragging, setDragging] = useState(false);
  const [settings, setSettings] = useState<CheckSettings>({ ...DEFAULT_SETTINGS, check_mode: initialMode });
  const [submitting, setSubmitting] = useState(false);
  const [activeCheck, setActiveCheck] = useState<CheckSummary | null>(null);
  const [corpusCount, setCorpusCount] = useState<number | null>(null);
  const [activeModel, setActiveModel] = useState<ModelCatalogItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ default_exclusions?: Partial<CheckSettings> }>("/settings")
      .then((res) => {
        if (res.default_exclusions) {
          setSettings((prev) => ({ ...prev, ...res.default_exclusions, check_mode: mode }));
        }
      })
      .catch(() => undefined);
    apiFetch<{ total_documents: number }>("/corpus/stats")
      .then((res) => setCorpusCount(res.total_documents))
      .catch(() => undefined);
    apiFetch<{ active_model_id: string; models: ModelCatalogItem[] }>("/models")
      .then((res) => {
        const found = res.models.find((m) => m.id === res.active_model_id) || res.models[0] || null;
        setActiveModel(found);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    setSettings((prev) => ({ ...prev, check_mode: mode }));
  }, [mode]);

  useEffect(() => {
    if (!activeCheck || activeCheck.status === "COMPLETED" || activeCheck.status === "FAILED") {
      return;
    }
    const timer = setInterval(async () => {
      try {
        const updated = await apiFetch<CheckSummary>(`/checks/${activeCheck.id}`);
        setActiveCheck(updated);
        if (updated.status === "COMPLETED") {
          clearInterval(timer);
          navigate(`/reports/${updated.id}`);
        } else if (updated.status === "FAILED") {
          clearInterval(timer);
          setSubmitting(false);
          setError(updated.error || "Pemeriksaan gagal diselesaikan.");
        }
      } catch (err: any) {
        setError(err.message);
      }
    }, 650);
    return () => clearInterval(timer);
  }, [activeCheck, navigate]);

  const handleFileSelected = (selected: File | null) => {
    setError(null);
    setFile(selected);
    if (selected && !titleInput) {
      setTitleInput(selected.name.replace(/\.[^/.]+$/, ""));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Silakan pilih dokumen (PDF, DOCX, atau TXT) terlebih dahulu.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (titleInput.trim()) fd.append("title", titleInput.trim());

      const uploaded = await apiFetch<DocumentItem>("/documents", { method: "POST", body: fd });
      const created = await apiFetch<{ check_id: string }>("/checks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: uploaded.id,
          settings: { ...settings, check_mode: mode },
        }),
      });
      const initial = await apiFetch<CheckSummary>(`/checks/${created.check_id}`);
      setActiveCheck(initial);
    } catch (err: any) {
      setSubmitting(false);
      setError(err.message || "Gagal memulai pemeriksaan.");
    }
  };

  const usesPlagiarism = mode === "PLAGIARISM_ONLY" || mode === "COMBINED";
  const usesAi = mode === "AI_ONLY" || mode === "COMBINED";

  return (
    <BlurFade duration={0.2}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <PageHeader
          eyebrow="Unggah & Analisis"
          title="Pemeriksaan Baru"
          description="Pilih jenis pemeriksaan, unggah dokumen akademik, lalu sesuaikan opsi seperlunya."
          badge={
            corpusCount !== null ? (
              <Badge variant="secondary" className="tabular-nums">
                {corpusCount} sumber lokal siap
              </Badge>
            ) : null
          }
        />

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Pemeriksaan tidak dapat dijalankan</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Step 1: Select Examination Mode BEFORE Upload */}
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle className="text-base">1. Pilih Mode Pemeriksaan</CardTitle>
            <CardDescription>
              Tentukan apakah ingin memeriksa kemiripan plagiasi saja, indikasi tulisan AI saja, atau keduanya secara terpisah.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-3" role="radiogroup" aria-label="Mode pemeriksaan">
              {MODE_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const selected = mode === opt.mode;
                return (
                  <button
                    key={opt.mode}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setMode(opt.mode)}
                    className={cn(
                      "flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors cursor-pointer",
                      selected
                        ? "border-primary bg-primary/5 ring-1 ring-primary"
                        : "border-border bg-card hover:bg-accent"
                    )}
                  >
                    <div className="flex w-full items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Icon className={cn("size-4 shrink-0", selected ? "text-primary" : "text-muted-foreground")} />
                        <span className="text-sm font-semibold text-foreground">{opt.title}</span>
                      </div>
                      {opt.badge && <Badge variant="default" className="text-[10px]">{opt.badge}</Badge>}
                    </div>
                    <p className="text-xs font-medium text-foreground/90">{opt.subtitle}</p>
                    <p className="text-xs text-muted-foreground">{opt.detail}</p>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Step 2: Upload Naskah */}
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle className="text-base">2. Unggah Naskah Akademik</CardTitle>
            <CardDescription>
              Mendukung berkas PDF, DOCX, TXT, HTML, maupun XML. Dokumen diproses secara lokal tanpa mengirim ke layanan berbayar.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                if (e.dataTransfer.files?.[0]) handleFileSelected(e.dataTransfer.files[0]);
              }}
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors cursor-pointer",
                dragging ? "border-primary bg-primary/5" : "border-border hover:bg-accent/50"
              )}
            >
              <UploadCloud className="size-8 text-muted-foreground" aria-hidden="true" />
              {file ? (
                <div className="flex flex-col items-center gap-1">
                  <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <FileText className="size-4 text-primary" />
                    <span>{file.name}</span>
                  </div>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {(file.size / 1024).toFixed(1)} KB · Klik untuk mengganti berkas
                  </span>
                </div>
              ) : (
                <div className="flex flex-col gap-1">
                  <p className="text-sm font-medium text-foreground">
                    Tarik &amp; lepas berkas ke sini, atau klik untuk memilih file
                  </p>
                  <p className="text-xs text-muted-foreground">Skripsi, tesis, artikel jurnal, atau makalah (PDF/DOCX/TXT)</p>
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt,.html,.htm,.xml"
                className="hidden"
                onChange={(e) => handleFileSelected(e.target.files?.[0] || null)}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="flex flex-col gap-1.5 min-w-0">
                <Label htmlFor="doc-title-input">Judul Dokumen (Opsional)</Label>
                <Input
                  id="doc-title-input"
                  value={titleInput}
                  onChange={(e) => setTitleInput(e.target.value)}
                  placeholder="Misal: Bab I–III Skripsi Manajemen Risiko"
                />
              </div>

              <div className="flex items-end lg:justify-end">
                <Button type="submit" size="lg" disabled={!file || submitting} className="w-full rounded-full lg:w-auto">
                  <Play className="size-4" data-icon="inline-start" aria-hidden="true" />
                  <span>
                    {submitting
                      ? "Sedang Memproses..."
                      : mode === "AI_ONLY"
                      ? "Jalankan Deteksi AI"
                      : mode === "COMBINED"
                      ? "Jalankan Pemeriksaan Gabungan"
                      : "Jalankan Pemeriksaan Plagiasi"}
                  </span>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Active Progress Feedback */}
        {activeCheck && (
          <Card className="border-primary/40 shadow-none">
            <CardContent className="flex flex-col gap-3 p-5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="size-4 text-primary" aria-hidden="true" />
                  <span className="text-sm font-semibold text-foreground">
                    {activeCheck.stage} ({activeCheck.report_number})
                  </span>
                </div>
                <span className="text-sm font-semibold tabular-nums text-primary">{activeCheck.progress}%</span>
              </div>
              <Progress value={activeCheck.progress} className="h-2" />
            </CardContent>
          </Card>
        )}

        {/* Step 3: Progressive Disclosure Settings */}
        <Accordion type="multiple" defaultValue={[]} className="rounded-xl border border-border bg-card px-5">
          {usesPlagiarism && (
            <AccordionItem value="plag-options" className="border-b-0">
              <AccordionTrigger className="hover:no-underline">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <SlidersHorizontal className="size-4 text-muted-foreground" aria-hidden="true" />
                  <span>Pengaturan Sumber &amp; Pengecualian Plagiasi</span>
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-5">
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                  <div className="flex flex-col gap-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Bagian yang Dikecualikan dari Skor
                    </p>
                    {[
                      { key: "exclude_bibliography", label: "Kecualikan Daftar Pustaka" },
                      { key: "exclude_citations", label: "Kecualikan Sitasi Dalam Teks" },
                      { key: "exclude_quotes", label: "Kecualikan Kutipan Langsung" },
                      { key: "exclude_toc", label: "Kecualikan Daftar Isi" },
                      { key: "exclude_common_phrases", label: "Kecualikan Frasa Akademik Umum" },
                    ].map((opt) => (
                      <div key={opt.key} className="flex items-center justify-between gap-3">
                        <Label htmlFor={opt.key} className="font-normal text-foreground cursor-pointer">
                          {opt.label}
                        </Label>
                        <Switch
                          id={opt.key}
                          checked={Boolean((settings as any)[opt.key])}
                          onCheckedChange={(val) => setSettings((s) => ({ ...s, [opt.key]: val }))}
                        />
                      </div>
                    ))}
                  </div>

                  <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex flex-col gap-0.5">
                        <Label htmlFor="ext-search-toggle" className="font-medium text-foreground">
                          <span className="inline-flex items-center gap-1.5">
                            <Globe className="size-3.5 text-muted-foreground" />
                            Pencarian Internet &amp; Jurnal Terbuka
                          </span>
                        </Label>
                        <span className="text-xs text-muted-foreground">
                          Cari sumber tambahan dari OpenAlex, Europe PMC, Crossref, arXiv, dan DOAJ.
                        </span>
                      </div>
                      <Switch
                        id="ext-search-toggle"
                        checked={settings.use_external_sources}
                        onCheckedChange={(val) => setSettings((s) => ({ ...s, use_external_sources: val }))}
                      />
                    </div>

                    <div className="flex flex-col gap-2">
                      <Label>Kedalaman Pencarian Eksternal</Label>
                      <div className="grid grid-cols-3 gap-2">
                        {(["QUICK", "BALANCED", "DEEP"] as const).map((level) => (
                          <Button
                            key={level}
                            type="button"
                            size="sm"
                            variant={settings.search_intensity === level ? "default" : "outline"}
                            onClick={() =>
                              setSettings((s) => ({
                                ...s,
                                search_intensity: level,
                                max_search_queries: level === "QUICK" ? 8 : level === "BALANCED" ? 24 : 48,
                                max_crawled_urls: level === "QUICK" ? 8 : level === "BALANCED" ? 16 : 30,
                              }))
                            }
                          >
                            {level === "QUICK" ? "Cepat" : level === "BALANCED" ? "Seimbang" : "Mendalam"}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>
          )}

          {usesAi && (
            <AccordionItem value="ai-options" className={usesPlagiarism ? "border-t border-border border-b-0" : "border-b-0"}>
              <AccordionTrigger className="hover:no-underline">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Bot className="size-4 text-muted-foreground" aria-hidden="true" />
                  <span>Informasi Model Deteksi Tulisan AI</span>
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-5 text-xs leading-relaxed text-muted-foreground flex flex-col gap-2">
                <p>
                  Model aktif: <strong className="text-foreground">{activeModel?.name || "NaskahGuard Calibrated Stylometry + N-gram LM v1"}</strong>
                </p>
                <p>
                  {activeModel?.indonesian_support || "Terkalibrasi untuk Bahasa Indonesia dan Bahasa Inggris akademik."}
                  {" "}Teks di bawah 80 kata akan ditandai sebagai <strong>Tidak Cukup Bukti</strong> agar terhindar dari salah tuduh.
                </p>
              </AccordionContent>
            </AccordionItem>
          )}
        </Accordion>
      </form>
    </BlurFade>
  );
};
