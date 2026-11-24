import React, { useEffect, useRef, useState } from "react";
import { Upload, Trash2, Database, BookMarked } from "lucide-react";
import { Link } from "react-router-dom";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { BlurFade } from "@/components/ui/blur-fade";
import { NumberTicker } from "@/components/ui/number-ticker";
import { apiFetch } from "../api/client";
import { DocumentItem } from "../types";

interface CorpusStats {
  total_documents: number;
  total_words: number;
  total_fingerprints: number;
}

export const CorpusPage: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
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
  const [pendingDelete, setPendingDelete] = useState<DocumentItem | null>(null);
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
      if (fileInputRef.current) fileInputRef.current.value = "";
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

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    await apiFetch(`/documents/${pendingDelete.id}`, { method: "DELETE" });
    setPendingDelete(null);
    loadData();
  };

  return (
    <BlurFade duration={0.22}>
      <div>
        <div className="page-header">
          <div>
            <h2 className="page-title">Korpus Sumber Lokal</h2>
            <p className="page-desc">
              Kelola koleksi dokumen pembanding lokal beserta metadata atribusi dan sidik jari Winnowing.
            </p>
          </div>
          <Link to="/repositories" className="btn">
            <BookMarked size={15} /> Repositori OAI-PMH
          </Link>
        </div>

        {stats && (
          <div className="kpi-grid">
            <div className="card">
              <div className="stat-label">Total Dokumen Korpus</div>
              <div className="stat-val">
                <NumberTicker value={stats.total_documents} />
              </div>
            </div>
            <div className="card">
              <div className="stat-label">Total Kata Terindeks</div>
              <div className="stat-val">
                <NumberTicker value={stats.total_words} />
              </div>
            </div>
            <div className="card">
              <div className="stat-label">Total Fingerprint Winnowing</div>
              <div className="stat-val">
                <NumberTicker value={stats.total_fingerprints} />
              </div>
            </div>
          </div>
        )}

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertTitle>Peringatan</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <form className="card" onSubmit={handleUpload} style={{ marginBottom: 20 }}>
          <h3 className="section-title">Tambah Dokumen ke Korpus</h3>
          <div className="form-grid" style={{ marginBottom: 12 }}>
            <div>
              <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Berkas (PDF/DOCX/TXT)</label>
              <input
                ref={fileInputRef}
                type="file"
                className="input"
                accept=".pdf,.docx,.txt"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </div>
            <div>
              <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Judul Sumber</label>
              <input
                type="text"
                className="input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Opsional (otomatis dari metadata)"
              />
            </div>
            <div>
              <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Penulis (pisahkan koma)</label>
              <input
                type="text"
                className="input"
                value={authors}
                onChange={(e) => setAuthors(e.target.value)}
                placeholder="mis. Budi Santoso, Siti Aminah"
              />
            </div>
            <div>
              <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Tahun Terbit</label>
              <input type="number" className="input" value={year} onChange={(e) => setYear(e.target.value)} placeholder="2024" />
            </div>
            <div>
              <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>DOI</label>
              <input type="text" className="input" value={doi} onChange={(e) => setDoi(e.target.value)} placeholder="10.xxxx/..." />
            </div>
            <div>
              <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>URL Sumber</label>
              <input type="url" className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />
            </div>
            <div>
              <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Tipe Sumber</label>
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
          <div className="empty-state">
            <Database size={26} color="var(--text-muted)" />
            <div style={{ fontWeight: 600 }}>Korpus lokal masih kosong</div>
            <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>
              Unggah dokumen referensi di atas atau panen dari <Link to="/repositories">Repositori Akademik (OAI-PMH)</Link>.
            </div>
          </div>
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
                      <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        {d.filename} {d.doi ? `· DOI: ${d.doi}` : ""}
                      </div>
                    </td>
                    <td>
                      {(d.authors || []).join(", ") || "-"}
                      {d.year ? ` (${d.year})` : ""}
                    </td>
                    <td>{d.source_type}</td>
                    <td>
                      <span className="badge badge-EXCLUDED">{d.access_status}</span>
                    </td>
                    <td className="num">{d.word_count.toLocaleString("id-ID")}</td>
                    <td>
                      <button type="button" className="btn btn-danger" onClick={() => setPendingDelete(d)}>
                        <Trash2 size={14} /> Hapus
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <AlertDialog open={pendingDelete !== null} onOpenChange={(open) => !open && setPendingDelete(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Hapus Sumber dari Korpus Lokal?</AlertDialogTitle>
              <AlertDialogDescription>
                Sumber <strong>{pendingDelete?.title || pendingDelete?.filename}</strong> beserta indeks sidik jarinya akan
                dihapus dari korpus pembanding lokal.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Batal</AlertDialogCancel>
              <AlertDialogAction onClick={confirmDelete}>Ya, Hapus Sumber</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </BlurFade>
  );
};
