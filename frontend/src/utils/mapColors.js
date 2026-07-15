// frontend/src/utils/mapColors.js
//
// Shared colour-ramp utilities for the map layer.
// Extracted from ConfidenceMapToggle.jsx so that the component file
// only exports React components (required by react-refresh/only-export-components).

export const MODE = { FORECAST: "forecast", CONFIDENCE: "confidence" };

// Perceptually-reasonable, colorblind-safer AQI severity ramp
export const AQI_STOPS = [
  { max: 50, color: "#2a9d8f" },       // good
  { max: 100, color: "#8ab17d" },      // satisfactory
  { max: 200, color: "#e9c46a" },      // moderate
  { max: 300, color: "#f4a261" },      // poor
  { max: 400, color: "#e76f51" },      // very poor
  { max: Infinity, color: "#9d0208" }, // severe
];

// Confidence-width ramp: narrow band = confident (teal), wide band = uncertain (violet).
export const CONFIDENCE_STOPS = [
  { max: 20, color: "#2a9d8f" },
  { max: 40, color: "#6d9dc5" },
  { max: 60, color: "#8e7cc3" },
  { max: 80, color: "#b56576" },
  { max: Infinity, color: "#6a0572" },
];

function colorFor(value, stops) {
  for (const stop of stops) {
    if (value <= stop.max) return stop.color;
  }
  return stops[stops.length - 1].color;
}

export function getFillColor(point, mode) {
  if (!point) return "#999999";
  if (mode === MODE.CONFIDENCE) {
    const width = Math.max(
      0,
      (point.upper_bound ?? point.value) - (point.lower_bound ?? point.value)
    );
    return colorFor(width, CONFIDENCE_STOPS);
  }
  return colorFor(point.value, AQI_STOPS);
}
