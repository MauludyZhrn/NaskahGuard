import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, Play, ShieldAlert } from "lucide-react";
import { apiFetch } from "../api/client";
import { CheckSettings, CheckSummary, DocumentItem } from "../types";

const DEFAULT_SETTINGS: CheckSettings = {
  exclude_bibliography: true,
  exclude_quotes: false,
  exclude_citations: true,
  exclude_cover: false,
  exclude_toc: true,
  exclude_common_phrases: true,
  min_match_words: 8,
  include_lexical_in_index: false,
  use_external_sources: false,
  external_providers: ["openalex", "crossref", "arxiv"],
  compare_with_previous_submissions: false,
  add_to_corpus_after_check: false,
  use_noplag_engine: false,
};

export const NewCheckPage: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [settings, setSettings] = useState<CheckSettings>(DEFAULT_SETTINGS);
  const [submitting, setSubmitting] = useState(false);
  const [activeCheck, setActiveCheck] = useState<CheckSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ default_exclusions?: CheckSettings }>("/settings")
      .then((res) => {
        if (res.default_exclusions) setSettings(res.default_exclusions);
      })
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
    }, 500);
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

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Pemeriksaan Baru</h2>
          <p className="page-desc">Unggah naskah PDF, DOCX, atau TXT untuk diperiksa terhadap korpus lokal.</p>
        </div>
      </div>

      {error && <div className="notice notice-warn">{error}</div>}

      <div className="card" style={{ marginBottom: 18 }}>
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
          <UploadCloud size={32} color="var(--accent)" style={{ marginBottom: 8 }} />
          <div style={{ fontWeight: 600 }}>
            {file ? `Terpilih: ${file.name} (${(file.size / 1024).toFixed(1)} KB)` : "Seret & lepaskan berkas di sini, atau klik untuk memilih"}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>
            Format yang didukung: .pdf, .docx, .txt
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            style={{ display: "none" }}
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16, marginBottom: 18 }}>
        <div className="card">
          <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>Pengaturan Pengecualian &amp; Ambang</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14 }}>
            <label><input type="checkbox" checked={settings.exclude_bibliography} onChange={(e) => setSettings({ ...settings, exclude_bibliography: e.target.checked })} /> Kecualikan Daftar Pustaka / Referensi</label>
            <label><input type="checkbox" checked={settings.exclude_citations} onChange={(e) => setSettings({ ...settings, exclude_citations: e.target.checked })} /> Kecualikan Sitasi dalam Teks</label>
            <label><input type="checkbox" checked={settings.exclude_quotes} onChange={(e) => setSettings({ ...settings, exclude_quotes: e.target.checked })} /> Kecualikan Kutipan Langsung (&quot;...&quot;)</label>
            <label><input type="checkbox" checked={settings.exclude_toc} onChange={(e) => setSettings({ ...settings, exclude_toc: e.target.checked })} /> Kecualikan Daftar Isi</label>
            <label><input type="checkbox" checked={settings.exclude_cover} onChange={(e) => setSettings({ ...settings, exclude_cover: e.target.checked })} /> Kecualikan Halaman Sampul</label>
            <label><input type="checkbox" checked={settings.exclude_common_phrases} onChange={(e) => setSettings({ ...settings, exclude_common_phrases: e.target.checked })} /> Kecualikan Frasa Akademik Umum</label>
            <label><input type="checkbox" checked={settings.include_lexical_in_index} onChange={(e) => setSettings({ ...settings, include_lexical_in_index: e.target.checked })} /> Masukkan kemiripan leksikal ke Similarity Index utama</label>
            <div style={{ marginTop: 6 }}>
              <label style={{ display: "block", fontSize: 13, color: "var(--text-secondary)", marginBottom: 4 }}>
                Panjang Frasa Cocok Minimum (kata: 3–50)
              </label>
              <input
                type="number"
                className="input"
                min={3}
                max={50}
                value={settings.min_match_words}
                onChange={(e) => setSettings({ ...settings, min_match_words: Math.max(3, Math.min(50, Number(e.target.value) || 8)) })}
                style={{ maxWidth: 120 }}
              />
            </div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>Pengaturan Pencarian Sumber</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14 }}>
            <label><input type="checkbox" checked={settings.compare_with_previous_submissions} onChange={(e) => setSettings({ ...settings, compare_with_previous_submissions: e.target.checked })} /> Bandingkan juga dengan dokumen submission sebelumnya</label>
            <label><input type="checkbox" checked={settings.add_to_corpus_after_check} onChange={(e) => setSettings({ ...settings, add_to_corpus_after_check: e.target.checked })} /> Indeks dokumen ini ke korpus lokal setelah selesai</label>
            <hr style={{ border: "none", borderTop: "1px solid var(--border)", width: "100%", margin: "6px 0" }} />
            <label style={{ fontWeight: 600 }}>
              <input type="checkbox" checked={settings.use_external_sources} onChange={(e) => setSettings({ ...settings, use_external_sources: e.target.checked })} /> Aktifkan Pencarian Sumber Ilmiah Terbuka Eksternal
            </label>
            <div className="notice" style={{ marginBottom: 4 }}>
              <ShieldAlert size={15} style={{ verticalAlign: "text-bottom", marginRight: 6 }} />
              <strong>Privasi:</strong> Secara default hanya korpus lokal yang diperiksa. Jika diaktifkan, NaskahGuard hanya mengirim <em>judul dan maksimal 10 frasa kunci</em> ke API resmi terpilih—tidak pernah mengirim teks penuh dokumen.
            </div>
            {settings.use_external_sources && (
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap", paddingLeft: 8 }}>
                {["openalex", "crossref", "arxiv", "pmc"].map((p) => (
                  <label key={p}>
                    <input
                      type="checkbox"
                      checked={settings.external_providers.includes(p)}
                      onChange={() => toggleProvider(p)}
                    />{" "}
                    {p.toUpperCase()}
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {activeCheck && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <strong>Memproses: {activeCheck.stage} ({activeCheck.report_number})</strong>
            <span>{activeCheck.progress}%</span>
          </div>
          <div style={{ height: 10, background: "var(--surface-alt)", borderRadius: 999, overflow: "hidden" }}>
            <div style={{ width: `${activeCheck.progress}%`, height: "100%", background: "var(--accent)", transition: "width 250ms ease" }} />
          </div>
        </div>
      )}

      <button type="button" className="btn btn-primary" disabled={submitting || !file} onClick={handleStart}>
        <Play size={16} />
        <span>{submitting ? "Sedang Memeriksa..." : "Mulai Pemeriksaan"}</span>
      </button>
    </div>
  );
};
