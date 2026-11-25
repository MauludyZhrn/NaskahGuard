import React from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function ModeBadge({ mode }: { mode?: string | null }) {
  const m = mode || "PLAGIARISM_ONLY";
  if (m === "COMBINED") {
    return (
      <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary font-medium">
        Gabungan
      </Badge>
    );
  }
  if (m === "AI_ONLY") {
    return (
      <Badge variant="outline" className="border-border bg-accent text-accent-foreground font-medium">
        Deteksi AI
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="font-medium">
      Plagiasi
    </Badge>
  );
}

export function AiClassificationBadge({ classification, label }: { classification?: string | null; label?: string | null }) {
  if (!classification) return <Badge variant="secondary">-</Badge>;
  const map: Record<string, { text: string; cls: string }> = {
    HUMAN_LIKELY: {
      text: label || "Cenderung Manusia",
      cls: "border-[color:var(--success-border)] bg-[var(--success-bg)] text-[color:var(--success-text)]",
    },
    MIXED_UNCERTAIN: {
      text: label || "Campuran / Tidak Pasti",
      cls: "border-[color:var(--lexical-border)] bg-[var(--lexical-bg)] text-[color:var(--lexical-text)]",
    },
    AI_LIKELY: {
      text: label || "Terindikasi Pola AI",
      cls: "border-destructive/40 bg-destructive/15 text-destructive",
    },
    INSUFFICIENT_DATA: {
      text: label || "Tidak Cukup Bukti",
      cls: "border-border bg-muted text-muted-foreground",
    },
  };
  const cfg = map[classification] || { text: label || classification, cls: "" };
  return (
    <Badge variant="outline" className={cn("font-medium", cfg.cls)}>
      {cfg.text}
    </Badge>
  );
}

export function similarityToneClass(value: number): string {
  if (value >= 30) return "text-destructive";
  if (value >= 15) return "text-[color:var(--lexical-text)]";
  return "text-[color:var(--success-text)]";
}
