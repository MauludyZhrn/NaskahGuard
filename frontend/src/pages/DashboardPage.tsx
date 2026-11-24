import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FilePlus2, ArrowRight } from "lucide-react";
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
  corpus_stats: {
    total_documents: number;
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

  if (error) return <div className="notice notice-warn">Gagal memuat dasbor: {error}</div>;
  if (!data) return <div className="card">Memuat data dasbor...</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Dasbor Pemeriksaan</h2>
          <p className="page-desc">Ringkasan nyata pemeriksaan dokumen dan statistik korpus lokal.</p>
        </div>
        <Link to="/new-check" className="btn btn-primary">
          <FilePlus2 size={16} />
          <span>Pemeriksaan Baru</span>
        </Link>
      </div>

      <div className="card-grid">
        <div className="card">
          <div className="stat-label">Total Dokumen Diperiksa</div>
          <div className="stat-val">{data.total_documents_checked}</div>
        </div>
        <div className="card">
          <div className="stat-label">Rata-rata Similarity Index</div>
          <div className="stat-val">
            {data.average_similarity !== null ? `${data.average_similarity.toFixed(2)}%` : "Belum ada data"}
          </div>
        </div>
        <div className="card">
          <div className="stat-label">Dokumen Korpus Terindeks</div>
          <div className="stat-val">{data.corpus_stats.total_documents}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            {data.corpus_stats.total_words.toLocaleString("id-ID")} kata · {data.corpus_stats.total_fingerprints.toLocaleString("id-ID")} fingerprint
          </div>
        </div>
        <div className="card">
          <div className="stat-label">Dokumen Unggahan Tersimpan</div>
          <div className="stat-val">{data.total_submissions}</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 18 }}>
        <div className="card">
          <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>Laporan Terbaru</h3>
          {data.recent_reports.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
              Belum ada data pemeriksaan selesai. Unggah dokumen korpus lalu mulai pemeriksaan baru.
            </p>
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
                      <td><code>{r.report_number}</code></td>
                      <td>{r.filename}</td>
                      <td className="num"><strong>{r.similarity_index.toFixed(2)}%</strong></td>
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
          <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>Aktivitas Terkini (Audit Log)</h3>
          {data.recent_activity.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Belum ada aktivitas tercatat.</p>
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
                      <td><strong>{a.action}</strong></td>
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
  );
};
