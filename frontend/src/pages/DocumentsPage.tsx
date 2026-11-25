import React, { useEffect, useState } from "react";
import { Download, FolderOpen, Search, Trash2 } from "lucide-react";
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
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiFetch, downloadProtectedFile } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { DocumentItem } from "../types";

export const DocumentsPage: React.FC = () => {
  const [docs, setDocs] = useState<DocumentItem[] | null>(null);
  const [search, setSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<DocumentItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    apiFetch<DocumentItem[]>("/documents?role=SUBMISSION")
      .then(setDocs)
      .catch((err: Error) => setError(err.message));
  };

  useEffect(() => {
    load();
  }, []);

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      await apiFetch(`/documents/${pendingDelete.id}`, { method: "DELETE" });
      setPendingDelete(null);
      load();
    } catch (err: any) {
      setError(err.message);
      setPendingDelete(null);
    }
  };

  const filtered = (docs || []).filter((d) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return `${d.title || ""} ${d.filename}`.toLowerCase().includes(q);
  });

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Pustaka Dokumen"
          description="Daftar seluruh naskah yang pernah diunggah untuk diperiksa kemiripan maupun pola tulisan AI."
        />

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Terjadi kendala</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="relative w-full sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari judul atau nama berkas..."
            className="pl-9"
            aria-label="Cari dokumen"
          />
        </div>

        <Card className="shadow-none">
          <CardContent className="p-0">
            {!docs ? (
              <div className="flex flex-col gap-3 p-6">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
                <FolderOpen className="size-8 text-muted-foreground" aria-hidden="true" />
                <p className="text-sm font-medium text-foreground">Belum ada naskah di pustaka</p>
                <p className="text-xs text-muted-foreground">Unggah naskah melalui menu Pemeriksaan Baru.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Judul &amp; Nama Berkas</TableHead>
                      <TableHead>Format</TableHead>
                      <TableHead className="text-right">Halaman</TableHead>
                      <TableHead className="text-right">Kata</TableHead>
                      <TableHead>Diunggah</TableHead>
                      <TableHead className="text-right">Aksi</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell className="max-w-[320px]">
                          <div className="truncate font-medium text-foreground">{d.title || d.filename}</div>
                          <div className="truncate text-xs text-muted-foreground">{d.filename}</div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">{d.file_type.toUpperCase()}</Badge>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{d.page_count}</TableCell>
                        <TableCell className="text-right tabular-nums">{d.word_count.toLocaleString("id-ID")}</TableCell>
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          {new Date(d.created_at).toLocaleDateString("id-ID")}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1.5">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => downloadProtectedFile(`/documents/${d.id}/file`, d.filename)}
                              aria-label={`Unduh ${d.filename}`}
                            >
                              <Download className="size-3.5" />
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => setPendingDelete(d)}
                              aria-label={`Hapus ${d.filename}`}
                            >
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
              <AlertDialogTitle>Hapus Dokumen?</AlertDialogTitle>
              <AlertDialogDescription>
                Menghapus <strong>{pendingDelete?.filename}</strong> juga menghapus riwayat pemeriksaan terkait berkas ini.
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
