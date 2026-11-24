import React from "react";
import { ArrowRight } from "lucide-react";

interface ProcessFlowchartProps {
  stageCounts: Record<string, Record<string, unknown>>;
}

const STAGES: Array<{ key: string; title: string; format: (d?: Record<string, unknown>) => string }> = [
  {
    key: "upload",
    title: "1. Upload Document",
    format: (d) => (d ? `${String(d.filename || "-")} (${Math.round(Number(d.size_bytes || 0) / 1024)} KB)` : "-"),
  },
  {
    key: "validation",
    title: "2. File Validation",
    format: (d) => (d ? `Tipe ${String(d.file_type || "-").toUpperCase()} · Hash ${String(d.file_hash || "-")}` : "-"),
  },
  {
    key: "extraction",
    title: "3. Text Extraction",
    format: (d) => (d ? `${d.pages ?? 0} hlm · ${Number(d.chars || 0).toLocaleString("id-ID")} karakter · ${d.ocr_pages ?? 0} hlm OCR` : "-"),
  },
  {
    key: "normalization",
    title: "4. Text Normalization",
    format: (d) => (d ? `${Number(d.tokens || 0).toLocaleString("id-ID")} token` : "-"),
  },
  {
    key: "segmentation",
    title: "5. Document Segmentation",
    format: (d) => (d ? `${d.paragraphs ?? 0} paragraf · ${d.sentences ?? 0} kalimat` : "-"),
  },
  {
    key: "source_discovery",
    title: "6. Source Discovery",
    format: (d) => (d ? `Lokal: ${d.local_docs ?? 0} · Kueri ekst: ${d.external_queries ?? 0} · Full-text: ${d.full_text_docs ?? 0}` : "-"),
  },
  {
    key: "candidate_retrieval",
    title: "7. Candidate Retrieval",
    format: (d) => (d ? `${d.candidates ?? 0} kandidat (Win: ${d.winnowing ?? 0}, LSH: ${d.minhash ?? 0}, BM25: ${d.bm25 ?? 0})` : "-"),
  },
  {
    key: "similarity_matching",
    title: "8. Similarity Matching",
    format: (d) => (d ? `Exact: ${d.exact_raw ?? 0} · Near: ${d.near_exact_raw ?? 0} · Lex: ${d.lexical_raw ?? 0} · Sem: ${d.semantic_raw ?? 0}` : "-"),
  },
  {
    key: "passage_alignment",
    title: "9. Passage Alignment",
    format: (d) => (d ? `${d.aligned_passages ?? 0} passage selaras` : "-"),
  },
  {
    key: "overlap_removal",
    title: "10. Duplicate Overlap Removal",
    format: (d) => (d ? `${d.passages_before ?? 0} -> ${d.verified_passages ?? 0} terhitung · ${d.duplicate_tokens_removed ?? 0} token overlap dihapus` : "-"),
  },
  {
    key: "score_calculation",
    title: "11. Score Calculation",
    format: (d) => (d ? `${d.matched_words ?? 0} / ${d.eligible_words ?? 0} kata · SI ${Number(d.similarity_index || 0).toFixed(2)}%` : "-"),
  },
  {
    key: "report",
    title: "12. Similarity Report",
    format: (d) => (d ? `${d.sources ?? 0} sumber · ${String(d.report_number || "-")}` : "-"),
  },
];

export const ProcessFlowchart: React.FC<ProcessFlowchartProps> = ({ stageCounts }) => {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
      {STAGES.map((st, idx) => {
        const data = stageCounts[st.key];
        return (
          <div
            key={st.key}
            className="card"
            style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", position: "relative" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <strong style={{ fontSize: 13 }}>{st.title}</strong>
              {idx < STAGES.length - 1 && <ArrowRight size={14} color="var(--text-muted)" aria-hidden="true" />}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", fontVariantNumeric: "tabular-nums" }}>
              {st.format(data)}
            </div>
          </div>
        );
      })}
    </div>
  );
};
