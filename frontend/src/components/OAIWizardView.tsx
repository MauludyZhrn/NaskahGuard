import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  ExternalLink,
  FileText,
  Info,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { OAIConnectionWizardReport, OAIWizardStage } from "../types";

interface OAIWizardViewProps {
  report: OAIConnectionWizardReport;
  showSamples?: boolean;
}

function StageIcon({ status }: { status: OAIWizardStage["status"] }) {
  if (status === "PASS") return <CheckCircle2 className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />;
  if (status === "WARN") return <AlertTriangle className="size-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />;
  if (status === "FAIL") return <XCircle className="size-4 shrink-0 text-destructive" aria-hidden="true" />;
  return <CircleDashed className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />;
}

function stageBadgeVariant(status: OAIWizardStage["status"]): "default" | "secondary" | "destructive" | "outline" {
  if (status === "PASS") return "default";
  if (status === "FAIL") return "destructive";
  if (status === "WARN") return "secondary";
  return "outline";
}

function stageLabel(status: OAIWizardStage["status"]): string {
  if (status === "PASS") return "Lulus";
  if (status === "WARN") return "Perhatian";
  if (status === "FAIL") return "Gagal";
  return "Dilewati";
}

export const OAIWizardView: React.FC<OAIWizardViewProps> = ({ report, showSamples = true }) => {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/40 px-4 py-3">
        <div className="flex flex-col gap-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-foreground">
              {report.identified_name || "Hasil Uji Koneksi 8 Tahap"}
            </span>
            <Badge variant="outline">{report.platform_label}</Badge>
            <Badge
              variant={
                report.overall_status === "READY"
                  ? "default"
                  : report.overall_status === "PARTIAL"
                    ? "secondary"
                    : "destructive"
              }
            >
              {report.overall_status === "READY"
                ? "Siap Dipanen"
                : report.overall_status === "PARTIAL"
                  ? "Terhubung (Dengan Catatan)"
                  : "Gagal Terhubung"}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground break-all">
            Endpoint teruji: <span className="font-mono text-foreground">{report.effective_url}</span>
            {report.recommended_prefix ? ` · Format disarankan: ${report.recommended_prefix}` : ""}
            {report.record_count_estimate !== undefined && report.record_count_estimate !== null
              ? ` · Estimasi record: ${report.record_count_estimate.toLocaleString("id-ID")}`
              : ""}
          </p>
          {report.failure_category_label && (
            <p className="text-xs font-medium text-destructive">
              Kategori kendala: {report.failure_category_label}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs tabular-nums">
          <span className="text-emerald-700 dark:text-emerald-400 font-medium">
            {report.summary_counts.pass} lulus
          </span>
          <span className="text-amber-700 dark:text-amber-400 font-medium">
            {report.summary_counts.warn} perhatian
          </span>
          <span className="text-destructive font-medium">
            {report.summary_counts.fail} gagal
          </span>
        </div>
      </div>

      <div className="divide-y divide-border rounded-lg border border-border bg-card">
        {report.stages.map((st) => (
          <div key={st.key} className="flex flex-col gap-1.5 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <StageIcon status={st.status} />
                <span className="text-xs font-medium text-muted-foreground tabular-nums">
                  Tahap {st.step}/8
                </span>
                <span className="text-sm font-medium text-foreground">{st.title}</span>
              </div>
              <div className="flex items-center gap-2">
                {st.http_status !== null && st.http_status !== undefined && (
                  <Badge variant="outline" className="font-mono text-[11px]">
                    HTTP {st.http_status}
                  </Badge>
                )}
                {st.error_category_label && (
                  <Badge variant="secondary" className="text-[11px]">
                    {st.error_category_label}
                  </Badge>
                )}
                {st.error_code && (
                  <Badge variant="outline" className="font-mono text-[11px]">
                    {st.error_code}
                  </Badge>
                )}
                <Badge variant={stageBadgeVariant(st.status)}>{stageLabel(st.status)}</Badge>
              </div>
            </div>
            <p className="pl-6 text-xs text-muted-foreground leading-relaxed">{st.message}</p>
            {st.suggestion && (
              <div className="ml-6 mt-1 flex items-start gap-2 rounded-md bg-muted/60 px-3 py-2 text-xs text-foreground">
                <Info className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden="true" />
                <span>
                  <strong>Saran perbaikan:</strong> {st.suggestion}
                </span>
              </div>
            )}
          </div>
        ))}
      </div>

      {showSamples && report.sample_records && report.sample_records.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Pratinjau Metadata ({report.sample_records.length} sampel)
            </h4>
            <span className="text-xs text-muted-foreground">
              Metadata saja tidak dihitung sebagai full-text hingga berkas PDF diekstrak.
            </span>
          </div>
          <div className="grid grid-cols-1 gap-2">
            {report.sample_records.slice(0, 3).map((rec) => (
              <div
                key={rec.identifier}
                className="flex flex-col gap-1 rounded-lg border border-border bg-card px-3.5 py-2.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2">
                    <FileText className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                    <span className="text-sm font-medium text-foreground line-clamp-2">
                      {rec.title}
                    </span>
                  </div>
                  {rec.pdf_urls.length > 0 ? (
                    <Badge variant="default" className="shrink-0">
                      PDF Ditemukan
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="shrink-0">
                      Metadata Saja
                    </Badge>
                  )}
                </div>
                <div className="pl-6 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  {rec.authors.length > 0 && (
                    <span>{rec.authors.slice(0, 2).join(", ")}{rec.authors.length > 2 ? " dkk." : ""}</span>
                  )}
                  {rec.year && <span>{rec.year}</span>}
                  {rec.doi && <span className="font-mono">DOI: {rec.doi}</span>}
                  {rec.datestamp && <span>Tanggal: {rec.datestamp}</span>}
                  {rec.pdf_urls[0] && (
                    <a
                      href={rec.pdf_urls[0]}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      <span>Tautan PDF</span>
                      <ExternalLink className="size-3" aria-hidden="true" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
