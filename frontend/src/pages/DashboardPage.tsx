import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FilePlus2, ArrowRight, Database, Globe, Sparkles } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { BlurFade } from "@/components/ui/blur-fade";
import { NumberTicker } from "@/components/ui/number-ticker";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "../api/client";

interface DashboardData {
  total_documents_checked: number;
  total_submissions: number;
  average_similarity: number | null;
  recent_reports: Array<{
    check_id: string;
    report_number: string;
    document_id: string;
    filename: string;
    title: string;
    similarity_index: number;
    matched_words: number;
    eligible_words: number;
    finished_at: string | null;
  }>;
  recent_activity: Array<{
    id: number;
    ts: string | null;
    actor: string;
    action: string;
    target_type: string;
    target_id: string | null;
  }>;
  trend?: Array<{ report_number: string; similarity_index: number; date: string }>;
  provider_stats?: { total_queries: number; total_acquisitions: number };
  corpus_stats: {
    total_documents: number;
    fulltext_sources_available?: number;
    total_words: number;
    total_fingerprints: number;
  };
}

export const DashboardPage: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DashboardData>("/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Gagal memuat dasbor</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-col gap-4">
        <div className="card">
          <Skeleton className="h-6 w-52 mb-3" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="kpi-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card">
              <Skeleton className="h-4 w-32 mb-2" />
              <Skeleton className="h-8 w-20" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const isEmpty = data.total_documents_checked === 0 && data.corpus_stats.total_documents === 0;

  return (
    <BlurFade duration={0.22}>
      <div>
        <div className="page-header">
          <div>
            <h2 className="page-title">Dasbor Pemeriksaan</h2>
            <p className="page-desc">
              Ringkasan operasional pemeriksaan kemiripan, ketersediaan sumber full-text, dan tren skor aktual.
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Link to="/corpus" className="btn">
              <Database size={15} />
              <span>Kelola Korpus</span>
            </Link>
            <Link to="/new-check" className="btn btn-primary">
              <FilePlus2 size={15} />
              <span>Pemeriksaan Baru</span>
            </Link>
          </div>
        </div>

        {isEmpty && (
          <BlurFade delay={0.05} duration={0.25}>
            <div className="empty-state" style={{ marginBottom: 20 }}>
              <Sparkles size={26} color="var(--color-primary)" />
              <div style={{ fontWeight: 700, fontSize: 16 }}>Selamat datang di NaskahGuard</div>
              <div style={{ fontSize: 13.5, color: "var(--text-secondary)", maxWidth: 620 }}>
                Tambahkan referensi pembanding di <Link to="/corpus">Korpus Sumber</Link> atau panen endpoint OAI-PMH di{" "}
                <Link to="/repositories">Repositori Akademik</Link>, lalu mulai <Link to="/new-check">Pemeriksaan Baru</Link>.
              </div>
            </div>
          </BlurFade>
        )}

        <div className="kpi-grid">
          <div className="card">
            <div className="stat-label">Pemeriksaan Selesai</div>
            <div className="stat-val">
              <NumberTicker value={data.total_documents_checked} />
            </div>
            <div className="stat-sub">{data.total_submissions} naskah tersimpan</div>
          </div>
          <div className="card">
            <div className="stat-label">Rata-rata Similarity Index</div>
            <div className="stat-val">
              {data.average_similarity !== null ? (
                <>
                  <NumberTicker value={data.average_similarity} decimalPlaces={2} />%
                </>
              ) : (
                <span style={{ fontSize: 18, color: "var(--text-muted)" }}>Belum ada data</span>
              )}
            </div>
            <div className="stat-sub">Dari pemeriksaan berstatus selesai</div>
          </div>
          <div className="card">
            <div className="stat-label">Sumber Full-Text Tersedia</div>
            <div className="stat-val">
              <NumberTicker value={data.corpus_stats.fulltext_sources_available ?? data.corpus_stats.total_documents} />
            </div>
            <div className="stat-sub">
              {data.corpus_stats.total_words.toLocaleString("id-ID")} kata ·{" "}
              {data.corpus_stats.total_fingerprints.toLocaleString("id-ID")} fingerprint
            </div>
          </div>
          <div className="card">
            <div className="stat-label">Kueri Pencarian Eksternal</div>
            <div className="stat-val">
              <NumberTicker value={data.provider_stats?.total_queries ?? 0} />
            </div>
            <div className="stat-sub">
              {data.provider_stats?.total_acquisitions ?? 0} kandidat diproses · <Link to="/discovery-monitor">Monitor</Link>
            </div>
          </div>
        </div>

        {data.trend && data.trend.length >= 2 && (
          <div className="card" style={{ marginBottom: 18 }}>
            <h3 className="section-title">Tren Similarity Index Pemeriksaan Terbaru</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={data.trend} margin={{ left: 0, right: 20, top: 8, bottom: 4 }}>
                <XAxis
                  dataKey="report_number"
                  tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                  tickLine={false}
                  axisLine={{ stroke: "var(--border)" }}
                />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} unit="%" />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="similarity_index"
                  name="Similarity Index (%)"
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 16 }}>
          <div className="card">
            <h3 className="section-title">Laporan Terbaru</h3>
            {data.recent_reports.length === 0 ? (
              <div className="empty-state" style={{ padding: "22px 14px" }}>
                <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>Belum ada pemeriksaan selesai.</div>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Laporan</th>
                      <th>Dokumen</th>
                      <th className="num">SI</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_reports.map((r) => (
                      <tr key={r.check_id}>
                        <td>
                          <code>{r.report_number}</code>
                        </td>
                        <td>{r.filename}</td>
                        <td className="num">
                          <strong>{r.similarity_index.toFixed(2)}%</strong>
                        </td>
                        <td>
                          <Link to={`/reports/${r.check_id}`} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                            <span>Buka</span>
                            <ArrowRight size={13} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3 className="section-title" style={{ margin: 0 }}>
                Linimasa Aktivitas Terkini
              </h3>
              <Link to="/discovery-monitor" style={{ fontSize: 12.5, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <Globe size={13} /> Monitor Penemuan
              </Link>
            </div>
            {data.recent_activity.length === 0 ? (
              <div className="empty-state" style={{ padding: "22px 14px" }}>
                <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>Belum ada aktivitas tercatat.</div>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Aksi</th>
                      <th>Target</th>
                      <th>Waktu</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_activity.map((a) => (
                      <tr key={a.id}>
                        <td>
                          <strong>{a.action}</strong>
                        </td>
                        <td>{a.target_type}</td>
                        <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                          {a.ts ? new Date(a.ts).toLocaleString("id-ID") : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </BlurFade>
  );
};
