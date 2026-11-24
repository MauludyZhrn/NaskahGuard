import React, { useEffect, useState } from "react";
import { Trash2, Download, FolderOpen } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, downloadProtectedFile } from "../api/client";
import { DocumentItem } from "../types";

export const DocumentsPage: React.FC = () => {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<DocumentItem | null>(null);

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

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      await apiFetch(`/documents/${pendingDelete.id}`, { method: "DELETE" });
      setPendingDelete(null);
      loadDocs();
    } catch (e: any) {
      setError(e.message);
      setPendingDelete(null);
    }
  };

  return (
    <BlurFade duration={0.22}>
      <div>
        <div className="page-header">
          <div>
            <h2 className="page-title">Pustaka Dokumen</h2>
            <p className="page-desc">
              Kelola dokumen naskah yang pernah diunggah. Penghapusan akan membersihkan seluruh data turunan secara permanen.
            </p>
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertTitle>Terjadi kesalahan</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {loading ? (
          <div className="card">
            <Skeleton className="h-6 w-48 mb-3" />
            <Skeleton className="h-28 w-full" />
          </div>
        ) : docs.length === 0 ? (
          <div className="empty-state">
            <FolderOpen size={26} color="var(--text-muted)" />
            <div style={{ fontWeight: 600 }}>Belum ada dokumen naskah</div>
            <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>
              Unggah naskah PDF, DOCX, atau TXT melalui menu <Link to="/new-check">Pemeriksaan Baru</Link>.
            </div>
          </div>
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
                      <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        {new Date(d.created_at).toLocaleString("id-ID")}
                      </div>
                    </td>
                    <td>{d.file_type.toUpperCase()}</td>
                    <td>{d.language}</td>
                    <td className="num">{d.page_count}</td>
                    <td className="num">{d.word_count.toLocaleString("id-ID")}</td>
                    <td>
                      {d.extraction_method} ({Math.round(d.extraction_confidence * 100)}%)
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 6 }}>
                        <button
                          type="button"
                          className="btn"
                          onClick={() => downloadProtectedFile(`/documents/${d.id}/file`, d.filename)}
                        >
                          <Download size={14} /> Unduh
                        </button>
                        <button type="button" className="btn btn-danger" onClick={() => setPendingDelete(d)}>
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

        <AlertDialog open={pendingDelete !== null} onOpenChange={(open) => !open && setPendingDelete(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Hapus Dokumen Secara Permanen?</AlertDialogTitle>
              <AlertDialogDescription>
                Dokumen <strong>{pendingDelete?.filename}</strong> beserta berkas asli, segmen ekstraksi, dan laporan
                kemiripan terkait akan dihapus dari penyimpanan lokal.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Batal</AlertDialogCancel>
              <AlertDialogAction onClick={confirmDelete}>Ya, Hapus Permanen</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </BlurFade>
  );
};
