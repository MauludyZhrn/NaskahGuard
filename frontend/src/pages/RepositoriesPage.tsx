import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  BookMarked,
  CheckCircle2,
  DownloadCloud,
  ExternalLink,
  FlaskConical,
  Globe,
  Library,
  Loader2,
  Pause,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  OAIAutoDetectResult,
  OAIConnectionWizardReport,
  OAIRepositoryItem,
  RepositoryCatalogItem,
} from "../types";

const PLATFORM_OPTIONS = [
  { value: "other", label: "Deteksi Otomatis / OAI-PMH Umum" },
  { value: "ojs", label: "OJS (/index.php/{jurnal}/oai)" },
  { value: "dspace7", label: "DSpace 7 (/server/oai/request)" },
  { value: "dspace_legacy", label: "DSpace Lama (/oai/request)" },
  { value: "eprints", label: "EPrints (/cgi/oai2)" },
  { value: "arxiv", label: "arXiv OAI-PMH" },
];

function connectionBadge(status: string) {
  if (status === "VERIFIED") {
    return <Badge variant="default">Terhubung</Badge>;
  }
  if (status === "PARTIAL") {
    return <Badge variant="secondary">Terhubung (Catatan)</Badge>;
  }
  if (status === "ERROR") {
    return <Badge variant="destructive">Kendala Koneksi</Badge>;
  }
  if (status === "HARVESTING") {
    return <Badge variant="secondary">Memanen</Badge>;
  }
  if (status === "PAUSED") {
    return <Badge variant="secondary">Dijeda</Badge>;
  }
  return <Badge variant="outline">Belum Diuji</Badge>;
}

function harvestStatusLabel(repo: OAIRepositoryItem) {
  const st = repo.harvest_state || "IDLE";
  if (st === "RUNNING") return "Sedang Memanen";
  if (st === "PAUSED") return "Dijeda (Bisa Lanjut)";
  if (st === "COMPLETED") return repo.has_resumption_token ? "Sebagian (Tersedia Lanjutan)" : "Selesai";
  if (st === "ERROR") return "Terhenti (Error)";
  return "Siap";
}

