import React, { useEffect, useState } from "react";
import { BookMarked, Plus, CheckCircle2, DownloadCloud, Trash2, RefreshCw } from "lucide-react";
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
import { apiFetch } from "../api/client";
import { OAIRepositoryItem } from "../types";

export const RepositoriesPage: React.FC = () => {
  const [repos, setRepos] = useState<OAIRepositoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [repoType, setRepoType] = useState<"ojs" | "dspace" | "eprints" | "other">("ojs");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<OAIRepositoryItem | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadRepos = () => {
    setLoading(true);
    apiFetch<OAIRepositoryItem[]>("/oai/repositories")
      .then((res) => {
        setRepos(res);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadRepos();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !baseUrl.trim()) return;
    setError(null);
    setMessage(null);
    try {
      await apiFetch("/oai/repositories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), base_url: baseUrl.trim(), repo_type: repoType }),
      });
      setName("");
      setBaseUrl("");
      setMessage("Repositori OAI-PMH berhasil ditambahkan.");
      loadRepos();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleVerify = async (id: string) => {
    setBusyId(id);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch<{ identify?: { repositoryName?: string } }>(`/oai/repositories/${id}/verify`, {
        method: "POST",
      });
      setMessage(`Verifikasi berhasil: ${res.identify?.repositoryName || "OAI-PMH valid"}.`);
      loadRepos();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const handleHarvest = async (id: string) => {
    setBusyId(id);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch<{ summary: { records_seen?: number; records_harvested?: number; fulltext_indexed?: number } }>(
        `/oai/repositories/${id}/harvest`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ max_records: 15, download_pdfs: true }),
        }
      );
      const seen = res.summary?.records_harvested ?? res.summary?.records_seen ?? 0;
      setMessage(`Panen selesai: ${seen} rekaman diperiksa, ${res.summary?.fulltext_indexed ?? 0} full-text terindeks.`);
      loadRepos();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setBusyId(pendingDelete.id);
    try {
      await apiFetch(`/oai/repositories/${pendingDelete.id}`, { method: "DELETE" });
      setPendingDelete(null);
      loadRepos();
    } catch (err: any) {
      setError(err.message);
      setPendingDelete(null);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <BlurFade duration={0.22}>
      <div>
        <div className="page-header">
          <div>
            <h2 className="page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <BookMarked size={21} /> Repositori Akademik (OAI-PMH)
            </h2>
            <p className="page-desc">
              Daftarkan endpoint OAI-PMH resmi jurnal OJS, DSpace, atau EPrints kampus untuk memperkaya korpus lokal secara legal.
            </p>
          </div>
          <button type="button" className="btn" onClick={loadRepos}>
            <RefreshCw size={14} /> Muat Ulang
          </button>
        </div>

        {message && <div className="notice">{message}</div>}
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertTitle>Peringatan OAI-PMH</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <form className="card" onSubmit={handleAdd} style={{ marginBottom: 18 }}>
          <h3 className="section-title">Tambah Repositori OAI-PMH</h3>
          <div className="form-grid" style={{ marginBottom: 12 }}>
            <div>
              <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Nama Repositori / Jurnal</label>
              <input
                className="input"
                placeholder="Mis. Jurnal Informatika Kampus (OJS)"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div>
              <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Base URL OAI-PMH Publik</label>
              <input
                className="input"
                placeholder="https://jurnal.contoh.ac.id/index.php/jif/oai"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                required
              />
            </div>
            <div>
              <label style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Platform</label>
              <select className="input" value={repoType} onChange={(e) => setRepoType(e.target.value as any)}>
                <option value="ojs">OJS (Open Journal Systems)</option>
                <option value="dspace">DSpace</option>
                <option value="eprints">EPrints</option>
                <option value="other">Lainnya</option>
              </select>
            </div>
          </div>
          <button type="submit" className="btn btn-primary">
            <Plus size={15} /> Daftarkan Repositori
          </button>
        </form>

        <div className="card">
          <h3 className="section-title">Daftar Repositori Terdaftar ({repos.length})</h3>
          {loading ? (
            <Skeleton className="h-24 w-full" />
          ) : repos.length === 0 ? (
            <div className="empty-state" style={{ padding: "24px 16px" }}>
              <BookMarked size={24} color="var(--text-muted)" />
              <div style={{ fontWeight: 600 }}>Belum ada repositori OAI-PMH terdaftar</div>
              <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Tambahkan endpoint OJS, DSpace, atau EPrints di atas untuk mulai memanen metadata &amp; PDF Open Access.
              </div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Repositori</th>
                    <th>Tipe</th>
                    <th>Status</th>
                    <th className="num">Rekaman</th>
                    <th className="num">Full-Text</th>
                    <th>Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {repos.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <strong>{r.identified_name || r.name}</strong>
                        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{r.base_url}</div>
                        {r.last_error && <div style={{ fontSize: 11.5, color: "var(--exact-text)" }}>{r.last_error}</div>}
                      </td>
                      <td>{r.repo_type.toUpperCase()}</td>
                      <td>
                        <span
                          className={`badge ${
                            r.status === "VERIFIED" ? "badge-SUCCESS" : r.status === "ERROR" ? "badge-EXACT" : "badge-neutral"
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="num">{r.records_harvested}</td>
                      <td className="num">{r.fulltext_indexed}</td>
                      <td>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          <button
                            type="button"
                            className="btn"
                            style={{ fontSize: 12, minHeight: 30, padding: "4px 8px" }}
                            disabled={busyId === r.id}
                            onClick={() => handleVerify(r.id)}
                          >
                            <CheckCircle2 size={12} /> Verifikasi
                          </button>
                          <button
                            type="button"
                            className="btn btn-primary"
                            style={{ fontSize: 12, minHeight: 30, padding: "4px 8px" }}
                            disabled={busyId === r.id}
                            onClick={() => handleHarvest(r.id)}
                          >
                            <DownloadCloud size={12} /> Panen
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger"
                            style={{ fontSize: 12, minHeight: 30, padding: "4px 8px" }}
                            disabled={busyId === r.id}
                            onClick={() => setPendingDelete(r)}
                            aria-label={`Hapus ${r.name}`}
                          >
                            <Trash2 size={12} />
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

        <AlertDialog open={pendingDelete !== null} onOpenChange={(open) => !open && setPendingDelete(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Hapus Repositori OAI-PMH?</AlertDialogTitle>
              <AlertDialogDescription>
                Entri repositori <strong>{pendingDelete?.name}</strong> ({pendingDelete?.base_url}) akan dihapus dari daftar
                harvester. Dokumen yang sudah terindeks di korpus lokal tidak ikut terhapus.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Batal</AlertDialogCancel>
              <AlertDialogAction onClick={confirmDelete}>Ya, Hapus</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </BlurFade>
  );
};
