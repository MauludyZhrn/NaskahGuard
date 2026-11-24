import React, { useEffect, useState } from "react";
import { RefreshCw, ExternalLink, Globe, CheckCircle2, AlertTriangle, XCircle, Clock, Activity } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { BlurFade } from "@/components/ui/blur-fade";
import { NumberTicker } from "@/components/ui/number-ticker";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "../api/client";
import { ProviderHealthItem, SourceAcquisitionItem } from "../types";
import { formatMs } from "../utils/format";

interface MonitorResponse {
  summary: {
    total_queries: number;
    failed_queries: number;
    total_acquisitions: number;
    status_counts: Record<string, number>;
  };
  recent_checks: Array<{
    id: string;
    report_number: string;
    status: string;
    stage: string;
    progress: number;
  }>;
  queries: Array<{
    id: number;
    check_id: string;
    provider: string;
    query: string;
    status: string;
    result_count: number;
    http_status: number | null;
    error: string | null;
    duration_ms: number;
    started_at: string | null;
  }>;
  acquisitions: SourceAcquisitionItem[];
}

const healthBadge = (p: ProviderHealthItem) => {
  if (!p.configured) return { cls: "badge-neutral", label: "NOT_CONFIGURED", icon: AlertTriangle };
  if (p.reachable === true || p.health === "healthy") return { cls: "badge-SUCCESS", label: "Terverifikasi Aktif", icon: CheckCircle2 };
  if (p.reachable === false || p.health === "degraded") return { cls: "badge-EXACT", label: "Gagal / Tidak Terjangkau", icon: XCircle };
  return { cls: "badge-SEMANTIC", label: "Siap (Belum Dicek Live)", icon: Clock };
};

