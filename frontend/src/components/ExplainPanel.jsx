// frontend/src/components/ExplainPanel.jsx
//
// Phase 6 (depth pass) — Implementation Plan, Phase 6 file list. Built LAST
// within Phase 6 per the plan ("if time is short, ship without SHAP rather
// than delay the rest") — this component degrades gracefully to
// attribution-only if no SHAP data is passed in.
//
// Two data sources, both already defined by the backend:
//   1. shapContributions — list of [feature_name, shap_value] tuples, exactly
//      the shape returned by shap_explain.explain_as_waterfall_data()
//   2. attribution — the AttributionResult shape from rule_engine.run_attribution():
//      { primary_cause, confidence_breakdown: {source: pct}, evidence: [...],
//        degraded_sources: [...] }
//
// This is the "explain this prediction" panel from the PRD — clicking a
// forecast point on the map should populate these two props from the
// corresponding /api/v1/forecast and /api/v1/attribution responses.

import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer, ReferenceLine } from "recharts";
import { AlertTriangle, ShieldAlert, MapPin } from "lucide-react";

const FEATURE_LABELS = {
  aqi_lag_1h: "AQI 1h ago",
  aqi_lag_24h: "AQI 24h ago",
  aqi_rolling_mean_6h: "6h rolling avg AQI",
  aqi_rolling_mean_24h: "24h rolling avg AQI",
  wind_speed: "Wind speed",
  wind_direction_sin: "Wind direction",
  wind_direction_cos: "Wind direction",
  fire_count_50km: "Fires within 50km",
  fire_count_100km: "Fires within 100km",
  fire_upwind_flag: "Fire upwind",
  road_density_500m: "Road density",
  land_use_category_code: "Land use type",
  hour_of_day_sin: "Time of day",
  hour_of_day_cos: "Time of day",
  month_of_year: "Season",
  horizon_hours: "Forecast horizon",
};

const SOURCE_LABELS = {
  agricultural_burning: "Agricultural / stubble burning",
  traffic: "Traffic",
  industrial: "Industrial",
  unknown: "Unknown",
};

function friendlyFeatureName(key) {
  return FEATURE_LABELS[key] ?? key.replace(/_/g, " ");
}

const DEFAULT_SHAP = [
  ["aqi_lag_24h", 13.8],
  ["aqi_rolling_mean_24h", 10.2],
  ["fire_count_50km", 8.4],
  ["aqi_lag_1h", 5.6],
  ["wind_direction_cos", -3.1],
  ["road_density_500m", 1.6],
];

const DEFAULT_ATTRIBUTION = {
  primary_cause: "agricultural_burning",
  confidence_breakdown: { agricultural_burning: 0.72, traffic: 0.18, industrial: 0.1 },
  evidence: [
    "14 active fire detections within 50km, upwind, in the last 12 hours",
    "Wind direction consistent with fire-to-station transport (within 30°)",
    "AQI rose 38 points in the 3 hours following estimated smoke arrival",
  ],
  degraded_sources: [],
  ward_info: {
    ward_id: "WARD_DEL_003",
    ward_name: "Connaught Place Ward",
    zone_name: "New Delhi Zone",
    city: "Delhi",
  },
};

function AttributionBar({ label, pct, isPrimary }) {
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className={isPrimary ? "font-semibold text-neutral-800" : "text-neutral-500"}>
          {SOURCE_LABELS[label] ?? label}
        </span>
        <span className={isPrimary ? "font-semibold text-neutral-800" : "text-neutral-500"}>
          {Math.round(pct * 100)}%
        </span>
      </div>
      <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-neutral-100">
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.round(pct * 100)}%`,
            backgroundColor: isPrimary ? "#e76f51" : "#c9c9c9",
          }}
        />
      </div>
    </div>
  );
}

export default function ExplainPanel({
  shapContributions = DEFAULT_SHAP,
  attribution = DEFAULT_ATTRIBUTION,
  modelVersion,
}) {
  const hasShap = Array.isArray(shapContributions) && shapContributions.length > 0;

  const chartData = hasShap
    ? [...shapContributions]
        .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
        .slice(0, 8)
        .map(([feature, value]) => ({
          feature: friendlyFeatureName(feature),
          value: Number(value.toFixed(2)),
        }))
        .reverse()
    : [];

  const sortedBreakdown = Object.entries(attribution?.confidence_breakdown ?? {}).sort(
    (a, b) => b[1] - a[1]
  );

  return (
    <div className="w-full rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-800">Why this prediction?</h3>
          {attribution?.ward_info && (
            <div className="mt-1 flex items-center gap-1.5 text-xs text-neutral-600">
              <MapPin size={12} className="text-rose-500 shrink-0" />
              <span className="font-medium text-neutral-700">
                {attribution.ward_info.ward_name}
              </span>
              <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-[10px] text-neutral-500">
                {attribution.ward_info.zone_name}
              </span>
            </div>
          )}
        </div>
        {modelVersion && (
          <span className="text-[10px] text-neutral-400">model {modelVersion}</span>
        )}
      </div>

      {/* Attribution confidence breakdown */}
      <div className="mt-4 space-y-2">
        {sortedBreakdown.map(([source, pct]) => (
          <AttributionBar
            key={source}
            label={source}
            pct={pct}
            isPrimary={source === attribution.primary_cause}
          />
        ))}
      </div>

      {attribution?.degraded_sources?.length > 0 && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">
          <ShieldAlert size={14} className="mt-0.5 shrink-0" />
          <span>
            {attribution.degraded_sources.map((s) => SOURCE_LABELS[s] ?? s).join(", ")} data was
            unavailable for this prediction — remaining sources were re-normalized (see Section 7.4).
          </span>
        </div>
      )}

      {attribution?.evidence?.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-neutral-100 pt-3 text-xs text-neutral-600">
          {attribution.evidence.map((line, i) => (
            <li key={i} className="flex gap-1.5">
              <span className="text-neutral-300">–</span>
              <span>{line}</span>
            </li>
          ))}
        </ul>
      )}

      {/* SHAP waterfall */}
      <div className="mt-5 border-t border-neutral-100 pt-4">
        <h4 className="text-xs font-semibold text-neutral-700">Forecast feature contributions</h4>
        {hasShap ? (
          <div style={{ width: "100%", height: 220 }}>
            <ResponsiveContainer>
              <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 0 }}>
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis dataKey="feature" type="category" width={130} tick={{ fontSize: 11 }} />
                <ReferenceLine x={0} stroke="#d4d4d4" />
                <Tooltip
                  formatter={(value) => [`${value > 0 ? "+" : ""}${value} AQI pts`, "Contribution"]}
                  contentStyle={{ fontSize: 12 }}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {chartData.map((d, i) => (
                    <Cell key={i} fill={d.value >= 0 ? "#e76f51" : "#2a9d8f"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="mt-2 flex items-center gap-2 rounded-lg bg-neutral-50 p-3 text-xs text-neutral-500">
            <AlertTriangle size={14} />
            SHAP explanation not available for this model version yet — attribution breakdown above
            is still fully valid on its own.
          </div>
        )}
      </div>
    </div>
  );
}
