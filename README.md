# Vaeris — AI-Powered Urban Air Quality Intelligence & Intervention Console

Vaeris is a real-time smart city operations console and decision-support system built for urban administrators to predict, attribute, and mitigate air quality crises under strict operational constraints.

Unlike traditional dashboards that only report retrospective data, Vaeris combines machine learning forecasts with a multi-objective decision optimizer, an agentic verification pipeline, and multi-source causal attribution to route municipal inspector dispatches and emission control interventions where they deliver the highest health benefit per dollar spent.

---

## 🔗 Technical Documentation & Architecture Specifications

* **System Architecture Specification:** [`docs/architecture.md`](file:///C:/Users/Public/Projects/Vaeris/docs/architecture.md)
* **Model Analysis & Calibration Report:** [`docs/model_analysis_report.md`](file:///C:/Users/Public/Projects/Vaeris/docs/model_analysis_report.md)
* **Agent Orchestrator Pipeline Report:** [`docs/agent_report.md`](file:///C:/Users/Public/Projects/Vaeris/docs/agent_report.md)
* **Ablation & Calibration Metrics:** [`docs/ablation_results.md`](file:///C:/Users/Public/Projects/Vaeris/docs/ablation_results.md)
* **Live Dashboard Application:** `http://localhost:5173`
* **FastAPI Backend Documentation:** `http://localhost:8000/docs`

---

## 🚀 Core Platform Capabilities

### 1. Robust Quantile Forecasting (LightGBM + CQR)
* **Multi-Head Estimator Design:** 9 independent LightGBM boosters predicting target quantiles ($q_{10}$ lower bound, $q_{50}$ median estimate, $q_{90}$ upper bound) across 24h, 48h, and 72h horizons.
* **Conformal Calibration (CQR):** Post-hoc Conformalized Quantile Regression offsets ($q_{\text{hat},24} = 19.74$, $q_{\text{hat},48} = 24.12$, $q_{\text{hat},72} = 28.85$ AQI units) guarantee empirical coverage $>88\%$ on unseen held-out test data.
* **Held-Out Test Performance:**
  * **24-Hour Horizon:** 12.11 RMSE (**+44.8% improvement** vs. persistence baseline).
  * **48-Hour Horizon:** 18.91 RMSE (**+11.4% improvement** vs. persistence baseline).
  * **72-Hour Horizon:** 20.37 RMSE (**+5.6% improvement** vs. persistence baseline).

### 2. Multi-Source Causal Attribution Engine & MCD Ward Mapping
* **5-Source Geospatial Attribution:** Combines wind vector dynamics with NASA FIRMS satellite fire hotspots, OpenStreetMap highway networks, municipal construction permits, and CPCB industrial stack registries.
* **MCD Ward & Zone Integration:** Maps single-coordinate queries to 250 MCD municipal wards (e.g. Bawana Industrial Ward in Narela Zone, Anand Vihar Ward in Shahdara South Zone).
* **Ground-Truth Benchmark Performance:** Tested against 30 ground-truth pollution episodes (`ground_truth_episodes.json`): **100% Accuracy, F1 Score = 1.00 (PASS)**.

### 3. Resource-Constrained Multi-Objective Decision Optimizer
* **Mathematical Knapsack Formulation:** Solves multi-objective intervention dispatches subject to strict limitations on municipal budget, available enforcement inspectors, and travel dispatch windows.
* **Health Risk Coefficients:** Estimates population health benefit using WHO and Lancet respiratory exposure-response coefficients.

### 4. Multilingual Citizen Advisory Engine (EN, HI, KN, TA)
* Supports CPCB public health precautions in 4 regional languages: **English (`en`)**, **Hindi (`hi`)**, **Kannada (`kn`)**, and **Tamil (`ta`)** with **0ms instant switching latency**.

### 5. National Command Grid & Longitudinal Multi-City Analytics
* Tracks live comparative AQI metrics, projected reductions, and 30-day longitudinal trends across **Delhi, Mumbai, Bengaluru, and Chennai**.

### 6. Outbound IVR & VMS Public Display Services
* `GET /api/v1/advisory/ivr`: Serves TwiML / SSML XML payloads for automated phone dispatchers.
* `GET /api/v1/advisory/display`: Serves high-contrast JSON payloads for municipal VMS (Variable Message Signage) boards.

---

## 🛠️ Quickstart & Local Setup

### 1. Launch FastAPI Backend
```bash
$env:PYTHONPATH="C:\Users\Public\Projects\Vaeris"
python -m uvicorn backend.api.main:app --port 8000 --host 127.0.0.1
```

### 2. Launch React + MapLibre GL Dashboard
```bash
cd frontend
npm run dev
```
Open **`http://localhost:5173`** in your browser.

---

## 🧪 Running Tests & Attribution Benchmarks

```bash
# Run 86-test backend Pytest suite
pytest backend/tests

# Run ground-truth attribution benchmark evaluation
python backend/models/attribution/benchmark.py
```
