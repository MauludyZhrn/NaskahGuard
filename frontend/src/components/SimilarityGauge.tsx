import React from "react";

interface SimilarityGaugeProps {
  value: number;
  level: string;
  thresholdLow: number;
  thresholdHigh: number;
}

export const SimilarityGauge: React.FC<SimilarityGaugeProps> = ({
  value,
  level,
  thresholdLow,
  thresholdHigh,
}) => {
  const clamped = Math.max(0, Math.min(100, value));
  const r = 68;
  const cx = 90;
  const cy = 84;
  const circumference = Math.PI * r;
  const filled = (clamped / 100) * circumference;

  let strokeColor = "#2563eb";
  if (clamped >= thresholdHigh) strokeColor = "#dc2626";
  else if (clamped >= thresholdLow) strokeColor = "#ea580c";

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }} aria-label={`Similarity Index ${clamped.toFixed(2)} persen, kategori ${level}`}>
      <svg width="180" height="106" viewBox="0 0 180 106">
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke="var(--border)"
          strokeWidth="12"
          strokeLinecap="round"
        />
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke={strokeColor}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
        />
        <text
          x={cx}
          y={cy - 14}
          textAnchor="middle"
          fontSize="24"
          fontWeight="700"
          fill="var(--text)"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {clamped.toFixed(2)}%
        </text>
        <text x={cx} y={cy + 6} textAnchor="middle" fontSize="12" fill="var(--text-secondary)">
          Kategori: {level}
        </text>
      </svg>
    </div>
  );
};
