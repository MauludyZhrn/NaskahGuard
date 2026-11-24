import React, { useEffect, useState } from "react";
import { Upload, Trash2 } from "lucide-react";
import { apiFetch } from "../api/client";
import { DocumentItem } from "../types";

interface CorpusStats {
  total_documents: number;
  total_words: number;
  total_fingerprints: number;
}

export const CorpusPage: React.FC = () => {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [authors, setAuthors] = useState("");
  const [year, setYear] = useState("");
  const [doi, setDoi] = useState("");
  const [url, setUrl] = useState("");
  const [sourceType, setSourceType] = useState("jurnal_lokal");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    apiFetch<DocumentItem[]>("/corpus").then(setDocs).catch((e) => setError(e.message));
    apiFetch<CorpusStats>("/corpus/stats").then(setStats).catch(() => undefined);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Pilih berkas dokumen sumber terlebih dahulu.");
      return;
    }
    setError(null);
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (title.trim()) fd.append("title", title.trim());
      if (authors.trim()) fd.append("authors", authors.trim());
      if (year.trim()) fd.append("year", year.trim());
      if (doi.trim()) fd.append("doi", doi.trim());
      if (url.trim()) fd.append("url", url.trim());
      fd.append("source_type", sourceType);
      await apiFetch("/corpus", { method: "POST", body: fd });
      setFile(null);
      setTitle("");
      setAuthors("");
      setYear("");
      setDoi("");
      setUrl("");
      loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (doc: DocumentItem) => {
    if (!window.confirm(`Hapus sumber "${doc.title || doc.filename}" dari korpus lokal?`)) return;
    await apiFetch(`/documents/${doc.id}`, { method: "DELETE" });
    loadData();
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Korpus Sumber Lokal</h2>
          <p className="page-desc">Kelola koleksi dokumen pembanding lokal beserta metadata atribusi dan indeks Winnowing.</p>
        </div>
      </div>

      {stats && (
        <div className="card-grid">
          <div className="card"><div className="stat-label">Total Dokumen Korpus</div><div className="stat-val">{stats.total_documents}</div></div>
          <div className="card"><div className="stat-label">Total Kata Terindeks</div><div className="stat-val">{stats.total_words.toLocaleString("id-ID")}</div></div>
          <div className="card"><div className="stat-label">Total Fingerprint Winnowing</div><div className="stat-val">{stats.total_fingerprints.toLocaleString("id-ID")}</div></div>
        </div>
      )}

      {error && <div className="notice notice-warn">{error}</div>}

      <form className="card" onSubmit={handleUpload} style={{ marginBottom: 20 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>Tambah Dokumen ke Korpus</h3>
        <div className="form-grid" style={{ marginBottom: 12 }}>
          <div>
            <label style={{ fontSize: 13 }}>Berkas (PDF/DOCX/TXT)</label>
            <input type="file" className="input" accept=".pdf,.docx,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
          <div>
            <label style={{ fontSize: 13 }}>Judul Sumber</label>
            <input type="text" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Opsional (otomatis dari metadata/nama file)" />
          </div>
          <div>
            <label style={{ fontSize: 13 }}>Penulis (pisahkan dengan koma)</label>
            <input type="text" className="input" value={authors} onChange={(e) => setAuthors(e.target.value)} placeholder="mis. Budi Santoso, Siti Aminah" />
          </div>
          <div>
            <label style={{ fontSize: 13 }}>Tahun Terbit</label>
            <input type="number" className="input" value={year} onChange={(e) => setYear(e.target.value)} placeholder="2024" />
          </div>
          <div>
            <label style={{ fontSize: 13 }}>DOI</label>
            <input type="text" className="input" value={doi} onChange={(e) => setDoi(e.target.value)} placeholder="10.xxxx/..." />
          </div>
          <div>
            <label style={{ fontSize: 13 }}>URL Sumber</label>
            <input type="url" className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />
          </div>
          <div>
            <label style={{ fontSize: 13 }}>Tipe Sumber</label>
            <select className="input" value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
              <option value="jurnal_lokal">Jurnal Ilmiah Lokal</option>
              <option value="skripsi_tesis">Skripsi / Tesis / Disertasi</option>
              <option value="prosiding">Prosiding Seminar</option>
              <option value="buku_referensi">Buku / Modul Ajar</option>
              <option value="local_document">Dokumen Lokal Lainnya</option>
            </select>
          </div>
        </div>
        <button type="submit" className="btn btn-primary" disabled={uploading}>
          <Upload size={15} />
          <span>{uploading ? "Mengindeks..." : "Unggah & Indeks ke Korpus"}</span>
        </button>
      </form>

      {docs.length === 0 ? (
        <div className="card">Belum ada data dokumen dalam korpus sumber lokal.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Judul / Berkas</th>
                <th>Penulis &amp; Tahun</th>
                <th>Tipe</th>
                <th>Status Akses</th>
                <th className="num">Kata</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>
                    <strong>{d.title || d.filename}</strong>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{d.filename} {d.doi ? `· DOI: ${d.doi}` : ""}</div>
                  </td>
                  <td>{(d.authors || []).join(", ") || "-"}{d.year ? ` (${d.year})` : ""}</td>
                  <td>{d.source_type}</td>
                  <td><span className="badge badge-EXCLUDED">{d.access_status}</span></td>
                  <td className="num">{d.word_count.toLocaleString("id-ID")}</td>
                  <td>
                    <button type="button" className="btn btn-danger" onClick={() => handleDelete(d)}>
                      <Trash2 size={14} /> Hapus
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
