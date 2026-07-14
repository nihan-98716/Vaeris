# Model Layer — Urban Air Quality Intelligence Platform

Companion code to the ML Model Specification document. Implements:

- `backend/models/forecasting/` — the LightGBM quantile forecasting model (MVP + depth-pass), shared feature engineering, ablation/baseline evaluation, and SHAP explainability
- `backend/models/attribution/` — the rule-and-correlation source attribution engine (not a trained classifier — see the spec doc, Section 7.1, for why)
- `backend/models/health_impact.py` — the indicative respiratory exposure risk calculation
- `backend/models/registry.py` — the generic versioned model artifact registry
- `backend/models/schemas.py` — shared dataclasses (`LatLon`, `ForecastResult`, `AttributionResult`, `HealthImpactResult`)

## Setup

```bash
pip install -r requirements.txt
```

## Running the tests

```bash
python tests/test_features.py
python tests/test_attribution.py
python tests/test_health_impact.py
```

These three test files use only pandas/numpy/stdlib and will run immediately.

## Training the forecasting model

You'll need a CSV of raw hourly station history matching the schema documented
at the top of `backend/models/forecasting/features.py` (station_id, latitude,
longitude, timestamp, aqi, wind_speed, wind_direction, temperature, humidity,
precipitation, boundary_layer_height, fire_count_50km, fire_count_100km,
fire_upwind_flag, road_density_500m, land_use_category).

For a quick synthetic dataset to test against before real ingestion (Phase 1)
is wired up, use `tests/synthetic_data.py`:

```python
from tests.synthetic_data import generate_history
generate_history(days=60).to_csv("synthetic_history.csv", index=False)
```

**MVP model (Phase 2):**
```bash
python -m backend.models.forecasting.train_mvp --data synthetic_history.csv --dataset-snapshot synthetic_v1
```

**Depth-pass quantile model (Phase 6), once the MVP vertical slice is working:**
```bash
python -m backend.models.forecasting.quantile_lgbm --data synthetic_history.csv --horizon 24 --dataset-snapshot synthetic_v1
python -m backend.models.forecasting.quantile_lgbm --data synthetic_history.csv --horizon 48 --dataset-snapshot synthetic_v1
python -m backend.models.forecasting.quantile_lgbm --data synthetic_history.csv --horizon 72 --dataset-snapshot synthetic_v1
```

Both scripts register their output in `model_registry/forecasting/` — see
`backend/models/registry.py` and ML Model Specification Section 6.10.

## Using inference in the API layer

```python
from backend.models.forecasting import inference
from backend.models.schemas import LatLon

def my_history_provider(location: LatLon):
    # Wire this to the PostGIS feature store (Implementation Plan, Phase 1/4).
    # Must return a DataFrame with the same raw schema used in training,
    # containing at least the last 24-48 hours for the nearest station.
    ...

result = inference.predict(LatLon(28.6304, 77.2495), horizon_hours=24, history_provider=my_history_provider)
```

## Using the attribution engine

```python
from backend.models.attribution.rule_engine import run_attribution

signals = {
    "fire_events": [{"distance_km": 42.0, "bearing_deg": 315.0, "detected_hours_ago": 3}],
    "wind_direction_deg": 315.0,
    "wind_speed_ms": 3.0,
    "road_density_500m": 0.2,
    "land_use_category": "residential",
    "aqi_now": 260.0,
    "aqi_rolling_mean_24h": 110.0,
    "hour_of_day": 5,
}
result = run_attribution(signals)
# If FIRMS was unavailable: run_attribution(signals, unavailable_sources=["agricultural_burning"])
```

## Important notes before using in production

1. **`health_impact.DEFAULT_RELATIVE_RISK_PER_UNIT_PM25` is a placeholder.**
   Replace it with the exact coefficient your team extracts from the WHO/GBD
   sources cited in the ML Model Specification, Section 3.6, before showing
   this number to anyone outside the team.

2. **Rule thresholds in `attribution/rules.py`** (fire bearing tolerance,
   road density threshold, AQI spike threshold, etc.) are reasonable
   starting points, not calibrated against real Delhi data. Per the
   Implementation Plan's cross-cutting config requirement, move these into
   `config/weights.yaml` once the backend config system exists, and tune
   them against real ingested data.

3. **Phase 6 (depth pass) has now actually been run, for real** — `lightgbm`
   and `shap` installed cleanly and a real multi-horizon quantile model was
   trained end-to-end on synthetic data (see `docs/ablation_results.md` for
   the real, measured numbers, including an honest miss at 24h and an
   under-coverage finding on the intervals — both flagged there with
   suggested fixes, not hidden). This replaces the earlier sandbox-shim
   validation from the Phase 2/MVP delivery.

## Phase 6 — depth pass (this delivery)

This package adds the Phase 6 depth-pass pieces on top of the earlier MVP:

- **`quantile_lgbm.py` was restructured**: it now trains ONE model across
  all requested horizons (`horizon_hours` is already a feature — see
  `features.py`), instead of one model per horizon. The original per-horizon
  version would have silently overwritten the registry's single `latest`
  pointer each time a new horizon was trained (`registry.py` tracks one
  latest version per *component*, not per horizon) — training 24h → 48h →
  72h in sequence would leave only the 72h model actually being served.
  Per-horizon accuracy is still reported separately (see
  `docs/ablation_results.md`), just not as three competing registry entries.
- **`docs/ablation_results.md`** — real numbers from an actual training run,
  not illustrative placeholders, including two honest findings you should
  read before the demo: the model currently loses to persistence at 24h
  (likely a synthetic-data artifact, flagged for re-measurement on real
  data), and the 80% interval's empirical coverage is only ~57% (the
  quantile bands are currently too narrow — two fix options are given).
- **`frontend/src/components/ConfidenceMapToggle.jsx`** — toggles the map
  between forecast-severity coloring and uncertainty-width coloring, per the
  PRD's confidence-map requirement. Renders its own point list as a stand-in
  until wired into the real MapLibre layer (Phase 4); exposes `getFillColor`
  so the actual map component can reuse the same color logic.
- **`frontend/src/components/ExplainPanel.jsx`** — the "explain this
  prediction" panel: renders the attribution confidence breakdown
  (`rule_engine.run_attribution()`'s output) and, if available, the SHAP
  waterfall (`shap_explain.explain_as_waterfall_data()`'s output). Degrades
  gracefully to attribution-only if SHAP data isn't passed in, matching the
  plan's "ship without SHAP rather than delay the rest" guidance.
- **`model_registry/forecasting/`** — contains only the `metadata.json`
  from the real training run described above, as evidence it happened.
  The trained `.txt` model binaries are intentionally excluded (see
  `model_registry/forecasting/README.md` and `.gitignore`) — per Section
  6.10 of the spec, only metadata is meant to be committed; binaries are
  regenerated locally by re-running `quantile_lgbm.py`.

### Running Phase 6 yourself

```bash
export PYTHONPATH=.

# Generate a synthetic dataset (swap for real ingested data when Phase 1 exists)
python -c "
from tests.synthetic_data import generate_history
generate_history(days=75, seed=42).to_csv('/tmp/history.csv', index=False)
"

# Train the multi-horizon quantile model — registers it and prints the
# same ablation report saved in docs/ablation_results.md
python -m backend.models.forecasting.quantile_lgbm \
    --data /tmp/history.csv --horizons 24,48,72 --dataset-snapshot synthetic_demo_v1
```
