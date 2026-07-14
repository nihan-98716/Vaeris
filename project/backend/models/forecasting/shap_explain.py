"""
backend/models/forecasting/shap_explain.py

SHAP explainability for the forecasting model — ML Model Specification,
Section 6.12. Computed only for the q50 (median) model, using LightGBM's
native TreeExplainer support. Built last in the depth pass (Phase 6) —
valuable for the explain-this-prediction dashboard panel, but not blocking.
"""

from typing import Dict, List, Tuple

import pandas as pd
import shap

from backend.models.forecasting.features import FORECASTING_FEATURE_COLUMNS
from backend.models.forecasting.inference import _load_boosters, _loaded_boosters

_explainer_cache = {"explainer": None, "model_version": None}


def _get_explainer():
    _load_boosters()
    q50_booster = _loaded_boosters.get("q50")
    if q50_booster is None:
        raise RuntimeError("No q50 model loaded — cannot build a SHAP explainer.")

    from backend.models.forecasting.inference import _loaded_metadata  # local import avoids a circular-import-at-module-load issue

    if _explainer_cache["model_version"] != _loaded_metadata["version"]:
        _explainer_cache["explainer"] = shap.TreeExplainer(q50_booster)
        _explainer_cache["model_version"] = _loaded_metadata["version"]

    return _explainer_cache["explainer"]


def explain(feature_row: pd.DataFrame) -> Dict[str, float]:
    """
    feature_row: a 1-row DataFrame with columns == FORECASTING_FEATURE_COLUMNS,
    as produced by features.build_inference_feature_row().

    Returns a dict of {feature_name: shap_value}, sorted by absolute
    contribution descending — ready to render directly as a waterfall chart
    in the dashboard's explain-this-prediction panel.
    """
    if list(feature_row.columns) != FORECASTING_FEATURE_COLUMNS:
        raise ValueError(
            "feature_row columns do not match FORECASTING_FEATURE_COLUMNS — "
            "build it via features.build_inference_feature_row(), don't construct it manually."
        )

    explainer = _get_explainer()
    shap_values = explainer.shap_values(feature_row)

    contributions = dict(zip(FORECASTING_FEATURE_COLUMNS, shap_values[0]))
    return dict(sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True))


def explain_as_waterfall_data(feature_row: pd.DataFrame) -> List[Tuple[str, float]]:
    """Convenience wrapper returning an ordered list of (feature, contribution) tuples, for direct chart rendering."""
    return list(explain(feature_row).items())
