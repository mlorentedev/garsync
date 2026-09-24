# GarSync — UX, DX and Delivery Surface

*Research brief 07 of the garsync architecture research series. All access dates 2026-09-23. Evidence marked **[MEASURED]** (source fetched and read in this session), **[CLAIMED]** (asserted by a source I only saw through search synthesis, or a vendor claim), **[INFERRED]** (my reasoning over the above).*

**Bottom line.** GarSync today is a well-disciplined data pipeline (`make check` green, ruff + `mypy --strict` + pytest in CI, release-please, SOPS, ADRs, lessons, specs) wrapped in a dashboard that is still a *report of numbers*: one page, KPI cards, a heatmap, one trend chart, an activity table — all client-side fetches against a hand-written TypeScript client. What the best personal-health products do is compress, not display: one morning number, three to six named contributors with baseline deltas, and one sentence of "what changed". The delivery surface (Telegram/Apprise digest, PWA with iOS web push, a read-only MCP server bounded by pre-aggregated windows) is cheaper and more differentiating than any new chart, and every ingredient already exists in kubelab. The DX gaps are unglamorous but blocking for a portfolio piece: **there is no LICENSE file** while the README badges MIT (GitHub reports `license: null`), `make smoke` cannot run without live Garmin credentials so no reviewer can ever execute it, coverage is claimed at >80% but never measured, the frontend re-declares the Pydantic schemas by hand, and there is no seeded demo mode. Fix the licence, the seed, and the generated client in v1; schedule the LLM coach and the MCP server for later.

---

## A. What the good personal-health dashboards actually do

