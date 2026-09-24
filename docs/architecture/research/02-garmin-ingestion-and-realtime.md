# Research: Garmin Data Ingestion Architecture for a Personal Health App

## Bottom Line

For a single individual running a self-hosted fitness dashboard, **python-garminconnect is the only viable direct ingestion path** — it is actively maintained, has 3000+ stars, covers 140+ Garmin Connect API endpoints (including workout push and scheduling), and auto-refreshes DI OAuth tokens indefinitely. The **official Garmin Developer Program is enterprise-only** and requires a legal entity — an individual will not get approved. **Intervals.icu is the best aggregator** ($0 free tier with API access, Garmin auto-sync, REST API, wellness push/pull, webhooks), but introduces a third-party dependency. **FitDays has three active unofficial clients** (TypeScript SDK, Python async client, Home Assistant integration) for the white-label scale ecosystem (Robi S6 / ICOMON), providing full body-composition data. The practical latency floor is **minutes for workouts** ( Garmin publishes them to ConnectAPI shortly after device sync) and **overnight for sleep-derived metrics** (HRV, training readiness, body battery).

---

## 1. Unofficial Route: python-garminconnect

**Status:** ACTIVE — v0.3.16 (PyPI), last push 2026-09-18, 3047 GitHub stars, 543 forks, MIT license. 6 open issues (non-blocking).

**Authentication flow:** Multi-strategy chain of five login paths:

1. `mobile+cffi` — iOS mobile app client ID + curl_cffi TLS fingerprint impersonation (primary)
2. `mobile+requests` — same client ID, plain requests fallback
3. `widget+cffi` — SSO embed widget flow, bypasses clientId rate-limit buckets
4. `portal+cffi` — Garmin Connect portal web login + curl_cffi
5. `portal+requests` — plain requests last resort

Each strategy is tried in order; only credential errors or MFA requirements stop the chain. On success, a DI OAuth2 `access_token` + `refresh_token` pair is stored in `~/.garminconnect/garmin_tokens.json` (mode 0600). Tokens auto-refresh indefinitely; a full credential re-login only occurs if the refresh token is revoked. [Source](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/client.py) (accessed 2026-09-24) — **MEASURED**

**MFA:** Full one-time code support. `login(email, password, prompt_mfa=callback)` or `return_on_mfa=True` + `resume_login(code)`. [Source](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/client.py) (accessed 2026-09-24) — **MEASURED**

**Token refresh:** Automatic before each API request. The client checks token expiry and refreshes via the DI OAuth2 endpoint (`diauth.garmin.com/di-oauth2-service/oauth/token`). [Source](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/client.py) (accessed 2026-09-24) — **MEASURED**

**Rate limits / Cloudflare:**

