import React, { useEffect, useState } from "react";
import { BookMarked, CheckCircle2, DownloadCloud, Plus, Trash2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { Badge } from "@/components/ui/badge";
import { BlurFade } from "@/components/ui/blur-fade";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiFetch } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { OAIRepositoryItem } from "../types";

export const RepositoriesPage: React.FC = () => {
  const [repos, setRepos] = useState<OAIRepositoryItem[] | null>(null);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<OAIRepositoryItem | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadRepos = () => {
    apiFetch<OAIRepositoryItem[]>("/oai/repositories")
      .then(setRepos)
      .catch((err: Error) => setError(err.message));
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
        body: JSON.stringify({ name: name.trim(), base_url: baseUrl.trim(), repo_type: "OAI-PMH" }),
      });
      setName("");
      setBaseUrl("");
      setMessage("Repositori akademik OAI-PMH berhasil ditambahkan.");
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
      setMessage(`Verifikasi berhasil: ${res.identify?.repositoryName || "Endpoint OAI-PMH valid"}.`);
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
      const res = await apiFetch<{ summary: { records_seen?: number; fulltext_indexed?: number } }>(
        `/oai/repositories/${id}/harvest`,
        { method: "POST" }
      );
      setMessage(
        `Panen selesai: ${res.summary?.records_seen ?? 0} entri ditemukan, ${res.summary?.fulltext_indexed ?? 0} dokumen penuh diindeks.`
      );
      loadRepos();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    await apiFetch(`/oai/repositories/${pendingDelete.id}`, { method: "DELETE" });
    setPendingDelete(null);
    loadRepos();
  };

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Repositori Akademik (OAI-PMH)"
          description="Hubungkan repositori skripsi, tesis, dan jurnal institusi Indonesia (seperti EPrints atau OJS) untuk memperkaya korpus pembanding lokal."
        />

        {message && (
          <Alert>
            <CheckCircle2 className="size-4" />
            <AlertTitle>Informasi Repositori</AlertTitle>
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Terjadi kendala</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Card className="shadow-none">
          <CardHeader>
            <CardTitle className="text-base">Daftarkan Endpoint OAI-PMH</CardTitle>
            <CardDescription>Masukkan nama kampus/jurnal dan URL endpoint OAI-PMH yang valid.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAdd} className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="repo-name">Nama Repositori</Label>
                <Input id="repo-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Misal: Repositori Universitas X" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="repo-url">URL OAI-PMH</Label>
                <Input id="repo-url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://repository.kampus.ac.id/cgi/oai2" />
              </div>
              <div className="flex items-end">
                <Button type="submit" disabled={!name.trim() || !baseUrl.trim()} className="w-full">
                  <Plus className="size-4" data-icon="inline-start" aria-hidden="true" />
                  <span>Simpan Repositori</span>
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardContent className="p-0">
            {!repos ? (
              <div className="p-6"><Skeleton className="h-32 w-full" /></div>
            ) : repos.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
                <BookMarked className="size-8 text-muted-foreground" aria-hidden="true" />
                <p className="text-sm font-medium text-foreground">Belum ada repositori OAI-PMH terdaftar</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Repositori</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Terpanen / Diindeks</TableHead>
                      <TableHead className="text-right">Aksi</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {repos.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell>
                          <div className="font-medium text-foreground">{r.name}</div>
                          <div className="text-xs text-muted-foreground">{r.base_url}</div>
                        </TableCell>
                        <TableCell><Badge variant="secondary">{r.status}</Badge></TableCell>
                        <TableCell className="text-right tabular-nums">
                          {r.records_harvested} / {r.fulltext_indexed}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1.5">
                            <Button size="sm" variant="outline" disabled={busyId === r.id} onClick={() => handleVerify(r.id)}>
                              Uji
                            </Button>
                            <Button size="sm" variant="outline" disabled={busyId === r.id} onClick={() => handleHarvest(r.id)}>
                              <DownloadCloud className="size-3.5" data-icon="inline-start" />
                              <span>Panen</span>
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setPendingDelete(r)}>
                              <Trash2 className="size-3.5 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        <AlertDialog open={Boolean(pendingDelete)} onOpenChange={(open) => !open && setPendingDelete(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Hapus Repositori Akademik?</AlertDialogTitle>
              <AlertDialogDescription>
                Menghapus <strong>{pendingDelete?.name}</strong> menghentikan penarikan indeks dari repositori tersebut.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Batal</AlertDialogCancel>
              <AlertDialogAction onClick={confirmDelete}>Hapus</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </BlurFade>
  );
};
