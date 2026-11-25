import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  DownloadCloud,
  Eye,
  ExternalLink,
  FlaskConical,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  ScrollText,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { BlurFade } from "@/components/ui/blur-fade";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiFetch } from "../api/client";
import { OAIWizardView } from "../components/OAIWizardView";
import { PageHeader } from "../components/PageHeader";
import {
  OAIHarvestLogItem,
  OAIHarvestRecordItem,
  OAIRepositoryItem,
  OAISampleRecord,
} from "../types";

function recordStatusBadge(status: string) {
  switch (status) {
    case "INDEXED":
      return <Badge variant="default">Diindeks</Badge>;
    case "PDF_INACCESSIBLE":
      return <Badge variant="destructive">PDF Tidak Dapat Diakses</Badge>;
    case "FAILED":
      return <Badge variant="destructive">Gagal</Badge>;
    case "DUPLICATE":
      return <Badge variant="outline">Duplikat</Badge>;
    case "DELETED":
      return <Badge variant="outline">Dihapus di Sumber</Badge>;
    case "PDF_FOUND":
      return <Badge variant="secondary">URL PDF Ditemukan</Badge>;
    default:
      return <Badge variant="secondary">Metadata Saja</Badge>;
  }
}

export const RepositoryDetailPage: React.FC = () => {
  const { repoId } = useParams<{ repoId: string }>();
  const navigate = useNavigate();

  const [repo, setRepo] = useState<OAIRepositoryItem | null>(null);
  const [records, setRecords] = useState<OAIHarvestRecordItem[]>([]);
  const [recordsTotal, setRecordsTotal] = useState(0);
  const [recordFilter, setRecordFilter] = useState("ALL");
  const [logs, setLogs] = useState<OAIHarvestLogItem[]>([]);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Harvest options
  const [maxRecords, setMaxRecords] = useState("15");
  const [selectedPrefix, setSelectedPrefix] = useState("oai_dc");
  const [selectedSet, setSelectedSet] = useState("");
  const [previewRecords, setPreviewRecords] = useState<OAISampleRecord[] | null>(null);

  const loadAll = useCallback(async () => {
    if (!repoId) return;
    try {
      const [repoData, recData, logData] = await Promise.all([
        apiFetch<OAIRepositoryItem>(`/oai/repositories/${repoId}`),
        apiFetch<{ total: number; items: OAIHarvestRecordItem[] }>(
          `/oai/repositories/${repoId}/records?status=${encodeURIComponent(recordFilter)}&limit=50`
        ),
        apiFetch<OAIHarvestLogItem[]>(`/oai/repositories/${repoId}/logs?limit=80`),
      ]);
      setRepo(repoData);
      setSelectedPrefix(repoData.metadata_prefix || "oai_dc");
      setSelectedSet(repoData.selected_set || "");
      setRecords(recData.items);
      setRecordsTotal(recData.total);
      setLogs(logData);
    } catch (err: any) {
      setError(err.message);
    }
  }, [repoId, recordFilter]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleSaveConfig = async () => {
    if (!repo) return;
    setBusyAction("save-config");
    setError(null);
    setMessage(null);
    try {
      await apiFetch(`/oai/repositories/${repo.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metadata_prefix: selectedPrefix.trim() || "oai_dc",
          selected_set: selectedSet.trim(),
        }),
      });
      setMessage("Pilihan format metadata dan koleksi disimpan.");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyAction(null);
    }
  };

  const handleVerify = async () => {
    if (!repo) return;
    setBusyAction("verify");
    setError(null);
    setMessage(null);
    try {
      await apiFetch(`/oai/repositories/${repo.id}/verify`, { method: "POST" });
      setMessage("Uji koneksi 8 tahap selesai dan tersimpan.");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
      await loadAll();
    } finally {
      setBusyAction(null);
    }
  };

  const handlePreview = async () => {
    if (!repo) return;
    setBusyAction("preview");
    setError(null);
    try {
      const res = await apiFetch<{ records: OAISampleRecord[] }>(`/oai/repositories/${repo.id}/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metadata_prefix: selectedPrefix.trim() || "oai_dc",
          set_spec: selectedSet.trim() || null,
          limit: 5,
        }),
      });
      setPreviewRecords(res.records);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyAction(null);
    }
  };

  const handleHarvest = async (mode: "start" | "resume") => {
    if (!repo) return;
    setBusyAction(mode);
    setError(null);
    setMessage(null);
    try {
      const endpoint =
        mode === "resume"
          ? `/oai/repositories/${repo.id}/resume`
          : `/oai/repositories/${repo.id}/harvest`;
      const res = await apiFetch<{
        summary: { records_harvested: number; fulltext_indexed: number; metadata_only: number; failed_records?: number };
      }>(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_records: Number(maxRecords) || 15,
          download_pdfs: true,
          resume: mode === "resume",
          set_spec: selectedSet.trim() || null,
          metadata_prefix: selectedPrefix.trim() || null,
        }),
      });
      setMessage(
        `Panen selesai: ${res.summary.records_harvested} rekaman diproses, ${res.summary.fulltext_indexed} full-text diindeks, ${res.summary.metadata_only} metadata saja.`
      );
      await loadAll();
    } catch (err: any) {
      setError(err.message);
      await loadAll();
    } finally {
      setBusyAction(null);
    }
  };

  const handlePause = async () => {
    if (!repo) return;
    setBusyAction("pause");
    setError(null);
    try {
      await apiFetch(`/oai/repositories/${repo.id}/pause`, { method: "POST" });
      setMessage("Panen dijeda. Anda dapat melanjutkan kapan saja dari posisi token terakhir.");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyAction(null);
    }
  };

  const handleRetryFailed = async () => {
    if (!repo) return;
    setBusyAction("retry");
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch<{ summary: { retried: number; recovered_indexed: number; still_failed: number } }>(
        `/oai/repositories/${repo.id}/retry-failed`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ limit: 20 }),
        }
      );
      setMessage(
        `Percobaan ulang selesai: ${res.summary.retried} dicoba, ${res.summary.recovered_indexed} berhasil diindeks, ${res.summary.still_failed} masih gagal.`
      );
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyAction(null);
    }
  };

  if (!repo) {
    return (
      <div className="flex flex-col gap-4">
        <Button variant="ghost" size="sm" className="w-fit" onClick={() => navigate("/repositories")}>
          <ArrowLeft className="size-4 mr-1.5" aria-hidden="true" />
          Kembali ke Daftar Repositori
        </Button>
        {error ? (
          <Alert variant="destructive">
            <AlertCircle className="size-4" aria-hidden="true" />
            <AlertTitle>Gagal memuat repositori</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : (
          <Skeleton className="h-48 w-full" />
        )}
      </div>
    );
  }

  const funnel = repo.funnel || {
    metadata_found: repo.records_harvested,
    metadata_saved: repo.metadata_saved_count || repo.records_harvested,
    pdf_urls_found: repo.pdf_urls_found_count || 0,
    pdf_accessible: repo.pdf_accessible_count || 0,
    fulltext_extracted: repo.fulltext_extracted_count || 0,
    document_indexed: repo.fulltext_indexed,
    document_compared: 0,
    failed_records: repo.failed_records_count || 0,
  };

  const funnelSteps = [
    { label: "Metadata Ditemukan", value: funnel.metadata_found },
    { label: "Metadata Tersimpan", value: funnel.metadata_saved },
    { label: "URL PDF Ditemukan", value: funnel.pdf_urls_found },
    { label: "PDF Dapat Diakses", value: funnel.pdf_accessible },
    { label: "Full-Text Diekstrak", value: funnel.fulltext_extracted },
    { label: "Diindeks Lokal", value: funnel.document_indexed },
    { label: "Dibandingkan", value: funnel.document_compared },
  ];

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between gap-2">
          <Button variant="ghost" size="sm" onClick={() => navigate("/repositories")}>
            <ArrowLeft className="size-4" data-icon="inline-start" aria-hidden="true" />
            <span>Kembali ke Daftar Repositori</span>
          </Button>
          <Button variant="outline" size="sm" onClick={loadAll}>
            <RefreshCw className="size-3.5" data-icon="inline-start" aria-hidden="true" />
            <span>Segarkan</span>
          </Button>
        </div>

        <PageHeader
          title={repo.name}
          description={`${repo.base_url} · Platform: ${repo.platform_label || repo.repo_type} · Format: ${repo.metadata_prefix}${repo.selected_set ? ` · Koleksi: ${repo.selected_set}` : ""}`}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" disabled={Boolean(busyAction)} onClick={handleVerify}>
                {busyAction === "verify" ? (
                  <Loader2 className="size-4 animate-spin" data-icon="inline-start" aria-hidden="true" />
                ) : (
                  <FlaskConical className="size-4" data-icon="inline-start" aria-hidden="true" />
                )}
                <span>Uji Koneksi</span>
              </Button>
              <Button size="sm" disabled={Boolean(busyAction)} onClick={() => handleHarvest("start")}>
                {busyAction === "start" ? (
                  <Loader2 className="size-4 animate-spin" data-icon="inline-start" aria-hidden="true" />
                ) : (
                  <DownloadCloud className="size-4" data-icon="inline-start" aria-hidden="true" />
                )}
                <span>Mulai Panen</span>
              </Button>
              {(repo.harvest_state === "PAUSED" || repo.has_resumption_token) && (
                <Button variant="secondary" size="sm" disabled={Boolean(busyAction)} onClick={() => handleHarvest("resume")}>
                  {busyAction === "resume" ? (
                    <Loader2 className="size-4 animate-spin" data-icon="inline-start" aria-hidden="true" />
                  ) : (
                    <Play className="size-4" data-icon="inline-start" aria-hidden="true" />
                  )}
                  <span>Lanjutkan</span>
                </Button>
              )}
              <Button variant="outline" size="sm" disabled={Boolean(busyAction)} onClick={handlePause}>
                <Pause className="size-4" data-icon="inline-start" aria-hidden="true" />
                <span>Jeda</span>
              </Button>
              {funnel.failed_records > 0 && (
                <Button variant="outline" size="sm" disabled={Boolean(busyAction)} onClick={handleRetryFailed}>
                  {busyAction === "retry" ? (
                    <Loader2 className="size-4 animate-spin" data-icon="inline-start" aria-hidden="true" />
                  ) : (
                    <RotateCcw className="size-4" data-icon="inline-start" aria-hidden="true" />
                  )}
                  <span>Ulangi Gagal ({funnel.failed_records})</span>
                </Button>
              )}
            </div>
          }
        />

        {message && (
          <Alert>
            <CheckCircle2 className="size-4" aria-hidden="true" />
            <AlertTitle>Pembaruan Repositori</AlertTitle>
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="size-4" aria-hidden="true" />
            <AlertTitle>Terjadi kendala</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* 7-Stage Full-Text Acquisition Funnel */}
        <Card className="shadow-none">
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="text-base">Alur Akuisisi Metadata & Full-Text (7 Tahap)</CardTitle>
                <CardDescription>
                  Metadata OAI-PMH dipisahkan secara tegas dari dokumen full-text yang berhasil diekstrak dan diindeks ke korpus lokal.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Label htmlFor="max-rec-input" className="text-xs text-muted-foreground">
                  Maks rekaman/sesi:
                </Label>
                <Input
                  id="max-rec-input"
                  type="number"
                  min="1"
                  max="200"
                  value={maxRecords}
                  onChange={(e) => setMaxRecords(e.target.value)}
                  className="h-8 w-20 text-xs"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-7">
              {funnelSteps.map((st, idx) => (
                <div
                  key={st.label}
                  className="flex flex-col justify-between rounded-lg border border-border bg-muted/30 p-3"
                >
                  <span className="text-[11px] font-medium text-muted-foreground leading-tight">
                    {idx + 1}. {st.label}
                  </span>
                  <span className="mt-2 text-xl font-semibold tabular-nums text-foreground">
                    {st.value}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Tabs defaultValue="wizard" className="w-full">
          <TabsList className="grid w-full grid-cols-2 sm:w-auto sm:inline-grid sm:grid-cols-4">
            <TabsTrigger value="wizard">Uji Koneksi (8 Tahap)</TabsTrigger>
            <TabsTrigger value="collection">Koleksi & Pratinjau</TabsTrigger>
            <TabsTrigger value="records">Rekaman ({recordsTotal})</TabsTrigger>
            <TabsTrigger value="logs">Log Aktivitas ({logs.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="wizard" className="mt-4">
            <Card className="shadow-none">
              <CardHeader>
                <CardTitle className="text-base">Hasil Diagnostik Koneksi 8 Tahap</CardTitle>
                <CardDescription>
                  Menampilkan status HTTP, kode error OAI-PMH, dan solusi terarah untuk setiap tahap protokol.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {repo.last_test_report ? (
                  <OAIWizardView report={repo.last_test_report} showSamples />
                ) : (
                  <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                    <FlaskConical className="size-8 text-muted-foreground" aria-hidden="true" />
                    <p className="text-sm text-muted-foreground">
                      Belum ada hasil uji koneksi 8 tahap untuk repositori ini.
                    </p>
                    <Button size="sm" onClick={handleVerify} disabled={Boolean(busyAction)}>
                      Jalankan Uji Koneksi Sekarang
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="collection" className="mt-4">
            <Card className="shadow-none">
              <CardHeader>
                <CardTitle className="text-base">Pemilihan Format Metadata, Koleksi & Pratinjau</CardTitle>
                <CardDescription>
                  Pilih format metadata dan koleksi (setSpec) yang ingin dipanen, lalu periksa sampel metadata sebelum memanen penuh.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="flex flex-col gap-1.5">
                    <Label>Format Metadata (metadataPrefix)</Label>
                    {(repo.supported_formats || []).length > 0 ? (
                      <Select value={selectedPrefix} onValueChange={setSelectedPrefix}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {(repo.supported_formats || []).map((fmt) => (
                            <SelectItem key={fmt} value={fmt}>
                              {fmt}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input value={selectedPrefix} onChange={(e) => setSelectedPrefix(e.target.value)} />
                    )}
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <Label>Koleksi / Jurnal (setSpec)</Label>
                    {(repo.available_sets || []).length > 0 ? (
                      <Select
                        value={selectedSet || "__ALL__"}
                        onValueChange={(v) => setSelectedSet(v === "__ALL__" ? "" : v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Semua koleksi" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__ALL__">Semua koleksi</SelectItem>
                          {(repo.available_sets || []).map((s) => (
                            <SelectItem key={s.setSpec} value={s.setSpec}>
                              {s.setName} ({s.setSpec})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input
                        value={selectedSet}
                        onChange={(e) => setSelectedSet(e.target.value)}
                        placeholder="Kosongkan untuk semua koleksi"
                      />
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button size="sm" onClick={handleSaveConfig} disabled={Boolean(busyAction)}>
                    Simpan Pilihan Koleksi
                  </Button>
                  <Button size="sm" variant="outline" onClick={handlePreview} disabled={Boolean(busyAction)}>
                    {busyAction === "preview" ? (
                      <Loader2 className="size-4 animate-spin" data-icon="inline-start" aria-hidden="true" />
                    ) : (
                      <Eye className="size-4" data-icon="inline-start" aria-hidden="true" />
                    )}
                    <span>Pratinjau Metadata</span>
                  </Button>
                </div>

                {previewRecords && (
                  <div className="flex flex-col gap-2 pt-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Hasil Pratinjau ({previewRecords.length} rekaman)
                    </h4>
                    {previewRecords.length === 0 ? (
                      <p className="text-xs text-muted-foreground">Tidak ada rekaman ditemukan pada kombinasi format dan koleksi ini.</p>
                    ) : (
                      previewRecords.map((rec) => (
                        <div key={rec.identifier} className="rounded-lg border border-border p-3 text-xs">
                          <div className="flex items-start justify-between gap-2">
                            <span className="font-medium text-sm text-foreground">{rec.title}</span>
                            <Badge variant={rec.pdf_urls.length > 0 ? "default" : "secondary"}>
                              {rec.pdf_urls.length > 0 ? "Ada URL PDF" : "Metadata Saja"}
                            </Badge>
                          </div>
                          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground">
                            <span className="font-mono">{rec.identifier}</span>
                            {rec.authors.length > 0 && <span>{rec.authors.join(", ")}</span>}
                            {rec.year && <span>{rec.year}</span>}
                            {rec.doi && <span className="font-mono">DOI: {rec.doi}</span>}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="records" className="mt-4">
            <Card className="shadow-none">
              <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">Rekaman Terpanen</CardTitle>
                  <CardDescription>
                    Status setiap rekaman OAI-PMH, termasuk dokumen yang berhasil diindeks, metadata saja, duplikat, atau gagal unduh PDF.
                  </CardDescription>
                </div>
                <Select value={recordFilter} onValueChange={setRecordFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ALL">Semua Status</SelectItem>
                    <SelectItem value="INDEXED">Diindeks Full-Text</SelectItem>
                    <SelectItem value="METADATA_SAVED">Metadata Saja</SelectItem>
                    <SelectItem value="PDF_INACCESSIBLE">PDF Tidak Dapat Diakses</SelectItem>
                    <SelectItem value="FAILED">Gagal</SelectItem>
                    <SelectItem value="DUPLICATE">Duplikat</SelectItem>
                    <SelectItem value="DELETED">Dihapus di Sumber</SelectItem>
                  </SelectContent>
                </Select>
              </CardHeader>
              <CardContent className="p-0">
                {records.length === 0 ? (
                  <div className="py-10 text-center text-sm text-muted-foreground">
                    Belum ada rekaman untuk filter ini.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Judul & Identifier</TableHead>
                          <TableHead>Tahun / DOI</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Catatan</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {records.map((rec) => (
                          <TableRow key={rec.id}>
                            <TableCell className="max-w-[340px]">
                              <div className="font-medium text-foreground line-clamp-2">
                                {rec.title || rec.oai_identifier}
                              </div>
                              <div className="text-[11px] font-mono text-muted-foreground truncate">
                                {rec.oai_identifier}
                              </div>
                              {rec.pdf_urls[0] && (
                                <a
                                  href={rec.pdf_urls[0]}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline mt-0.5"
                                >
                                  <span>Buka URL PDF</span>
                                  <ExternalLink className="size-3" aria-hidden="true" />
                                </a>
                              )}
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              <div>{rec.year || "-"}</div>
                              {rec.doi && <div className="font-mono text-[11px]">{rec.doi}</div>}
                            </TableCell>
                            <TableCell>{recordStatusBadge(rec.status)}</TableCell>
                            <TableCell className="max-w-[260px] text-xs text-muted-foreground">
                              {rec.error_message || (rec.document_id ? "Terhubung ke korpus lokal" : "Metadata tersimpan")}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="logs" className="mt-4">
            <Card className="shadow-none">
              <CardHeader>
                <CardTitle className="text-base">Log Aktivitas & Diagnostik Panen</CardTitle>
                <CardDescription>
                  Catatan kronologis seluruh uji koneksi, negosiasi format, pemulihan token, dan panen.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {logs.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-10 text-sm text-muted-foreground">
                    <ScrollText className="size-6" aria-hidden="true" />
                    <span>Belum ada catatan aktivitas.</span>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Waktu</TableHead>
                          <TableHead>Level</TableHead>
                          <TableHead>Tahap</TableHead>
                          <TableHead>Pesan</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {logs.map((lg) => (
                          <TableRow key={lg.id}>
                            <TableCell className="text-xs text-muted-foreground whitespace-nowrap tabular-nums">
                              {lg.created_at ? new Date(lg.created_at).toLocaleString("id-ID") : "-"}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={
                                  lg.level === "ERROR"
                                    ? "destructive"
                                    : lg.level === "WARN"
                                      ? "secondary"
                                      : "outline"
                                }
                              >
                                {lg.level}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-xs font-mono text-muted-foreground">
                              {lg.stage}
                              {lg.error_code ? ` (${lg.error_code})` : ""}
                            </TableCell>
                            <TableCell className="text-xs text-foreground">{lg.message}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </BlurFade>
  );
};
