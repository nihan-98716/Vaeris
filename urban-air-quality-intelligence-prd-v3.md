# Product Requirements Document (v3)
## AI-Powered Urban Air Quality Intelligence Platform

**Hackathon:** ET AI Hackathon 2026
**Problem Statement:** #5 — AI-Powered Urban Air Quality Intelligence for Smart City Intervention
**Document version:** 3.1 — final refinement pass; no further architectural revisions planned. Next step is implementation, not another PRD version.
**Timeline:** 2-week build

**Changelog from v3.0 (targeted final refinements only — the architecture itself is considered settled):** Made the optimizer's objective function unit-consistent via normalization and explicit weights. Added per-source confidence percentages to the rule-based attribution output (primary vs. secondary cause). Extended explainability to the optimizer's recommendation, not just the forecast. Locked historical replay to one specific, confirmed, checkable date rather than a placeholder month. Replaced "DALY" with "indicative respiratory exposure risk" in all demo-facing language. Relabeled the before/after panel outputs as "Projected AQI," never "Actual AQI." Added a consolidated Evidence Score panel. Raised the question of whether the LLM is doing meaningful work in the orchestrator, with deterministic orchestration + LLM-for-summary as the fallback design. Swapped the day 12/13 build order so citizen advisory is built before the more easily-cut multi-city view. Added a data-source fallback/caching risk and mitigation. Added a zero-cost split-screen demo opener.

---

## 1. Problem statement

India's air quality crisis spans well beyond Delhi — Mumbai, Kolkata, Bengaluru, and Chennai all show measurable deterioration, and 24 of India's 50 most polluted cities are Tier 1/Tier 2 urban centres (CPCB, 2024). Despite over 900 CAAQMS stations deployed under NCAP, a 2024 CAG audit found only 31% of cities with monitoring data had any actionable multi-agency response protocol linked to those readings. The data exists; the intelligence layer to act on it does not — and even where dashboards exist, none of them answer the question a city administrator actually has: **given limited enforcement resources, what should we do right now?**

## 2. The one-city narrative (anchors the whole demo)

Every feature in this document should trace back to this story, told for one real, named event:

> **Monday, Delhi, November — a stubble-burning episode.**
> AQI spikes in North Delhi. The system detects the spike, attributes it (via wind vector + FIRMS fire detection, not a black-box guess) to agricultural burning 40km northwest rather than local traffic. The decision layer, given a fixed enforcement budget, recommends: dispatch inspectors to two specific hotspots, and flags that local construction dust in Ward 18 is a *secondary, addressable* contributor even though it isn't the dominant cause. The dashboard shows the projected AQI with and without the recommended action — 312 vs. 271, a 41-point difference — and a corresponding drop in estimated respiratory-risk exposure.

This narrative is the backbone of the live demo (Section 12) and the historical replay feature (Section 5.7). Everything else in this PRD exists to make this story true and demonstrable, not just illustrative.

**Demo opener (presentation instruction, not a build item):** open the live demo with a static split-screen slide before touching the dashboard —

```
Left: "Traditional Dashboard"        Right: "This Platform"
      AQI: 312                             AQI: 312
                                            ↓ Primary Cause
                                            ↓ Confidence
                                            ↓ Best Action
                                            ↓ Projected Reduction
                                            ↓ Health Impact
```

