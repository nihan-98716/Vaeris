# Implementation Plan (v2)
## AI-Powered Urban Air Quality Intelligence Platform

**Based on:** PRD v3.1 (final) + implementation plan review
**Repo strategy:** `main` stays always-demoable. Every phase is built on its own branch off `main`, tested, then merged via PR. Never work directly on `main`.
**Branch naming convention:** `phase-N-short-name`
**Commit convention:** `[phase-N] type: short description` — types: `feat`, `fix`, `data`, `chore`, `docs`, `test`

**Changelog from v2.0 (targeted final patches — the phase structure and ordering are considered settled):** Locked the historical replay to a real, verifiable date (November 18, 2024 — Delhi's worst AQI day of that season) instead of a placeholder. Added default optimizer weights to the config example. Added an explicit confidence-reduction formula for graceful degradation instead of leaving it to per-developer interpretation. Added API versioning (`/api/v1/...`), dashboard loading states, model registry metadata, and database constraints (not just indexes). Extended CI to include a frontend build step. Added a representative-location selection method for the MVP forecast. Added team execution policies: branch protection (no direct pushes to `main`), a feature freeze after Phase 7 unless ahead of schedule, and an explicit Definition of Ready alongside each phase's Definition of Done. Adjusted Phase 2's time budget to be realistic about data cleaning and retraining overhead.

## 0.1 Team execution policies

These apply across the whole plan and matter more than any remaining technical detail:

- **Branch protection**: `main` requires a passing CI run and at least one review before merge. No direct pushes to `main`, ever — this is what makes the branch-per-phase structure actually protective rather than cosmetic.
- **Definition of Ready**: no phase starts until the phase(s) it depends on have been verified working against their Definition of Done — not just merged. A merged PR with an untested edge case is not "ready" for the next phase to build on.
- **Feature freeze after Phase 7**: once Phase 7 (replay + before/after) is merged and demoable, no new feature work starts unless the team is demonstrably ahead of schedule. Phases 8–10 are explicitly allowed to be cut or simplified — freeze scope, don't freeze effort on stabilizing what already exists.
- **Offline-first demo strategy, stated explicitly**: the platform must be demoable with no internet connection, using the cached snapshot from Phase 1. This is a real, tested capability (verified in Phase 11), and it's worth stating outright in the pitch deck — it's an unusually strong reliability signal for a hackathon demo.

---

## 0. Cross-cutting infrastructure (applies to every phase below)

These aren't a separate phase — they're standing requirements every phase must satisfy. Called out here once so they don't get silently skipped under time pressure.

| Requirement | What it means in practice |
|---|---|
| **Config, not magic numbers** | All thresholds, weights, and tunables live in `backend/config/settings.py` and `backend/config/weights.yaml` — never hardcoded inline. Optimizer weights (Section 5.2 of the PRD) live in `weights.yaml` from the moment they're introduced (Phase 5B). |
| **Structured logging** | Every module (ingestion, models, API, agent) logs through a single `backend/logging/logger.py`. At minimum: pipeline run start/end, model inference calls, API errors, optimizer decisions, agent trigger events. |
| **Graceful degradation on external API failure** | Every external data source (CPCB, OpenAQ, FIRMS, OpenWeather/ERA5, OSM) must have a defined fallback: if it fails, the system continues with reduced confidence rather than crashing. This is implemented in Phase 1 and referenced by every phase that consumes that data. |
| **API schemas** | Every FastAPI endpoint has an explicit Pydantic request/response model — no endpoint returns ad hoc dict/JSON. |
| **Cache TTLs** | Every Redis-cached value has an explicit TTL, set per data type (e.g. forecast: 15 min, attribution: 30 min) — defined in `backend/config/settings.py`, not left to default/infinite. |
| **Database indexes** | PostGIS tables get spatial indexes (GiST) on geometry columns and standard indexes on timestamp columns from the schema's first migration, not added later as an afterthought. |
| **Database constraints** | Beyond indexes: `NOT NULL` on required fields, `CHECK` constraints on value ranges (e.g. AQI ≥ 0), `UNIQUE` constraints on station+timestamp pairs to prevent duplicate ingestion — especially on timestamp columns, where duplicate/out-of-order writes are the most likely bug. |
| **API versioning** | All endpoints are versioned from the start: `/api/v1/forecast`, `/api/v1/decision`, etc. — never bare `/forecast`. Costs nothing now, avoids a breaking change later. |
| **Secrets** | Real API keys are never committed. `.env` is gitignored from Phase 0; `.env.example` holds placeholders only. |
| **CI** | A GitHub Actions workflow runs, in order: `black` → `ruff` → `pytest` → **frontend build** (`npm run build`) on every push, from Phase 0 onward. The frontend build step catches breakage CI would otherwise miss. |
| **One-command local stack** | The entire stack (Postgres+PostGIS, Redis, backend, frontend) runs via a single `docker-compose up`. Demo machines differ — this removes "works on my machine" as a risk on demo day. |

---

## Phase 0 — Project scaffolding, config, logging, and CI

**Branch:** `phase-0-project-setup`
**Corresponds to:** Day 1 (morning)
**Depends on:** nothing

### Description
Set up the repository skeleton and — per review — the infrastructure that was previously missing: configuration, logging, and CI, built in from the start rather than retrofitted.

### Tasks
- Initialize monorepo structure (`backend/`, `frontend/`, `data/`, `docs/`)
- Set up Python environment (backend) and Node environment (frontend)
- Configure PostgreSQL + PostGIS and Redis locally via Docker Compose
- Set up `.env.example` for all API keys; confirm `.env` is gitignored
- Set up linting/formatting (`ruff`/`black`, `eslint`/`prettier`)
- Build `backend/config/settings.py` (central config loader) and an initial `backend/config/weights.yaml` stub
- Build `backend/logging/logger.py` (structured logger used by every later phase)
- Set up GitHub Actions CI: lint + test on every push
- Write root `README.md` and `docs/architecture.md`

### Files created
```
docker-compose.yml
.env.example
.gitignore
README.md
.github/workflows/ci.yml
backend/requirements.txt
backend/pyproject.toml
backend/config/__init__.py
backend/config/settings.py
backend/config/weights.yaml
backend/logging/__init__.py
backend/logging/logger.py
frontend/package.json
frontend/vite.config.js
docs/architecture.md
```

### Definition of done
- `docker-compose up` brings up Postgres+PostGIS and Redis locally
- `git push` triggers CI and it passes on the empty scaffold
- `settings.py` successfully loads values from `.env` and `weights.yaml`
- Any module can call `logger.info(...)` and see structured output

### Commit messages
```
[phase-0] chore: initialize monorepo structure and docker-compose services
[phase-0] chore: add central config system (settings.py + weights.yaml)
[phase-0] chore: add structured logging module
[phase-0] chore: add GitHub Actions CI (lint + test)
[phase-0] docs: add architecture diagram and root README
```

### Merge
PR: `phase-0-project-setup` → `main`.

---

## Phase 1 — Data ingestion pipeline (with graceful degradation)

**Branch:** `phase-1-data-ingestion`
**Corresponds to:** Days 1–2
**Depends on:** Phase 0

### Description
Build the ingestion layer for one city (Delhi). Per review, **data alignment — not modeling — is the biggest engineering risk**: different sources have different update frequencies, coordinate reference systems, and timestamp formats. This phase treats normalization and fallback behavior as first-class work, not cleanup.

### Tasks
- Implement API clients for CPCB, OpenAQ, FIRMS, OpenWeather/ERA5, OSM
- Implement a **normalization layer**: unify all timestamps to UTC, reconcile CRS across sources into a single spatial reference (EPSG:4326), and resample mismatched update frequencies onto a common time grid
- Implement **graceful degradation per source with an explicit formula**, not ad hoc handling: if a source is unavailable, its weight in the relevant downstream calculation is set to zero and the *remaining* sources are re-normalized to sum to 1. Concretely, for attribution: if FIRMS is unavailable, remove the fire-related rule's contribution entirely and re-normalize the remaining rule confidences (traffic, industry, land-use) proportionally so they still sum to 100% — never leave a silent gap or divide by a stale denominator. The same re-normalization pattern applies to any other source outage.
- Design PostGIS schema with spatial (GiST) indexes on geometry columns, standard indexes on timestamp columns, and constraints (`NOT NULL` on required fields, `CHECK (aqi >= 0)`-style range checks, `UNIQUE` on station+timestamp pairs to prevent duplicate ingestion) from the first migration
- Implement data validation checks (completeness, staleness, null handling)
- **Lock the historical replay date now, not later**: **November 18, 2024** — Delhi's worst air-quality day of that pollution season (CPCB 24h AQI ~491, "severe plus"; PM2.5 peaked around 602 µg/m³ per CSE analysis), following GRAP-III invocation on November 14, 2024. This is a real, publicly documented, checkable event — capture a recorded snapshot of CPCB/OpenAQ/FIRMS/weather data for November 13–18, 2024 as the local fallback dataset used by Phase 7's replay feature. The platform's own attribution engine determines the actual source mix for that window from real data — the date is locked for reproducibility, not because the outcome is predetermined.
- Write ingestion pipeline tests, including a test that simulates one source failing and confirms the re-normalization formula above

### Files created
```
backend/ingestion/__init__.py
backend/ingestion/cpcb_client.py
backend/ingestion/openaq_client.py
backend/ingestion/firms_client.py
backend/ingestion/weather_client.py
backend/ingestion/osm_client.py
backend/ingestion/normalize.py          # timestamp/CRS/frequency reconciliation
backend/ingestion/fallback.py           # per-source graceful degradation + re-normalization
backend/ingestion/pipeline.py
backend/ingestion/validators.py
backend/db/schema.sql                   # includes GiST indexes + NOT NULL/CHECK/UNIQUE constraints
backend/db/connection.py
backend/db/migrations/0001_init.sql
data/snapshots/README.md
data/snapshots/delhi_2024-11-13_to_2024-11-18.json
backend/tests/test_ingestion.py
backend/tests/test_fallback.py
```

### Definition of done
- Pipeline populates PostGIS with real, time/CRS-aligned data for Delhi
- Simulated FIRMS outage test passes: pipeline continues, re-normalizes remaining attribution sources per the formula above, does not crash
- Snapshot for November 13–18, 2024 exists and loads without any live API call
- Schema constraints (`NOT NULL`, `CHECK`, `UNIQUE`) reject at least one deliberately invalid test row
- All ingestion and fallback tests pass in CI

### Commit messages
```
[phase-1] feat: add CPCB, OpenAQ, FIRMS, weather, and OSM clients
[phase-1] feat: add timestamp/CRS/frequency normalization layer
[phase-1] feat: add per-source graceful degradation and fallback logic
[phase-1] feat: add PostGIS schema with spatial and timestamp indexes
[phase-1] feat: add data validation checks
[phase-1] data: capture fallback snapshot for confirmed replay date
[phase-1] test: add ingestion and simulated-outage fallback tests
```

### Merge
PR: `phase-1-data-ingestion` → `main`. Review checklist: confirm at least one source-failure scenario was actually tested, not just handled in theory.

---

## Phase 2 — MVP forecasting model (city/representative-grid level)

**Branch:** `phase-2-forecasting-mvp`
**Corresponds to:** Days 3–4 (budgeted as 1.5 days, not 1 — realistically most of this time goes to data cleaning, missing-value handling, feature debugging, and at least one retrain, not just the initial training run)
**Depends on:** Phase 1

### Description
Per review, start with a **simple, low-risk scope**: a point-estimate LightGBM model at city level or a handful of representative grid cells — not full per-station/per-grid training, which can explode in scope. Quantile bounds, SHAP, and full-grid expansion are deferred to Phase 6, after a vertical demo slice exists.

**Representative location selection method (stated explicitly, not left implicit):** five representative stations are selected manually for the MVP, chosen to cover a spread of source-profile diversity — e.g. one traffic-dominant location, one industrial-zone location, one location historically affected by seasonal stubble-burning transport, and two general-coverage locations. This is a deliberate, statable choice, not an unexplained "representative" placeholder — if time allows later, this can be upgraded to K-means clustering over all monitoring stations, but manual selection is sufficient and defensible for the MVP.

### Tasks
- Build minimal feature engineering (lag features, weather features)
- Train a single LightGBM point-estimate model for the primary city, at a small number of representative locations (not the full grid)
- Implement a basic inference module
- Log training run via `logger`
- Write a smoke test confirming inference returns a plausible number

### Files created
```
backend/models/forecasting/__init__.py
backend/models/forecasting/features.py
backend/models/forecasting/train_mvp.py
backend/models/forecasting/inference_mvp.py
backend/tests/test_forecasting_mvp.py
```

### Definition of done
- A trained model produces a 24h point forecast for at least 3–5 representative locations in the demo city
- No attempt yet to cover the full 1km grid — that's explicitly deferred

### Commit messages
```
[phase-2] feat: add MVP feature engineering
[phase-2] feat: train MVP point-estimate LightGBM model (representative locations)
[phase-2] feat: add MVP inference module
[phase-2] test: add forecasting MVP smoke test
```

### Merge
PR: `phase-2-forecasting-mvp` → `main`.

---

## Phase 3 — MVP attribution engine

**Branch:** `phase-3-attribution-mvp`
**Corresponds to:** Day 3 (parallel with Phase 2 if 2 developers)
**Depends on:** Phase 1

### Description
Build the core rule-and-correlation attribution logic — the FIRMS/wind causal chain plus land-use/traffic correlation — at a basic level sufficient for the first vertical demo slice. Confidence weighting refinement is deferred to Phase 6.

### Tasks
- Implement the FIRMS + wind vector + AQI-spike-timing rule
- Implement basic land-use and traffic-density correlation rules
- Implement a simple ranked output (source + rough confidence), refined later
- Write unit tests with synthetic fire-dominant and traffic-dominant scenarios

### Files created
```
backend/models/attribution/__init__.py
backend/models/attribution/rules.py
backend/models/attribution/rule_engine.py
backend/tests/test_attribution_mvp.py
```

### Definition of done
- Given real Phase 1 data, engine returns a basic ranked attribution with a rough confidence value
- Unit tests cover fire-dominant and traffic-dominant synthetic scenarios

### Commit messages
```
[phase-3] feat: add FIRMS/wind causal correlation rule
[phase-3] feat: add land-use and traffic-density correlation rules
[phase-3] feat: add basic ranked attribution output
[phase-3] test: add attribution MVP unit tests
```

### Merge
PR: `phase-3-attribution-mvp` → `main`.

---

## Phase 4 — MVP API + dashboard (first end-to-end vertical slice)

**Branch:** `phase-4-mvp-dashboard`
**Corresponds to:** Days 4–5
**Depends on:** Phase 2, Phase 3

### Description
**This is the most important phase in the plan.** Per review, the goal is a working, demoable application by day 5–6 — not a polished backend with no frontend. This phase wires the MVP forecast and attribution models to a real (if basic) dashboard. Every Pydantic schema, cache TTL, and index from the cross-cutting section applies here first.

### Tasks
- Build FastAPI app with **versioned** `/api/v1/forecast` and `/api/v1/attribution` endpoints, each with explicit Pydantic response models
- Add Redis caching with explicit TTLs (forecast: 15 min, attribution: 30 min, set in `settings.py`)
- Build a basic command-center dashboard: MapLibre GL map, AQI markers/heatmap for the representative locations, a simple side panel showing forecast + attribution for a selected point
- **Add loading states**: a skeleton UI or spinner for every panel while its API call is in flight — a blank screen during a 1-2 second fetch reads as broken to a judge, even when it isn't
- Wire frontend to the live API
- **Checkpoint: demo this internally to the team on day 5–6, end to end, before starting Phase 5**

### Files created
```
backend/api/__init__.py
backend/api/main.py
backend/api/schemas.py                  # Pydantic request/response models
backend/api/routes/forecast.py
backend/api/routes/attribution.py
backend/api/cache.py                    # Redis wrapper with TTL support
frontend/src/components/CommandCenterLayout.jsx
frontend/src/components/AQIMap.jsx
frontend/src/components/BasicInfoPanel.jsx
frontend/src/components/LoadingSkeleton.jsx
frontend/src/api/client.js
frontend/src/App.jsx
backend/tests/test_api_mvp.py
```

### Definition of done
- Opening the dashboard shows real forecast/attribution data for the demo city, end to end, from live ingested data
- Every endpoint is versioned (`/api/v1/...`) and its response matches a defined Pydantic schema
- Cached responses respect their configured TTL
- Every panel shows a loading state instead of a blank screen while its data is in flight
- **The team can show this to someone unfamiliar with the project and it makes sense as a standalone (if basic) product**

### Commit messages
```
[phase-4] feat: add FastAPI app with Pydantic schemas
[phase-4] feat: add forecast/attribution endpoints with Redis TTL caching
[phase-4] feat: add basic command-center dashboard and map
[phase-4] feat: wire dashboard to live API
```

### Merge
PR: `phase-4-mvp-dashboard` → `main`. **This merge is the day 5–6 checkpoint** — do not proceed to Phase 5 until this works end to end.

---

## Phase 5 — Decision-optimization layer

**Branch:** `phase-5-decision-optimization`
**Corresponds to:** Days 6–7
**Depends on:** Phase 4

### Description
Build the formally-defined, weighted-and-normalized optimizer. Per review, this — not the agent layer — is where disproportionate effort should go, since it's what judges will actually interact with via the decision panel.

**Definition of Ready:** do not start this phase until Phase 4's Definition of Done has been personally verified by whoever starts Phase 5 — i.e. actually open the dashboard and confirm it shows live data, don't just trust that the PR merged.

### Tasks
- Move optimizer weights into `backend/config/weights.yaml` (aqi, population, health, cost) rather than hardcoding — this makes weight experimentation a config change, not a code change. Default weights, stated explicitly rather than left for "whoever gets to it first" to decide:
  ```yaml
  aqi: 0.45
  population: 0.25
  health: 0.20
  cost: 0.10
  ```
- Implement normalization functions per objective term
- Implement the weighted scoring formula reading from `weights.yaml`
- Implement the constrained solver (greedy/knapsack) respecting budget/inspectors/travel-time
- Implement the indicative health-impact estimate (never "DALY" in user-facing strings)
- Add `/decision` endpoint with a Pydantic schema
- Build the decision panel UI showing ranked recommendations with expected reduction, cost, affected population
- Add tests confirming changing `weights.yaml` changes the ranking without a code change

### Files created
```
backend/decision/__init__.py
backend/decision/normalize.py
backend/decision/objective.py           # reads weights from config/weights.yaml
backend/decision/health_impact.py
backend/decision/optimizer.py
backend/api/routes/decision.py
frontend/src/components/DecisionPanel.jsx
backend/tests/test_decision.py
```

### Definition of done
- Editing `weights.yaml` and restarting the service changes recommendation ranking, with no code change required
- Decision panel shows real, specific recommendations with all required fields
- No user-facing string uses "DALY"

### Commit messages
```
[phase-5] feat: move optimizer weights into config/weights.yaml
[phase-5] feat: add normalization functions for objective terms
[phase-5] feat: add weighted scoring formula and constrained solver
[phase-5] feat: add indicative health-impact estimate
[phase-5] feat: add decision endpoint and UI panel
[phase-5] test: add config-driven weight-change tests
```

### Merge
PR: `phase-5-decision-optimization` → `main`.

---

## Phase 6 — Depth pass: quantile forecasting, confidence map, attribution confidence, SHAP

**Branch:** `phase-6-depth-pass`
**Corresponds to:** Days 8–9
**Depends on:** Phase 5

### Description
Now that a working vertical slice exists (Phase 4) and the decision layer is real (Phase 5), invest in depth: upgrade the MVP forecast to full quantile output with grid expansion (as performance allows), refine attribution confidence weighting, and — per review — add SHAP **last**, since it's valuable but not blocking.

### Tasks
- Upgrade forecasting from point-estimate to quantile LightGBM (lower/median/upper)
- Expand grid coverage beyond the initial representative locations, only as far as performance/time allows — do not force full 1km coverage if it risks the schedule
- Add the model registry for versioned artifacts, with a small JSON metadata file per version recording: model version, RMSE (vs. persistence and moving-average baselines), training date, and dataset/snapshot version used — enough to answer "which model produced this, and how good is it" without digging through logs
- Compute and log ablation numbers (RMSE vs. persistence and moving-average baselines) into `docs/ablation_results.md`, with the honest measured number
- Refine attribution into a confidence-weighted, ranked breakdown (e.g. Fire 72% / Traffic 18% / Industry 10%) with primary/secondary labeling
- Build the confidence map toggle UI
- **Last**: add SHAP explainability and the explain-this-prediction waterfall panel — if time is short at the end of this phase, ship without SHAP rather than delay the rest

### Files created
```
backend/models/forecasting/quantile_lgbm.py
backend/models/forecasting/inference.py       # replaces inference_mvp.py
backend/models/registry.py
backend/models/forecasting/ablation.py
docs/ablation_results.md
backend/models/attribution/confidence.py
frontend/src/components/ConfidenceMapToggle.jsx
backend/models/forecasting/shap_explain.py     # built last, see note above
frontend/src/components/ExplainPanel.jsx       # built last, see note above
```

### Definition of done
- Quantile forecast is live for as much of the grid as time allows, with `docs/ablation_results.md` recording real, measured numbers
- Attribution output includes confidence percentages and primary/secondary labeling
- Confidence map toggle works
- SHAP panel works if time allowed; if not, the rest of this phase still ships without it

### Commit messages
```
[phase-6] feat: upgrade forecasting to quantile LightGBM
[phase-6] feat: add model registry
[phase-6] feat: add ablation reporting vs. baselines
[phase-6] feat: add confidence-weighted attribution ranking
[phase-6] feat: add confidence map toggle
[phase-6] feat: add SHAP explainability and explain-prediction panel (if time allows)
```

### Merge
PR: `phase-6-depth-pass` → `main`.

---

## Phase 7 — Before/after comparison and historical replay (moved ahead of the agent)

**Branch:** `phase-7-replay-and-comparison`
**Corresponds to:** Days 10–11
**Depends on:** Phase 5, Phase 6

### Description
Per review, historical replay is more demo-impressive than agent orchestration and doesn't depend on it — so it moves earlier. This phase builds the before/after panel and the historical replay of the confirmed, dated event, both usable in the demo even if the agent layer (Phase 8) ends up simplified or partially cut.

### Tasks
- Implement the shared source-weight approximation used for both the scenario slider and the automatic before/after comparison
- Build the before/after panel, labeled "Projected AQI" throughout — never "Actual"
- Build the historical replay timeline UI for **November 13–18, 2024** using the Phase 1 snapshot — must work with no network connection
- Build the zero-cost split-screen demo-opener slide

### Files created
```
backend/decision/scenario_approximation.py
frontend/src/components/BeforeAfterPanel.jsx
frontend/src/components/ReplayTimeline.jsx
frontend/src/data/replayEvent.js
docs/demo-opener-slide.html
```

### Definition of done
- Before/after panel reflects a real optimizer recommendation, labeled correctly
- Replay works fully offline using the November 13–18, 2024 cached snapshot
- Demo-opener slide exists as a standalone asset

### Commit messages
```
[phase-7] feat: add shared source-weight scenario approximation
[phase-7] feat: add before/after comparison panel
[phase-7] feat: add historical replay timeline for Nov 13-18 2024 (offline-capable)
[phase-7] docs: add split-screen demo opener slide
```

### Merge
PR: `phase-7-replay-and-comparison` → `main`. Treat this as a second major demo checkpoint — the core story (PRD Section 2) is now fully demoable even if Phase 8 gets cut short.

---

## Phase 8 — Agent orchestrator (reduced scope, LLM optional)

**Branch:** `phase-8-agent-orchestrator`
**Corresponds to:** Day 12
**Depends on:** Phase 5, Phase 7

### Description
Per review, this phase is intentionally reduced in scope and priority relative to v1 of this plan. The system must work correctly with **no LLM involved at all** — the LLM only enhances the natural-language explanation on top of an already-functioning deterministic pipeline. If time is short, ship the deterministic version and treat the LLM layer as a stretch goal within this same phase, not a blocker for anything else.

### Tasks
- Implement a **deterministic** pipeline: forecast → attribution → optimizer → structured result. This must work standalone, with no LLM call in the path, before anything else in this phase starts
- Add a Verifier step that cross-checks attribution against a second data source (land-use/traffic) before marking high confidence — this can be simple deterministic logic, not necessarily LLM-based
- Only then: add an LLM call, via a provider-agnostic interface, that turns the structured result into a natural-language summary — with a timeout and fallback: if the LLM call is slow or fails, show the structured result without a prose summary rather than blocking the response past the 3-second target
- Add the consolidated Evidence Score output (confidence % + checklist) — this is deterministic, not LLM-based
- Add the `/investigate` endpoint

### Files created
```
backend/agent/__init__.py
backend/agent/pipeline.py               # deterministic forecast→attribution→optimizer flow
backend/agent/verifier.py               # deterministic cross-check
backend/agent/summary.py                # LLM summary, with timeout + fallback
backend/agent/evidence_score.py
backend/api/routes/investigate.py
backend/tests/test_agent_deterministic.py    # tests the pipeline with the LLM step disabled
backend/tests/test_agent_summary_fallback.py # tests timeout/failure fallback behavior
```

### Definition of done
- `/investigate` returns a complete, correct result with the LLM summary step disabled entirely (env flag or config toggle)
- With the LLM enabled, a simulated slow/failed LLM call still returns the structured result within the 3-second target, just without prose
- Evidence Score output matches Phase 6/7 attribution and decision outputs

### Commit messages
```
[phase-8] feat: add deterministic forecast→attribution→optimizer pipeline
[phase-8] feat: add deterministic Verifier cross-check
[phase-8] feat: add LLM-based summary with timeout and fallback
[phase-8] feat: add consolidated Evidence Score output
[phase-8] feat: add /investigate endpoint
[phase-8] test: add deterministic-mode and LLM-fallback tests
```

### Merge
PR: `phase-8-agent-orchestrator` → `main`. Review checklist: confirm the system was actually tested with the LLM disabled, not just designed to support it in theory.

---

## Phase 9 — Citizen advisory (Demo tier — first thing to cut)

**Branch:** `phase-9-citizen-advisory`
**Corresponds to:** Day 13
**Depends on:** Phase 5

### Description
Unchanged in priority from v1 — explicitly the first feature to drop if the team is behind schedule at this point.

### Tasks
- Implement the advisory prompt template
- Implement English + one additional language
- Add `/advisory` endpoint with Pydantic schema
- Build the citizen advisory UI panel

### Files created
```
backend/api/routes/advisory.py
backend/agent/advisory_prompt.py
frontend/src/components/CitizenAdvisoryPanel.jsx
```

### Definition of done
- Advisory panel returns a specific, non-generic alert in both languages

### Commit messages
```
[phase-9] feat: add citizen advisory prompt template
[phase-9] feat: add advisory endpoint
[phase-9] feat: add citizen advisory UI panel
```

### Merge
PR: `phase-9-citizen-advisory` → `main`. **Skip this phase if behind schedule.**

---

## Phase 10 — Multi-city comparison (Demo tier — lowest priority)

**Branch:** `phase-10-multi-city`
**Corresponds to:** Day 13 (if time allows) or skipped
**Depends on:** Phase 6

### Description
Unchanged — lowest priority, first candidate to skip entirely.

### Tasks
- Ingest a second city via Phase 1 pipeline
- Run inference (not retraining) for the second city
- Build multi-city comparison UI

### Files created
```
frontend/src/components/MultiCityView.jsx
data/processed/<second_city>_snapshot.json
```

### Definition of done
- Dashboard toggles between two cities with real or clearly-labeled sample data

### Commit messages
```
[phase-10] data: ingest and process second city dataset
[phase-10] feat: add multi-city comparison view
```

### Merge
PR: `phase-10-multi-city` → `main`. **Skip entirely if behind schedule** — confirmed lowest priority.

---

## Phase 11 — Integration testing, error-handling audit, demo rehearsal

**Branch:** `phase-11-integration-and-demo-prep`
**Corresponds to:** Day 14 (buffer)
**Depends on:** all prior phases

### Description
Stabilization only — no new features. Adds an explicit audit pass over the graceful-degradation requirements from Section 0, since those are easy to half-implement under time pressure.

### Tasks
- Run full end-to-end integration test
- **Explicitly test every external API failure path** (CPCB down, OpenAQ down, FIRMS down, weather down) and confirm graceful degradation actually holds, not just for the one source tested in Phase 1
- Finalize `docs/ablation_results.md` with final measured numbers
- Confirm every Redis-cached endpoint respects its configured TTL
- Confirm CI is green on the final commit
- Rehearse the demo end to end at least 3 times, timed, including with Wi-Fi disabled (fallback snapshot path)
- Prepare final architecture diagram and demo script

### Files created
```
docs/demo_script.md
docs/final_architecture_diagram.png
tests/test_integration_e2e.py
tests/test_all_source_failures.py
```

### Definition of done
- Full demo runs successfully at least twice in a row without manual intervention
- Demo still works with network disconnected
- Every external source's failure path has been explicitly tested, not just designed
- Ablation numbers in the deck match `docs/ablation_results.md` exactly

### Commit messages
```
[phase-11] test: add end-to-end integration test
[phase-11] test: add tests for every external source failure path
[phase-11] docs: finalize ablation results
[phase-11] fix: [specific bugs found during rehearsal, one commit per fix]
[phase-11] docs: add final demo script and architecture diagram
```

### Merge
PR: `phase-11-integration-and-demo-prep` → `main`. Tag: `git tag submission-v1`.

---

## Branch flow summary (reordered for vertical delivery)

```
main
 ├─ phase-0-project-setup              → merge → main   (config, logging, CI from day 1)
 ├─ phase-1-data-ingestion              → merge → main   (data alignment is the top risk here)
 ├─ phase-2-forecasting-mvp             → merge → main   (parallel with phase-3)
 ├─ phase-3-attribution-mvp             → merge → main   (parallel with phase-2)
 ├─ phase-4-mvp-dashboard               → merge → main   ★ DAY 5-6 CHECKPOINT: working end-to-end demo
 ├─ phase-5-decision-optimization       → merge → main   (disproportionate effort here, not agent)
 ├─ phase-6-depth-pass                  → merge → main   (quantile, confidence, SHAP — SHAP last)
 ├─ phase-7-replay-and-comparison       → merge → main   ★ moved ahead of agent — more demo-impressive
 ├─ phase-8-agent-orchestrator          → merge → main   (LLM optional, deterministic core required)
 ├─ phase-9-citizen-advisory            → merge → main   (skip if behind)
 ├─ phase-10-multi-city                 → merge → main   (skip if behind — lowest priority)
 └─ phase-11-integration-and-demo-prep  → merge → main   (tag: submission-v1)
```

**The single most important structural change from v1:** phases 0–4 now produce a working, if basic, end-to-end product by day 5–6, instead of a fully-built backend with no visible frontend until much later. Every phase after that adds depth and polish to something that already runs, rather than being the first point at which the pieces are connected.

**Enforced throughout:** `main` is branch-protected (CI + review required, no direct pushes). After Phase 7 merges, treat the feature set as frozen unless the team is genuinely ahead of schedule — Phases 8–10 are explicitly expendable, stabilizing what already works is not.

## Optional team role split (for a multi-person team)

| Role | Owns |
|---|---|
| Developer 1 | Ingestion, database, API layer (Phases 1, 4 backend half, 11 API checks) |
| Developer 2 | Forecasting, attribution, optimizer (Phases 2, 3, 5, 6 modeling half) |
| Developer 3 | Dashboard, replay, before/after, evidence UI (Phases 4 frontend half, 6 UI half, 7) |
| Developer 4 (if available) | Agent, citizen advisory, integration, demo polish (Phases 8, 9, 11) |

This split minimizes blocking, since Phase 2/3 (modeling) and Phase 4's frontend half can proceed in parallel once Phase 1 lands.

---

*End of implementation plan — v2.*
