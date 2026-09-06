---
id: lesson-002-garmin-api-data-availability-gaps
type: lesson
status: active
created: "2026-05-29"
owner: manu
tags: [garsync, lesson, garmin-api, data-audit, dashboard]
---

# Garmin API data availability gaps

- **Context:** Sprint 3 dashboard — discovered during data audit
- **Finding:** The `garminconnect` Python library returns null for: `hrv_balance`, `body_battery_highest`, `body_battery_lowest`, `stress_average`, and all sleep phase fields (`deep_sleep_seconds`, `light_sleep_seconds`, `rem_sleep_seconds`, `awake_sleep_seconds`, `sleep_score`). Only `resting_heart_rate` and activity data are consistently populated.
- **Impact:** Removed SleepChart, HRV KPI card, and Body Battery KPI from the dashboard. The schema and API endpoints remain (data might become available with a future library update).
- **Pattern:** Always audit real data in the DB before building UI components. Don't trust API schemas — verify field population with actual queries.

**Tags:** `#garmin-api` `#data-audit` `#dashboard`