export const DiscoveryMonitorPage: React.FC = () => {
  const [data, setData] = useState<MonitorResponse | null>(null);
  const [providers, setProviders] = useState<ProviderHealthItem[]>([]);
  const [selectedCheckId, setSelectedCheckId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [probing, setProbing] = useState(false);
  const [diagMsg, setDiagMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadMonitor = (cid: string) => {
    setLoading(true);
    const qs = cid ? `?check_id=${encodeURIComponent(cid)}` : "";
    Promise.all([
      apiFetch<MonitorResponse>(`/providers/monitor${qs}`),
      apiFetch<{ providers: ProviderHealthItem[] }>("/providers"),
    ])
      .then(([mon, prov]) => {
        setData(mon);
        setProviders(prov.providers || []);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadMonitor(selectedCheckId);
  }, [selectedCheckId]);

  const runLiveDiagnostics = async () => {
    setProbing(true);
    setDiagMsg(null);
    setError(null);
    try {
      const res = await apiFetch<{ providers: ProviderHealthItem[]; checked_at: string }>("/providers/diagnostics", {
        method: "POST",
      });
      setProviders(res.providers || []);
      const okCount = (res.providers || []).filter((p) => p.reachable === true).length;
      setDiagMsg(
        `Diagnostik konektivitas selesai (${new Date(res.checked_at).toLocaleTimeString("id-ID")}): ${okCount} dari ${
          res.providers.length
        } provider terverifikasi terjangkau.`
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setProbing(false);
    }
  };

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Gagal memuat monitor penemuan</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (!data && loading) {
    return (
      <div className="card">
        <Skeleton className="h-6 w-60 mb-3" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (!data) return null;

  const sc = data.summary.status_counts;

  return (
    <BlurFade duration={0.22}>
      <div>
        <div className="page-header">
          <div>
            <h2 className="page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Globe size={21} /> Monitor Penemuan Sumber
            </h2>
            <p className="page-desc">
              Dasbor operasional diagnostik konektivitas nyata provider, kueri, pengunduhan full-text, dan status pengindeksan.
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <select
              className="input"
              value={selectedCheckId}
              onChange={(e) => setSelectedCheckId(e.target.value)}
              style={{ width: "auto", minWidth: 200 }}
              aria-label="Filter berdasarkan pemeriksaan"
            >
              <option value="">Semua Pemeriksaan</option>
              {data.recent_checks.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.report_number} ({c.status} · {c.progress}%)
                </option>
              ))}
            </select>
            <button type="button" className="btn btn-primary" disabled={probing} onClick={runLiveDiagnostics}>
              <Activity size={14} /> {probing ? "Mengecek..." : "Uji Konektivitas Provider"}
            </button>
            <button type="button" className="btn" onClick={() => loadMonitor(selectedCheckId)}>
              <RefreshCw size={14} /> Muat Ulang
            </button>
          </div>
        </div>

        {diagMsg && <div className="notice">{diagMsg}</div>}

        <div className="kpi-grid">
          <div className="card">
            <div className="stat-label">Total Kueri Provider</div>
            <div className="stat-val">
              <NumberTicker value={data.summary.total_queries} />
            </div>
            <div className="stat-sub">Gagal / timeout: {data.summary.failed_queries}</div>
          </div>
          <div className="card">
            <div className="stat-label">Kandidat &amp; URL Ditemukan</div>
            <div className="stat-val">
              <NumberTicker value={data.summary.total_acquisitions} />
            </div>
            <div className="stat-sub">Metadata-only: {sc.METADATA_ONLY || 0}</div>
          </div>
          <div className="card">
            <div className="stat-label">Full-Text Terindeks</div>
            <div className="stat-val">
              <NumberTicker value={(sc.FULLTEXT_INDEXED || 0) + (sc.MATCH_VERIFIED || 0)} />
            </div>
            <div className="stat-sub">Cocok terverifikasi: {sc.MATCH_VERIFIED || 0}</div>
          </div>
          <div className="card">
            <div className="stat-label">Dibatasi / Gagal Unduh</div>
            <div className="stat-val">
              <NumberTicker value={(sc.CRAWL_FAILED || 0) + (sc.ACCESS_RESTRICTED || 0)} />
            </div>
            <div className="stat-sub">
              Akses ditolak: {sc.ACCESS_RESTRICTED || 0} · Gagal: {sc.CRAWL_FAILED || 0}
            </div>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 18 }}>
          <h3 className="section-title">Diagnostik &amp; Kesehatan Provider ({providers.length})</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Provider</th>
                  <th>Tipe</th>
                  <th>Status Verifikasi</th>
                  <th className="num">Permintaan</th>
                  <th className="num">Hasil</th>
                  <th className="num">Timeout</th>
                  <th>Detail &amp; Pemeriksaan Terakhir</th>
                </tr>
              </thead>
              <tbody>
                {providers.map((p) => {
                  const hb = healthBadge(p);
                  const Icon = hb.icon;
                  return (
                    <tr key={p.id}>
                      <td>
                        <strong>{p.name}</strong>
                      </td>
                      <td>{p.type}</td>
                      <td>
                        <span className={`badge ${hb.cls}`}>
                          <Icon size={11} /> {hb.label}
                        </span>
                      </td>
                      <td className="num">{p.request_count}</td>
                      <td className="num">{p.result_count}</td>
                      <td className="num">{p.timeout_count}</td>
                      <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                        <div>{p.last_error ? `Error: ${p.last_error}` : p.status}</div>
                        {p.last_checked && (
                          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                            Dicek: {new Date(p.last_checked).toLocaleTimeString("id-ID")}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 18 }}>
          <h3 className="section-title">Status Akuisisi &amp; Ekstraksi URL ({data.acquisitions.length})</h3>
          {data.acquisitions.length === 0 ? (
            <div className="empty-state" style={{ padding: "22px 14px" }}>
              <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>
                Belum ada aktivitas akuisisi sumber eksternal tercatat.
              </div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Judul &amp; URL</th>
                    <th>Format</th>
                    <th>Metode</th>
                    <th>Status</th>
                    <th className="num">Durasi</th>
                  </tr>
                </thead>
                <tbody>
                  {data.acquisitions.map((a) => (
                    <tr key={a.id}>
                      <td>
                        <strong>{a.provider}</strong>
                      </td>
                      <td>
                        <strong>{a.title}</strong>
                        {a.source_url && (
                          <div style={{ fontSize: 12 }}>
                            <a href={a.source_url} target="_blank" rel="noreferrer">
                              {a.source_url.slice(0, 72)}
                              {a.source_url.length > 72 ? "..." : ""} <ExternalLink size={11} />
                            </a>
                          </div>
                        )}
                        {a.error && <div style={{ fontSize: 11.5, color: "var(--exact-text)" }}>{a.error}</div>}
                      </td>
                      <td>{a.file_type ? a.file_type.toUpperCase() : "-"}</td>
                      <td>{a.used_playwright ? "Playwright" : "HTTP"}</td>
                      <td>
                        <span className="badge badge-SEMANTIC">{a.status}</span>
                      </td>
                      <td className="num">{formatMs(a.duration_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <h3 className="section-title">Linimasa Kueri Provider ({data.queries.length})</h3>
          {data.queries.length === 0 ? (
            <div className="empty-state" style={{ padding: "22px 14px" }}>
              <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>Belum ada kueri ke provider eksternal.</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Kueri</th>
                    <th>Status</th>
                    <th className="num">Hasil</th>
                    <th className="num">HTTP</th>
                    <th className="num">Durasi</th>
                  </tr>
                </thead>
                <tbody>
                  {data.queries.map((q) => (
                    <tr key={q.id}>
                      <td>
                        <strong>{q.provider}</strong>
                      </td>
                      <td style={{ fontSize: 13 }}>{q.query}</td>
                      <td>
                        <span className={`badge ${q.status === "OK" ? "badge-SUCCESS" : "badge-EXACT"}`}>{q.status}</span>
                        {q.error && <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 2 }}>{q.error}</div>}
                      </td>
                      <td className="num">{q.result_count}</td>
                      <td className="num">{q.http_status ?? "-"}</td>
                      <td className="num">{formatMs(q.duration_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </BlurFade>
  );
};
