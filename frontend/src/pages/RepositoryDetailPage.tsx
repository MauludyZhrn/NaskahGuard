import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  CalendarClock,
  CheckCircle2,
  Database,
  DownloadCloud,
  Eye,
  ExternalLink,
  FlaskConical,
  FolderTree,
  History,
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
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiFetch } from "../api/client";
import { OAIWizardView } from "../components/OAIWizardView";
import { PageHeader } from "../components/PageHeader";
import {
  OAIHarvestLogItem,
  OAIHarvestRecordItem,
  OAIHarvestRunItem,
  OAIIndexedDocumentItem,
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
  const [failedRecords, setFailedRecords] = useState<OAIHarvestRecordItem[]>([]);
  const [indexedDocs, setIndexedDocs] = useState<OAIIndexedDocumentItem[]>([]);
  const [runs, setRuns] = useState<OAIHarvestRunItem[]>([]);
  const [logs, setLogs] = useState<OAIHarvestLogItem[]>([]);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Collection & Filter options
  const [setSearch, setSetSearch] = useState("");
  const [selectedPrefix, setSelectedPrefix] = useState("oai_dc");
  const [selectedSet, setSelectedSet] = useState("");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [keywordFilter, setKeywordFilter] = useState("");
  const [docTypeFilter, setDocTypeFilter] = useState("ALL");
  const [maxRecords, setMaxRecords] = useState("15");
  const [maxDownloads, setMaxDownloads] = useState("10");
  const [incremental, setIncremental] = useState(true);
  const [previewRecords, setPreviewRecords] = useState<OAISampleRecord[] | null>(null);

  // Schedule state
  const [schedEnabled, setSchedEnabled] = useState(false);
  const [schedHours, setSchedHours] = useState("24");

  const loadAll = useCallback(async () => {
    if (!repoId) return;
    try {
      const [repoData, recData, failData, idxData, runData, logData] = await Promise.all([
        apiFetch<OAIRepositoryItem>(`/oai/repositories/${repoId}`),
        apiFetch<{ total: number; items: OAIHarvestRecordItem[] }>(
          `/oai/repositories/${repoId}/records?status=${encodeURIComponent(recordFilter)}&limit=50`
        ),
        apiFetch<{ total: number; items: OAIHarvestRecordItem[] }>(
          `/oai/repositories/${repoId}/records?status=PDF_INACCESSIBLE&limit=50`
        ),
        apiFetch<{ total: number; items: OAIIndexedDocumentItem[] }>(
          `/oai/repositories/${repoId}/indexed-documents`
        ),
        apiFetch<OAIHarvestRunItem[]>(`/oai/repositories/${repoId}/runs?limit=30`),
        apiFetch<OAIHarvestLogItem[]>(`/oai/repositories/${repoId}/logs?limit=80`),
      ]);
      setRepo(repoData);
      setSelectedPrefix(repoData.metadata_prefix || "oai_dc");
      setSelectedSet(repoData.selected_set || "");
      setYearFrom(repoData.year_from ? String(repoData.year_from) : "");
      setYearTo(repoData.year_to ? String(repoData.year_to) : "");
      setKeywordFilter(repoData.keyword_filter || "");
      setDocTypeFilter(repoData.doc_type_filter || "ALL");
      setMaxDownloads(String(repoData.max_downloads ?? 10));
      setSchedEnabled(Boolean(repoData.schedule_enabled));
      setSchedHours(String(repoData.schedule_interval_hours ?? 24));
      setRecords(recData.items);
      setRecordsTotal(recData.total);
      setFailedRecords(failData.items);
      setIndexedDocs(idxData.items);
      setRuns(runData);
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
          year_from: yearFrom.trim() ? Number(yearFrom) : null,
          year_to: yearTo.trim() ? Number(yearTo) : null,
          keyword_filter: keywordFilter.trim(),
          doc_type_filter: docTypeFilter === "ALL" ? "" : docTypeFilter,
          max_downloads: Number(maxDownloads) || 10,
        }),
      });
      setMessage("Pengaturan koleksi & filter panen disimpan.");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyAction(null);
    }
  };

  const handleSaveSchedule = async () => {
    if (!repo) return;
    setBusyAction("schedule");
    setError(null);
    setMessage(null);
    try {
      await apiFetch(`/oai/repositories/${repo.id}/schedule`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schedule_enabled: schedEnabled,
          schedule_interval_hours: Math.max(1, Number(schedHours) || 24),
        }),
      });
      setMessage(
        schedEnabled
          ? `Panen terjadwal opsional aktif setiap ${Math.max(1, Number(schedHours) || 24)} jam.`
          : "Panen terjadwal opsional dinonaktifkan."
      );
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
        summary: {
          records_scanned?: number;
          records_harvested: number;
          fulltext_indexed: number;
          metadata_only: number;
          failed_records?: number;
        };
      }>(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_records: Number(maxRecords) || 15,
          max_downloads: Number(maxDownloads) >= 0 ? Number(maxDownloads) : 10,
          download_pdfs:
            repo.harvesting_permission_status === "METADATA_ALLOWED_FULLTEXT_RESTRICTED"
              ? false
              : (repo.default_download_pdfs ?? true),
          resume: mode === "resume",
          incremental,
          set_spec: selectedSet.trim() || null,
          metadata_prefix: selectedPrefix.trim() || null,
          year_from: yearFrom.trim() ? Number(yearFrom) : null,
          year_to: yearTo.trim() ? Number(yearTo) : null,
          keyword_filter: keywordFilter.trim() || null,
          doc_type_filter: docTypeFilter === "ALL" ? null : docTypeFilter,
        }),
      });
      setMessage(
        `Panen selesai (${res.summary.records_scanned ?? res.summary.records_harvested} dipindai): ${res.summary.records_harvested} rekaman disimpan, ${res.summary.fulltext_indexed} full-text diindeks ke korpus lokal, ${res.summary.metadata_only} metadata saja.`
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

  const filteredSets = (repo.available_sets || []).filter((s) => {
    const q = setSearch.trim().toLowerCase();
    if (!q) return true;
    return `${s.setName} ${s.setSpec}`.toLowerCase().includes(q);
  });

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
          description={`${repo.base_url} · Platform: ${repo.platform_label || repo.repo_type} · Status Koneksi: ${repo.status} · Format: ${repo.metadata_prefix}${repo.selected_set ? ` · Koleksi: ${repo.selected_set}` : ""}`}
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

        {repo.harvesting_permission_status === "METADATA_ALLOWED_FULLTEXT_RESTRICTED" && (
          <Alert>
            <AlertCircle className="size-4" aria-hidden="true" />
            <AlertTitle>Kebijakan Data: Mode Metadata Saja (Default)</AlertTitle>
            <AlertDescription className="flex flex-wrap items-center gap-2">
              <span>
                {repo.harvesting_permission_label || "Metadata diizinkan dengan atribusi; panen massal PDF oleh robot dibatasi oleh kebijakan repositori."}
              </span>
              {repo.policy_url && (
                <a href={repo.policy_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary underline">
                  <span>Lihat Kebijakan Resmi</span>
                  <ExternalLink className="size-3" aria-hidden="true" />
                </a>
              )}
            </AlertDescription>
          </Alert>
        )}

        {/* Info Ringkas Kebijakan, Format & Estimasi */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="shadow-none">
            <CardHeader className="pb-1.5 pt-3">
              <CardDescription className="text-xs">Status Koneksi &amp; Format</CardDescription>
              <CardTitle className="text-sm flex items-center gap-2">
                <Badge variant={repo.status === "VERIFIED" ? "default" : repo.status === "ERROR" ? "destructive" : "outline"}>
                  {repo.status}
                </Badge>
                <span className="font-mono text-xs text-muted-foreground">
                  {(repo.supported_formats || []).length} format
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-3 flex flex-wrap gap-1">
              {(repo.supported_formats || [repo.metadata_prefix]).slice(0, 5).map((f) => (
                <Badge key={f} variant="secondary" className="font-mono text-[10px]">{f}</Badge>
              ))}
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardHeader className="pb-1.5 pt-3">
              <CardDescription className="text-xs">Jumlah Koleksi &amp; Rekaman</CardDescription>
              <CardTitle className="text-sm tabular-nums">
                {(repo.available_sets || []).length} koleksi ·{" "}
                {repo.record_count_estimate !== null && repo.record_count_estimate !== undefined
                  ? `${repo.record_count_estimate.toLocaleString("id-ID")} est.`
                  : `${repo.records_harvested} dipanen`}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-3 text-xs text-muted-foreground">
              Terpanen: {repo.records_harvested} · Diindeks: {repo.fulltext_indexed}
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardHeader className="pb-1.5 pt-3">
              <CardDescription className="text-xs">Kebijakan Full-Text</CardDescription>
              <CardTitle className="text-sm">
                {repo.fulltext_policy_label || "Full-Text Publik Terbuka"}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-3 text-xs text-muted-foreground">
              {repo.default_download_pdfs ? "Unduh PDF terbuka aktif" : "Mode default: Metadata Saja"}
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardHeader className="pb-1.5 pt-3">
              <CardDescription className="text-xs">Status Izin Panen</CardDescription>
              <CardTitle className="text-sm">
                {repo.harvesting_permission_label || "Terbuka untuk Metadata & Full-Text"}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-3 text-xs text-muted-foreground">
              {repo.legacy_url ? `Endpoint lama: ${repo.legacy_url}` : repo.identified_name || repo.name}
            </CardContent>
          </Card>
        </div>

        {/* Monitor Panen + Funnel 7 Tahap + Jadwal Opsional */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="shadow-none lg:col-span-2">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-base">Alur Akuisisi Metadata & Full-Text (7 Tahap)</CardTitle>
                  <CardDescription>
                    Metadata OAI-PMH tidak pernah dihitung sebagai full-text sebelum PDF berhasil diunduh, diekstrak, dan diindeks ke korpus lokal.
                  </CardDescription>
                </div>
                <Badge variant={repo.harvest_state === "ERROR" ? "destructive" : "secondary"}>
                  Monitor: {repo.harvest_state || "IDLE"}
                </Badge>
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

          <Card className="shadow-none">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <CalendarClock className="size-4 text-primary" aria-hidden="true" />
                <CardTitle className="text-base">Panen Terjadwal Opsional</CardTitle>
              </div>
              <CardDescription>
                Aktifkan pemanenan inkremental berkala secara terbatas (maks 15 rekaman, 10 unduhan PDF per siklus).
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <Label htmlFor="sched-switch" className="text-sm">Aktifkan Jadwal Berkala</Label>
                <Switch id="sched-switch" checked={schedEnabled} onCheckedChange={setSchedEnabled} />
              </div>
              <div className="flex items-center gap-2">
                <Label htmlFor="sched-hours" className="text-xs text-muted-foreground whitespace-nowrap">
                  Interval (jam):
                </Label>
                <Input
                  id="sched-hours"
                  type="number"
                  min="1"
                  max="720"
                  value={schedHours}
                  onChange={(e) => setSchedHours(e.target.value)}
                  className="h-8 text-xs"
                />
                <Button size="sm" variant="outline" disabled={busyAction === "schedule"} onClick={handleSaveSchedule}>
                  Simpan Jadwal
                </Button>
              </div>
              {repo.next_scheduled_at && repo.schedule_enabled && (
                <p className="text-[11px] text-muted-foreground">
                  Jadwal berikutnya: {new Date(repo.next_scheduled_at).toLocaleString("id-ID")}
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="wizard" className="w-full">
          <TabsList className="flex flex-wrap h-auto gap-1 justify-start">
            <TabsTrigger value="wizard">Uji Koneksi (8 Tahap)</TabsTrigger>
            <TabsTrigger value="collection">Penjelajah Koleksi & Filter</TabsTrigger>
            <TabsTrigger value="indexed">Dokumen Terindeks ({indexedDocs.length})</TabsTrigger>
            <TabsTrigger value="failed">Rekaman Gagal ({funnel.failed_records})</TabsTrigger>
            <TabsTrigger value="records">Semua Rekaman ({recordsTotal})</TabsTrigger>
            <TabsTrigger value="history">Riwayat & Log ({runs.length})</TabsTrigger>
          </TabsList>

          {/* TAB 1: Wizard */}
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

          {/* TAB 2: Collection Browser + Advanced Filters */}
          <TabsContent value="collection" className="mt-4 flex flex-col gap-4">
            <Card className="shadow-none">
              <CardHeader>
                <CardTitle className="text-base">Kontrol Panen Terbatas & Filter Lanjutan</CardTitle>
                <CardDescription>
                  Pilih koleksi, rentang tahun publikasi, kata kunci, jenis dokumen, dan batas unduhan PDF agar korpus lokal tetap terkurasi dan tidak memanen seluruh repositori tanpa batas.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div className="flex flex-col gap-1.5">
                    <Label>Format Metadata (metadataPrefix)</Label>
                    {(repo.supported_formats || []).length > 0 ? (
                      <Select value={selectedPrefix} onValueChange={setSelectedPrefix}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {(repo.supported_formats || []).map((fmt) => (
                            <SelectItem key={fmt} value={fmt}>{fmt}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input value={selectedPrefix} onChange={(e) => setSelectedPrefix(e.target.value)} />
                    )}
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <Label>Koleksi Terpilih (setSpec)</Label>
                    <Input
                      value={selectedSet}
                      onChange={(e) => setSelectedSet(e.target.value)}
                      placeholder="Kosongkan untuk semua koleksi"
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <Label>Jenis Dokumen</Label>
                    <Select value={docTypeFilter} onValueChange={setDocTypeFilter}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ALL">Semua Jenis Dokumen</SelectItem>
                        <SelectItem value="artikel">Artikel Jurnal</SelectItem>
                        <SelectItem value="skripsi">Skripsi / Tugas Akhir</SelectItem>
                        <SelectItem value="tesis">Tesis</SelectItem>
                        <SelectItem value="disertasi">Disertasi</SelectItem>
                        <SelectItem value="prosiding">Prosiding Konferensi</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="f-year-from">Tahun Mulai</Label>
                    <Input id="f-year-from" type="number" placeholder="2020" value={yearFrom} onChange={(e) => setYearFrom(e.target.value)} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="f-year-to">Tahun Akhir</Label>
                    <Input id="f-year-to" type="number" placeholder="2026" value={yearTo} onChange={(e) => setYearTo(e.target.value)} />
                  </div>
                  <div className="flex flex-col gap-1.5 lg:col-span-1">
                    <Label htmlFor="f-kw">Kata Kunci</Label>
                    <Input id="f-kw" placeholder="Misal: falak, syariah" value={keywordFilter} onChange={(e) => setKeywordFilter(e.target.value)} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="f-max-rec">Batas Rekaman</Label>
                    <Input id="f-max-rec" type="number" min="1" max="200" value={maxRecords} onChange={(e) => setMaxRecords(e.target.value)} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="f-max-dl">Batas Unduhan PDF</Label>
                    <Input id="f-max-dl" type="number" min="0" max="200" value={maxDownloads} onChange={(e) => setMaxDownloads(e.target.value)} />
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <Switch id="f-inc" checked={incremental} onCheckedChange={setIncremental} />
                    <Label htmlFor="f-inc" className="text-xs">
                      Panen Inkremental (hanya ambil data baru sejak datestamp {repo.last_datestamp || "awal"})
                    </Label>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" variant="outline" onClick={handleSaveConfig} disabled={Boolean(busyAction)}>
                      Simpan Filter Default
                    </Button>
                    <Button size="sm" variant="outline" onClick={handlePreview} disabled={Boolean(busyAction)}>
                      {busyAction === "preview" ? (
                        <Loader2 className="size-4 animate-spin mr-1.5" aria-hidden="true" />
                      ) : (
                        <Eye className="size-4 mr-1.5" aria-hidden="true" />
                      )}
                      Pratinjau Sampel
                    </Button>
                    <Button size="sm" onClick={() => handleHarvest("start")} disabled={Boolean(busyAction)}>
                      <DownloadCloud className="size-4 mr-1.5" aria-hidden="true" />
                      Panen dengan Filter Ini
                    </Button>
                  </div>
                </div>

                {/* Collection Browser */}
                {(repo.available_sets || []).length > 0 && (
                  <div className="flex flex-col gap-2 pt-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <FolderTree className="size-4 text-primary" aria-hidden="true" />
                        <h4 className="text-sm font-semibold">Penjelajah Koleksi / Sets ({filteredSets.length})</h4>
                      </div>
                      <Input
                        className="h-8 w-64 text-xs"
                        placeholder="Saring nama atau setSpec..."
                        value={setSearch}
                        onChange={(e) => setSetSearch(e.target.value)}
                      />
                    </div>
                    <div className="max-h-56 overflow-y-auto rounded-lg border border-border divide-y divide-border">
                      <button
                        type="button"
                        onClick={() => setSelectedSet("")}
                        className={`w-full flex items-center justify-between px-3 py-2 text-left text-xs hover:bg-muted/50 ${
                          selectedSet === "" ? "bg-muted font-semibold text-primary" : ""
                        }`}
                      >
                        <span>Semua Koleksi</span>
                        <span className="font-mono text-muted-foreground">(tanpa filter set)</span>
                      </button>
                      {filteredSets.map((s) => (
                        <button
                          key={s.setSpec}
                          type="button"
                          onClick={() => setSelectedSet(s.setSpec)}
                          className={`w-full flex items-center justify-between px-3 py-2 text-left text-xs hover:bg-muted/50 ${
                            selectedSet === s.setSpec ? "bg-muted font-semibold text-primary" : ""
                          }`}
                        >
                          <span className="truncate pr-3">{s.setName}</span>
                          <span className="font-mono text-muted-foreground shrink-0">{s.setSpec}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

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
                              {rec.pdf_urls.length > 0 ? "Ada URL PDF" : "Metadata / Landing Saja"}
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

          {/* TAB 3: Indexed Documents + Full Provenance */}
          <TabsContent value="indexed" className="mt-4">
            <Card className="shadow-none">
              <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">Dokumen Full-Text Terindeks ke Korpus Lokal</CardTitle>
                  <CardDescription>
                    Seluruh dokumen di bawah ini sudah memiliki teks penuh terindeks (Winnowing + MinHash LSH) dan otomatis menjadi sumber pembanding pada pemeriksaan plagiasi berikutnya beserta provenance lengkapnya.
                  </CardDescription>
                </div>
                <Button size="sm" variant="outline" onClick={() => navigate("/corpus")}>
                  <Database className="size-4 mr-1.5" aria-hidden="true" />
                  Buka Korpus Sumber
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                {indexedDocs.length === 0 ? (
                  <div className="py-10 text-center text-sm text-muted-foreground">
                    Belum ada dokumen full-text yang berhasil diindeks dari repositori ini.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Judul Karya & Sumber</TableHead>
                          <TableHead>Penulis & Tahun</TableHead>
                          <TableHead>DOI / Lisensi</TableHead>
                          <TableHead className="text-right">Kata / Hal</TableHead>
                          <TableHead>Waktu Penarikan</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {indexedDocs.map((doc) => (
                          <TableRow key={doc.document_id}>
                            <TableCell className="max-w-[340px]">
                              <div className="font-medium text-foreground line-clamp-2">{doc.title}</div>
                              <div className="text-[11px] text-muted-foreground">
                                {doc.university} · {doc.repository_name}
                              </div>
                              {doc.url && (
                                <a
                                  href={doc.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline mt-0.5"
                                >
                                  <span>URL Asli</span>
                                  <ExternalLink className="size-3" aria-hidden="true" />
                                </a>
                              )}
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground max-w-[200px]">
                              <div className="line-clamp-2">
                                {doc.authors.length > 0 ? doc.authors.slice(0, 3).join(", ") : "-"}
                              </div>
                              <div>{doc.year || "-"}</div>
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              <div className="font-mono text-[11px]">{doc.doi || "-"}</div>
                              <div>{doc.license || "Open Access"}</div>
                            </TableCell>
                            <TableCell className="text-right text-xs tabular-nums">
                              <div className="font-medium">{doc.word_count.toLocaleString("id-ID")} kata</div>
                              <div className="text-muted-foreground">{doc.page_count} hal</div>
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                              <div>{doc.retrieved_at ? new Date(doc.retrieved_at).toLocaleString("id-ID") : "-"}</div>
                              {doc.compared_checks_count > 0 && (
                                <Badge variant="default" className="mt-1 text-[10px]">
                                  Dipakai {doc.compared_checks_count}x
                                </Badge>
                              )}
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

          {/* TAB 4: Failed Records */}
          <TabsContent value="failed" className="mt-4">
            <Card className="shadow-none">
              <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">Rekaman Gagal / PDF Tidak Dapat Diakses</CardTitle>
                  <CardDescription>
                    Rekaman yang gagal mengunduh PDF tetap disimpan metadatanya secara terpisah dan tidak pernah diklaim sebagai full-text.
                  </CardDescription>
                </div>
                {failedRecords.length > 0 && (
                  <Button size="sm" variant="outline" disabled={Boolean(busyAction)} onClick={handleRetryFailed}>
                    <RotateCcw className="size-4 mr-1.5" aria-hidden="true" />
                    Ulangi Rekaman Gagal
                  </Button>
                )}
              </CardHeader>
              <CardContent className="p-0">
                {failedRecords.length === 0 ? (
                  <div className="py-10 text-center text-sm text-muted-foreground">
                    Tidak ada rekaman yang gagal mengunduh PDF.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Judul & Identifier</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Alasan Kegagalan</TableHead>
                          <TableHead className="text-right">Percobaan</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {failedRecords.map((rec) => (
                          <TableRow key={rec.id}>
                            <TableCell className="max-w-[320px]">
                              <div className="font-medium text-foreground line-clamp-2">{rec.title || rec.oai_identifier}</div>
                              <div className="text-[11px] font-mono text-muted-foreground truncate">{rec.oai_identifier}</div>
                            </TableCell>
                            <TableCell>{recordStatusBadge(rec.status)}</TableCell>
                            <TableCell className="text-xs text-destructive max-w-[300px]">
                              {rec.error_message || rec.error_code || "PDF tidak dapat diakses"}
                            </TableCell>
                            <TableCell className="text-right text-xs tabular-nums">{rec.attempts}x</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* TAB 5: All Records */}
          <TabsContent value="records" className="mt-4">
            <Card className="shadow-none">
              <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">Semua Rekaman OAI-PMH</CardTitle>
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

          {/* TAB 6: Harvest History (Runs) & Logs */}
          <TabsContent value="history" className="mt-4 flex flex-col gap-4">
            <Card className="shadow-none">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <History className="size-4 text-primary" aria-hidden="true" />
                  <CardTitle className="text-base">Riwayat Sesi Panen</CardTitle>
                </div>
                <CardDescription>
                  Ringkasan setiap sesi pemanenan (Manual, Lanjutan, Terjadwal) beserta jumlah rekaman dipindai, cocok filter, dan terindeks.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {runs.length === 0 ? (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    Belum ada riwayat sesi panen untuk repositori ini.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Waktu Mulai</TableHead>
                          <TableHead>Mode / Koleksi</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Dipindai</TableHead>
                          <TableHead className="text-right">Tersimpan</TableHead>
                          <TableHead className="text-right">Diindeks</TableHead>
                          <TableHead className="text-right">Gagal</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {runs.map((run) => (
                          <TableRow key={run.id}>
                            <TableCell className="text-xs whitespace-nowrap tabular-nums">
                              {run.started_at ? new Date(run.started_at).toLocaleString("id-ID") : "-"}
                            </TableCell>
                            <TableCell className="text-xs">
                              <Badge variant="outline" className="mr-1.5">{run.trigger_mode}</Badge>
                              <span className="font-mono text-muted-foreground">{run.set_spec || "Semua"}</span>
                            </TableCell>
                            <TableCell>
                              <Badge variant={run.status === "ERROR" ? "destructive" : run.status === "COMPLETED" ? "default" : "secondary"}>
                                {run.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right text-xs tabular-nums">{run.records_scanned}</TableCell>
                            <TableCell className="text-right text-xs tabular-nums">{run.records_harvested}</TableCell>
                            <TableCell className="text-right text-xs tabular-nums font-medium">{run.fulltext_indexed}</TableCell>
                            <TableCell className="text-right text-xs tabular-nums">{run.failed_records}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="shadow-none">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <ScrollText className="size-4 text-primary" aria-hidden="true" />
                  <CardTitle className="text-base">Log Aktivitas & Diagnostik</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {logs.length === 0 ? (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    Belum ada catatan aktivitas.
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
