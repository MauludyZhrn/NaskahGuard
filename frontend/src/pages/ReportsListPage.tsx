import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileBarChart2 } from "lucide-react";
import { BlurFade } from "@/components/ui/blur-fade";
import { Skeleton } from "@/components/ui/skeleton";
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

  if (loading) {
    return (
      <div className="card">
        <Skeleton className="h-6 w-48 mb-3" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <BlurFade duration={0.22}>
      <div>
        <div className="page-header">
          <div>
            <h2 className="page-title">Laporan Kemiripan</h2>
            <p className="page-desc">Daftar laporan pemeriksaan yang telah selesai dan siap diaudit.</p>
          </div>
        </div>

        {checks.length === 0 ? (
          <div className="empty-state">
            <FileBarChart2 size={26} color="var(--text-muted)" />
            <div style={{ fontWeight: 600 }}>Belum ada laporan selesai</div>
            <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>
              Jalankan <Link to="/new-check">Pemeriksaan Baru</Link> untuk menghasilkan laporan kemiripan.
            </div>
          </div>
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
                      <td>
                        <code>{c.report_number}</code>
                      </td>
                      <td>
                        <strong>{c.document_filename || "-"}</strong>
                      </td>
                      <td className="num">
                        <strong>{Number(m?.similarity_index || 0).toFixed(2)}%</strong>
                      </td>
                      <td className="num">
                        {m?.matched_words ?? 0} / {m?.eligible_words ?? 0}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            cat === "Tinggi" ? "badge-EXACT" : cat === "Sedang" ? "badge-NEAR_EXACT" : "badge-SUCCESS"
                          }`}
                        >
                          {cat}
                        </span>
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        {c.finished_at ? new Date(c.finished_at).toLocaleString("id-ID") : "-"}
                      </td>
                      <td>
                        <Link className="btn btn-primary" to={`/reports/${c.id}`}>
                          Buka Laporan
                        </Link>
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
