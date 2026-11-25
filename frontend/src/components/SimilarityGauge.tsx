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

  let strokeColor = "var(--success-text)";
  if (clamped >= thresholdHigh) strokeColor = "var(--chart-primary)";
  else if (clamped >= thresholdLow) strokeColor = "var(--chart-secondary)";

  return (
    <div
      className="inline-flex shrink-0 flex-col items-center"
      aria-label={`Indeks Kemiripan ${clamped.toFixed(1)} persen, kategori ${level}`}
    >
      <svg width="128" height="74" viewBox="0 0 128 74">
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke="var(--border)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke={strokeColor}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
        />
        <text
          x={cx}
          y={cy - 6}
          textAnchor="middle"
          fontSize="19"
          fontWeight="600"
          fill="currentColor"
          style={{ fontFamily: "var(--font-serif)" }}
          className="text-foreground tabular-nums"
        >
          {clamped.toFixed(1)}%
        </text>
      </svg>
    </div>
  );
};
