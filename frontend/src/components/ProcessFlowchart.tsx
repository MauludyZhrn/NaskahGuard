import React from "react";
import { ArrowRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface ProcessFlowchartProps {
  stageCounts: Record<string, Record<string, unknown>>;
}

const STAGES: Array<{ key: string; title: string; format: (d?: Record<string, unknown>) => string }> = [
  {
    key: "upload",
    title: "1. Unggah Naskah",
    format: (d) => (d ? `${String(d.filename || "-")} (${Math.round(Number(d.size_bytes || 0) / 1024)} KB)` : "-"),
  },
  {
    key: "validation",
    title: "2. Validasi Berkas",
    format: (d) => (d ? `Format ${String(d.file_type || "-").toUpperCase()} · Hash terverifikasi` : "-"),
  },
  {
    key: "extraction",
    title: "3. Ekstraksi Teks",
    format: (d) => (d ? `${d.pages ?? 0} halaman · ${Number(d.chars || 0).toLocaleString("id-ID")} karakter` : "-"),
  },
  {
    key: "normalization",
    title: "4. Normalisasi Kata",
    format: (d) => (d ? `${Number(d.tokens || 0).toLocaleString("id-ID")} kata dinormalisasi` : "-"),
  },
  {
    key: "segmentation",
    title: "5. Pembagian Struktur",
    format: (d) => (d ? `${d.paragraphs ?? 0} paragraf · ${d.sentences ?? 0} kalimat` : "-"),
  },
  {
    key: "source_discovery",
    title: "6. Pencarian Sumber",
    format: (d) => (d ? `Lokal: ${d.local_docs ?? 0} · Kueri web: ${d.external_queries ?? 0} · Teks lengkap: ${d.full_text_docs ?? 0}` : "-"),
  },
  {
    key: "candidate_retrieval",
    title: "7. Seleksi Kandidat",
    format: (d) => (d ? `${d.candidates ?? 0} kandidat pembanding lolos saringan awal` : "-"),
  },
  {
    key: "similarity_matching",
    title: "8. Pencocokan Teks",
    format: (d) => (d ? `Identik: ${d.exact_raw ?? 0} · Mirip Dekat: ${d.near_exact_raw ?? 0} · Frasa: ${d.lexical_raw ?? 0}` : "-"),
  },
  {
    key: "passage_alignment",
    title: "9. Penyelarasan Bagian",
    format: (d) => (d ? `${d.aligned_passages ?? 0} bagian teks disejajarkan` : "-"),
  },
  {
    key: "overlap_removal",
    title: "10. Atribusi Tunggal",
    format: (d) => (d ? `${d.verified_passages ?? 0} bagian unik (${d.duplicate_tokens_removed ?? 0} tumpang tindih dicegah)` : "-"),
  },
  {
    key: "score_calculation",
    title: "11. Hitung Persentase",
    format: (d) => (d ? `${d.matched_words ?? 0} / ${d.eligible_words ?? 0} kata · ${Number(d.similarity_index || 0).toFixed(1)}%` : "-"),
  },
  {
    key: "report",
    title: "12. Susun Laporan",
    format: (d) => (d ? `${d.sources ?? 0} sumber · Nomor ${String(d.report_number || "-")}` : "-"),
  },
];

export const ProcessFlowchart: React.FC<ProcessFlowchartProps> = ({ stageCounts }) => {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {STAGES.map((st, idx) => {
        const data = stageCounts[st.key];
        return (
          <Card key={st.key} className="shadow-none">
            <CardContent className="flex flex-col justify-between gap-2 p-4">
              <div className="flex items-center justify-between gap-2">
                <strong className="text-sm font-semibold text-foreground">{st.title}</strong>
                {idx < STAGES.length - 1 && (
                  <ArrowRight className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                )}
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground tabular-nums">
                {st.format(data)}
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
};