export const RepositoriesPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("personal");
  const [repos, setRepos] = useState<OAIRepositoryItem[] | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<OAIRepositoryItem | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Catalog state
  const [catalogItems, setCatalogItems] = useState<RepositoryCatalogItem[] | null>(null);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogPlatform, setCatalogPlatform] = useState("ALL");
  const [catalogStatus, setCatalogStatus] = useState("ALL");
  const [testingCatalogId, setTestingCatalogId] = useState<string | null>(null);
  const [addingCatalogId, setAddingCatalogId] = useState<string | null>(null);
  const [catalogWizardResult, setCatalogWizardResult] = useState<{
    entry: RepositoryCatalogItem;
    wizard: OAIConnectionWizardReport;
  } | null>(null);

  // Add to Catalog Modal
  const [addCatalogOpen, setAddCatalogOpen] = useState(false);
  const [catUniv, setCatUniv] = useState("");
  const [catName, setCatName] = useState("");
  const [catUrl, setCatUrl] = useState("");
  const [catPlatform, setCatPlatform] = useState("other");
  const [catDesc, setCatDesc] = useState("");
  const [savingCat, setSavingCat] = useState(false);

  // Add Personal / Wizard dialog state
  const [addOpen, setAddOpen] = useState(false);
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formType, setFormType] = useState("other");
  const [formPrefix, setFormPrefix] = useState("oai_dc");
  const [formSet, setFormSet] = useState("");
  const [formDelay, setFormDelay] = useState("0.8");
  const [formTimeout, setFormTimeout] = useState("20");
  const [detecting, setDetecting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [detectResult, setDetectResult] = useState<OAIAutoDetectResult | null>(null);
  const [wizardReport, setWizardReport] = useState<OAIConnectionWizardReport | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);

  // Edit dialog state
  const [editRepo, setEditRepo] = useState<OAIRepositoryItem | null>(null);
  const [editName, setEditName] = useState("");
  const [editUrl, setEditUrl] = useState("");
  const [editType, setEditType] = useState("other");
  const [editPrefix, setEditPrefix] = useState("oai_dc");
  const [editSet, setEditSet] = useState("");
  const [editDelay, setEditDelay] = useState("0.8");
  const [editTimeout, setEditTimeout] = useState("20");
  const [savingEdit, setSavingEdit] = useState(false);

  const loadRepos = useCallback(() => {
    apiFetch<OAIRepositoryItem[]>("/oai/repositories")
      .then(setRepos)
      .catch((err: Error) => setError(err.message));
  }, []);

  const loadCatalog = useCallback(() => {
    const qs = new URLSearchParams();
    if (catalogQuery.trim()) qs.set("q", catalogQuery.trim());
    if (catalogPlatform !== "ALL") qs.set("platform", catalogPlatform);
    if (catalogStatus !== "ALL") qs.set("status", catalogStatus);
    apiFetch<{ items: RepositoryCatalogItem[] }>(`/oai/catalog?${qs.toString()}`)
      .then((res) => setCatalogItems(res.items))
      .catch((err: Error) => setError(err.message));
  }, [catalogQuery, catalogPlatform, catalogStatus]);

  useEffect(() => {
    loadRepos();
  }, [loadRepos]);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  const resetAddModal = () => {
    setFormName("");
    setFormUrl("");
    setFormType("other");
    setFormPrefix("oai_dc");
    setFormSet("");
    setFormDelay("0.8");
    setFormTimeout("20");
    setDetectResult(null);
    setWizardReport(null);
    setModalError(null);
  };

  const handleAutoDetect = async () => {
    if (!formUrl.trim()) return;
    setDetecting(true);
    setModalError(null);
    setDetectResult(null);
    try {
      const res = await apiFetch<OAIAutoDetectResult>("/oai/auto-detect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base_url: formUrl.trim() }),
      });
      setDetectResult(res);
      if (res.found && res.detected_url) {
        setFormUrl(res.detected_url);
        setFormType(res.platform_detected || "other");
        if (!formName.trim() && res.identified_name) {
          setFormName(res.identified_name);
        }
      }
    } catch (err: any) {
      setModalError(err.message);
    } finally {
      setDetecting(false);
    }
  };

  const handleTestWizard = async () => {
    if (!formUrl.trim()) return;
    setTesting(true);
    setModalError(null);
    setWizardReport(null);
    try {
      const report = await apiFetch<OAIConnectionWizardReport>("/oai/test-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: formUrl.trim(),
          metadata_prefix: formPrefix.trim() || "oai_dc",
          set_spec: formSet.trim() || null,
          probe_pdf: false,
          auto_detect_fallback: true,
        }),
      });
      setWizardReport(report);
      if (report.ok) {
        if (!formName.trim() && report.identified_name) {
          setFormName(report.identified_name);
        }
        if (report.platform_detected) {
          setFormType(report.platform_detected);
        }
        if (report.recommended_prefix) {
          setFormPrefix(report.recommended_prefix);
        }
      }
    } catch (err: any) {
      setModalError(err.message);
    } finally {
      setTesting(false);
    }
  };

  const handleSaveNew = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim() || !formUrl.trim()) return;
    setSaving(true);
    setModalError(null);
    try {
      await apiFetch<OAIRepositoryItem>("/oai/repositories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formName.trim(),
          base_url: wizardReport?.ok ? wizardReport.effective_url : formUrl.trim(),
          repo_type: formType,
          metadata_prefix: formPrefix.trim() || "oai_dc",
          selected_set: formSet.trim() || null,
          rate_limit_delay_sec: Number(formDelay) || 0.8,
          request_timeout_sec: Number(formTimeout) || 20,
          test_report: wizardReport,
        }),
      });
      setAddOpen(false);
      resetAddModal();
      setMessage("Repositori akademik OAI-PMH berhasil ditambahkan ke daftar pribadi.");
      loadRepos();
      loadCatalog();
    } catch (err: any) {
      setModalError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTestCatalog = async (entry: RepositoryCatalogItem) => {
    setTestingCatalogId(entry.id);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch<{ entry: RepositoryCatalogItem; wizard: OAIConnectionWizardReport }>(
        `/oai/catalog/${entry.id}/test`,
        { method: "POST" }
      );
      setCatalogWizardResult(res);
      setMessage(
        `Hasil uji konektivitas ${res.entry.university}: status ${res.entry.oai_status} (${res.entry.collections_count} koleksi, ${res.entry.supported_formats.length} format metadata).`
      );
      loadCatalog();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setTestingCatalogId(null);
    }
  };

  const handleAddFromCatalog = async (entry: RepositoryCatalogItem) => {
    setAddingCatalogId(entry.id);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch<{ created: boolean; repository: OAIRepositoryItem }>(
        `/oai/catalog/${entry.id}/add`,
        { method: "POST" }
      );
      setMessage(
        res.created
          ? `${entry.name} ditambahkan ke Daftar Repositori Pribadi.`
          : `${entry.name} sudah ada pada Daftar Repositori Pribadi.`
      );
      loadRepos();
      loadCatalog();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setAddingCatalogId(null);
    }
  };

  const handleSaveCatalogEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!catUniv.trim() || !catName.trim() || !catUrl.trim()) return;
    setSavingCat(true);
    setError(null);
    try {
      await apiFetch("/oai/catalog", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          university: catUniv.trim(),
          name: catName.trim(),
          base_url: catUrl.trim(),
          platform: catPlatform,
          description: catDesc.trim() || null,
        }),
      });
      setAddCatalogOpen(false);
      setCatUniv("");
      setCatName("");
      setCatUrl("");
      setCatPlatform("other");
      setCatDesc("");
      setMessage("Repositori ditambahkan ke katalog dengan status Belum Diuji. Klik 'Uji Konektivitas' untuk memverifikasi.");
      loadCatalog();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSavingCat(false);
    }
  };

  const openEditDialog = (repo: OAIRepositoryItem) => {
    setEditRepo(repo);
    setEditName(repo.name);
    setEditUrl(repo.base_url);
    setEditType(repo.platform_detected || repo.repo_type || "other");
    setEditPrefix(repo.metadata_prefix || "oai_dc");
    setEditSet(repo.selected_set || "");
    setEditDelay(String(repo.rate_limit_delay_sec ?? 0.8));
    setEditTimeout(String(repo.request_timeout_sec ?? 20));
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editRepo) return;
    setSavingEdit(true);
    setError(null);
    try {
      await apiFetch<OAIRepositoryItem>(`/oai/repositories/${editRepo.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName.trim(),
          base_url: editUrl.trim(),
          repo_type: editType,
          metadata_prefix: editPrefix.trim() || "oai_dc",
          selected_set: editSet.trim(),
          rate_limit_delay_sec: Number(editDelay) || 0.8,
          request_timeout_sec: Number(editTimeout) || 20,
        }),
      });
      setEditRepo(null);
      setMessage("Pengaturan repositori berhasil diperbarui.");
      loadRepos();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleVerify = async (repo: OAIRepositoryItem) => {
    setBusyId(repo.id);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch<{ wizard?: OAIConnectionWizardReport; identify?: { repositoryName?: string } }>(
        `/oai/repositories/${repo.id}/verify`,
        { method: "POST" }
      );
      setMessage(
        `Uji koneksi 8 tahap selesai: ${res.identify?.repositoryName || repo.name} (${res.wizard?.overall_status || "VERIFIED"}).`
      );
      loadRepos();
    } catch (err: any) {
      setError(err.message);
      loadRepos();
    } finally {
      setBusyId(null);
    }
  };

  const handleHarvest = async (repo: OAIRepositoryItem, resume = false) => {
    setBusyId(repo.id);
    setError(null);
    setMessage(null);
    try {
      const endpoint = resume
        ? `/oai/repositories/${repo.id}/resume`
        : `/oai/repositories/${repo.id}/harvest`;
      const res = await apiFetch<{
        summary: { records_harvested?: number; fulltext_indexed?: number; metadata_only?: number };
      }>(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_records: 15,
          max_downloads: repo.max_downloads ?? 10,
          download_pdfs: true,
          resume,
        }),
      });
      setMessage(
        `Panen ${repo.name} selesai: ${res.summary?.records_harvested ?? 0} rekaman diproses, ${res.summary?.fulltext_indexed ?? 0} full-text diindeks ke korpus lokal.`
      );
      loadRepos();
    } catch (err: any) {
      setError(err.message);
      loadRepos();
    } finally {
      setBusyId(null);
    }
  };

  const handlePause = async (repo: OAIRepositoryItem) => {
    setBusyId(repo.id);
    setError(null);
    try {
      await apiFetch(`/oai/repositories/${repo.id}/pause`, { method: "POST" });
      setMessage(`Repositori ${repo.name} dijeda. Progres dan token tersimpan.`);
      loadRepos();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      await apiFetch(`/oai/repositories/${pendingDelete.id}`, { method: "DELETE" });
      setMessage(`Repositori ${pendingDelete.name} dihapus.`);
      setPendingDelete(null);
      loadRepos();
      loadCatalog();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const totalRecords = (repos || []).reduce((acc, r) => acc + r.records_harvested, 0);
  const totalFulltext = (repos || []).reduce((acc, r) => acc + r.fulltext_indexed, 0);
  const totalVerified = (repos || []).filter((r) => r.status === "VERIFIED").length;

  return (
    <BlurFade duration={0.2}>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Repositori Akademik Indonesia (OAI-PMH)"
          description="Temukan repositori universitas dari katalog, uji konektivitas OAI-PMH, dan indeks karya ilmiah full-text terbuka ke korpus pembanding lokal."
          actions={
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => { loadRepos(); loadCatalog(); }}>
                <RefreshCw className="size-4" data-icon="inline-start" aria-hidden="true" />
                <span>Muat Ulang</span>
              </Button>
              <Button size="sm" onClick={() => { resetAddModal(); setAddOpen(true); }}>
                <Plus className="size-4" data-icon="inline-start" aria-hidden="true" />
                <span>Tambah Repositori</span>
              </Button>
            </div>
          }
        />

        {message && (
          <Alert>
            <CheckCircle2 className="size-4" aria-hidden="true" />
            <AlertTitle>Informasi Repositori</AlertTitle>
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

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card className="shadow-none">
            <CardHeader className="pb-2">
              <CardDescription>Daftar Pribadi</CardDescription>
              <CardTitle className="text-2xl tabular-nums">{repos ? repos.length : "-"}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              {totalVerified} terverifikasi siap panen
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader className="pb-2">
              <CardDescription>Total Metadata Terpanen</CardDescription>
              <CardTitle className="text-2xl tabular-nums">{totalRecords}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Metadata tersimpan tidak pernah dianggap sebagai full-text
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader className="pb-2">
              <CardDescription>Full-Text Diindeks ke Korpus</CardDescription>
              <CardTitle className="text-2xl tabular-nums">{totalFulltext}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Otomatis tersedia sebagai pembanding plagiasi lokal
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2 sm:w-auto sm:inline-grid">
            <TabsTrigger value="personal" className="gap-2">
              <BookMarked className="size-4" aria-hidden="true" />
              <span>Daftar Pribadi ({repos ? repos.length : 0})</span>
            </TabsTrigger>
            <TabsTrigger value="catalog" className="gap-2">
              <Library className="size-4" aria-hidden="true" />
              <span>Katalog Repositori ({catalogItems ? catalogItems.length : 0})</span>
            </TabsTrigger>
          </TabsList>

          {/* TAB 1: Personal Repositories */}
          <TabsContent value="personal" className="mt-4">
            <Card className="shadow-none">
              <CardHeader className="border-b border-border pb-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle className="text-base">Daftar Repositori Terhubung</CardTitle>
                    <CardDescription>
                      Klik nama repositori untuk membuka Penjelajah Koleksi, filter tahun/kata kunci/jenis dokumen, dokumen terindeks, dan riwayat panen.
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {!repos ? (
                  <div className="p-6">
                    <Skeleton className="h-32 w-full" />
                  </div>
                ) : repos.length === 0 ? (
                  <div className="flex flex-col items-center justify-center gap-3 py-12 text-center px-6">
                    <BookMarked className="size-9 text-muted-foreground" aria-hidden="true" />
                    <div>
                      <p className="text-sm font-medium text-foreground">Belum ada repositori OAI-PMH di daftar pribadi</p>
                      <p className="mt-1 text-xs text-muted-foreground max-w-md">
                        Tambahkan endpoint secara manual atau pilih dan uji repositori universitas Indonesia dari tab Katalog Repositori.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => setActiveTab("catalog")}>
                        <Library className="size-4" data-icon="inline-start" aria-hidden="true" />
                        <span>Jelajahi Katalog</span>
                      </Button>
                      <Button size="sm" onClick={() => { resetAddModal(); setAddOpen(true); }}>
                        <Plus className="size-4" data-icon="inline-start" aria-hidden="true" />
                        <span>Tambah Manual</span>
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Nama</TableHead>
                          <TableHead>Platform</TableHead>
                          <TableHead>Koneksi</TableHead>
                          <TableHead className="text-right">Record</TableHead>
                          <TableHead className="text-right">Full-text</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Aksi</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {repos.map((r) => {
                          const isBusy = busyId === r.id;
                          const canResume = r.harvest_state === "PAUSED" || Boolean(r.has_resumption_token);
                          return (
                            <TableRow key={r.id}>
                              <TableCell className="max-w-[280px]">
                                <button
                                  type="button"
                                  onClick={() => navigate(`/repositories/${r.id}`)}
                                  className="text-left font-medium text-foreground hover:text-primary hover:underline block truncate max-w-full"
                                >
                                  {r.name}
                                </button>
                                <div className="text-xs text-muted-foreground truncate" title={r.base_url}>
                                  {r.base_url}
                                </div>
                                {r.last_error && (
                                  <div className="mt-0.5 text-[11px] text-destructive truncate" title={r.last_error}>
                                    {r.last_error}
                                  </div>
                                )}
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline">{r.platform_label || r.repo_type}</Badge>
                                <div className="mt-0.5 text-[11px] text-muted-foreground font-mono">
                                  {r.metadata_prefix}
                                  {r.selected_set ? ` · ${r.selected_set}` : ""}
                                </div>
                              </TableCell>
                              <TableCell>{connectionBadge(r.status)}</TableCell>
                              <TableCell className="text-right tabular-nums font-medium">
                                {r.records_harvested}
                              </TableCell>
                              <TableCell className="text-right tabular-nums font-medium">
                                {r.fulltext_indexed}
                                {(r.failed_records_count ?? 0) > 0 && (
                                  <div className="text-[11px] text-amber-700 dark:text-amber-400">
                                    {r.failed_records_count} gagal PDF
                                  </div>
                                )}
                              </TableCell>
                              <TableCell>
                                <div className="text-xs text-muted-foreground">{harvestStatusLabel(r)}</div>
                                {r.schedule_enabled && (
                                  <div className="text-[11px] text-primary">
                                    Terjadwal / {r.schedule_interval_hours || 24} jam
                                  </div>
                                )}
                              </TableCell>
                              <TableCell className="text-right">
                                <div className="flex justify-end gap-1">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => navigate(`/repositories/${r.id}`)}
                                    title="Buka Detail Repositori"
                                  >
                                    <ExternalLink className="size-3.5" aria-hidden="true" />
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={isBusy}
                                    onClick={() => handleVerify(r)}
                                    title="Uji Koneksi 8 Tahap"
                                  >
                                    {isBusy ? (
                                      <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                                    ) : (
                                      <FlaskConical className="size-3.5" aria-hidden="true" />
                                    )}
                                    <span className="ml-1 hidden xl:inline">Uji</span>
                                  </Button>
                                  {canResume ? (
                                    <Button
                                      size="sm"
                                      variant="default"
                                      disabled={isBusy}
                                      onClick={() => handleHarvest(r, true)}
                                      title="Lanjutkan Panen dari Token Terakhir"
                                    >
                                      <Play className="size-3.5" aria-hidden="true" />
                                      <span className="ml-1 hidden xl:inline">Lanjut</span>
                                    </Button>
                                  ) : (
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      disabled={isBusy}
                                      onClick={() => handleHarvest(r, false)}
                                      title="Mulai Panen Metadata & Full-Text Publik"
                                    >
                                      <DownloadCloud className="size-3.5" aria-hidden="true" />
                                      <span className="ml-1 hidden xl:inline">Panen</span>
                                    </Button>
                                  )}
                                  {r.harvest_state === "RUNNING" && (
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      disabled={isBusy}
                                      onClick={() => handlePause(r)}
                                      title="Jeda Panen"
                                    >
                                      <Pause className="size-3.5" aria-hidden="true" />
                                    </Button>
                                  )}
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => openEditDialog(r)}
                                    title="Edit Pengaturan"
                                  >
                                    <Pencil className="size-3.5" aria-hidden="true" />
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => setPendingDelete(r)}
                                    title="Hapus Repositori"
                                  >
                                    <Trash2 className="size-3.5 text-destructive" aria-hidden="true" />
                                  </Button>
                                </div>
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
          </TabsContent>

          {/* TAB 2: Repository Discovery Catalog */}
          <TabsContent value="catalog" className="mt-4 flex flex-col gap-4">
            <Card className="shadow-none">
              <CardHeader className="pb-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">Katalog Penemuan Repositori Akademik</CardTitle>
                    <CardDescription>
                      Cari nama universitas atau jurnal, pilih platform, uji konektivitas OAI-PMH secara langsung, lalu tambahkan ke daftar pribadi Anda. Repositori berstatus Belum Diuji sebelum diverifikasi.
                    </CardDescription>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => setAddCatalogOpen(true)}>
                    <Globe className="size-4" data-icon="inline-start" aria-hidden="true" />
                    <span>Daftarkan URL ke Katalog</span>
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                  <div className="md:col-span-2 relative">
                    <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" aria-hidden="true" />
                    <Input
                      className="pl-9"
                      placeholder="Cari nama universitas, repositori, atau domain..."
                      value={catalogQuery}
                      onChange={(e) => setCatalogQuery(e.target.value)}
                    />
                  </div>
                  <Select value={catalogPlatform} onValueChange={setCatalogPlatform}>
                    <SelectTrigger>
                      <SelectValue placeholder="Semua Platform" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ALL">Semua Platform</SelectItem>
                      <SelectItem value="ojs">OJS</SelectItem>
                      <SelectItem value="dspace7">DSpace 7</SelectItem>
                      <SelectItem value="dspace_legacy">DSpace Lama</SelectItem>
                      <SelectItem value="eprints">EPrints</SelectItem>
                      <SelectItem value="arxiv">arXiv OAI-PMH</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={catalogStatus} onValueChange={setCatalogStatus}>
                    <SelectTrigger>
                      <SelectValue placeholder="Semua Status OAI" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ALL">Semua Status OAI</SelectItem>
                      <SelectItem value="UNVERIFIED">Belum Diuji</SelectItem>
                      <SelectItem value="VERIFIED">Terhubung</SelectItem>
                      <SelectItem value="PARTIAL">Terhubung (Catatan)</SelectItem>
                      <SelectItem value="ERROR">Kendala Koneksi</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {!catalogItems ? (
                  <Skeleton className="h-40 w-full" />
                ) : catalogItems.length === 0 ? (
                  <div className="py-10 text-center text-sm text-muted-foreground">
                    Tidak ada entri katalog yang cocok dengan pencarian Anda.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-lg border border-border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Universitas &amp; Repositori</TableHead>
                          <TableHead>Status OAI-PMH</TableHead>
                          <TableHead className="text-right">Koleksi / Record</TableHead>
                          <TableHead>Format Metadata</TableHead>
                          <TableHead>Kebijakan Full-Text &amp; Izin Panen</TableHead>
                          <TableHead className="text-right">Aksi</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {catalogItems.map((item) => {
                          const isTesting = testingCatalogId === item.id;
                          const isAdding = addingCatalogId === item.id;
                          const isRestricted = item.harvesting_permission_status === "METADATA_ALLOWED_FULLTEXT_RESTRICTED";
                          return (
                            <TableRow key={item.id}>
                              <TableCell className="max-w-[290px]">
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span className="font-medium text-foreground">{item.university}</span>
                                  <Badge variant="outline" className="text-[10px]">{item.platform_label}</Badge>
                                </div>
                                <div className="text-xs text-foreground/85">{item.name}</div>
                                <div className="text-[11px] font-mono text-muted-foreground truncate" title={item.base_url}>
                                  {item.base_url}
                                </div>
                                {item.legacy_url && (
                                  <div className="text-[10px] font-mono text-muted-foreground truncate" title={item.legacy_url}>
                                    Lama (redirect): {item.legacy_url}
                                  </div>
                                )}
                              </TableCell>
                              <TableCell>
                                {connectionBadge(item.oai_status)}
                                {item.last_error && (
                                  <div className="mt-1 max-w-[200px] text-[11px] text-muted-foreground line-clamp-2" title={item.last_error}>
                                    {item.last_error}
                                  </div>
                                )}
                              </TableCell>
                              <TableCell className="text-right tabular-nums text-xs">
                                <div className="font-medium">
                                  {item.last_tested_at ? `${item.collections_count} koleksi` : "-"}
                                </div>
                                <div className="text-muted-foreground">
                                  {item.record_count_estimate !== null && item.record_count_estimate !== undefined
                                    ? `${item.record_count_estimate.toLocaleString("id-ID")} rekaman`
                                    : "-"}
                                </div>
                              </TableCell>
                              <TableCell className="max-w-[180px]">
                                {item.supported_formats.length > 0 ? (
                                  <div className="flex flex-wrap gap-1">
                                    {item.supported_formats.slice(0, 4).map((fmt) => (
                                      <Badge key={fmt} variant="secondary" className="font-mono text-[10px]">
                                        {fmt}
                                      </Badge>
                                    ))}
                                    {item.supported_formats.length > 4 && (
                                      <span className="text-[10px] text-muted-foreground">
                                        +{item.supported_formats.length - 4}
                                      </span>
                                    )}
                                  </div>
                                ) : (
                                  <span className="text-xs text-muted-foreground">Belum diuji</span>
                                )}
                              </TableCell>
                              <TableCell className="max-w-[230px] text-xs">
                                <Badge variant={isRestricted ? "secondary" : "outline"} className="text-[10px] mb-1">
                                  {item.fulltext_policy_label || "Full-Text Publik Terbuka"}
                                </Badge>
                                <div className="text-[11px] text-muted-foreground leading-snug">
                                  {item.harvesting_permission_label || "Terbuka untuk Metadata & Full-Text"}
                                </div>
                                {item.policy_url && (
                                  <a
                                    href={item.policy_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline mt-0.5"
                                  >
                                    <span>Kebijakan Data</span>
                                    <ExternalLink className="size-3" aria-hidden="true" />
                                  </a>
                                )}
                              </TableCell>
                              <TableCell className="text-right">
                                <div className="flex justify-end gap-1.5">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={isTesting}
                                    onClick={() => handleTestCatalog(item)}
                                  >
                                    {isTesting ? (
                                      <Loader2 className="size-3.5 animate-spin mr-1" aria-hidden="true" />
                                    ) : (
                                      <FlaskConical className="size-3.5 mr-1" aria-hidden="true" />
                                    )}
                                    <span>Uji</span>
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant={item.already_in_personal ? "secondary" : "default"}
                                    disabled={isAdding || item.already_in_personal}
                                    onClick={() => handleAddFromCatalog(item)}
                                    title={
                                      item.requires_verification_before_save && item.oai_status === "UNVERIFIED"
                                        ? "Akan menjalankan uji koneksi otomatis sebelum disimpan"
                                        : undefined
                                    }
                                  >
                                    {isAdding ? (
                                      <Loader2 className="size-3.5 animate-spin mr-1" aria-hidden="true" />
                                    ) : (
                                      <Plus className="size-3.5 mr-1" aria-hidden="true" />
                                    )}
                                    <span>
                                      {item.already_in_personal
                                        ? "Di Daftar"
                                        : item.requires_verification_before_save && item.oai_status === "UNVERIFIED"
                                          ? "Uji & Tambah"
                                          : "Tambahkan"}
                                    </span>
                                  </Button>
                                </div>
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
          </TabsContent>
        </Tabs>

        {/* Catalog Connectivity Result Dialog */}
        <Dialog open={Boolean(catalogWizardResult)} onOpenChange={(open) => !open && setCatalogWizardResult(null)}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                Hasil Uji Konektivitas — {catalogWizardResult?.entry.university}
              </DialogTitle>
              <DialogDescription>
                {catalogWizardResult?.entry.base_url}
              </DialogDescription>
            </DialogHeader>
            {catalogWizardResult && <OAIWizardView report={catalogWizardResult.wizard} showSamples />}
            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setCatalogWizardResult(null)}>
                Tutup
              </Button>
              {catalogWizardResult && !catalogWizardResult.entry.already_in_personal && (
                <Button
                  onClick={async () => {
                    const entry = catalogWizardResult.entry;
                    setCatalogWizardResult(null);
                    await handleAddFromCatalog(entry);
                  }}
                >
                  <Plus className="size-4 mr-1.5" aria-hidden="true" />
                  Tambahkan ke Daftar Pribadi
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Manual Register to Catalog Dialog */}
        <Dialog open={addCatalogOpen} onOpenChange={setAddCatalogOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Daftarkan Endpoint ke Katalog</DialogTitle>
              <DialogDescription>
                Masukkan nama universitas, nama repositori, dan URL OAI-PMH resmi. Entri baru selalu dimulai dengan status Belum Diuji hingga Anda menguji konektivitasnya.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSaveCatalogEntry} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="cat-univ">Nama Universitas / Institusi</Label>
                <Input id="cat-univ" value={catUniv} onChange={(e) => setCatUniv(e.target.value)} placeholder="Contoh: Universitas ..." required />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="cat-name">Nama Repositori / Jurnal</Label>
                <Input id="cat-name" value={catName} onChange={(e) => setCatName(e.target.value)} placeholder="Contoh: Institutional Repository" required />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="cat-url">Base URL OAI-PMH</Label>
                <Input id="cat-url" value={catUrl} onChange={(e) => setCatUrl(e.target.value)} placeholder="https://..." required />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Platform</Label>
                <Select value={catPlatform} onValueChange={setCatPlatform}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PLATFORM_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="cat-desc">Catatan Singkat (Opsional)</Label>
                <Input id="cat-desc" value={catDesc} onChange={(e) => setCatDesc(e.target.value)} placeholder="Deskripsi koleksi skripsi, tesis, atau jurnal" />
              </div>
              <DialogFooter className="pt-2">
                <Button type="button" variant="outline" onClick={() => setAddCatalogOpen(false)}>Batal</Button>
                <Button type="submit" disabled={savingCat}>
                  {savingCat && <Loader2 className="size-4 animate-spin mr-1.5" aria-hidden="true" />}
                  Simpan ke Katalog
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Add Personal Repository + 8-Stage Connection Test Wizard Modal */}
        <Dialog
          open={addOpen}
          onOpenChange={(open) => {
            setAddOpen(open);
            if (!open) resetAddModal();
          }}
        >
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Tambah Repositori Akademik (OAI-PMH)</DialogTitle>
              <DialogDescription>
                Masukkan URL endpoint OAI-PMH secara manual atau gunakan Deteksi Otomatis, lalu jalankan Uji Koneksi 8 Tahap sebelum menyimpan.
              </DialogDescription>
            </DialogHeader>

            {modalError && (
              <Alert variant="destructive">
                <AlertCircle className="size-4" aria-hidden="true" />
                <AlertTitle>Gagal memproses</AlertTitle>
                <AlertDescription>{modalError}</AlertDescription>
              </Alert>
            )}

            <form onSubmit={handleSaveNew} className="flex flex-col gap-4">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="add-repo-url">URL Endpoint OAI-PMH atau Portal</Label>
                  <div className="flex gap-2">
                    <Input
                      id="add-repo-url"
                      value={formUrl}
                      onChange={(e) => setFormUrl(e.target.value)}
                      placeholder="https://repository.kampus.ac.id/server/oai/request"
                      required
                    />
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!formUrl.trim() || detecting}
                      onClick={handleAutoDetect}
                      title="Coba deteksi jalur DSpace 7, DSpace lama, OJS, atau EPrints"
                    >
                      {detecting ? (
                        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                      ) : (
                        <Sparkles className="size-4" aria-hidden="true" />
                      )}
                      <span className="ml-1.5 hidden sm:inline">Deteksi</span>
                    </Button>
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="add-repo-name">Nama Repositori</Label>
                  <Input
                    id="add-repo-name"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="Misal: Repositori Universitas / Jurnal OJS"
                    required
                  />
                </div>
              </div>

              {detectResult && (
                <Alert variant={detectResult.found ? "default" : "destructive"}>
                  <Search className="size-4" aria-hidden="true" />
                  <AlertTitle>
                    {detectResult.found ? "Endpoint OAI-PMH Terdeteksi" : "Endpoint Belum Terdeteksi Otomatis"}
                  </AlertTitle>
                  <AlertDescription>{detectResult.message}</AlertDescription>
                </Alert>
              )}

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <Label>Platform</Label>
                  <Select value={formType} onValueChange={setFormType}>
                    <SelectTrigger>
                      <SelectValue placeholder="Pilih platform" />
                    </SelectTrigger>
                    <SelectContent>
                      {PLATFORM_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="add-repo-prefix">Format Metadata (metadataPrefix)</Label>
                  {wizardReport && wizardReport.supported_formats.length > 0 ? (
                    <Select value={formPrefix} onValueChange={setFormPrefix}>
                      <SelectTrigger id="add-repo-prefix">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {wizardReport.supported_formats.map((fmt) => (
                          <SelectItem key={fmt} value={fmt}>
                            {fmt}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      id="add-repo-prefix"
                      value={formPrefix}
                      onChange={(e) => setFormPrefix(e.target.value)}
                      placeholder="oai_dc"
                    />
                  )}
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="add-repo-set">Koleksi / Set (Opsional)</Label>
                  {wizardReport && wizardReport.available_sets.length > 0 ? (
                    <Select
                      value={formSet || "__ALL__"}
                      onValueChange={(v) => setFormSet(v === "__ALL__" ? "" : v)}
                    >
                      <SelectTrigger id="add-repo-set">
                        <SelectValue placeholder="Semua koleksi" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__ALL__">Semua koleksi</SelectItem>
                        {wizardReport.available_sets.map((s) => (
                          <SelectItem key={s.setSpec} value={s.setSpec}>
                            {s.setName} ({s.setSpec})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      id="add-repo-set"
                      value={formSet}
                      onChange={(e) => setFormSet(e.target.value)}
                      placeholder="Kosongkan untuk semua"
                    />
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="add-delay">Jeda Antar Permintaan (detik)</Label>
                  <Input
                    id="add-delay"
                    type="number"
                    step="0.2"
                    min="0"
                    max="30"
                    value={formDelay}
                    onChange={(e) => setFormDelay(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="add-timeout">Batas Waktu / Timeout (detik)</Label>
                  <Input
                    id="add-timeout"
                    type="number"
                    min="5"
                    max="120"
                    value={formTimeout}
                    onChange={(e) => setFormTimeout(e.target.value)}
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-muted/30 px-3.5 py-2.5">
                <p className="text-xs text-muted-foreground">
                  Jalankan Uji Koneksi 8 Tahap untuk memverifikasi Identify, format metadata, koleksi, dan URL PDF sebelum menyimpan.
                </p>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={!formUrl.trim() || testing}
                  onClick={handleTestWizard}
                >
                  {testing ? (
                    <Loader2 className="size-4 animate-spin" data-icon="inline-start" aria-hidden="true" />
                  ) : (
                    <FlaskConical className="size-4" data-icon="inline-start" aria-hidden="true" />
                  )}
                  <span>Uji Koneksi (8 Tahap)</span>
                </Button>
              </div>

              {wizardReport?.auto_detect_suggestion?.found &&
                wizardReport.auto_detect_suggestion.detected_url && (
                  <Alert>
                    <Sparkles className="size-4" aria-hidden="true" />
                    <AlertTitle>Endpoint Alternatif Terverifikasi Ditemukan</AlertTitle>
                    <AlertDescription className="flex flex-wrap items-center justify-between gap-2">
                      <span>
                        Jalur aktif ditemukan:{" "}
                        <span className="font-mono font-medium">
                          {wizardReport.auto_detect_suggestion.detected_url}
                        </span>
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          const sug = wizardReport.auto_detect_suggestion!;
                          if (sug.detected_url) setFormUrl(sug.detected_url);
                          setFormType(sug.platform_detected || "other");
                          if (!formName.trim() && sug.identified_name) {
                            setFormName(sug.identified_name);
                          }
                        }}
                      >
                        Gunakan URL Ini
                      </Button>
                    </AlertDescription>
                  </Alert>
                )}

              {wizardReport && <OAIWizardView report={wizardReport} showSamples />}

              <DialogFooter className="gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setAddOpen(false)}>
                  Batal
                </Button>
                <Button type="submit" disabled={!formName.trim() || !formUrl.trim() || saving}>
                  {saving ? (
                    <Loader2 className="size-4 animate-spin" data-icon="inline-start" aria-hidden="true" />
                  ) : (
                    <Plus className="size-4" data-icon="inline-start" aria-hidden="true" />
                  )}
                  <span>Simpan Repositori</span>
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Edit Repository Dialog */}
        <Dialog open={Boolean(editRepo)} onOpenChange={(open) => !open && setEditRepo(null)}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Edit Pengaturan Repositori</DialogTitle>
              <DialogDescription>
                Perbarui nama, endpoint, format metadata, koleksi (setSpec), atau parameter jeda permintaan.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSaveEdit} className="flex flex-col gap-3.5">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="edit-name">Nama Repositori</Label>
                <Input id="edit-name" value={editName} onChange={(e) => setEditName(e.target.value)} required />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="edit-url">URL Endpoint OAI-PMH</Label>
                <Input id="edit-url" value={editUrl} onChange={(e) => setEditUrl(e.target.value)} required />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label>Platform</Label>
                  <Select value={editType} onValueChange={setEditType}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PLATFORM_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="edit-prefix">Format Metadata</Label>
                  <Input id="edit-prefix" value={editPrefix} onChange={(e) => setEditPrefix(e.target.value)} />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="edit-set">Koleksi / setSpec (Opsional)</Label>
                <Input id="edit-set" value={editSet} onChange={(e) => setEditSet(e.target.value)} placeholder="Kosongkan untuk semua koleksi" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="edit-delay">Jeda (detik)</Label>
                  <Input id="edit-delay" type="number" step="0.2" min="0" max="30" value={editDelay} onChange={(e) => setEditDelay(e.target.value)} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="edit-timeout">Timeout (detik)</Label>
                  <Input id="edit-timeout" type="number" min="5" max="120" value={editTimeout} onChange={(e) => setEditTimeout(e.target.value)} />
                </div>
              </div>
              <DialogFooter className="pt-2">
                <Button type="button" variant="outline" onClick={() => setEditRepo(null)}>
                  Batal
                </Button>
                <Button type="submit" disabled={savingEdit}>
                  {savingEdit && <Loader2 className="size-4 animate-spin mr-1.5" aria-hidden="true" />}
                  Simpan Perubahan
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={Boolean(pendingDelete)} onOpenChange={(open) => !open && setPendingDelete(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Hapus Repositori Akademik?</AlertDialogTitle>
              <AlertDialogDescription>
                Menghapus <strong>{pendingDelete?.name}</strong> akan menghapus konfigurasi, riwayat rekaman panen, dan log aktivitasnya. Dokumen yang sudah terindeks di korpus lokal tetap aman.
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
