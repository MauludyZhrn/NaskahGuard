import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BarChart3 } from "lucide-react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { BlurFade } from "@/components/ui/blur-fade";
import { NumberTicker } from "@/components/ui/number-ticker";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "../api/client";
import { ProviderHealthItem } from "../types";

interface DashboardPayload {
  total_documents_checked: number;
  average_similarity: number | null;
  trend: Array<{ report_number: string; similarity_index: number; date: string }>;
  recent_reports: Array<{
    check_id: string;
    report_number: string;
    filename: string;
    similarity_index: number;
    matched_words: number;
    eligible_words: number;
  }>;
  corpus_stats: {
    total_documents: number;
    fulltext_sources_available: number;
    total_words: number;
    total_fingerprints: number;
  };
  provider_stats: {
    total_queries: number;
    total_acquisitions: number;
  };
}

export const AnalyticsOverviewPage: React.FC = () => {
  const [dash, setDash] = useState<DashboardPayload | null>(null);
  const [providers, setProviders] = useState<ProviderHealthItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<DashboardPayload>("/dashboard"),
      apiFetch<{ providers: ProviderHealthItem[] }>("/providers"),
    ])
      .then(([d, p]) => {
        setDash(d);
        setProviders(p.providers || []);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Gagal memuat analitik</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (!dash) {
    return (
      <div className="card">
        <Skeleton className="h-6 w-52 mb-3" />
        <Skeleton className="h-44 w-full" />
      </div>
    );
  }

  return (
    <BlurFade duration={0.22}>
      <div>
        <div className="page-header">
          <div>
            <h2 className="page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <BarChart3 size={21} /> Analitik Sistem &amp; Pencarian
            </h2>
            <p className="page-desc">
              Ringkasan metrik lintas pemeriksaan, perkembangan korpus lokal, dan efektivitas provider sumber.
            </p>
          </div>
        </div>

        <div className="kpi-grid">
          <div className="card">
            <div className="stat-label">Pemeriksaan Selesai</div>
            <div className="stat-val">
              <NumberTicker value={dash.total_documents_checked} />
            </div>
            <div className="stat-sub">
              Rata-rata skor: {dash.average_similarity !== null ? `${dash.average_similarity.toFixed(2)}%` : "-"}
            </div>
          </div>
          <div className="card">
            <div className="stat-label">Dokumen Korpus / Full-Text</div>
            <div className="stat-val">
              <NumberTicker value={dash.corpus_stats.total_documents} />
            </div>
            <div className="stat-sub">Full-text siap: {dash.corpus_stats.fulltext_sources_available}</div>
          </div>
          <div className="card">
            <div className="stat-label">Total Sidik Jari (Winnowing)</div>
            <div className="stat-val">
              <NumberTicker value={dash.corpus_stats.total_fingerprints} />
            </div>
            <div className="stat-sub">{dash.corpus_stats.total_words.toLocaleString("id-ID")} kata terindeks</div>
          </div>
          <div className="card">
            <div className="stat-label">Kueri / Akuisisi Eksternal</div>
            <div className="stat-val">
              <NumberTicker value={dash.provider_stats.total_queries} />
            </div>
            <div className="stat-sub">{dash.provider_stats.total_acquisitions} kandidat sumber tercatat</div>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 16 }}>
          <div className="card">
            <h3 className="section-title">Tren Similarity Index Terbaru (%)</h3>
            {dash.trend.length === 0 ? (
              <div className="empty-state" style={{ padding: "24px 16px" }}>
                <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>Belum ada data pemeriksaan untuk ditampilkan.</div>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={dash.trend} margin={{ top: 10, right: 16, left: -12, bottom: 0 }}>
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--text-secondary)" }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} domain={[0, 100]} />
                  <Tooltip />
                  <Bar dataKey="similarity_index" name="Similarity Index (%)" fill="#1E3A5F" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="card">
            <h3 className="section-title">Performa Provider Sumber</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th className="num">Kueri</th>
                    <th className="num">Hasil</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {providers.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <strong>{p.name}</strong>
                      </td>
                      <td className="num">{p.request_count}</td>
                      <td className="num">{p.result_count}</td>
                      <td>
                        <span
                          className={`badge ${
                            !p.configured
                              ? "badge-neutral"
                              : p.health === "healthy"
                              ? "badge-SUCCESS"
                              : p.health === "degraded"
                              ? "badge-EXACT"
                              : "badge-SEMANTIC"
                          }`}
                        >
                          {!p.configured ? "NOT_CONFIGURED" : p.health}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {dash.recent_reports.length > 0 && (
          <div className="card" style={{ marginTop: 16 }}>
            <h3 className="section-title">Laporan Terakhir</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Laporan</th>
                    <th>Berkas</th>
                    <th className="num">Kata Cocok / Eligible</th>
                    <th className="num">Similarity Index</th>
                  </tr>
                </thead>
                <tbody>
                  {dash.recent_reports.map((r) => (
                    <tr key={r.check_id}>
                      <td>
                        <Link to={`/reports/${r.check_id}`}>
                          <strong>{r.report_number}</strong>
                        </Link>
                      </td>
                      <td>{r.filename}</td>
                      <td className="num">
                        {r.matched_words} / {r.eligible_words}
                      </td>
                      <td className="num">
                        <strong>{r.similarity_index.toFixed(2)}%</strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </BlurFade>
  );
};
