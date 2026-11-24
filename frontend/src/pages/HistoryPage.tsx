import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
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

  if (loading) return <div className="card">Memuat riwayat pemeriksaan...</div>;
  if (error) return <div className="notice notice-warn">{error}</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Riwayat Pemeriksaan</h2>
          <p className="page-desc">Daftar seluruh pekerjaan pemeriksaan dokumen beserta status dan skornya.</p>
        </div>
      </div>

      {checks.length === 0 ? (
        <div className="card">Belum ada data riwayat pemeriksaan.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>No. Laporan</th>
                <th>Dokumen</th>
                <th>Status</th>
                <th className="num">Progres</th>
                <th className="num">Similarity Index</th>
                <th>Waktu</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((c) => {
                const si = c.metrics && typeof c.metrics.similarity_index === "number"
                  ? `${c.metrics.similarity_index.toFixed(2)}%`
                  : "-";
                return (
                  <tr key={c.id}>
                    <td><code>{c.report_number}</code></td>
                    <td>{c.document_filename || c.document_id}</td>
                    <td>{c.status} ({c.stage})</td>
                    <td className="num">{c.progress}%</td>
                    <td className="num"><strong>{si}</strong></td>
                    <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      {new Date(c.created_at).toLocaleString("id-ID")}
                    </td>
                    <td>
                      {c.status === "COMPLETED" ? (
                        <Link to={`/reports/${c.id}`}>Lihat Laporan</Link>
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
  );
};
