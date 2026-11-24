import React, { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { apiFetch } from "../api/client";
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

interface ProviderInfo {
  id: string;
  name: string;
  type: string;
  default_enabled: boolean;
  full_text_capable: boolean;
  rate_limit?: string;
  status: string;
}

export const SettingsPage: React.FC = () => {
  const [payload, setPayload] = useState<SettingsPayload | null>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [tokenInput, setTokenInput] = useState(() => localStorage.getItem("ng_api_token") || "");
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<SettingsPayload>("/settings").then(setPayload).catch((e) => setError(e.message));
    apiFetch<{ providers: ProviderInfo[] }>("/providers").then((d) => setProviders(d.providers)).catch(() => undefined);
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

  if (!payload) return <div className="card">{error || "Memuat pengaturan..."}</div>;

  const ex = payload.default_exclusions;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Pengaturan Aplikasi &amp; Status Sistem</h2>
          <p className="page-desc">Konfigurasi default pengecualian, ambang kategori operasional, dan pemantauan modul lokal.</p>
        </div>
      </div>

      {savedMsg && <div className="notice">{savedMsg}</div>}
      {error && <div className="notice notice-warn">{error}</div>}

      <form onSubmit={handleSave} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16, marginBottom: 20 }}>
        <div className="card">
          <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>Default Pengecualian</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14 }}>
            <label><input type="checkbox" checked={ex.exclude_bibliography} onChange={(e) => setPayload({ ...payload, default_exclusions: { ...ex, exclude_bibliography: e.target.checked } })} /> Kecualikan Daftar Pustaka</label>
            <label><input type="checkbox" checked={ex.exclude_citations} onChange={(e) => setPayload({ ...payload, default_exclusions: { ...ex, exclude_citations: e.target.checked } })} /> Kecualikan Sitasi dalam Teks</label>
            <label><input type="checkbox" checked={ex.exclude_quotes} onChange={(e) => setPayload({ ...payload, default_exclusions: { ...ex, exclude_quotes: e.target.checked } })} /> Kecualikan Kutipan Langsung</label>
            <label><input type="checkbox" checked={ex.exclude_toc} onChange={(e) => setPayload({ ...payload, default_exclusions: { ...ex, exclude_toc: e.target.checked } })} /> Kecualikan Daftar Isi</label>
            <label><input type="checkbox" checked={ex.exclude_cover} onChange={(e) => setPayload({ ...payload, default_exclusions: { ...ex, exclude_cover: e.target.checked } })} /> Kecualikan Halaman Sampul</label>
            <label><input type="checkbox" checked={ex.exclude_common_phrases} onChange={(e) => setPayload({ ...payload, default_exclusions: { ...ex, exclude_common_phrases: e.target.checked } })} /> Kecualikan Frasa Umum</label>
            <div style={{ marginTop: 6 }}>
              <label style={{ fontSize: 13 }}>Minimal Kata Cocok (3–50)</label>
              <input type="number" className="input" min={3} max={50} value={ex.min_match_words} onChange={(e) => setPayload({ ...payload, default_exclusions: { ...ex, min_match_words: Number(e.target.value) || 8 } })} />
            </div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>Ambang Kategori Operasional &amp; Token</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div>
              <label style={{ fontSize: 13 }}>Batas Bawah (&quot;Rendah&quot; &lt; X%)</label>
              <input type="number" step="0.5" className="input" value={payload.threshold_low} onChange={(e) => setPayload({ ...payload, threshold_low: Number(e.target.value) })} />
            </div>
            <div>
              <label style={{ fontSize: 13 }}>Batas Atas (&quot;Tinggi&quot; &gt;= Y%)</label>
              <input type="number" step="0.5" className="input" value={payload.threshold_high} onChange={(e) => setPayload({ ...payload, threshold_high: Number(e.target.value) })} />
            </div>
            <div>
              <label style={{ fontSize: 13 }}>Bearer API Token (opsional, jika NG_API_TOKEN aktif)</label>
              <input type="password" className="input" value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} placeholder="Kosongkan untuk mode lokal tanpa token" />
            </div>
            <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>
              Ambang di atas merupakan kategori operasional aplikasi yang dapat dikonfigurasi, bukan standar resmi institusi.
            </p>
            <button type="submit" className="btn btn-primary" style={{ alignSelf: "flex-start" }}>
              <Save size={15} /> Simpan Pengaturan
            </button>
          </div>
        </div>
      </form>

      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ margin: "0 0 10px", fontSize: 16 }}>Status Modul Sistem (Read-Only)</h3>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, lineHeight: 1.8 }}>
          <li><strong>Backend PDF:</strong> {payload.system.pdf_backend}</li>
          <li><strong>Status OCR Lokal:</strong> {payload.system.ocr_message}</li>
          <li><strong>Status Modul Semantik:</strong> {payload.system.semantic_message}</li>
          <li><strong>Retensi Otomatis:</strong> {payload.system.retention_days > 0 ? `${payload.system.retention_days} hari` : "Nonaktif (0 hari)"}</li>
        </ul>
      </div>

      <div className="card">
        <h3 style={{ margin: "0 0 10px", fontSize: 16 }}>Status Penyedia Sumber (Source Providers)</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Provider</th>
                <th>Tipe</th>
                <th>Full-Text</th>
                <th>Batas Laju (Rate Limit)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {providers.map((p) => (
                <tr key={p.id}>
                  <td><strong>{p.name}</strong></td>
                  <td>{p.type}</td>
                  <td>{p.full_text_capable ? "Ya" : "Metadata Saja"}</td>
                  <td>{p.rate_limit || "-"}</td>
                  <td>{p.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
