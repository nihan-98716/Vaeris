"""
backend/models/forecasting/inference.py

The stable inference interface — ML Model Specification, Section 6.11.

This is the ONLY module the API layer should import for forecasting.
Its function signature and ForecastResult shape do not change between the
MVP model (Phase 2, q50-only) and the depth-pass quantile model (Phase 6,
q10/q50/q90) — only the model files loaded from the registry change.

Design note on data access: this module does not talk to PostGIS directly.
It expects a `history_provider` callable — in production this is wired to
the ingestion/feature-store layer (Implementation Plan, Phase 1/4); for
testing and the demo script, a synthetic or CSV-backed provider can be
substituted. This keeps the model layer testable without a live database.
"""

from pathlib import Path
from typing import Callable, Dict, Optional

import lightgbm as lgb
import pandas as pd

from backend.models import registry
from backend.models.forecasting.features import build_inference_feature_row
from backend.models.schemas import ForecastResult, LatLon

RELIABLE_HORIZON_CUTOFF_HOURS = 48

# HistoryProvider: given a LatLon, returns a DataFrame of recent raw hourly
# history for the nearest/matching station, in the schema documented in
# features.py. Must return at least ~24-48 hours of rows for lag/rolling
# features to be computable.
HistoryProvider = Callable[[LatLon], pd.DataFrame]


class ModelNotRegisteredError(Exception):
    pass


_loaded_boosters: Dict[str, lgb.Booster] = {}
_loaded_metadata: Optional[dict] = None
_loaded_version_dir: Optional[Path] = None


def _load_boosters(force_reload: bool = False) -> None:
    """
    Loads the latest registered forecasting model(s) into memory. Called
    once at process startup in production (see Implementation Plan, Phase 4
    — models are loaded once, not per-request). Safe to call multiple times;
    only reloads if force_reload=True or nothing has been loaded yet.
    """
    global _loaded_metadata, _loaded_version_dir

    if _loaded_boosters and not force_reload:
        return

    version_dir, metadata = registry.load_latest("forecasting")
    boosters = {}
    for quantile_name in metadata.get("quantiles", ["q50"]):
        model_path = version_dir / f"model_{quantile_name}.txt"
        if not model_path.exists():
            raise ModelNotRegisteredError(
                f"metadata.json lists quantile '{quantile_name}' but {model_path} is missing."
            )
        boosters[quantile_name] = lgb.Booster(model_file=str(model_path))

    _loaded_boosters.clear()
    _loaded_boosters.update(boosters)
    _loaded_metadata = metadata
    _loaded_version_dir = version_dir


def get_loaded_metadata() -> dict:
    _load_boosters()
    return dict(_loaded_metadata)


def predict_from_history(
    station_history_df: pd.DataFrame,
    location: LatLon,
    horizon_hours: int,
) -> ForecastResult:
    """
    Core prediction logic, directly testable without wiring up a real
    history provider — pass in a DataFrame of raw hourly history yourself
    (e.g. in tests, or the demo script).
    """
    _load_boosters()

    feature_row = build_inference_feature_row(station_history_df, horizon_hours)

    q50_booster = _loaded_boosters.get("q50")
    if q50_booster is None:
        raise ModelNotRegisteredError("No q50 (median) model found in the loaded registry entry.")
    value = float(q50_booster.predict(feature_row)[0])

    if "q10" in _loaded_boosters and "q90" in _loaded_boosters:
        lower_bound = float(_loaded_boosters["q10"].predict(feature_row)[0])
        upper_bound = float(_loaded_boosters["q90"].predict(feature_row)[0])
    else:
        # MVP model: point-estimate only, no quantile bounds available yet.
        # Per the spec, the interface shape stays identical — bounds simply
        # collapse to the point estimate until the depth-pass model is registered.
        lower_bound = value
        upper_bound = value

    confidence_tier = "reliable" if horizon_hours <= RELIABLE_HORIZON_CUTOFF_HOURS else "experimental"

    return ForecastResult(
        value=value,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        confidence_tier=confidence_tier,
        model_version=_loaded_metadata["version"],
        horizon_hours=horizon_hours,
    )


def predict(
    location: LatLon,
    horizon_hours: int,
    history_provider: Optional[HistoryProvider] = None,
) -> ForecastResult:
    """
    The documented, stable inference entrypoint (ML Model Specification,
    Section 6.11). In production, `history_provider` is bound at API
    startup to a function reading from the PostGIS feature store
    (Implementation Plan, Phase 1/4) — see backend/api/routes/forecast.py.
    """
    if history_provider is None:
        raise NotImplementedError(
            "predict() requires a history_provider callable that returns recent "
            "raw hourly history for the given location. Wire this up to the "
            "ingestion/feature-store layer (Implementation Plan, Phase 1/4) at "
            "API startup, or pass one explicitly for testing."
        )
    station_history_df = history_provider(location)
    return predict_from_history(station_history_df, location, horizon_hours)
