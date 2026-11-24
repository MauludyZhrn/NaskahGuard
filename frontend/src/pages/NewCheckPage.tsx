import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  UploadCloud,
  Play,
  ShieldAlert,
  SlidersHorizontal,
  Globe,
  CheckCircle2,
  AlertTriangle,
  FileText,
} from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { BlurFade } from "@/components/ui/blur-fade";
import { Progress } from "@/components/ui/progress";
import { apiFetch } from "../api/client";
import { CheckSettings, CheckSummary, DocumentItem, ProviderHealthItem } from "../types";

const DEFAULT_SETTINGS: CheckSettings = {
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

const INTENSITY_PRESETS: Record<"QUICK" | "BALANCED" | "DEEP", { label: string; queries: number; urls: number; desc: string }> = {
  QUICK: { label: "Cepat (QUICK)", queries: 8, urls: 8, desc: "Hingga 8 kueri inti, cocok untuk pemeriksaan singkat." },
  BALANCED: { label: "Seimbang (BALANCED)", queries: 24, urls: 16, desc: "Hingga 24 kueri tersebar per bab, rekomendasi standar." },
  DEEP: { label: "Mendalam (DEEP)", queries: 48, urls: 30, desc: "Hingga 48 kueri multi-bab + frasa panjang untuk skripsi/tesis." },
};

export const NewCheckPage: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [settings, setSettings] = useState<CheckSettings>(DEFAULT_SETTINGS);
  const [submitting, setSubmitting] = useState(false);
  const [activeCheck, setActiveCheck] = useState<CheckSummary | null>(null);
  const [corpusCount, setCorpusCount] = useState<number | null>(null);
  const [providers, setProviders] = useState<ProviderHealthItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ default_exclusions?: Partial<CheckSettings> }>("/settings")
      .then((res) => {
        if (res.default_exclusions) {
          setSettings((prev) => ({ ...prev, ...res.default_exclusions }));
        }
      })
      .catch(() => undefined);
    apiFetch<{ total_documents: number }>("/corpus/stats")
      .then((res) => setCorpusCount(res.total_documents))
      .catch(() => undefined);
    apiFetch<{ providers: ProviderHealthItem[] }>("/providers")
      .then((res) => setProviders(res.providers || []))
      .catch(() => undefined);
  }, []);

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
          setError(updated.error || "Pemeriksaan gagal diproses.");
          setSubmitting(false);
        }
      } catch (e: any) {
        setError(e.message);
      }
    }, 600);
    return () => clearInterval(timer);
  }, [activeCheck, navigate]);

  const handleStart = async () => {
    if (!file) {
      setError("Pilih berkas PDF, DOCX, atau TXT terlebih dahulu.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const uploaded = await apiFetch<DocumentItem>("/documents", { method: "POST", body: fd });
      const created = await apiFetch<{ check_id: string }>("/checks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: uploaded.id, settings }),
      });
      const initial = await apiFetch<CheckSummary>(`/checks/${created.check_id}`);
      setActiveCheck(initial);
    } catch (e: any) {
      setError(e.message);
      setSubmitting(false);
    }
  };

  const toggleProvider = (id: string) => {
    setSettings((prev) => {
      const exists = prev.external_providers.includes(id);
      return {
        ...prev,
        external_providers: exists
          ? prev.external_providers.filter((p) => p !== id)
          : [...prev.external_providers, id],
      };
    });
  };

  const applyIntensity = (mode: "QUICK" | "BALANCED" | "DEEP") => {
    const preset = INTENSITY_PRESETS[mode];
    setSettings((prev) => ({
      ...prev,
      search_intensity: mode,
      max_search_queries: preset.queries,
      max_crawled_urls: preset.urls,
    }));
  };

  const providerStatusMap = new Map(providers.map((p) => [p.id, p]));
  const activeExclusionsCount = [
    settings.exclude_bibliography,
    settings.exclude_citations,
    settings.exclude_quotes,
    settings.exclude_toc,
    settings.exclude_cover,
    settings.exclude_common_phrases,
  ].filter(Boolean).length;

  return (
    <BlurFade duration={0.22}>
      <div>
        <div className="page-header">
          <div>
            <h2 className="page-title">Pemeriksaan Baru</h2>
            <p className="page-desc">
              Unggah naskah akademik dan atur ruang lingkup pemeriksaan secara transparan.
            </p>
          </div>
        </div>

        {corpusCount === 0 && !settings.use_external_sources && (
          <div className="notice notice-warn">
            Korpus sumber lokal saat ini kosong (0 dokumen). Unggah dokumen pembanding di menu{" "}
            <strong>Korpus Sumber</strong> atau aktifkan <strong>Pencarian Sumber Eksternal</strong>.
          </div>
        )}
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertTitle>Tidak dapat memulai pemeriksaan</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Bagian 1: Unggah Dokumen */}
        <section className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 className="section-title" style={{ margin: 0 }}>
              1. Unggah Dokumen Naskah
            </h3>
            <span className="badge badge-neutral">PDF · DOCX · TXT</span>
          </div>
          <div
            className={`dropzone ${dragging ? "dragging" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]);
            }}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click();
            }}
          >
            {file ? (
              <>
                <FileText size={30} color="var(--color-primary)" style={{ marginBottom: 8 }} />
                <div style={{ fontWeight: 600, fontSize: 15 }}>{file.name}</div>
                <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>
                  Ukuran: {(file.size / 1024).toFixed(1)} KB · Klik untuk mengganti berkas
                </div>
              </>
            ) : (
              <>
                <UploadCloud size={32} color="var(--color-primary)" style={{ marginBottom: 8 }} />
                <div style={{ fontWeight: 600 }}>Seret &amp; lepaskan berkas di sini, atau klik untuk memilih</div>
                <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>
                  Mendukung naskah skripsi, tesis, jurnal, dan makalah (.pdf, .docx, .txt)
                </div>
              </>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              style={{ display: "none" }}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>
        </section>

        {/* Bagian 2: Pengaturan Pemeriksaan */}
        <section className="card" style={{ marginBottom: 16 }}>
          <h3 className="section-title">2. Pengaturan Pemeriksaan &amp; Pengecualian</h3>
          <div className="form-grid" style={{ gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14 }}>
              <label>
                <input
                  type="checkbox"
                  checked={settings.exclude_bibliography}
                  onChange={(e) => setSettings({ ...settings, exclude_bibliography: e.target.checked })}
                />{" "}
                Kecualikan Daftar Pustaka / Referensi
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={settings.exclude_citations}
                  onChange={(e) => setSettings({ ...settings, exclude_citations: e.target.checked })}
                />{" "}
                Kecualikan Sitasi dalam Teks
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={settings.exclude_quotes}
                  onChange={(e) => setSettings({ ...settings, exclude_quotes: e.target.checked })}
                />{" "}
                Kecualikan Kutipan Langsung (&quot;...&quot;)
              </label>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14 }}>
              <label>
                <input
                  type="checkbox"
                  checked={settings.exclude_toc}
                  onChange={(e) => setSettings({ ...settings, exclude_toc: e.target.checked })}
                />{" "}
                Kecualikan Daftar Isi
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={settings.exclude_cover}
                  onChange={(e) => setSettings({ ...settings, exclude_cover: e.target.checked })}
                />{" "}
                Kecualikan Halaman Sampul
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={settings.exclude_common_phrases}
                  onChange={(e) => setSettings({ ...settings, exclude_common_phrases: e.target.checked })}
                />{" "}
                Kecualikan Frasa Akademik Umum
              </label>
            </div>
          </div>
          <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center" }}>
            <div>
              <label style={{ display: "block", fontSize: 12.5, color: "var(--text-secondary)", marginBottom: 4 }}>
                Panjang Frasa Cocok Minimum (kata: 3–50)
              </label>
              <input
                type="number"
                className="input"
                min={3}
                max={50}
                value={settings.min_match_words}
                onChange={(e) =>
                  setSettings({ ...settings, min_match_words: Math.max(3, Math.min(50, Number(e.target.value) || 8)) })
                }
                style={{ width: 120 }}
              />
            </div>
            <label style={{ fontSize: 14, marginTop: 16 }}>
              <input
                type="checkbox"
                checked={settings.include_lexical_in_index}
                onChange={(e) => setSettings({ ...settings, include_lexical_in_index: e.target.checked })}
              />{" "}
              Sertakan kemiripan leksikal ke Similarity Index utama
            </label>
          </div>
        </section>

        {/* Bagian 3: Pencarian Sumber Eksternal */}
        <section className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <div>
              <h3 className="section-title" style={{ margin: "0 0 4px", display: "flex", alignItems: "center", gap: 8 }}>
                <Globe size={17} /> 3. Pencarian Sumber Eksternal (Internet &amp; Database Akademik)
              </h3>
              <p style={{ margin: 0, fontSize: 13, color: "var(--text-muted)" }}>
                Default hanya memeriksa korpus lokal ({corpusCount ?? "..."} dokumen). Aktifkan untuk mencari ke OpenAlex, Europe PMC, arXiv, Crossref, DOAJ, atau Web.
              </p>
            </div>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontWeight: 600, fontSize: 14, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={settings.use_external_sources}
                onChange={(e) => setSettings({ ...settings, use_external_sources: e.target.checked })}
              />
              <span>{settings.use_external_sources ? "Aktif" : "Nonaktif (Lokal Saja)"}</span>
            </label>
          </div>

          {settings.use_external_sources && (
            <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
              <div className="notice" style={{ marginBottom: 14 }}>
                <ShieldAlert size={15} style={{ verticalAlign: "text-bottom", marginRight: 6 }} />
                <strong>Pemberitahuan Privasi Kueri Eksternal:</strong> Hanya potongan frasa atau kata kunci terpilih (maksimal sesuai kuota kueri, bukan keseluruhan isi naskah/tesis) yang dikirim ke provider yang Anda centang.
              </div>

              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Profil Intensitas Pencarian (Batas Maksimum Kueri)</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 10 }}>
                  {(["QUICK", "BALANCED", "DEEP"] as const).map((mode) => {
                    const preset = INTENSITY_PRESETS[mode];
                    const active = (settings.search_intensity || "BALANCED") === mode;
                    return (
                      <button
                        key={mode}
                        type="button"
                        className="card"
                        onClick={() => applyIntensity(mode)}
                        style={{
                          textAlign: "left",
                          cursor: "pointer",
                          padding: 12,
                          borderColor: active ? "var(--color-primary)" : "var(--border)",
                          background: active ? "var(--color-primary-soft)" : "var(--surface-alt)",
                        }}
                      >
                        <div style={{ fontWeight: 600, fontSize: 13.5, color: active ? "var(--color-primary-text)" : "var(--text)" }}>
                          {preset.label}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>{preset.desc}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14, marginBottom: 14 }}>
                <label>
                  <input
                    type="checkbox"
                    checked={settings.enable_academic_search}
                    onChange={(e) => setSettings({ ...settings, enable_academic_search: e.target.checked })}
                  />{" "}
                  Pencarian Database Akademik (OpenAlex, Europe PMC, arXiv, Crossref, DOAJ)
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={settings.enable_web_search}
                    onChange={(e) => setSettings({ ...settings, enable_web_search: e.target.checked })}
                  />{" "}
                  Pencarian Web Umum (SearXNG / Official Web API — jika terkonfigurasi)
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={settings.enable_fulltext_download}
                    onChange={(e) => setSettings({ ...settings, enable_fulltext_download: e.target.checked })}
                  />{" "}
                  Unduh Full-Text PDF/HTML/XML secara Otomatis (legal, Open Access &amp; patuh robots.txt)
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={settings.enable_browser_crawler}
                    onChange={(e) => setSettings({ ...settings, enable_browser_crawler: e.target.checked })}
                  />{" "}
                  Playwright Browser Crawler (konteks terisolasi, hanya untuk halaman publik berbasis JavaScript)
                </label>
              </div>

              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Pilih Provider &amp; Status Konfigurasi</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8 }}>
                {[
                  { id: "openalex", label: "OpenAlex" },
                  { id: "europe_pmc", label: "Europe PMC" },
                  { id: "arxiv", label: "arXiv" },
                  { id: "doaj", label: "DOAJ (Open Access)" },
                  { id: "crossref", label: "Crossref (Metadata)" },
                  { id: "searxng", label: "SearXNG (Web)" },
                  { id: "web_api", label: "Official Web API" },
                ].map((p) => {
                  const info = providerStatusMap.get(p.id);
                  const configured = info ? info.configured : true;
                  return (
                    <label
                      key={p.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 8,
                        padding: "8px 10px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border)",
                        background: "var(--surface-alt)",
                        fontSize: 13,
                        opacity: configured ? 1 : 0.72,
                      }}
                    >
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                        <input
                          type="checkbox"
                          checked={settings.external_providers.includes(p.id)}
                          onChange={() => toggleProvider(p.id)}
                        />
                        {p.label}
                      </span>
                      <span className={`badge ${configured ? "badge-SUCCESS" : "badge-neutral"}`} style={{ fontSize: 10.5 }}>
                        {configured ? (
                          <>
                            <CheckCircle2 size={10} /> Siap
                          </>
                        ) : (
                          <>
                            <AlertTriangle size={10} /> NOT_CONFIGURED
                          </>
                        )}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </section>

        {/* Bagian 4: Pengaturan Lanjutan (shadcn Accordion tertutup default) */}
        <Accordion type="single" collapsible className="mb-4">
          <AccordionItem value="advanced" className="card p-0 overflow-hidden">
            <AccordionTrigger className="px-4 py-3.5 hover:no-underline hover:bg-muted/40">
              <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
                <SlidersHorizontal size={16} /> 4. Pengaturan Lanjutan (Batas Kueri, Crawler &amp; Korpus)
              </span>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4 pt-3 border-t" style={{ borderColor: "var(--border)" }}>
              <div className="form-grid" style={{ marginBottom: 14 }}>
                <div>
                  <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Maks. Kueri Pencarian (1–48)</label>
                  <input
                    type="number"
                    className="input"
                    min={1}
                    max={48}
                    value={settings.max_search_queries}
                    onChange={(e) =>
                      setSettings({ ...settings, max_search_queries: Math.max(1, Math.min(48, Number(e.target.value) || 24)) })
                    }
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Maks. URL Di-crawl (1–50)</label>
                  <input
                    type="number"
                    className="input"
                    min={1}
                    max={50}
                    value={settings.max_crawled_urls}
                    onChange={(e) =>
                      setSettings({ ...settings, max_crawled_urls: Math.max(1, Math.min(50, Number(e.target.value) || 12)) })
                    }
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Batas Ukuran Unduhan (MB)</label>
                  <input
                    type="number"
                    className="input"
                    min={1}
                    max={100}
                    value={settings.max_download_mb}
                    onChange={(e) =>
                      setSettings({ ...settings, max_download_mb: Math.max(1, Math.min(100, Number(e.target.value) || 25)) })
                    }
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Bahasa Pencarian</label>
                  <select
                    className="input"
                    value={settings.search_language}
                    onChange={(e) => setSettings({ ...settings, search_language: e.target.value as "all" | "id" | "en" })}
                  >
                    <option value="all">Semua (ID &amp; EN)</option>
                    <option value="id">Bahasa Indonesia</option>
                    <option value="en">Bahasa Inggris</option>
                  </select>
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14 }}>
                <label>
                  <input
                    type="checkbox"
                    checked={settings.compare_with_previous_submissions}
                    onChange={(e) => setSettings({ ...settings, compare_with_previous_submissions: e.target.checked })}
                  />{" "}
                  Bandingkan juga dengan dokumen submission sebelumnya
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={settings.add_to_corpus_after_check}
                    onChange={(e) => setSettings({ ...settings, add_to_corpus_after_check: e.target.checked })}
                  />{" "}
                  Indeks dokumen ini ke korpus lokal setelah pemeriksaan selesai
                </label>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* Ringkasan Konfigurasi Aktif & Tombol Mulai */}
        <div
          className="card"
          style={{
            marginBottom: 16,
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 14,
          }}
        >
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            <strong>Konfigurasi Aktif:</strong> Korpus Lokal ({corpusCount ?? 0} dok) ·{" "}
            {settings.use_external_sources
              ? `Eksternal Aktif (${settings.search_intensity || "BALANCED"}, maks ${settings.max_search_queries} kueri, ${settings.external_providers.length} provider)`
              : "Eksternal Nonaktif"}{" "}
            · {activeExclusionsCount} aturan pengecualian · Min. {settings.min_match_words} kata
          </div>
          <button type="button" className="btn btn-primary" disabled={submitting || !file} onClick={handleStart}>
            <Play size={16} />
            <span>{submitting ? "Sedang Memeriksa..." : "Mulai Pemeriksaan"}</span>
          </button>
        </div>

        {activeCheck && (
          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 14 }}>
              <strong>
                Memproses Tahap Nyata: {activeCheck.stage} ({activeCheck.report_number})
              </strong>
              <span className="num">{activeCheck.progress}%</span>
            </div>
            <Progress value={activeCheck.progress} className="h-2.5" />
          </div>
        )}
      </div>
    </BlurFade>
  );
};