This costs nothing to build (it's a single slide) but gives judges the "why is this different" answer in ten seconds, before the live system has even loaded.

## 3. Objectives (measurable, honestly worded)

| Objective | Target |
|---|---|
| Forecast accuracy over naive baseline | RMSE **expected** to improve at least 20% over a persistence baseline at 24h horizon — reported as an actual measured result on held-out data, not promised in advance |
| Forecast horizon | **24h and 48h forecasts are the reliability target.** 72h is offered as an explicitly labeled "experimental / lower-confidence" extension, not a core guarantee |
| Time from signal to recommendation | Under 3 seconds in the live demo, cached/precomputed wherever possible |
| Attribution defensibility | Every attribution claim traceable to a named, cited real data source (wind, fire detection, land use) — no unexplained classifier-only claims |
| Decision usefulness | Every recommendation includes a stated expected AQI reduction and a resource cost, not just a ranked list |
| Dashboard responsiveness | Interactions render in under 2 seconds using precomputed/cached outputs |

## 4. Scope: mandatory components, tiered by depth (unchanged from v2)

| Tier | Component | Depth of implementation |
|---|---|---|
| **Core** | Hyperlocal Predictive AQI Forecasting | Full build: single committed model, uncertainty bounds, ablation validation, confidence map |
| **Core** | Geospatial Pollution Source Attribution | Full build: explainable hybrid rule-and-correlation engine (no black-box classifier) |
| **Core** | Command-center Dashboard | Full build: map, panels, explain-prediction, confidence view, before/after comparison |
| **Secondary** | Enforcement Intelligence & Prioritisation | Now a formally defined constrained optimization (Section 5.2), not a ranking formula |
| **Demo** | Multi-City Comparative Dashboard | Thin aggregation view over existing outputs for a second city |
| **Demo** | Citizen Health Risk Advisory | LLM-generated advisory, 1–2 languages, built last (see revised timeline) |

## 5. Differentiators — refined for technical rigor

### 5.1 Forecasting — one committed model

**Model: LightGBM with quantile loss.** This is now the single committed choice — no "or Prophet or ensemble" hedging. Prophet and ensembling are explicitly future work, not parallel options during the build.

- Reliable range: 24h and 48h, validated against held-out data
- Experimental range: 72h, clearly labeled in the UI as lower-confidence
- Uncertainty is native to quantile LightGBM output (upper/lower quantile predictions), not a separate model

### 5.2 Decision-optimization layer — formally defined

Previously named an algorithm ("greedy/knapsack") without an objective. It is now formally specified:

**Maximize (weighted, normalized score — not a raw sum of incompatible units):**
```
Score = w1 × normalize(AQI Reduction)
      + w2 × normalize(Population Impact)
      + w3 × normalize(Health Benefit)
      − w4 × normalize(Intervention Cost)
```
Each term is min-max normalized to a 0–1 range before weighting, since AQI points, people, and rupees are not directly addable. Starting weights (e.g. w1=0.4, w2=0.3, w3=0.2, w4=0.1) are configurable and stated explicitly in the demo rather than left implicit — this preempts the "how are you adding incompatible quantities" question directly.

**Subject to:**
```
Budget (available enforcement spend)
Inspectors (available personnel)
Travel time (feasible dispatch radius within the decision window)
```

Implemented as a greedy or small knapsack-style solver over this explicit, normalized objective — the algorithm choice is secondary to having a real, unit-consistent objective function, which is what makes the output defensible rather than "just sorting."

Every output is phrased as: *"Action X — expected AQI reduction: N points, cost: inspector-hours Y, affected population: Z."*

### 5.3 Attribution — hybrid rule-and-correlation engine, not a standalone classifier

The standalone GBM classifier from v2 is **removed**. Label provenance was the unresolved question a judge would ask, and there's no honest answer for where "ground truth" source labels would come from in two weeks. Replaced with an explicit, explainable rule-and-correlation engine combining:

- NASA FIRMS fire/hotspot detection + wind vector + AQI spike timing (causal chain, unchanged from v1/v2 — still the strongest single idea in the document)
- Land-use classification (industrial/residential/agricultural zoning)
- Traffic density (OSM road density proxy)
- Weather correlation (stagnant wind conditions favor local accumulation; strong directional wind favors distant transport)

Each attribution output states **which rule(s) fired and why**, rather than a bare probability from an opaque model, and now also carries a **confidence weighting per source** so the output reads as a ranked breakdown rather than a single label — e.g. *Fire 72% · Traffic 18% · Industry 10%* — with the top entry labeled the primary cause and the rest labeled secondary/contributing causes. This is more explainable, more defensible under judge questioning, and removes the "who labeled this" problem entirely.

### 5.4 Agentic orchestrator — simplified

v2's orchestrator listed memory, planning, verification, tool selection, and state as separate subsystems — over-engineered relative to what a single AQI event actually requires. Simplified to a linear, still-genuinely-agentic pipeline:

```
Planner → Executor → Verifier
```

- **Planner**: given a trigger, decides which of the available tools (forecast, attribution, optimizer) are relevant to call and in what order — this is the one piece of real "agentic" decision-making, and it's enough
- **Executor**: calls the selected tools and assembles results
- **Verifier**: cross-checks the Executor's output against a second signal before presenting it as high-confidence (e.g. confirms an attribution claim against the land-use/traffic data before stating it)
- **Memory** is not a separate subsystem — it's just conversation/session state carried across a single investigation, which is sufficient for this use case

Implemented via a provider-agnostic LLM tool-use interface (team may use whichever LLM is most comfortable — this stays unchanged from v2).

**Open question to resolve early in the build, not late:** if the Planner→Executor→Verifier flow only ever calls forecast → attribution → optimizer → summary in that fixed order, an LLM may not be doing meaningful decision-making at all. In that case, implement the Planner and Executor as **deterministic orchestration code** (a plain function pipeline, no LLM involved) and reserve the LLM strictly for the **natural-language summary step** — turning structured outputs into the plain-English investigation report. Only keep the LLM "in the loop" for planning/verification if there's a real scenario where the tool-call order or selection genuinely varies based on intermediate results (e.g. skipping the optimizer if attribution confidence is too low to act on). If that scenario doesn't exist in the two-week build, don't force it in — a deterministic pipeline with an LLM-generated summary is simpler, faster to build, and no less legitimate a system.

### 5.5 Confidence map — unchanged from v2, still a strong differentiator

Toggleable map layer between predicted AQI and prediction confidence, reusing the quantile forecast output directly. No changes.

### 5.6 Health impact — reframed as indicative

Previously implied a precise DALY/hospital-admission figure. The dashboard and demo now avoid the term "DALY" entirely and instead label this output as:

> "Indicative respiratory exposure risk, estimated using published WHO/Lancet exposure-response coefficients. Not a clinical or epidemiological forecast."

DALY-style methodology may still be cited in the appendix/technical write-up as the underlying reference, but the term itself is not used in the live demo or dashboard UI — "indicative respiratory exposure risk" is easier to defend under questioning and doesn't invite a judge to test the DALY math specifically.

### 5.7 Historical replay — one named event, one specific date

Narrowed from "a historical week" to **one specific, named episode**. Team must select and confirm one actual, documented date (e.g. a specific day in the November 2024 Delhi stubble-burning season, verified against CPCB/news records) before building the replay — not a generic "November" placeholder. If a judge asks "did this actually happen," the answer must be a specific, checkable date, not an illustrative composite. This is the single story the demo is built around — the concrete proof of the Section 2 narrative, scrubbed hour-by-hour, presented as a timeline (see Section 7 UI requirement) rather than a static replay screen: *8 AM — AQI rises → fire detected → recommendation generated → projected improvement shown*.

### 5.8 Explainability — SHAP, specifically, for both forecast and decision

Since LightGBM is now the committed forecasting model, explainability is implemented concretely via **SHAP values** on the forecasting model, surfaced in the explain-this-prediction panel as a waterfall chart of feature contributions. This replaces the vaguer "explainability as a cross-cutting requirement" language from v2 with a specific, buildable method.

This is extended to the **decision-optimizer's output** as well, not just the forecast: when the optimizer picks a specific ward for intervention, a simple contribution breakdown (how much each weighted objective term — AQI reduction, population, health benefit, cost — contributed to that ward outranking the alternatives) is shown alongside it. This doesn't need SHAP itself, since the optimizer's scoring formula is already transparent (Section 5.2) — it just needs to be surfaced, not just computed.

### 5.9 Model monitoring — defined metrics, not a bolted-on panel

v2 mentioned "drift, confidence, station health" without definitions. Now concretely scoped to only what's actually computable in two weeks:

- **Missing/stale data**: percentage of expected station readings received in the last hour (a simple completeness check)
- **Forecast confidence**: the width of the quantile interval, already computed by the model — no new metric needed
- **Drift**: explicitly **cut from the core build** unless a clear before/after distribution comparison is trivial to compute; not worth inventing a metric just to have one

### 5.10 Before/after comparison panel — new, directly from review

Every recommended action surfaces a simple, high-impact comparison:

```
Without intervention → Projected AQI = 312
With recommendation  → Projected AQI = 271
Difference            → 41 AQI points (projected)
```

Both values are explicitly labeled **"Projected AQI,"** never "Actual AQI" — this is a model estimate, not a measured outcome, and the UI/labeling must not imply otherwise. This is cheap to build (it's the same source-weight approximation used for the scenario slider in v2, applied automatically to the optimizer's top recommendation) and was specifically flagged as highly persuasive for a live demo.

### 5.11 Evidence score — new

Every recommendation surfaces a single, consolidated evidence summary rather than making the judge piece together confidence from separate panels:

```
Confidence: 92%
Evidence:
  ✓ Fire detection (FIRMS)
  ✓ Wind vector consistent
  ✓ Traffic data ruled out as primary
  ✓ Satellite aerosol signal consistent
```

This is a thin presentation layer over data already computed in Sections 5.3 (rule confidence) and 5.4 (Verifier's cross-checks) — no new modeling work, but it fits naturally with the explainability focus and gives judges one place to see "why should I trust this" at a glance.

## 6. Explicitly optional / out of scope (unchanged from v2, reconfirmed)

- ❌ Sensor calibration layer — no paired cheap/reference sensor dataset available
- ❌ Crowdsourced attribution reporting — no real users in a demo, adds surface area without improving core AI
- ❌ Four-language UI at launch — ship 1–2 languages fully
- ❌ Full model-rerun scenario simulation — source-weight approximation only
- ❌ Standalone attribution classifier — replaced by the rule-and-correlation engine (5.3)
- ❌ Prophet / ensemble forecasting in parallel with LightGBM — future work only
- ❌ Data-drift metric — cut unless trivially computable

## 7. UI/UX requirements

| Feature | Description | Status |
|---|---|---|
| Command-center layout | Persistent map (~60% viewport) + live side panel | Core |
| Explain-this-prediction panel | SHAP waterfall chart of feature contributions | Core |
| Confidence map toggle | AQI view vs. prediction-confidence view | Core |
| Decision panel | Optimizer's recommended interventions with expected reduction, cost, affected population | Core |
| Before/after comparison panel | AQI with vs. without recommended action | Core |
| Scenario simulation slider | Source-weight approximation, not full rerun | Core |
| Historical replay | The named Delhi November stubble-burning event, scrubbed hour-by-hour | Demo device |
| Bilingual UI | English + one additional language | Core (built last, see Section 11) |
| Accessible color scale | Perceptually uniform, colorblind-safe AQI ramp | Core |

## 8. System architecture (training and inference now separated)

```
Data sources (CPCB, OpenAQ, Sentinel/MODIS, OpenWeather/ERA5, NASA FIRMS, OSM)
        │
        ▼
Ingestion & feature pipeline (scheduled pulls, spatial joins, feature store)
        │
        ├──────────────────────────┐
        ▼                          ▼
  Training pipeline          Inference pipeline
  (offline, run once/        (online, serves the
   periodically to           dashboard from cached,
   produce the LightGBM      precomputed outputs)
   quantile model)                 │
        │                          │
        └────────► Model registry ◄┘
                   (trained model
                    artifact, versioned)
                          │
                          ▼
            Core prediction layer (inference-time)
  ├─ Forecasting (LightGBM quantile, 24h/48h reliable, 72h experimental)
  ├─ Attribution (rule-and-correlation engine, Section 5.3)
  └─ SHAP explainability outputs
        │
        ▼
Decision layer
  └─ Decision-optimization agent (Section 5.2, formal objective + constraints)
        │
        ▼
Agentic orchestrator (Planner → Executor → Verifier)
        │
        ▼
API & orchestration layer (FastAPI, Redis cache, model registry hooks)
        │
        ▼
Web dashboard (React + MapLibre GL + Recharts)
  ├─ Multi-city comparison (Demo tier)
  └─ Citizen advisory (Demo tier, built last)
```

## 9. Tech stack

| Layer | Choice | Rationale |
|---|---|---|
| Database | PostgreSQL + PostGIS | Native spatial joins |
| Cache | **Redis** | Fast serving of precomputed forecasts/attributions to the API layer |
| Pipeline scheduling | Cron / lightweight Airflow | Periodic data pulls |
| Forecasting | **LightGBM (quantile loss) — single committed choice** | Fast, explainable via SHAP, native uncertainty support |
| Attribution | Rule-and-correlation engine (Section 5.3) | Fully explainable, no label-provenance problem |
| Explainability | **SHAP** | Concrete, standard, works natively with LightGBM |
| Decision optimization | Greedy/knapsack solver over the formal objective (5.2) | Lightweight, explainable |
| Agent orchestration | Provider-agnostic LLM tool-use interface; **LangGraph only if the Planner→Executor→Verifier flow genuinely benefits from graph-based state management** — otherwise a plain tool-calling loop is sufficient and simpler | Avoids adding framework complexity the simplified agent doesn't need |
| Backend API | FastAPI | Python-native, fast to build |
| Frontend | React + **MapLibre GL** + Recharts/Plotly | MapLibre is fully open source, avoids licensing concerns Mapbox can raise |

## 10. Data sources (unchanged from v2)

| Source | Use | Access |
|---|---|---|
| CPCB CAAQMS | Ground-truth AQI readings | Public data portal/API |
| OpenAQ | Supplementary AQI coverage | Public REST API |
| Sentinel-5P / MODIS | Aerosol index, NO2 column density | Public, free tier |
| OpenWeather / ERA5 | Wind, humidity, temperature, precipitation | Public API |
| NASA FIRMS | Active fire/hotspot detection | Public, free API |
| OpenStreetMap | Road density, POIs | Public |
| WHO/Lancet exposure-response coefficients | Indicative health-impact conversion | Published, citable |

## 11. Two-week build plan (rebalanced — replay and citizen advisory no longer crammed together)

| Days | Milestone |
|---|---|
| 1–4 | Ingestion pipeline live for the Delhi target city; LightGBM quantile forecasting working end-to-end (24h/48h reliable range) |
| 5–6 | Rule-and-correlation attribution engine, including FIRMS causal correlation |
| 7–8 | Dashboard core: command-center layout, map, SHAP explain-prediction panel, confidence map |
| 9–10 | Decision-optimization layer (formal objective + constraints) and simplified Planner→Executor→Verifier orchestrator |
| 11 | Before/after comparison panel; historical replay built specifically around the confirmed, dated Delhi stubble-burning event; Evidence Score panel |
| 12 | Citizen advisory (1–2 languages, Demo tier) — built before multi-city since it carries more visible demo value |
| 13 | Multi-city aggregation (second city, Demo tier) — the first thing cut if the team is running behind, since it's the least central to the core narrative |
| 14 | Buffer — ablation numbers finalized, integration testing, demo rehearsal, deck, architecture diagram |

## 12. Judging criteria alignment

| Criterion | Weight | Primary features addressing it |
|---|---|---|
| Innovation | 25% | Decision-optimization layer with formal objective, explainable rule-based attribution, simplified but genuine agentic orchestrator |
| Business Impact | 25% | Indicative health-impact framing, before/after comparison panel, one-city narrative (Section 2) |
| Technical Excellence | 20% | SHAP explainability, single committed forecasting model with honest horizon labeling, separated training/inference architecture |
| Scalability | 15% | Stateless API, Redis caching, model registry, provider-agnostic LLM interface |
| User Experience | 15% | Command-center layout, confidence map, decision panel, before/after comparison, historical replay |

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Data quality — missing values, broken stations, inconsistent update frequency, timezone mismatches | Build data-validation checks into ingestion from day 1 — still the top engineering risk |
| RMSE target not met on held-out data | Report the actual measured number in the deck regardless of outcome; frame the 20% figure as expected, not guaranteed, from the outset |
| 72h forecast quality is poor | Label it experimental in the UI; do not feature it in the core demo narrative |
| Judges question attribution label provenance | Pre-empted by removing the classifier entirely in favor of the rule-and-correlation engine |
| Orchestrator behaves inconsistently | Fixed, small tool set; rehearse the same trigger scenarios repeatedly before demo day |
| Decision-optimizer constraints look arbitrary | Use a clearly-labeled placeholder ("assume 5 inspectors, ₹X budget") rather than presenting it as calibrated to a real city's actual capacity |
| Timeline slip on days 9–11 (the technically hardest stretch) | Day 14 buffer exists specifically for this; multi-city aggregation (Demo tier, day 13) is the first thing cut if slippage occurs |
| External data source unavailable during development or on demo day (CPCB, OpenAQ, FIRMS, OpenWeather/ERA5 outage or rate-limiting) | Cache a recorded snapshot of each source's data for the confirmed replay date (Section 5.7) and keep it as a local fallback dataset from day 1 — never depend on a live API call succeeding during the actual demo |

---

*End of document — v3.*
