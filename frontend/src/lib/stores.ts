import { atom } from "nanostores";

export interface DateRange {
  start: string;
  end: string;
}

function defaultRange(): DateRange {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
}

export const $dateRange = atom<DateRange>(defaultRange());

export function setDateRange(start: string, end: string): void {
  $dateRange.set({ start, end });
}
