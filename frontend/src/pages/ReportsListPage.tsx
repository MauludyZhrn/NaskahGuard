import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/client";
import { CheckSummary } from "../types";

export const ReportsListPage: React.FC = () => {
  const [checks, setChecks] = useState<CheckSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<CheckSummary[]>("/checks")
      .then((rows) => setChecks(rows.filter((r) => r.status === "COMPLETED")))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="card">Memuat daftar laporan...</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Laporan Kemiripan</h2>
          <p className="page-desc">Daftar laporan pemeriksaan yang telah selesai dan siap diaudit.</p>
        </div>
      </div>

      {checks.length === 0 ? (
        <div className="card">Belum ada data laporan kemiripan. Jalankan pemeriksaan baru terlebih dahulu.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nomor Laporan</th>
                <th>Dokumen</th>
                <th className="num">Similarity Index</th>
                <th className="num">Kata Cocok</th>
                <th>Kategori Operasional</th>
                <th>Selesai</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((c) => {
                const m = c.metrics as Record<string, any>;
                const cat = m?.operational_category?.level || "-";
                return (
                  <tr key={c.id}>
                    <td><code>{c.report_number}</code></td>
                    <td><strong>{c.document_filename || "-"}</strong></td>
                    <td className="num"><strong>{Number(m?.similarity_index || 0).toFixed(2)}%</strong></td>
                    <td className="num">{m?.matched_words ?? 0} / {m?.eligible_words ?? 0}</td>
                    <td>{cat}</td>
                    <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      {c.finished_at ? new Date(c.finished_at).toLocaleString("id-ID") : "-"}
                    </td>
                    <td>
                      <Link className="btn btn-primary" to={`/reports/${c.id}`}>Buka Laporan</Link>
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
