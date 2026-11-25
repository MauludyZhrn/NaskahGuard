import React, { useEffect, useRef, useState } from "react";
import { Database, Plus, Search, Trash2 } from "lucide-react";
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
import { DocumentItem } from "../types";

interface CorpusStats {
  total_documents: number;
  total_words: number;
  total_fingerprints: number;
}

export const CorpusPage: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [docs, setDocs] = useState<DocumentItem[] | null>(null);
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [search, setSearch] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [authors, setAuthors] = useState("");
  const [year, setYear] = useState("");
  const [doi, setDoi] = useState("");
  const [url, setUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<DocumentItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    apiFetch<DocumentItem[]>("/corpus").then(setDocs).catch((e: Error) => setError(e.message));
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
      fd.append("source_type", "LOCAL_CORPUS");
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

  const filtered = (docs || []).filter((d) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return `${d.title || ""} ${d.filename} ${(d.authors || []).join(" ")}`.toLowerCase().includes(q);
  });

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Korpus Sumber Pembanding"
          description="Kelola koleksi dokumen pembanding lokal agar pemeriksaan berjalan cepat dan tidak bergantung internet."
          badge={
            stats ? (
              <Badge variant="secondary" className="tabular-nums">
                {stats.total_documents} sumber · {stats.total_words.toLocaleString("id-ID")} kata
              </Badge>
            ) : null
          }
        />

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Operasi korpus gagal</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Card className="shadow-none">
          <CardHeader>
            <CardTitle className="text-base">Tambahkan Sumber Lokal Baru</CardTitle>
            <CardDescription>Unggah jurnal, skripsi arsip, atau buku referensi (PDF, DOCX, TXT).</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleUpload} className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="flex flex-col gap-1.5 md:col-span-3">
                <Label htmlFor="corpus-file">Berkas Sumber</Label>
                <Input
                  id="corpus-file"
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,.html,.xml"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="corpus-title">Judul Referensi</Label>
                <Input id="corpus-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Judul karya ilmiah" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="corpus-authors">Penulis</Label>
                <Input id="corpus-authors" value={authors} onChange={(e) => setAuthors(e.target.value)} placeholder="Nama penulis" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="corpus-year">Tahun</Label>
                <Input id="corpus-year" value={year} onChange={(e) => setYear(e.target.value)} placeholder="2024" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="corpus-doi">DOI (Opsional)</Label>
                <Input id="corpus-doi" value={doi} onChange={(e) => setDoi(e.target.value)} placeholder="10.xxxx/..." />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="corpus-url">URL Sumber (Opsional)</Label>
                <Input id="corpus-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />
              </div>
              <div className="flex items-end">
                <Button type="submit" disabled={uploading || !file} className="w-full">
                  <Plus className="size-4" data-icon="inline-start" aria-hidden="true" />
                  <span>{uploading ? "Mengindeks..." : "Tambahkan ke Korpus"}</span>
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <div className="relative w-full sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari judul sumber atau penulis..."
            className="pl-9"
          />
        </div>

        <Card className="shadow-none">
          <CardContent className="p-0">
            {!docs ? (
              <div className="p-6 flex flex-col gap-3">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
                <Database className="size-8 text-muted-foreground" aria-hidden="true" />
                <p className="text-sm font-medium text-foreground">Korpus sumber masih kosong</p>
                <p className="text-xs text-muted-foreground">Tambahkan dokumen referensi atau panen repositori akademik OAI-PMH.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Judul &amp; Penulis</TableHead>
                      <TableHead>Sumber</TableHead>
                      <TableHead className="text-right">Kata</TableHead>
                      <TableHead className="text-right">Aksi</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell className="max-w-[360px]">
                          <div className="truncate font-medium text-foreground">{d.title || d.filename}</div>
                          <div className="truncate text-xs text-muted-foreground">
                            {(d.authors || []).join(", ") || d.filename}
                            {d.year ? ` (${d.year})` : ""}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{d.source_type}</Badge>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{d.word_count.toLocaleString("id-ID")}</TableCell>
                        <TableCell className="text-right">
                          <Button type="button" size="sm" variant="outline" onClick={() => setPendingDelete(d)}>
                            <Trash2 className="size-3.5 text-destructive" />
                          </Button>
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
              <AlertDialogTitle>Hapus Dokumen Korpus?</AlertDialogTitle>
              <AlertDialogDescription>
                Dokumen <strong>{pendingDelete?.title || pendingDelete?.filename}</strong> tidak lagi dibandingkan pada pemeriksaan baru.
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
