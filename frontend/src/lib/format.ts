/** Escape HTML special characters to prevent XSS */
export function escapeHtml(str: string): string {
  const map: Record<string, string> = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  return str.replace(/[&<>"']/g, (c) => map[c] ?? c);
}

/** Format seconds to "Xh Ym" or "Ym" */
export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "--";
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

/** Format meters to "X.XX km" or "--" */
export function formatDistance(meters: number | null): string {
  if (meters === null || meters === undefined) return "--";
  return `${(meters / 1000).toFixed(2)} km`;
}

/** Format ISO date string to "Mon DD" */
export function formatDate(iso: string | null): string {
  if (!iso) return "--";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Format ISO datetime to "Mon DD, HH:MM" */
export function formatDateTime(iso: string | null): string {
  if (!iso) return "--";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Format ISO date to short "M/D" for chart labels */
export function formatChartDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

/** Activity type to emoji icon */
export function activityIcon(type: string | null): string {
  if (!type) return "";
  const t = type.toLowerCase();
  if (t.includes("run")) return "🏃";
  if (t.includes("cycl") || t.includes("bike")) return "🚴";
  if (t.includes("swim")) return "🏊";
  if (t.includes("walk") || t.includes("hik")) return "🚶";
  if (t.includes("strength")) return "🏋️";
  if (t.includes("snowboard") || t.includes("ski")) return "🏂";
  if (t.includes("yoga")) return "🧘";
  return "🎯";
}
