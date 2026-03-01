import { Chart, type ChartOptions } from "chart.js/auto";

/** Apply dark theme defaults to all Chart.js instances */
export function applyChartDefaults(): void {
  Chart.defaults.color = "#94a3b8";
  Chart.defaults.font.family =
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  Chart.defaults.plugins.tooltip.backgroundColor = "rgba(15, 23, 42, 0.9)";
  Chart.defaults.plugins.tooltip.titleColor = "#f8fafc";
  Chart.defaults.plugins.tooltip.bodyColor = "#cbd5e1";
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.displayColors = true;
}

/** Shared grid + scale options for dark theme */
export const darkScaleOptions: ChartOptions<"line">["scales"] = {
  x: { grid: { color: "#334155" } },
  y: { grid: { color: "#334155" } },
};

export const darkLegend = {
  position: "top" as const,
  align: "end" as const,
  labels: { usePointStyle: true, boxWidth: 8 },
};
