const API = import.meta.env.PUBLIC_API_URL ?? "http://localhost:8000";

// --- Types matching FastAPI Pydantic schemas ---

export interface ActivityItem {
  activity_id: number;
  activity_name: string | null;
  activity_type: string | null;
  start_time: string | null;
  duration_seconds: number | null;
  distance_meters: number | null;
  average_heart_rate: number | null;
  max_heart_rate: number | null;
  calories: number | null;
}

export interface PaginatedActivities {
  items: ActivityItem[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

export interface BiometricItem {
  date: string;
  resting_heart_rate: number | null;
  hrv_balance: string | null;
  body_battery_highest: number | null;
  body_battery_lowest: number | null;
  stress_average: number | null;
}

export interface BiometricsResponse {
  metrics: BiometricItem[];
  start_date: string;
  end_date: string;
  count: number;
}

export interface SummaryStats {
  period: string;
  start_date: string;
  end_date: string;
  total_activities: number;
  total_duration_seconds: number;
  total_distance_meters: number;
  total_calories: number;
  avg_duration_seconds: number | null;
  avg_distance_meters: number | null;
  avg_heart_rate: number | null;
  avg_resting_heart_rate: number | null;
  avg_stress: number | null;
  avg_body_battery_high: number | null;
  avg_sleep_seconds: number | null;
  avg_sleep_score: number | null;
}

export interface HeatmapDay {
  date: string;
  activity_count: number;
  total_duration: number | null;
  total_calories: number | null;
  intensity_level: number;
}

export interface HeatmapStatistics {
  total_active_days: number;
  total_activities: number;
  max_daily_count: number;
}

export interface HeatmapResponse {
  year: number;
  days: HeatmapDay[];
  statistics: HeatmapStatistics;
}

export interface SleepItem {
  date: string;
  sleep_start: string | null;
  sleep_end: string | null;
  total_sleep_seconds: number | null;
  deep_sleep_seconds: number | null;
  light_sleep_seconds: number | null;
  rem_sleep_seconds: number | null;
  awake_sleep_seconds: number | null;
  sleep_score: number | null;
}

export interface SleepResponse {
  sleep_sessions: SleepItem[];
  start_date: string;
  end_date: string;
  count: number;
}

export interface SyncStatus {
  last_sync_time: string | null;
  last_sync_status: string | null;
  total_activities: number;
  total_biometrics: number;
  total_sleep: number;
  total_sync_logs: number;
}

// --- Fetch helpers ---

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, API);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    }
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  syncStatus: () => get<SyncStatus>("/api/sync/status"),

  activities: (opts?: {
    page?: number;
    limit?: number;
    start_date?: string;
    end_date?: string;
  }) => {
    const params: Record<string, string> = {};
    if (opts?.page !== undefined) params.page = String(opts.page);
    if (opts?.limit !== undefined) params.limit = String(opts.limit);
    if (opts?.start_date) params.start_date = opts.start_date;
    if (opts?.end_date) params.end_date = opts.end_date;
    return get<PaginatedActivities>("/api/activities", params);
  },

  biometrics: (startDate: string, endDate: string) =>
    get<BiometricsResponse>("/api/biometrics", {
      start_date: startDate,
      end_date: endDate,
    }),

  statsSummary: (period: string = "week") =>
    get<SummaryStats>("/api/stats/summary", { period }),

  sleep: (startDate: string, endDate: string) =>
    get<SleepResponse>("/api/sleep", {
      start_date: startDate,
      end_date: endDate,
    }),

  heatmap: (year?: number) => {
    const params: Record<string, string> = {};
    if (year) params.year = String(year);
    return get<HeatmapResponse>("/api/stats/heatmap", params);
  },
};
