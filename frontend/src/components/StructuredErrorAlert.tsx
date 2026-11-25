import React from "react";
import { AlertCircle, Info } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import type { StructuredUiError } from "../api/client";

interface StructuredErrorAlertProps {
  error: StructuredUiError;
  title?: string;
}

export const StructuredErrorAlert: React.FC<StructuredErrorAlertProps> = ({
  error,
  title = "Gagal memproses permintaan",
}) => {
  return (
    <Alert variant="destructive">
      <AlertCircle className="size-4" aria-hidden="true" />
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <AlertTitle className="mb-0">{title}</AlertTitle>
          <Badge variant="outline" className="border-destructive/40 text-[11px] font-medium">
            {error.errorKindLabel}
          </Badge>
          {error.httpStatus !== null && error.httpStatus !== undefined && (
            <Badge variant="outline" className="border-destructive/40 font-mono text-[11px]">
              HTTP {error.httpStatus}
            </Badge>
          )}
        </div>
        <AlertDescription>
          <dl className="grid grid-cols-1 gap-y-1.5 text-xs sm:grid-cols-[140px_1fr] sm:gap-x-3">
            <dt className="font-semibold text-foreground/90">Tahap yang gagal</dt>
            <dd className="text-foreground">{error.stage}</dd>

            <dt className="font-semibold text-foreground/90">URL yang sedang diuji</dt>
            <dd className="font-mono break-all text-foreground">{error.testedUrl || "-"}</dd>

            <dt className="font-semibold text-foreground/90">Status HTTP</dt>
            <dd className="font-mono text-foreground">
              {error.httpStatus !== null && error.httpStatus !== undefined
                ? `HTTP ${error.httpStatus}`
                : "Tidak ada respons HTTP (koneksi terputus / timeout)"}
            </dd>

            <dt className="font-semibold text-foreground/90">Penyebab</dt>
            <dd className="text-foreground leading-relaxed">{error.cause}</dd>

            <dt className="font-semibold text-foreground/90">Saran perbaikan</dt>
            <dd className="flex items-start gap-1.5 rounded-md bg-background/70 px-2.5 py-1.5 text-foreground leading-relaxed">
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>{error.suggestion}</span>
            </dd>
          </dl>
        </AlertDescription>
      </div>
    </Alert>
  );
};
