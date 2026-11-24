/** Format duration in seconds into clean Bahasa Indonesia text (e.g. "2 menit 15 detik"). */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "-";
  const totalSec = Math.round(seconds);
  if (totalSec < 1) return "< 1 detik";
  if (totalSec < 60) return `${totalSec} detik`;
  const mins = Math.floor(totalSec / 60);
  const remSec = totalSec % 60;
  if (mins < 60) {
    return remSec > 0 ? `${mins} menit ${remSec} detik` : `${mins} menit`;
  }
  const hrs = Math.floor(mins / 60);
  const remMin = mins % 60;
  return `${hrs} jam ${remMin} menit ${remSec} detik`;
}

export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "-";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return formatDuration(ms / 1000);
}
