import React, { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, FilePlus2, FileSearch2, Search } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { BlurFade } from "@/components/ui/blur-fade";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiFetch } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { AiClassificationBadge, ModeBadge, similarityToneClass } from "../components/StatusBadge";
import { CheckMode, CheckSummary } from "../types";

interface HistoryPageProps {
  lockedMode?: CheckMode;
  pageTitle?: string;
  pageDescription?: string;
}

const STATUS_ID: Record<string, string> = {
  COMPLETED: "Selesai",
  PROCESSING: "Diproses",
  QUEUED: "Antrean",
  FAILED: "Gagal",
};

export const HistoryPage: React.FC<HistoryPageProps> = ({
  lockedMode,
  pageTitle,
  pageDescription,
}) => {
  const [searchParams] = useSearchParams();
  const [checks, setChecks] = useState<CheckSummary[] | null>(null);
  const [search, setSearch] = useState("");
  const [modeFilter, setModeFilter] = useState<string>(lockedMode || searchParams.get("mode") || "ALL");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (lockedMode) setModeFilter(lockedMode);
  }, [lockedMode]);

  useEffect(() => {
    const qs = lockedMode ? `?mode=${lockedMode}` : "";
    setChecks(null);
    apiFetch<CheckSummary[]>(`/checks${qs}`)
      .then(setChecks)
      .catch((err: Error) => setError(err.message));
  }, [lockedMode]);

  const filtered = useMemo(() => {
    if (!checks) return [];
    const q = search.trim().toLowerCase();
    return checks.filter((chk) => {
      const m = chk.mode || "PLAGIARISM_ONLY";
      if (modeFilter !== "ALL" && m !== modeFilter) return false;
      if (!q) return true;
      const hay = `${chk.report_number} ${chk.document_title || ""} ${chk.document_filename || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [checks, search, modeFilter]);

  const title =
    pageTitle ||
    (lockedMode === "PLAGIARISM_ONLY"
      ? "Daftar Deteksi Plagiasi"
      : lockedMode === "AI_ONLY"
      ? "Daftar Deteksi Tulisan AI"
      : lockedMode === "COMBINED"
      ? "Daftar Laporan Gabungan"
      : "Riwayat Pemeriksaan");

  const desc =
    pageDescription ||
    (lockedMode === "PLAGIARISM_ONLY"
      ? "Seluruh pemeriksaan kemiripan naskah terhadap korpus lokal dan sumber terbuka."
      : lockedMode === "AI_ONLY"
      ? "Seluruh pemeriksaan indikasi pola penulisan AI secara lokal."
      : lockedMode === "COMBINED"
      ? "Pemeriksaan lengkap yang menyajikan laporan plagiasi dan deteksi AI secara terpisah."
      : "Telusuri seluruh riwayat pemeriksaan plagiasi, deteksi AI, dan laporan gabungan.");

  const newCheckTarget = lockedMode ? `/new-check?mode=${lockedMode}` : "/new-check";

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <PageHeader
          title={title}
          description={desc}
          actions={
            <Button asChild>
              <Link to={newCheckTarget}>
                <FilePlus2 className="size-4" data-icon="inline-start" aria-hidden="true" />
                <span>Pemeriksaan Baru</span>
              </Link>
            </Button>
          }
        />

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Gagal memuat riwayat</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Filter Bar */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari judul dokumen atau nomor laporan..."
              className="pl-9"
              aria-label="Cari riwayat pemeriksaan"
            />
          </div>

          {!lockedMode && (
            <div className="flex flex-wrap items-center gap-1.5">
              {(
                [
                  { id: "ALL", label: "Semua Mode" },
                  { id: "PLAGIARISM_ONLY", label: "Plagiasi" },
                  { id: "AI_ONLY", label: "Deteksi AI" },
                  { id: "COMBINED", label: "Gabungan" },
                ] as const
              ).map((tab) => (
                <Button
                  key={tab.id}
                  type="button"
                  size="sm"
                  variant={modeFilter === tab.id ? "default" : "outline"}
                  onClick={() => setModeFilter(tab.id)}
                >
                  {tab.label}
                </Button>
              ))}
            </div>
          )}
        </div>

        <Card className="shadow-none">
          <CardContent className="p-0">
            {!checks ? (
              <div className="flex flex-col gap-3 p-6">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
                <FileSearch2 className="size-8 text-muted-foreground" aria-hidden="true" />
                <div className="flex flex-col gap-1">
                  <p className="text-sm font-semibold text-foreground">Belum ada data pemeriksaan yang cocok</p>
                  <p className="text-xs text-muted-foreground">
                    Unggah dokumen baru atau ubah kata kunci pencarian di atas.
                  </p>
                </div>
                <Button size="sm" variant="outline" asChild>
                  <Link to={newCheckTarget}>Buat Pemeriksaan Baru</Link>
                </Button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>No. Laporan</TableHead>
                      <TableHead>Dokumen</TableHead>
                      <TableHead>Mode</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Indeks Kemiripan</TableHead>
                      <TableHead>Indikasi Pola AI</TableHead>
                      <TableHead>Waktu</TableHead>
                      <TableHead className="text-right">Aksi</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((chk) => {
                      const m = chk.mode || "PLAGIARISM_ONLY";
                      const si = Number((chk.metrics as any)?.similarity_index ?? 0);
                      const aiRep = chk.ai_report;
                      return (
                        <TableRow key={chk.id}>
                          <TableCell className="font-mono text-xs font-medium">{chk.report_number}</TableCell>
                          <TableCell className="max-w-[260px]">
                            <div className="truncate font-medium text-foreground">
                              {chk.document_title || chk.document_filename || "Tanpa Judul"}
                            </div>
                            <div className="truncate text-xs text-muted-foreground">{chk.document_filename}</div>
                          </TableCell>
                          <TableCell>
                            <ModeBadge mode={m} />
                          </TableCell>
                          <TableCell>
                            <Badge variant={chk.status === "FAILED" ? "destructive" : "secondary"}>
                              {STATUS_ID[chk.status] || chk.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-semibold tabular-nums">
                            {m === "AI_ONLY" ? (
                              <span className="text-xs font-normal text-muted-foreground">Tidak Dijalankan</span>
                            ) : chk.status === "COMPLETED" ? (
                              <span className={similarityToneClass(si)}>{si.toFixed(1)}%</span>
                            ) : (
                              "-"
                            )}
                          </TableCell>
                          <TableCell>
                            {aiRep ? (
                              <div className="flex flex-wrap items-center gap-1.5">
                                <AiClassificationBadge
                                  classification={aiRep.classification}
                                  label={
                                    aiRep.ai_likelihood_pct !== null
                                      ? `${aiRep.classification_label} (${aiRep.ai_likelihood_pct.toFixed(0)}%)`
                                      : aiRep.classification_label
                                  }
                                />
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">Tidak Dijalankan</span>
                            )}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                            {new Date(chk.created_at).toLocaleDateString("id-ID")}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button size="sm" variant="outline" asChild>
                              <Link to={`/reports/${chk.id}`}>
                                <span>Buka</span>
                                <ArrowRight className="size-3.5" data-icon="inline-end" aria-hidden="true" />
                              </Link>
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </BlurFade>
  );
};
