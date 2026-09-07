---
id: lesson-011-reactive-dashboards-loading-states-and-trend-ana
type: lesson
status: active
created: "2026-05-29"
recorded: "2026-03-07"
owner: manu
tags: [garsync, lesson, ux, frontend, astro, data-visualization]
---

# Reactive Dashboards: Loading States and Trend Analysis

> Recorded 2026-03-07 in the flat `docs/lessons.md`; first appeared in git on 2026-05-29.

**Context:** Improving UX in the Astro dashboard for GarSync.

**Problem:** Static charts and tables felt 'frozen' while waiting for API responses. KPI cards provided context but no sense of progress or regression over time.

**Solution:** 1. Implemented 'Skeletons' (loading placeholders) using Tailwind's animate-pulse. These are triggered on every data-store change before the fetch starts.
2. Added 'Trend Indicators' by performing two parallel API calls: one for the current range and one for the immediately preceding range of equal duration. 
3. Used semantic coloring for trends (e.g., lower Resting HR is good/green, while more Activities is good/green).
The dashboard now feels much more reactive and provides actionable insights (progress tracking).

**Tags:** `#ux` `#frontend` `#astro` `#data-visualization`
