// frontend/src/components/ConfidenceMapToggle.jsx
//
// Phase 6 (depth pass) — Implementation Plan, Phase 6 file list.
//
// A toggle that switches the dashboard's map layer between:
//   - "Forecast"   : colors wards/grid-cells by the predicted median AQI
//   - "Confidence" : colors wards/grid-cells by how WIDE the model's
//                    uncertainty band is (upper_bound - lower_bound), so a
//                    judge/user can see at a glance where the model is
//                    confident vs. guessing (e.g. far from any station).
//
// Expects an array of forecast points shaped exactly like the backend's
// ForecastResult (backend/models/schemas.py) plus lat/lon, e.g.:
//   { id, latitude, longitude, value, lower_bound, upper_bound,
//     confidence_tier, horizon_hours, model_version }
//
// This component does not render the map itself (that's MapLibre/Mapbox,
// wired in Phase 4) — it renders the toggle control + a legend, and calls
// `onModeChange(mode)` / exposes `getFillColor(point)` so the parent map
// component can apply per-point styling without this component needing to
// know about the mapping library in use.

import { useState, useMemo } from "react";
import { Gauge, Layers } from "lucide-react";
import { MODE, getFillColor, AQI_STOPS, CONFIDENCE_STOPS } from "../utils/mapColors";

const DEFAULT_POINTS = [
  { id: "demo-1", name: "Ward A", value: 312, lower_bound: 268, upper_bound: 349, confidence_tier: "reliable", horizon_hours: 24 },
  { id: "demo-2", name: "Ward B", value: 96, lower_bound: 80, upper_bound: 118, confidence_tier: "reliable", horizon_hours: 24 },
  { id: "demo-3", name: "Ward C", value: 178, lower_bound: 110, upper_bound: 240, confidence_tier: "experimental", horizon_hours: 72 },
];

export default function ConfidenceMapToggle({ points = DEFAULT_POINTS, onModeChange }) {
  const [mode, setMode] = useState(MODE.FORECAST);

  const rows = useMemo(
    () =>
      points.map((p) => ({
        ...p,
        width: Math.max(0, (p.upper_bound ?? p.value) - (p.lower_bound ?? p.value)),
        fill: getFillColor(p, mode),
      })),
    [points, mode]
  );

  function selectMode(next) {
    setMode(next);
    onModeChange?.(next);
  }

  const stops = mode === MODE.CONFIDENCE ? CONFIDENCE_STOPS : AQI_STOPS;
  const legendLabels =
    mode === MODE.CONFIDENCE
      ? ["Narrow (confident)", "20-40", "40-60", "60-80", "Wide (uncertain)"]
      : ["Good", "Satisfactory", "Moderate", "Poor", "Very poor", "Severe"];

  return (
    <div className="w-full rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-neutral-700">
          <Layers size={16} className="text-neutral-500" />
          Map layer
        </div>
        <div className="inline-flex rounded-lg border border-neutral-200 bg-neutral-50 p-0.5">
          <button
            type="button"
            onClick={() => selectMode(MODE.FORECAST)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              mode === MODE.FORECAST
                ? "bg-white text-neutral-900 shadow-sm"
                : "text-neutral-500 hover:text-neutral-700"
            }`}
          >
            Forecast
          </button>
          <button
            type="button"
            onClick={() => selectMode(MODE.CONFIDENCE)}
            className={`inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              mode === MODE.CONFIDENCE
                ? "bg-white text-neutral-900 shadow-sm"
                : "text-neutral-500 hover:text-neutral-700"
            }`}
          >
            <Gauge size={14} />
            Confidence
          </button>
        </div>
      </div>

      <p className="mt-2 text-xs text-neutral-500">
        {mode === MODE.FORECAST
          ? "Colors each area by predicted AQI severity."
          : "Colors each area by how wide the model's uncertainty band is — wide bands mean the model has less to go on (e.g. far from a ground station, or a long forecast horizon)."}
      </p>

      {/* Legend */}
      <div className="mt-3 flex items-center gap-1">
        {stops.map((s, i) => (
          <div key={i} className="flex flex-1 flex-col items-center gap-1">
            <div className="h-2 w-full rounded-full" style={{ backgroundColor: s.color }} />
            <span className="text-[10px] text-neutral-400">{legendLabels[i]}</span>
          </div>
        ))}
      </div>

      {/* Point list — stands in for actual map markers until wired into MapLibre (Phase 4) */}
      <div className="mt-4 divide-y divide-neutral-100 border-t border-neutral-100">
        {rows.map((r) => (
          <div key={r.id} className="flex items-center justify-between py-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full" style={{ backgroundColor: r.fill }} />
              <span className="text-neutral-700">{r.name ?? r.id}</span>
              {r.confidence_tier === "experimental" && (
                <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                  experimental · {r.horizon_hours}h
                </span>
              )}
            </div>
            <div className="text-right text-neutral-500">
              {mode === MODE.FORECAST ? (
                <span className="tabular-nums">{Math.round(r.value)} AQI</span>
              ) : (
                <span className="tabular-nums">±{Math.round(r.width / 2)}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
