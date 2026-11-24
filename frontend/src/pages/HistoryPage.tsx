import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { History, ArrowRight } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { BlurFade } from "@/components/ui/blur-fade";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "../api/client";
import { CheckSummary } from "../types";

export const HistoryPage: React.FC = () => {
  const [checks, setChecks] = useState<CheckSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<CheckSummary[]>("/checks")
      .then(setChecks)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="card">
        <Skeleton className="h-6 w-52 mb-3" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Gagal memuat riwayat</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <BlurFade duration={0.22}>
      <div>
        <div className="page-header">
          <div>
            <h2 className="page-title">Riwayat Pemeriksaan</h2>
            <p className="page-desc">Daftar seluruh pekerjaan pemeriksaan dokumen beserta tahapan, progres, dan skornya.</p>
          </div>
        </div>

        {checks.length === 0 ? (
          <div className="empty-state">
            <History size={26} color="var(--text-muted)" />
            <div style={{ fontWeight: 600 }}>Belum ada riwayat pemeriksaan</div>
            <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>
              Mulai pemeriksaan pertama Anda pada menu <Link to="/new-check">Pemeriksaan Baru</Link>.
            </div>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>No. Laporan</th>
                  <th>Dokumen</th>
                  <th>Status</th>
                  <th style={{ minWidth: 130 }}>Progres</th>
                  <th className="num">Similarity Index</th>
                  <th>Waktu</th>
                  <th>Aksi</th>
                </tr>
              </thead>
              <tbody>
                {checks.map((c) => {
                  const si =
                    c.metrics && typeof c.metrics.similarity_index === "number"
                      ? `${c.metrics.similarity_index.toFixed(2)}%`
                      : "-";
                  return (
                    <tr key={c.id}>
                      <td>
                        <code>{c.report_number}</code>
                      </td>
                      <td>
                        <strong>{c.document_filename || c.document_id}</strong>
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            c.status === "COMPLETED"
                              ? "badge-SUCCESS"
                              : c.status === "FAILED"
                              ? "badge-EXACT"
                              : "badge-SEMANTIC"
                          }`}
                        >
                          {c.status}
                        </span>
                        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{c.stage}</div>
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <Progress value={c.progress} className="h-2 flex-1" />
                          <span className="num" style={{ fontSize: 12 }}>
                            {c.progress}%
                          </span>
                        </div>
                      </td>
                      <td className="num">
                        <strong>{si}</strong>
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        {new Date(c.created_at).toLocaleString("id-ID")}
                      </td>
                      <td>
                        {c.status === "COMPLETED" ? (
                          <Link to={`/reports/${c.id}`} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                            <span>Laporan</span>
                            <ArrowRight size={13} />
                          </Link>
                        ) : (
                          <span style={{ color: "var(--text-muted)" }}>-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </BlurFade>
  );
};
