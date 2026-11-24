import React, { useEffect, useState } from "react";
import { Trash2, Download } from "lucide-react";
import { apiFetch, downloadProtectedFile } from "../api/client";
import { DocumentItem } from "../types";

export const DocumentsPage: React.FC = () => {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDocs = () => {
    setLoading(true);
    apiFetch<DocumentItem[]>("/documents?role=SUBMISSION")
      .then(setDocs)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDocs();
  }, []);

  const handleDelete = async (doc: DocumentItem) => {
    if (!window.confirm(`Hapus dokumen "${doc.filename}" beserta seluruh hasil ekstraksi dan laporannya secara permanen?`)) {
      return;
    }
    try {
      await apiFetch(`/documents/${doc.id}`, { method: "DELETE" });
      loadDocs();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Pustaka Dokumen</h2>
          <p className="page-desc">Kelola dokumen naskah yang pernah diunggah. Penghapusan akan membersihkan seluruh data turunan.</p>
        </div>
      </div>

      {error && <div className="notice notice-warn">{error}</div>}
      {loading ? (
        <div className="card">Memuat pustaka dokumen...</div>
      ) : docs.length === 0 ? (
        <div className="card">Belum ada data dokumen yang diunggah.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nama Berkas</th>
                <th>Tipe</th>
                <th>Bahasa</th>
                <th className="num">Halaman</th>
                <th className="num">Kata</th>
                <th>Ekstraksi</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>
                    <strong>{d.filename}</strong>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{new Date(d.created_at).toLocaleString("id-ID")}</div>
                  </td>
                  <td>{d.file_type.toUpperCase()}</td>
                  <td>{d.language}</td>
                  <td className="num">{d.page_count}</td>
                  <td className="num">{d.word_count.toLocaleString("id-ID")}</td>
                  <td>{d.extraction_method} ({Math.round(d.extraction_confidence * 100)}%)</td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        type="button"
                        className="btn"
                        onClick={() => downloadProtectedFile(`/documents/${d.id}/file`, d.filename)}
                      >
                        <Download size={14} /> Unduh
                      </button>
                      <button type="button" className="btn btn-danger" onClick={() => handleDelete(d)}>
                        <Trash2 size={14} /> Hapus
                      </button>
                    </div>
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