1. **Compression is the product, not the chart.** Oura's redesign is explicitly justified by members "having had to sift through multiple data points to distill the need-to-know insights"; the WHOOP breakdown describes the same move — dozens of biometric signals becoming one 0–100 Recovery number each morning, calling the data visualisation "the primary feature, not an afterthought". **[CLAIMED]** — vendor/agency pages, read via search synthesis, not fetched.
   [Oura](https://ouraring.com/blog/new-oura-app-experience/) · [WHOOP breakdown](https://www.925studios.co/blog/whoop-design-breakdown)

2. **The morning briefing has a canonical shape.** Athlytic's own docs describe it: one Recovery score generated once in the morning from HRV + resting HR against a rolling 60-day personal baseline, and — importantly — "the score does not (by default) decrease as you exert yourself"; the exertion target is a *separate* all-day number. Bevel publishes the same 0–100% recovery framing. Athlytic's store listing summarises it as "one number in the morning, one target all day". **[CLAIMED]** (vendor docs via search synthesis).
   [Athlytic — Understanding Recovery](https://athlyticapp.helpscoutdocs.com/article/20-understanding-recovery) · [Bevel — Recovery Score](https://www.bevel.health/blog/what-is-recovery-score)

3. **Load-based dashboards are legitimately chart-heavy, but they anchor on one derived triple.** Intervals.icu's Fitness page is built on the PMC (Fitness/Fatigue/Form = CTL/ATL/TSB), and its forum guides are blunt that the single most valuable visual is that one chart — everything else is secondary. A community-built "cockpit" view puts form status at the top and the week in a three-band grid beneath it. **[CLAIMED]** (vendor feature page + forum posts via search synthesis).
   [Intervals.icu Fitness chart](https://www.intervals.icu/features/fitness-chart/) · [Fitness page guide](https://forum.intervals.icu/t/fitness-page-a-guide-to-getting-started/17702/2)

4. **Apple Fitness gates trends on data volume and lets the user curate the cards.** The iPhone Fitness summary is a card stack the user can add/remove/reorder ("Edit Summary"), and Trends cards only appear after ~6 months of history. **[CLAIMED]** (Apple support pages via search synthesis).
   [See your activity summary](https://support.apple.com/guide/iphone/see-your-activity-summary-iph4c34a8a95/ios) · [Track your trends](https://support.apple.com/en-gb/105003)

5. **Recurring anatomy across all of the above (five blocks, in this order).** **[INFERRED]** from 1–4: (i) one hero score for *today*; (ii) 3–6 contributor rows, each showing value + delta vs personal baseline; (iii) a 30–90 day trend band for the two or three series that changed; (iv) a long-horizon calendar/consistency view; (v) a chronological feed. GarSync has iii, iv, v plus undifferentiated KPI cards, and lacks i and ii entirely.

6. **GarSync's current information architecture, measured.** `frontend/src/pages/index.astro` renders, in order: header with `SyncBadge` + `DateRangePicker`, then `KpiCards`, `Heatmap`, `TrendChart`, `ActivityTable` — a single page, no routes other than `index.astro`, no navigation shell, no hero score, no derived score of any kind in the source tree. **[MEASURED]** ([index.astro on master](https://github.com/mlorentedev/garsync/blob/master/frontend/src/pages/index.astro), local read).

7. **Composite readiness scores are themselves of questionable validity — which is GarSync's opening.** A 2025 review of composite health scores in consumer wearables evaluates the "readiness, recovery, strain" indices of leading manufacturers and finds their methodology, contributors and scientific basis unclear. **[CLAIMED]** (peer-reviewed abstract via search synthesis; DOI below). A portfolio piece that *publishes* its formula, its baseline window and its data coverage next to the score is more defensible than one that copies an opaque 0–100.
   [Readiness, recovery, and strain: composite health scores in consumer wearables](https://doi.org/10.1515/teb-2025-0001)

8. **The physiological signal underneath is real, but it is a signal.** Independent work supports HRV-based daily prescription: RMSSD is the most robust practical metric across sensor types and body positions, and HRV-guided training programmes match predetermined ones with less accumulated effort. So a "today's intensity" recommendation is defensible *if* it states the metric and the baseline window. **[CLAIMED]** (review articles via search synthesis).
   [Monitoring Training Adaptation and Recovery Status (Sensors 2026)](https://www.mdpi.com/1424-8220/26/1/3)

## B. Delivery of insight outside the dashboard

9. **ntfy on iOS from a self-hosted server needs the upstream relay — this is a hard constraint, not a preference.** The ntfy docs are explicit: "Unlike Android, iOS heavily restricts background processing, which sadly makes it impossible to implement instant push notifications without a central server"; you set `upstream-base-url: "https://ntfy.sh"`, which forwards a minimal poll-request containing only the message ID, and "If `upstream-base-url` is not set, notifications will still eventually get to your device, but delivery can take hours". **[MEASURED]** (fetched the config page and read the section).
   [ntfy — iOS instant notifications](https://docs.ntfy.sh/config/#ios-instant-notifications)

10. **Apprise is a router, ntfy is a push endpoint.** The distinction is consistent across comparisons: Apprise fans one API call out to 100+ destinations and delivers nothing itself; ntfy runs its own apps and delivers to phones. Since kubelab already runs Apprise, the correct move is to route GarSync → Apprise → Telegram (and optionally ntfy) rather than to add a notification service. **[CLAIMED]** (comparison articles via search synthesis) + **[MEASURED]** kubelab inventory as given.
    [Apprise vs ntfy compared](https://selfhosting.sh/compare/apprise-vs-ntfy/)

11. **Cadence: the industrial answer is "one decision per morning, one rollup per week" — not per-metric alerts.** Research on push-notification volume frames over-notification as a direct cause of "notification fatigue, resulting in user disengagement or app uninstallation", which is why production notification systems optimise *volume* per user per period rather than per-event delivery. A widely-cloned n8n digest pattern goes further and has the model decide whether there is anything worth sending at all. **[CLAIMED]** (ACM/arXiv abstracts and an n8n template via search synthesis).
    [Notification Volume Control (Pinterest, KDD'18)](https://dl.acm.org/doi/10.1145/3219819.3219906) · [Long-term notification optimisation (arXiv 2202.08812)](https://arxiv.org/pdf/2202.08812)

12. **Home Assistant proves the demand and warns about the fragility.** `cyberjunky/home-assistant-garmin_connect` — MIT, 565 stars, last push **2026-09-22**, 73 forks, 6 open issues — exposes 130+ Garmin sensors to HA. **[MEASURED]** (GitHub API). It exists as a *custom* component because Home Assistant Core dropped the built-in Garmin integration over its reliance on web scraping and Garmin subsequently restricted API access to businesses. **[CLAIMED]** (community write-ups via search synthesis). GarSync's scraper-based `garminconnect` dependency sits on the same footing — which is an argument for delivering insight *out* of the pipeline (digest, MCP, exports) so the SQLite copy keeps its value even if the upstream breaks.
    [github.com/cyberjunky/home-assistant-garmin_connect](https://github.com/cyberjunky/home-assistant-garmin_connect)

## C. Turning an LLM into a coach over this data

13. **Use the right MCP primitive for each job — the spec makes the split explicit.** Tools are model-controlled executable functions; resources are *application-controlled* context addressed by URI, supporting URI templates with arguments and annotations (`audience`, `priority` 0.0–1.0, `lastModified`) that clients use to filter "which resources to include in context"; prompts are user-controlled templates. **[MEASURED]** (fetched both spec pages).
    [MCP — Resources](https://modelcontextprotocol.io/specification/2025-06-18/server/resources) · [MCP — Prompts](https://modelcontextprotocol.io/specification/2025-06-18/server/prompts)

14. **The token budget is decided by tool *shape*, not by data volume.** Tool definitions load into the model's context on every call whether used or not, which is the documented failure mode behind "failed tool calls, wrong parameter values, and retries that waste context"; wide-schema vendors report the same problem from the other side and recommend compact, de-duplicated result shapes. **[CLAIMED]** (AWS ML blog and Axiom blog via search synthesis). Design consequence **[INFERRED]**: six to eight tools maximum, each returning a *pre-aggregated bounded window* (≤31 daily rows or ≤52 weekly rollups) plus an explicit `coverage` field; never a raw intraday series by default.
    [MCP tool design (AWS)](https://aws.amazon.com/blogs/machine-learning/mcp-tool-design-practical-approaches-and-tradeoffs/) · [Designing MCP servers for wide schemas (Axiom)](https://axiom.co/blog/designing-mcp-servers-for-wide-events)

15. **Precedent exists for wrist/health MCP servers, and its granularity is instructive:** user discovery, activity summaries, sleep, workout events, granular time series, and cycle records — i.e. aggregates plus *one* escape hatch for granularity, not twenty tools. **[CLAIMED]** (project READMEs and a vendor blog via search synthesis). I did **not** verify licence, stars or last-commit for these, so I do **not** recommend them; they are design precedents only.
    [Open Wearables](https://github.com/the-momentum/open-wearables) · [personal-health-mcp](https://github.com/adamconde/personal-health-mcp)

16. **GarSync already has the signal a coach needs most: data-coverage honesty.** `docs/lessons/lesson-002-garmin-api-data-availability-gaps.md` exists in-repo, and the schema carries `sync_log`. **[MEASURED]** (repo tree). Any LLM narration must therefore be fed *coverage* alongside values — an invented trend over a 40% gap is the single most likely failure of this feature. **[INFERRED]**

17. **Safety boundary.** Health data leaving the cluster to a model provider is a privacy decision; and an MCP server must be read-only, single-user, and behind the same gate that `src/garsync/api/main.py` already implements (session cookie for pages, `X-API-KEY` or session for `/api/*`, `hmac.compare_digest`, login rate limiter). **[MEASURED]** for the gate; read-only/single-user as **[INFERRED]** design requirement.

## D. Mobile packaging

18. **A PWA is the only mobile path that costs nothing and works on iOS.** WebKit's own announcement states that with iOS/iPadOS 16.4 a Home Screen web app can request push permission "as long as that request is in response to direct user interaction", that the notifications behave like native ones, that Badging API and the manifest `id` member are supported, and — the sentence that matters for a solo operator — "You do not need to be a member of the Apple Developer Program to use it". **[MEASURED]** (fetched webkit.org).
    [Web Push for Web Apps on iOS and iPadOS](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/)

19. **…but it is not installable today, because the manifest does not exist.** `frontend/public/` contains only `favicon.ico` and `favicon.svg`; `frontend/astro.config.mjs` has exactly one integration (`@astrojs/tailwind`) and no PWA integration or `manifest` config. **[MEASURED]** (GitHub tree + local file). The recommended integration is `@vite-pwa/astro` — MIT, 320 stars, last push **2025-11-27**, 14 forks — which generates the manifest and a Workbox service worker; note the ~10 months without a commit, so pin and re-check before adopting. **[MEASURED]** (GitHub API) — the "pin and re-check" part is **[INFERRED]**.
    [github.com/vite-pwa/astro](https://github.com/vite-pwa/astro)

20. **iOS has no programmatic install and that changes onboarding UX.** There is no `beforeinstallprompt` on iOS and no install API — the only path is the Share sheet → "Add to Home Screen"; Android/desktop have the prompt. **[CLAIMED]** (OpenPWA reference pages via search synthesis). Coverage is also not uniform across browsers in earlier versions; not worth chasing. The practical consequence **[INFERRED]**: the dashboard needs a one-time "install this to get morning alerts" panel that detects `navigator.standalone` and instructs, because push permission is *only* requestable from the installed app.

21. **What a PWA cannot do — and why it matters for the scale.** A Home Screen web app has no HealthKit access, no reliable background BLE, no widgets, and no dependable background sync. So the bathroom-scale path must never depend on the phone being open: it has to be a server-side fetch or a file ingest. **[INFERRED]**, consistent with 18–20.

22. **Native shell: skip it, and say so explicitly in the README.** For one operator the costs (Apple Developer Programme, review cycle, a second codebase, no shared types) dwarf the benefits over a PWA whose login gate and same-origin static serving already exist in `main.py` (`StaticFiles(directory=frontend/dist, html=True)`). **[MEASURED]** for the serving model, **[INFERRED]** for the conclusion.

23. **A "lightweight client" already exists and is free: the digest itself.** Telegram/ntfy message = a client with zero install; `garsync brief` in the CLI = a third surface with zero UI work. Both are cheaper than any app shell and both are demoable. **[INFERRED]**.

## E. DX: what mature projects do vs what this repo does

24. **Present and genuinely good (measured inventory).** Makefile with `setup/check/lint/type/test/smoke/dev/docker/clean`; ruff + `ruff format --check`; `mypy --strict`; pytest with `tests/conftest.py` fixtures; `.github/workflows/ci.yml` running lint → type → test for backend and `astro check` → `npm run build` for frontend, with SHA-pinned actions and a venv cache; release-please with `bump-minor-pre-major`; dependabot; a Starlight docs site deployed to GitHub Pages; SOPS+age secrets; ADRs, numbered lessons, and a `specs/SEC-001` SDD folder. **[MEASURED]** (Makefile, ci.yml, release-please-config.json, tree).
    [ci.yml](https://github.com/mlorentedev/garsync/blob/master/.github/workflows/ci.yml) · [Makefile](https://github.com/mlorentedev/garsync/blob/master/Makefile)

25. **Blocker — no licence, while the README claims one.** `README.md` carries an MIT badge and says "MIT — see [LICENSE]", but `LICENSE` returns **HTTP 404** and the GitHub API reports `"license": null` for the repository. Without the file the default is "all rights reserved", which is the worst possible state for a portfolio piece. **[MEASURED]**.

26. **Blocker — the smoke test cannot be run by anyone but the author.** `make smoke` exits early unless `data/garsync.db` exists ("run 'make sync' first"), and `make sync` requires a SOPS-decrypted `.env.tmp` plus live Garmin credentials; `make check` does not invoke `smoke`. So the one end-to-end check is unreachable in CI and for every reviewer. **[MEASURED]** (Makefile). The fix is already half-built: `tests/conftest.py` defines an in-memory DB plus `sample_activity_row` / `sample_biometrics_row` / `sample_sleep_row` fixtures whose keys match the table columns exactly — a `make seed` that writes N days of those rows into `data/garsync.db` makes smoke, CI, screenshots and a public demo all possible at once. **[MEASURED]** for the fixtures, **[INFERRED]** for the remedy.

27. **Coverage is claimed, never measured.** `docs/architecture/prd-v1.md` NFR-1 states "Test coverage >80%", `pytest-cov` is a dev dependency, and neither `make test` nor CI passes `--cov` or a threshold. **[MEASURED]** (pyproject.toml, Makefile, ci.yml). For a portfolio claim, an unmeasured number is worse than no number.

28. **The typed client is hand-maintained and will drift.** `frontend/src/lib/api.ts` declares 14 interfaces (`ActivityItem`, `PaginatedActivities`, `BiometricItem`, `SummaryStats`, `HeatmapResponse`, `SleepResponse`, `SyncStatus`, …) that duplicate the Pydantic models behind `src/garsync/api/schemas.py`, while FastAPI already publishes the same contract at `/openapi.json`. **[MEASURED]** (both files). Recommended generator: `openapi-ts/openapi-typescript` — MIT, 8,380 stars, 666 forks, last push **2026-09-22**, actively maintained — wired as `make client` plus a CI job that regenerates and fails on `git diff --exit-code`. **[MEASURED]**. Note: `hey-api/openapi-typescript` (0 stars, created 2026-06-19) is *not* the maintained home; the real project is the `openapi-ts` org.
    [openapi-ts/openapi-typescript](https://github.com/openapi-ts/openapi-typescript) · [FastAPI — Generating SDKs](https://fastapi.tiangolo.com/advanced/generate-clients/)

29. **Two frontend delivery smells, both one-line fixes.** `api.ts` defaults to `PUBLIC_API_URL ?? "http://localhost:8000"` — so the deployed same-origin build silently depends on a build-time variable being set — and it compiles `PUBLIC_API_KEY` into the static bundle, i.e. a credential baked into a client artifact. Defaulting the base URL to `""` (relative) makes the same-origin case the default, and cookies (already `SameSite=Lax`, `Secure` unless `GARSYNC_INSECURE_COOKIES=1`) make the build-time key unnecessary for the dashboard. **[MEASURED]** (api.ts, main.py).

30. **No browser-level test, no devcontainer, no preview environment.**
    - `frontend/package.json` has no Playwright/Vitest; the only frontend verification is `astro check` + `npm run build`. **[MEASURED]**
    - `.devcontainer/` does not exist anywhere in the tree; the reproducible path for a stranger is: Python 3.12 + Poetry + Node 22 + SOPS + an age key. **[MEASURED]**
    - The workflow set is `ci`, `docs`, `release`, `pr-agent`, `repo-hygiene`, `bitacora-status`, `add-to-project` — nothing per-PR-deployed. **[MEASURED]** A per-PR environment is *possible* on kubelab (Argo CD + K3s + Traefik + Headscale), and established patterns for Argo CD PR-preview Applications exist. **[CLAIMED]** ([Octopus guide](https://octopus.com/blog/creating-temporary-preview-environments-based-pull-requests-argo-cd)). My recommendation for a single-user authenticated app is the cheaper option: Playwright screenshots attached as PR artifacts. **[INFERRED]**

31. **Migrations and observability are the two gaps that bite when the schema grows.** `main.py`'s lifespan calls `init_db(conn)` on every boot while the PRD's FR-1.2 asks for "migraciones versionadas"; there is no version table and no upgrade path — and weight/body-composition/nutrition tables are coming. There is likewise no `/healthz`, no metrics endpoint, and no alerting on a stale sync even though kubelab already runs Grafana + Loki + Vector and Apprise. **[MEASURED]** for the absence. For a personal pipeline the failure mode is *silent* staleness, so `last_sync_age_seconds` plus one Apprise alert at >36h is the highest-value observability item. **[INFERRED]**

32. **Dead dependencies shipped to every install.** `pyproject.toml` still requires `streamlit>=1.63.0` and `plotly>=7.0.0`, and no Streamlit app exists anywhere in the tree (the dashboard is Astro + Chart.js). **[MEASURED]** (pyproject.toml + full file tree). Removing them shortens install, shrinks the image, and removes a misleading signal for anyone reading the dependency list.

33. **Presentation bar, and where GarSync sits.** Strong self-hosted personal dashboards lead with screenshots *and* a live demo (Dashy: "User Showcase | Live Demo | Getting Started | Documentation"); multi-service personal dashboards publish a live demo URL prominently. **[CLAIMED]** ([Dashy](https://github.com/lissy93/dashy)). GarSync's README has badges, a problem/value table and a one-line ASCII data flow, but **no screenshot, no GIF, no live demo, no architecture diagram, and no licence file** — and its Quick Start cannot show a newcomer anything without Garmin credentials and a SOPS key. **[MEASURED]**.

34. **Accessibility and performance bar for a dashboard.** Core Web Vitals targets are public and unambiguous: LCP ≤2.5s, INP ≤200ms, CLS ≤0.1 at the 75th percentile. **[MEASURED]** ([web.dev LCP](https://web.dev/articles/lcp), [INP](https://web.dev/articles/optimize-inp)). WCAG 2.2 AA requires 4.5:1 for body text, 3:1 for large text and for non-text UI, and — via techniques G14/G182 — that information conveyed by colour is *also* available as text. **[MEASURED]** ([WCAG 2.2](https://www.w3.org/TR/WCAG22/), [Quickref](https://www.w3.org/WAI/WCAG22/quickref/?levels=aaa&versions=2.2)). GarSync's heatmap encodes intensity as colour level and its trend series are colour-coded, and PRD NFR-6 already promises LCP <2s — all unmeasured. **[MEASURED]** for the code and the PRD; the mismatch is **[INFERRED]**. Colour-blind-safe categorical palettes are a solved problem (Okabe–Ito / Tol / Brewer) and cost one constants file. **[CLAIMED]** ([data.europa.eu guide](https://data.europa.eu/apps/data-visualisation-guide/accessible-colour-palettes)).

## F. The bathroom scale, because it constrains the UX

35. **FitDays has no public API; three unofficial clients exist and all are small and young.** `AboveColin/fitdays` — MIT, 2 stars, created 2026-07-25, last push **2026-09-14**, async Python, and its own description states "There is no public API, so this package speaks the app's own protocol". `roquerodrigo/fitdays-api` — MIT, 3 stars, created 2026-05-02, last push **2026-09-22**, TypeScript. `fitdays-mcp-server` on npm — MIT, latest 1.2.0, depends on `fitdays-api@1.0.0` and `@modelcontextprotocol/sdk@^1.29.0`. **[MEASURED]** (GitHub API + npm registry). Verdict **[INFERRED]**: use them as *protocol references*, vendor the shape behind GarSync's own adapter interface, pin exact versions, and keep the documented FitDays CSV export as the fallback path.
    [AboveColin/fitdays](https://github.com/AboveColin/fitdays) · [roquerodrigo/fitdays-api](https://github.com/roquerodrigo/fitdays-api) · [fitdays-mcp-server](https://www.npmjs.com/package/fitdays-mcp-server) · [FitDays CSV export docs](https://fitdays.org/docs/user-manual/app-features)

36. **Body composition must be a weekly trend row, not a daily chart.** Bioimpedance scales plus hydration noise make day-over-day fat-percent moves meaningless; every consumer product that gets this right shows weight as a smoothed trend with a weekly cadence. **[INFERRED]** from the UX patterns in 1–5. This is also the cheapest visible "closes the loop on body composition" win.

---

## What this means for garsync

Concretely, in the order I would do it.

1. **Add `LICENSE` (MIT) and fix the README badge to match reality.** One file. Its absence is currently the single most damaging fact about the repo as a portfolio artifact. — finding 25.
2. **Build the morning brief as the primary screen, not a new chart.** Restructure `frontend/src/pages/index.astro` into `Today` (hero score + contributors + one sentence) with `Trends`, `Body`, `Log` as siblings under a bottom tab bar. Reuse `KpiCards.astro` as the contributor-row component rather than writing a new one.
3. **Publish the formula and the coverage next to every derived number.** A readiness score whose definition is visible (`Form = CTL28 − ATL7`; `RMSSD 7d vs 60d baseline`; "12 of 14 days present") is both honest and the differentiator against opaque vendor scores. — findings 6, 7, 16.
4. **Build `make seed` from the fixtures that already exist, then make `smoke` and CI depend on it.** `tests/conftest.py` already produces table-shaped dicts; `make seed DAYS=400` making a deterministic `data/garsync.db` unlocks CI smoke, Playwright, screenshots, a public demo mode, and a 5-minute reviewer onboarding in one change. — finding 26.
5. **Add the coverage gate you already claim.** `--cov=src/garsync --cov-fail-under=80` in `make test` and CI. If the number is 61%, change the PRD to 61% and write the real figure down. — finding 27.
6. **Generate the client.** `make client` (openapi-typescript) + CI drift check; delete the 14 hand-written interfaces. Add the relative-URL default and drop `PUBLIC_API_KEY` from the dashboard path. — findings 28, 29.
7. **Ship insight to a channel, not to a dashboard the user must remember to open.** Daily 07:00 brief and Sunday weekly review through kubelab's existing Apprise → Telegram. Content rule: one derived line, up to three contributor deltas, one deep link — nothing else. No per-metric alerts. — findings 9–11.
8. **Add `/healthz` exposing db reachability and `last_sync_age_seconds`, and one Apprise alert at >36h.** This is the item that protects the whole product from silently becoming a stale-data museum. — finding 31.
9. **Do the PWA in the same pass as the digest,** because the PWA only earns its place through push: manifest + service worker via `@vite-pwa/astro`, an install panel for iOS (no `beforeinstallprompt`, only Share → Add to Home Screen), and web push used for exactly one class of message: "sync failed / data stale". — findings 18–21.
10. **Version the schema before it grows.** `PRAGMA user_version` + an explicit migration step in `init_db`, with a test that upgrades a v1 fixture DB to v2 — do this *before* the weight and nutrition tables land. — finding 31.
11. **Colour and contrast pass, plus a Lighthouse budget.** One palettes file (Okabe–Ito), a numeric legend and `aria-label` on the heatmap so intensity is not colour-only, and a CI Lighthouse run asserting the PRD's own LCP target. — finding 34.
12. **Make the repo self-describing for a reviewer.** Architecture diagram (Mermaid in README is enough), 3–5 screenshots of the seeded demo, one short GIF of the morning brief, and a Quick Start section that reaches a populated dashboard *without* Garmin credentials. — finding 33.
13. **Only then the LLM coach and MCP server.** Read-only, six to eight tools over bounded pre-aggregated windows, two resource templates (`garsync://day/{date}`, `garsync://week/{iso}`), every response carrying coverage, behind the existing session/API-key gate. Weekly narration is a *prompt* with the week's aggregates as a resource — not a tool that reads the database freely. — findings 13–17.

**v1 must-haves:** items 1–9, 11; plus drop `streamlit`/`plotly` from `pyproject.toml` (one line, real install-time and credibility cost) and add a `.devcontainer/` so the "one command" promise survives leaving the author's machine.

**Later (v2+):** the MCP server and LLM narration (13); the body-composition module behind a `ScaleSource` interface with the CSV fallback (35, 36); nutrition logging — which needs a food database, and Open Food Facts is the only free open one I verified exists ([API docs](https://openfoodfacts.github.io/openfoodfacts-server/api/)); per-PR preview environments on kubelab Argo CD, or Playwright screenshots as the cheaper substitute; and a native shell only if widgets or HealthKit ever become requirements.

**Explicitly not recommended:** a native app today (finding 22); copying a vendor's opaque composite score (finding 7); exposing raw intraday series to an LLM (finding 14); per-metric push alerts (finding 11); adopting `hey-api/openapi-typescript` as the codegen home (finding 28).

---

## Open questions and decisions needed

1. **Is the audience the author alone, or a public demo?** This single answer decides whether a seeded demo mode, privacy scrubbing, screenshots-as-artifacts and a licence file are mandatory (they are, if public) or merely nice.
2. **Synthetic fixtures or anonymised real data for the demo?** Synthetic is safe and already half-written; anonymised real data makes screenshots convincing but risks health-data exposure in a public repo. I would choose synthetic and say so in the README.
3. **Where does the LLM run?** Local (Ollama on the homelab, no data leaves the cluster) versus a hosted API. This is a privacy decision, not a performance one, and it gates the whole coach feature.
4. **Which notification channel is authoritative** — Telegram via the existing Apprise, ntfy (which needs the `https://ntfy.sh` upstream relay for iOS instant delivery), or PWA web push (iOS requires a Home Screen install first)? Picking two is reasonable; picking three guarantees noise.
5. **One formula, or a generalisable product?** If the readiness score is tuned for one person, an ADR should say so and forbid generalisation. If it is meant to be a product, it needs validation logic that a single-user dataset cannot supply.
6. **v1 deployment target:** nan.builders Basic Space (env vars only, no platform auth — so GarSync's own login gate is the *only* gate, and there is no PVC-backup story on a free tier) versus kubelab K3s (Authelia OIDC available, PVC, backups, existing observability). The answer changes the auth design: with Authelia, the in-app password gate becomes optional rather than load-bearing.
7. **Scale strategy:** unofficial FitDays protocol (fast, fragile, tiny maintainers), the documented CSV export (manual, stable), or replacing the scale with an open-API vendor. The protocol path is only defensible behind an adapter interface with the CSV path as the tested fallback.
8. **SQLite backup cadence and mechanism under a single replica** — `VACUUM INTO` on a schedule to MinIO is the obvious shape, but someone has to decide whether it blocks the sync window.

---

## Sources

**Kept — primary/technical, fetched in this session [MEASURED]**

- ntfy config, iOS instant notifications — https://docs.ntfy.sh/config/#ios-instant-notifications — access 2026-09-23. The `upstream-base-url` requirement is the constraint that decides the iOS push design.
- WebKit, "Web Push for Web Apps on iOS and iPadOS" — https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/ — access 2026-09-23. Authoritative on Home-Screen-only, user-gesture permission, badging, manifest `id`, no Developer Programme needed.
- MCP specification 2025-06-18 — Resources — https://modelcontextprotocol.io/specification/2025-06-18/server/resources — access 2026-09-23. Application-controlled context, URI templates, annotations, `subscribe`/`listChanged`.
- MCP specification 2025-06-18 — Prompts — https://modelcontextprotocol.io/specification/2025-06-18/server/prompts — access 2026-09-23. User-controlled templates; the right primitive for a weekly review.
- WCAG 2.2 — https://www.w3.org/TR/WCAG22/ and Quickref — https://www.w3.org/WAI/WCAG22/quickref/?levels=aaa&versions=2.2 — access 2026-09-23. Contrast thresholds and the colour-independence techniques (G14/G182).
- web.dev, LCP — https://web.dev/articles/lcp — and INP — https://web.dev/articles/optimize-inp — access 2026-09-23. The 2.5s / 200ms / p75 numbers.
- FastAPI, Generating SDKs — https://fastapi.tiangolo.com/advanced/generate-clients/ — access 2026-09-23. Official guidance that `/openapi.json` is meant to drive client generation.
- GitHub REST API — repo and tree metadata for `mlorentedev/garsync` — https://api.github.com/repos/mlorentedev/garsync — access 2026-09-23. `license: null`, 0 stars, 13 open issues, default branch `master`, last push 2026-09-22.
- `LICENSE` 404 — https://raw.githubusercontent.com/mlorentedev/garsync/master/LICENSE — access 2026-09-23. Proof of the licence gap.
- .github/workflows/ci.yml — https://github.com/mlorentedev/garsync/blob/master/.github/workflows/ci.yml — access 2026-09-23. What CI does and does not run.
- Makefile, on master — https://github.com/mlorentedev/garsync/blob/master/Makefile — access 2026-09-23 (also read locally). `smoke` requires a live-synced DB; `check` omits it.
- Frontend/backend contracts read locally: `frontend/src/lib/api.ts`, `frontend/astro.config.mjs`, `frontend/src/pages/index.astro`, `frontend/package.json`, `src/garsync/api/main.py`, `tests/conftest.py`, `pyproject.toml`, `docs/architecture/prd-v1.md` — access 2026-09-23.
- Repo metadata for recommended dependencies (all via GitHub API / npm registry, access 2026-09-23): `openapi-ts/openapi-typescript` (MIT, 8,380★, pushed 2026-09-22); `vite-pwa/astro` (MIT, 320★, pushed 2025-11-27); `cyberjunky/home-assistant-garmin_connect` (MIT, 565★, pushed 2026-09-22); `AboveColin/fitdays` (MIT, 2★, pushed 2026-09-14); `roquerodrigo/fitdays-api` (MIT, 3★, pushed 2026-09-22); `fitdays-mcp-server` (MIT, npm 1.2.0).

**Kept — secondary, vendor or research claims [CLAIMED]**

- Oura app redesign — https://ouraring.com/blog/new-oura-app-experience/ — access 2026-09-23.
- WHOOP design breakdown — https://www.925studios.co/blog/whoop-design-breakdown — access 2026-09-23.
- Athlytic, Understanding Recovery — https://athlyticapp.helpscoutdocs.com/article/20-understanding-recovery — access 2026-09-23.
- Bevel, What is Recovery Score — https://www.bevel.health/blog/what-is-recovery-score — access 2026-09-23.
- Intervals.icu Fitness chart — https://www.intervals.icu/features/fitness-chart/ and forum guide — https://forum.intervals.icu/t/fitness-page-a-guide-to-getting-started/17702/2 — access 2026-09-23.
- Apple, Fitness summary and trends — https://support.apple.com/guide/iphone/see-your-activity-summary-iph4c34a8a95/ios and https://support.apple.com/en-gb/105003 — access 2026-09-23.
- Composite health scores review — https://doi.org/10.1515/teb-2025-0001 — access 2026-09-23.
- HRV monitoring review (Sensors) — https://www.mdpi.com/1424-8220/26/1/3 — access 2026-09-23.
- Pinterest notification volume control — https://dl.acm.org/doi/10.1145/3219819.3219906 — access 2026-09-23.
- Long-term push-notification optimisation — https://arxiv.org/pdf/2202.08812 — access 2026-09-23.
- MCP tool design tradeoffs (AWS) — https://aws.amazon.com/blogs/machine-learning/mcp-tool-design-practical-approaches-and-tradeoffs/ — access 2026-09-23.
- Axiom, MCP servers for wide schemas — https://axiom.co/blog/designing-mcp-servers-for-wide-events — access 2026-09-23.
- Apprise vs ntfy compared — https://selfhosting.sh/compare/apprise-vs-ntfy/ — access 2026-09-23. Used only for the router-vs-endpoint distinction, which the ntfy docs corroborate.
- OpenPWA, iOS install and push references — https://openpwa.net/reference/installation/ios-add-to-home-screen/ and https://openpwa.net/reference/notifications/ios-safari-push/ — access 2026-09-23. Cross-checks the WebKit primary source.
- Octopus, Argo CD PR preview environments — https://octopus.com/blog/creating-temporary-preview-environments-based-pull-requests-argo-cd — access 2026-09-23.
- Dashy — https://github.com/lissy93/dashy — access 2026-09-23. Cited only as an example of README/demo conventions; licence and commit date not verified, so not recommended as a dependency.
- data.europa.eu, accessible colour palettes — https://data.europa.eu/apps/data-visualisation-guide/accessible-colour-palettes — access 2026-09-23.
- FitDays app features / CSV export — https://fitdays.org/docs/user-manual/app-features — access 2026-09-23.
- n8n digest workflow template — https://n8n.io/workflows/11425-create-personalized-news-digests-with-gpt-51-serpapi-and-telegram-delivery/ — access 2026-09-23. Evidence for the "only send when worth it" pattern.
- Open Food Facts API — https://openfoodfacts.github.io/openfoodfacts-server/api/ — access 2026-09-23. Named only as the free food database if the diet angle proceeds.

**Dropped**

- `screensdesign.com` App Store teardown pages — paywalled screen galleries; the two sentences I could read were promotional.
- `mobbin.com` screen listings — no readable content in the fetched result.
- `colorblind.io` palette guide — a marketing page for the Okabe–Ito/Wong palette; the same hex values are better sourced from the Tol/khroma literature and the EU guide above.
- `xda-developers.com` and `sumguy.com` notification comparisons — opinion listicles; the ntfy primary docs already settle the iOS question.
- `medium.com/uxdesign.co` WHOOP gamification piece and `ixd.prattsi.org` critique — commentary on the same design I already sourced from Oura's and Athlytic's own documentation.
- `home-assistant-guide.com` / `home-assistantinpills.net` — used transiently for the Garmin-scraping history and then dropped in favour of the integration's own repository metadata.
- `open-wearables`, `personal-health-mcp`, `google-health-mcp`, `wellness-project-mcp` — kept as design precedents for MCP tool granularity only; licence, stars and commit dates were **not** verified, so they are explicitly **not** recommended.
- The Pinecone/DigitalOcean AI blog category — summary pages with no primary specification content.

**Not verified, therefore not claimed anywhere above:** whether the FitDays protocol remains stable (no upstream stability statement exists), whether `vite-pwa/astro` will ship updates for Astro 6, the real current test-coverage percentage for garsync, and whether nan.builders Basic Space provides a persistent volume (the brief's deployment implication assumes the scratchpad's recorded decision about a PVC).
