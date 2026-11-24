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
  const r = 46;
  const cx = 64;
  const cy = 58;
  const circumference = Math.PI * r;
  const filled = (clamped / 100) * circumference;

  let strokeColor = "#2563eb";
  if (clamped >= thresholdHigh) strokeColor = "#dc2626";
  else if (clamped >= thresholdLow) strokeColor = "#ea580c";

  return (
    <div
      style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}
      aria-label={`Similarity Index ${clamped.toFixed(2)} persen, kategori ${level}`}
    >
      <svg width="128" height="74" viewBox="0 0 128 74">
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke="var(--border)"
          strokeWidth="9"
          strokeLinecap="round"
        />
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke={strokeColor}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
        />
        <text
          x={cx}
          y={cy - 6}
          textAnchor="middle"
          fontSize="18"
          fontWeight="700"
          fill="var(--text)"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {clamped.toFixed(2)}%
        </text>
      </svg>
    </div>
  );
};