- Garmin aggressively rate-limits SSO endpoints (429s). Since March 2026, multiple reports show IP- and account-level rate limiting. [Source](https://github.com/matin/garth/issues/217) (accessed 2026-09-24) — **MEASURED**
- The library combats this with curl_cffi TLS impersonation (safari_ios, chrome120 profiles) and multi-strategy chaining. [Source](https://github.com/cyberjunky/python-garminconnect/commit/bf0c802c8c4b1dc7eddbb4e223e3a3e0fd09b42e) (accessed 2026-09-24) — **MEASURED**
- In July 2026, a widespread rate-limit storm forced all strategies (portal+cffi, portal+requests, mobile+cffi, mobile+requests) all hitting 429 simultaneously. The widget+cffi strategy was added as a new rate-limit bucket. [Source](https://github.com/cyberjunky/python-garminconnect/discussions/387) and [Issue #344](https://github.com/cyberjunky/python-garminconnect/issues/344) (accessed 2026-09-24) — **MEASURED**
- **Risk:** Garmin can (and has) block all programmatic login paths from an IP. This is a transient issue — waiting or trying a different strategy usually resolves it within hours. **Not a ban**, but a temporary throttle. [Source](https://github.com/cyberjunky/python-garminconnect/issues/337) (accessed 2026-09-24) — **MEASURED**

**Observed ban / lockout:** No verified permanent bans reported in the issue tracker. However, the `429 Too Many Requests — IP rate limited by Garmin mobile` message confirms Garmin does rate-limit. The rate-limit is per-account (not per-IP or per-UA), so network or header changes alone won't help once triggered. [Source](https://github.com/cyberjunky/python-garminconnect/issues/344) (accessed 2026-09-24) — **MEASURED**

**Data endpoints covered** (140+ endpoints, 14 categories):

| Category | Endpoints | Key data for garsync |
|---|---|---|
| User & Profile | 4 | Settings, profile |
| Daily Health & Activity | 10 | Steps, daily calories, resting HR, sleep ranges |
| Advanced Health Metrics | 16 | **HRV, VO2max, FTP, training readiness, training zones, running tolerance** |
| Historical Data & Trends | 9 | Date range queries, weekly aggregates |
| Activities & Workouts | 37 | Activities list/detail, FIT/GPX download, workout CRUD, push to device, schedule |
| Body Composition & Weight | 7 | Weight, body composition |
| Goals & Achievements | 15 | Challenges, badges, personal records, race predictions |
| Device & Technical | 7 | Device info, settings, alarms |
| Hydration & Wellness | 20 | Nutrition, BP, menstrual, hydration |
| System & Export | 5 | Reports, GraphQL |
| Training Plans | 9 | Plan CRUD, upload typed strength workout, push to device |

[Source](https://github.com/cyberjunky/python-garminconnect/blob/master/README.md) (accessed 2026-09-24) — **MEASURED**

**Workout push / scheduling:** Full support. `upload_running_workout()`, `upload_cycling_workout()`, `upload_strength_workout()`, `schedule_workout(workout_id, date_str)`, and `push_to_device()`. Workouts can be typed (running, cycling, swimming, walking, hiking, strength, cardio, yoga, HIIT, multi-sport, mobility). [Source](https://github.com/cyberjunky/python-garminconnect/pull/327) and [workout.py](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/workout.py) (accessed 2026-09-24) — **MEASURED**

**FIT/GPX download:** `download_activity(activity_id, fmt="fit")` and `download_activity(activity_id, fmt="gpx")` supported. [Source](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/__init__.py) (accessed 2026-09-24) — **MEASURED**

**Existing garsync integration:** garsync's `GarminClient` already uses this library (imported as `from garminconnect import Garmin`). It wraps `login()`, `get_activities()`, `get_heart_rates()`, `get_body_battery()`, `get_all_day_stress()`, `get_hrv_data()`, `get_sleep_data()` — currently fetching activities, biometrics, and sleep. [Source: garsync source /home/manu/Projects/garsync/src/garsync/client.py](accessed 2026-09-24) — **MEASURED**

**Failure mode:** The library reverse-engineers Garmin's private endpoints. Garmin can change or remove them without notice. The current strategy chain (5 login paths) is the result of multiple such breakages. Rate limiting is escalating; a future Garmin Cloudflare update could temporarily knock out all strategies. **Mitigation:** cache tokens aggressively, add exponential backoff with jitter on 429s, and consider a small delay between bulk fetches.

---

## 2. Official Route: Garmin Connect Developer Program + Garmin Health API

**Eligibility:** Enterprise / legal entity only. Garmin explicitly states: "only for business use" and the application process rejects individual developers. [Source](https://developer.garmin.com/gc-developer-program/program-faq/) (accessed 2026-09-24) — **MEASURED**

**Available APIs:**

| API | Purpose | Push / Pull |
|---|---|---|
| Activity API | Read detailed fitness data from user's wearable activities | Pull + webhooks |
| Training API | Publish structured workouts and training plans to user's Garmin Connect calendar | Push |
| Health API | All-day health metrics (steps, HR, sleep, stress) for corporate wellness / population health / patient monitoring | Push + pull |
| Courses API | Publish routes and courses to user's device | Push |
| Women's Health API | Menstrual cycle, pregnancy data | Pull |

[Source](https://developer.garmin.com/gc-developer-program/) (accessed 2026-09-24) — **MEASURED**

**Cost:** No licensing or maintenance fees for Developer Program access. [Source](https://developer.garmin.com/gc-developer-program/program-faq/) (accessed 2026-09-24) — **MEASURED**

**Garmin Health SDK:** Available for enterprise partners; commercial use requires a license fee or minimum device order quantity. [Source](https://developer.garmin.com/health-sdk/questions-answers) (accessed 2026-09-24) — **MEASURED**

**Individual access:** **Not possible.** ghurt's analysis is corroborated by multiple reported rejections on Garmin forums (e.g., ticket #202822 rejected despite being a registered LLC with privacy policy in place, then re-submitted). [Source](https://ghurt.org/garmin-api-for-personal-use) (accessed 2026-09-24) — **CLAIMED** (third-party analysis; [Source](https://forums.garmin.com/developer/connect-iq/f/discussion/434542/garmin-connect-developer-program---access-request-rejected-without-notification) (accessed 2026-09-24) — **MEASURED** forum post showing a real rejection)

**Webhook semantics:** The Activity API supports push architecture — Garmin sends webhooks on new activities. [Source](https://developer.garmin.com/gc-developer-program/activity-api/) (accessed 2026-09-24) — **MEASURED**

**Verdict for garsync:** **Not realistic.** Garmin will not grant an individual developer access to their personal data via the official API. This is by design — Garmin considers personal data an adversarial data export problem, not an open platform feature.

---

## 3. Aggregator Routes

### 3a. Intervals.icu — **Strong recommendation**

| Property | Value |
|---|---|
| Pricing | **Free tier $0** with full API access; Supporter tier $4/mo (€40/yr) for extra features |
| API access | Personal API key or OAuth 2.0; REST API at `intervals.icu/api/v1/` |
| Garmin integration | Auto-sync from Garmin (connect Garmin account, periodic pull) |
| Data available | Activities (FIT/TCX/GPX), wellness (weight, resting HR, HRV, steps), calendar/workouts, webhooks |
| Wellness push/pull | `PUT /athlete/{id}/wellness-bulk` for weight, resting HR, HRV, steps, etc.; `GET /athlete/{id}/wellness` for reads |
| Webhooks | ACTIVITY_UPLOADED, ACTIVITY_ANALYZED (60s delay), CALENDAR_UPDATED, SPORT_SETTINGS_UPDATED |
| Licence | Permissive; API Terms require Garmin attribution |

[Source](https://forum.intervals.icu/t/intervals-icu-api-integration-cookbook/80090) (accessed 2026-09-24), [Pricing](https://www.intervals.icu/pricing/) (accessed 2026-09-24) — **MEASURED**

**Strengths:** Free for personal use. Full REST API with personal API key (no OAuth needed). Garmin auto-sync removes the ban-risk entirely. Wellness bulk upload means you can push FitDays scale data into intervals.icu and then read it back (or push directly from garsync). Webhooks for real-time activity detection.

**Weaknesses:** Adds a third-party dependency. The free tier has no rate-limit docs published (assumed reasonable for personal use). The wellness fields are a curated subset — not all Garmin metrics map cleanly (e.g., Body Battery and stress have limited or no direct mapping). Activity analysis (FTP, training load, etc.) is computed by intervals.icu, not Garmin.

### 3b. Strava API

| Property | Value |
|---|---|
| Access | Self-serve OAuth 2.0; any Strava user can create an app |
| Data | Activities (GPS, heart rate, power, cadence), routes, gear |
| Health metrics | **No body composition, no sleep, no HRV, no resting HR, no body battery** |
| Rate limit | 100k requests / hour, 500 requests / hour / app (per-app) |
| Cost | Free |

[Source](https://developers.strava.com/docs/getting-started/) (accessed 2026-09-24) — **MEASURED**

**Verdict for garsync:** Strava is an **activity** aggregator, not a health metrics aggregator. Garmin auto-sync exists but only for activities (not daily health data). No body composition, no sleep, no HRV, no wellness. Useful only as an activity cross-posting target, not as a health data sink.

### 3c. RunGap

- Native Garmin Connect integration for activity syncing.
- No published developer API. Activity data is read-only and appears inside RunGap's UI only.
- Garmin integration has broken multiple times and required app-store updates to fix. [Source](https://rungap.zendesk.com/hc/en-us/articles/32313611441042-FIXED-Garmin-Connect-integration-down-again) (accessed 2026-09-24) — **MEASURED**
- **Not viable** as a programmatic ingestion layer.

### 3d. Tapiriik

- Open-source fitness data sync service (Python, AGPL-3). GitHub: [tapiriik](https://github.com/tapiriik/tapiriik).
- Supports Garmin Connect ↔ Strava / TrainingPeaks / etc. activity sync.
- **No published REST API**. Requires running your own instance.
- Service has been largely dormant; the last active development was several years ago.
- **Not recommended** — abandoned project, no API contract, no FitDays integration.

### 3e. Tapiriik successor / Alternatives

No significant Tapiriik successor with a public API has emerged. The ecosystem has converged on intervals.icu as the personal-aggregation default.

---

## 4. Polling Cadence vs. Data Availability

This section is critical for choosing a polling interval. Garmin does **not** publish metrics to its API in real time after a workout. Data availability follows a predictable pattern:

| Metric Class | Availability | Latency Floor | Notes |
|---|---|---|---|
| **Activities (GPS, HR, power, cadence)** | Published within minutes of device sync to Garmin Connect | **~10-30 minutes** after workout ends (assuming device is synced) | `get_activities()` returns activities shortly after Garmin processes them. FIT/GPX download available immediately. |
| **Sleep stages (deep/REM/light/awake)** | Published after overnight sync + Garmin's processing pipeline | **2-6 hours after wake** | Sleep data is unreliable for hours. Multiple forum threads report sleep data "changes later in the day" — REM data, wake times, and even sleep start/end can shift hours after the activity is first recorded. [Source](https://forums.garmin.com/apps-software/mobile-apps-web/f/garmin-connect-mobile-andriod/409817/sleep-data-changes-later-in-the-day/1935649) (accessed 2026-09-24) — **CLAIMED** (user reports across multiple forum threads) |
| **Sleep score** | Same delay as sleep stages | **2-6 hours after wake** | Computed from sleep stages + other signals. Unstable until processing completes. |
| **HRV (raw + baseline)** | Published overnight | **Early morning (4-8 AM local)** | HRV is computed from nightly HR data. Only available after the full overnight sleep processing cycle. [Source](https://www.garmin.com/en-US/garmin-technology/running-science/physiological-measurements/training-readiness/) (accessed 2026-09-24) — **CLAIMED** (Garmin's own training readiness documentation implies HRV is overnight-computed) |
| **Training readiness** | Published overnight | **Early morning (4-8 AM local)** | Computed from HRV, sleep quality, previous day's load, etc. Only available after overnight processing. [Source](https://www.garmin.com/en-US/garmin-technology/running-science/physiological-measurements/training-readiness/) (accessed 2026-09-24) — **CLAIMED** |
| **Body Battery** | Updated throughout day (during rest) + overnight refresh | **Continuous, but refreshed overnight** | Body Battery is a continuous metric but is "locked in" after sleep. Values stabilize post-wake. |
| **Stress score** | Published after workout + during day | **~10-30 min post-workout** | All-day stress is computed from HR data in near real-time during the day. Daily summary available by end of day. |
| **Resting HR** | Published overnight | **Early morning** | Derived from overnight HR data. |
| **VO2max / Fitness Age / Race Predictions** | Updated after qualifying workouts + overnight | **2-6 hours post-workout** | Requires a qualifying activity (e.g., continuous HR > 1 zone below LT for 10+ min). Computed asynchronously. [Source](https://github.com/cyberjunky/python-garminconnect/blob/master/README.md) (accessed 2026-09-24) — **MEASURED** (endpoint list in README) |
| **Body Battery / Body Composition (weight)** | Daily / after weigh-in | **Variable** | Body composition (via Garmin body-composition-compatible scales) updates on weigh-in. Weight via FitDays scale is different. |
| **Weight (direct from Garmin scale)** | On weigh-in | **Near real-time** | Garmin Connect only shows weight from Garmin-branded scales. Third-party scales (FitDays) must be ingested separately. |

**Practical ingestion strategy:**

- **Activities:** Poll every 15-30 min during waking hours, or use a webhook if available.
- **Sleep/HRV/Training Readiness:** Single daily poll at 07:00 local time (after overnight processing). Do NOT poll multiple times per day — data is unstable.
- **Stress:** Poll daily at end of day or near real-time if desired.
- **Biometrics window:** Poll 06:00-08:00 daily to catch HRV, resting HR, body battery, and training readiness in a single batch.

---

## 5. Raw FIT Files vs. Garmin-Computed Metrics

**Garmin Connect API provides pre-computed metrics.** The `get_heart_rates()`, `get_body_battery()`, `get_all_day_stress()`, `get_hrv_data()` endpoints return Garmin's processed values. The `get_activities()` endpoint returns summary data; full detail is available via `get_activity(activity_id)` which returns minute-by-minute HR, cadence, power, etc.

**FIT file parsing is available as an alternative:**

- Garmin provides FIT file downloads via `download_activity(activity_id, fmt="fit")`.
- Python FIT parsing is available via `fit-tool` (by Stages Cycling), `fitparse`, and Garmin's own FIT SDK.
- FIT files contain raw sensor data: GPS, barometric altitude, cadence, power (if available), stride length, ground contact time, etc. — all unprocessed.
- **Garmin-computed metrics vs. FIT raw:** Garmin's HRV and training readiness are computed from the FIT data using proprietary algorithms. You can re-compute HRV from raw HR data in the FIT file, but the results will differ from Garmin's baseline/balance values because Garmin applies smoothing, sleep-stage weighting, and individual calibration that is not public.

**Verdict for garsync:** For body composition, HRV, training readiness, and body battery, rely on Garmin's computed metrics from the API. For activities, storing both the Garmin API summary and the FIT file gives maximum flexibility: the API summary for dashboard rendering, the FIT file for later re-analysis.

---

## 6. Pushing Workouts into Garmin (Reverse Dependency)

**python-garminconnect fully supports workout push:**

- `upload_running_workout(workout)` — upload a structured running workout to Garmin Connect
- `upload_cycling_workout(workout)` — cycling intervals
- `upload_strength_workout(workout)` — strength training (exercise sets with weight/reps)
- `schedule_workout(workout_id, date_str)` — schedule a workout on the Garmin Connect calendar
- `push_to_device(workout_id, device_id)` — push directly to a paired Garmin device

Workout types: running, cycling, swimming, walking, hiking, multi-sport, cardio training, strength training, yoga, Pilates, HIIT, mobility. Steps support time, distance, calories, power, heart-rate, cadence, and grade targets. [Source](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/workout.py) (accessed 2026-09-24) — **MEASURED**

**Garmin Official Training API:** Enterprise-only (see Section 2). Allows pushing structured workouts and training plans to a user's Garmin Connect calendar, which then syncs to devices. This is the same capability as the unofficial methods above, but via a supported contract.

**FIT-file upload to Garmin Connect:** `garmin_uploader` (by La0, Go, MIT) can upload .fit, .tcx, .gpx files to Garmin Connect. This is a separate tool from python-garminconnect but uses the same underlying upload endpoint (`connect.garmin.com/modern/proxy/upload-service/upload`). [Source](https://github.com/La0/garmin-uploader/blob/master/garmin_uploader/api.py) (accessed 2026-09-24) — **MEASURED**

**Practical use case for garsync:** A coaching layer could compute adjusted workouts (e.g., "you had poor recovery, downgrade today's interval intensity by 10%") and push them to the user's Garmin Connect calendar via `schedule_workout()`. The user then sees the adjusted workout on their Garmin device.

---

## What This Means for garsync

### Recommended ingestion architecture

1. **Keep python-garminconnect as the primary Garmin ingestion path.** It already works in garsync. The risk is Cloudflare/rate-limit, not ban. Mitigate with: (a) token caching, (b) 5-strategy login fallback, (c) exponential backoff on 429, (d) poll once daily at 07:00 for biometrics, (e) poll every 30 min for new activities.
2. **Add FitDays scale integration via the `fitdays` Python package** (`pip install fitdays`). It's MIT-licensed, async, provides full body-composition data (weight, body fat %, muscle mass, bone mass, BMR, body water, body age, heart rate from the scale), and supports multi-user accounts. The client has self-healing login (re-auth from password digest when token expires). [Source: fitdays README](https://github.com/AboveColin/fitdays/blob/main/README.md) (accessed 2026-09-24) — **MEASURED**
3. **Add intervals.icu as a secondary aggregator / backup path.** Use it to: (a) cross-validate Garmin activity data, (b) push FitDays weight data for consistency, (c) receive webhooks for new activities as a real-time complement to polling, (d) access intervals.icu's computed metrics (FTP, training load, VO2max analysis) that go beyond Garmin's basic calculations. The free tier is sufficient for personal use.
4. **Do NOT attempt Garmin Health API.** It requires a legal entity and is rejected for individuals. Period.

### Data model additions for the scale

The `fitdays` package provides these fields per measurement (all accessible via `get_sync()` → `.measurements`):

- `weight_kg`, `bmi`, `body_fat_pct`, `subcutaneous_fat_pct`, `visceral_fat`, `muscle_pct`, `skeletal_muscle_pct`, `bone_mass_kg`, `body_water_pct`, `protein_pct`, `bmr`, `body_age`, `heart_rate`, `impedance`
- Derived masses: `body_fat_kg`, `muscle_mass_kg`, `skeletal_muscle_kg`, `body_water_kg`, `protein_kg`
- Multi-user support: each measurement has a `suid` linking to the profile that stepped on the scale.

### Ingestion cadence recommendation

| Frequency | What | Why |
|---|---|---|
| **07:00 daily** | Biometrics (HRV, resting HR, body battery, stress, training readiness, body composition from Garmin scale) | Overnight metrics are unstable until processing completes |
| **Every 30 min** | New activities (poll `get_activities()` with date filter) | Activities publish within minutes of device sync |
| **On demand** | FIT file download for full-detail analysis | On-demand, not polled |
| **Daily (after weigh-in)** | FitDays body composition | Manual trigger or webhook from a companion script |
| **Webhook (intervals.icu)** | Real-time activity notification | ACTIVITY_UPLOADED webhook fires when Garmin-synced activity is processed by intervals.icu |

---

## Open Questions and Decisions Needed

1. **Do you want FitDays data in intervals.icu or directly in garsync?** Both work. Direct ingestion via the `fitdays` Python package is simpler (no third-party dependency). Pushing to intervals.icu gives cross-validation and intervals.icu's wellness analytics.
2. **Garmin body-composition scale vs. FitDays scale:** Garmin's own body-composition scales (e.g., Garmin Index) sync directly to Garmin Connect. If you use a Garmin scale, you get body comp via `get_body_composition()` in python-garminconnect. With a FitDays scale, you must use the FitDays API. The fields overlap (weight, body fat %, muscle mass, BMR) but are computed differently.
3. **Do you need real-time activity detection?** If yes, intervals.icu webhooks provide the lowest-latency path. Without them, polling every 30 min is the practical minimum.
4. **Workout coaching push — do you want it?** The `schedule_workout()` path exists and works. It requires defining workout steps (time/distance/HR/pace targets) with Pydantic models. This is a non-trivial feature to design.
5. **Garmin Health API — is there any path?** Only if you form a legal entity (LLC, GmbH, etc.) and apply as a business. The application is reviewed manually and takes 2-4 weeks. There is no guarantee of approval. For a personal app, this is a dead end.

---

## Sources

### Measured (source code / official docs fetched and read)

- [cyberjunky/python-garminconnect — README](https://github.com/cyberjunky/python-garminconnect/blob/master/README.md) — 140+ endpoint coverage, workout push, auth flow, licensing (MIT, 3047 stars, last push 2026-09-18)
- [python-garminconnect / client.py — auth strategy chain](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/client.py) — 5-strategy login, curl_cffi TLS impersonation, DI OAuth2 token refresh
- [python-garminconnect / workout.py — workout models](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/workout.py) — workout step types, sport types, push-to-device
- [python-garminconnect / __init__.py — endpoints](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/__init__.py) — API URL patterns, upload endpoint
- [python-garminconnect / PR #327 — workout scheduling](https://github.com/cyberjunky/python-garminconnect/pull/327) — `schedule_workout()` implementation
- [garsync / src/garsync/client.py](file:///home/manu/Projects/garsync/src/garsync/client.py) — existing Garmin client wrapper using garminconnect
- [garmin_uploader / api.py](https://github.com/La0/garmin-uploader/blob/master/garmin_uploader/api.py) — FIT/TCX/GPX upload endpoint URL
- [Garmin Connect Developer Program FAQ](https://developer.garmin.com/gc-developer-program/program-faq/) — enterprise-only, no fees
- [Garmin Training API](https://developer.garmin.com/gc-developer-program/training-api/) — structured workout push to calendar
- [Garmin Health API](https://developer.garmin.com/gc-developer-program/health-api/) — corporate wellness API
- [FitDays API TypeScript SDK — README](https://github.com/roquerodrino/fitdays-api) — login, sync, weight_list, ext_data parsing
- [fitdays Python async client — README](https://github.com/AboveColin/fitdays/blob/main/README.md) — Measurement fields, self-healing login
- [Intervals.icu API Integration Cookbook](https://forum.intervals.icu/t/intervals-icu-api-integration-cookbook/80090) — wellness upload/download, activity upload, webhooks
- [Intervals.icu Pricing](https://www.intervals.icu/pricing/) — Free $0 tier, Supporter $4/mo
- [Intervals.icu Open API](https://www.intervals.icu/features/open-api/) — REST API, FIT/TCX/GPX upload, OAuth, personal API key

### Claimed (community reports, forum posts)

- [Garmin Forums — Sleep data changes later in the day](https://forums.garmin.com/apps-software/mobile-apps-web/f/garmin-connect-mobile-andriod/409817/sleep-data-changes-later-in-the-day/1935649) — sleep data stability issues reported by users
- [Garmin Forums — Training Readiness docs](https://www.garmin.com/en-US/garmin-technology/running-science/physiological-measurements/training-readiness/) — HRV overnight processing described by Garmin
- [Garmin Forums — Developer Program rejection](https://forums.garmin.com/developer/connect-iq/f/discussion/434542/garmin-connect-developer-program---access-request-rejected-without-notification) — real account rejection example
- [ghurt.org — Why Garmin has no personal API](https://ghurt.org/garmin-api-for-personal-use) — third-party analysis of Garmin's developer program policy
- [Garmin Connect auto-uploader (Inc21)](https://github.com/Inc21/Garmin-Connect-Auto-Uploader) — background FIT upload tool (Wahoo, MyWhoosh → Garmin)
- [RunGap support — Garmin integration down](https://rungap.zendesk.com/hc/en-us/articles/32313611441042-FIXED-Garmin-Connect-integration-down-again) — Garmin integration breakage example

### Dropped

- **Strava API docs** — Not relevant; no health metrics, only activities. Kept in findings but low value.
- **Tapiriik** — Abandoned project, no API contract, no FitDays integration. Dropped entirely.
- **RunGap** — No developer API, no programmatic access. Dropped entirely.
- **Garmin Connect Health SDKs** — Enterprise-only, commercial licensing required. Confirmed dead end for personal use.
- **PyPI garminconnect package pages** — Redundant with GitHub README; data captured above.
- **fitdays-mcp-server (npm)** — Useful as evidence of FitDays API stability, but data already captured from the primary fitdays Python SDK.
- **GARMIN_ACTIVITY_UPLOADER / Peloton-to-Garmin** — Same upload endpoint as garmin_uploader, no additional insights.
