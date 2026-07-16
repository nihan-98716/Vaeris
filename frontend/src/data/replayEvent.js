/**
 * frontend/src/data/replayEvent.js
 *
 * Offline-embedded historical replay data for the Nov 13-18 2024 Delhi
 * stubble-burning / GRAP-III air quality crisis.
 *
 * This module contains NO fetch/network calls and works entirely without
 * network connectivity. All values are representative of CPCB monitoring
 * data for this confirmed event.
 *
 * Source context:
 *   - CPCB 24h AQI ~491 ("Severe Plus") on November 18, 2024
 *   - PM2.5 peaked near 602 µg/m³ per Centre for Science and Environment analysis
 *   - GRAP-III invoked on November 14, 2024
 *   - Dominant NW wind transport of smoke from Punjab/Haryana stubble burning
 */

export const REPLAY_EVENT_METADATA = {
  eventName: 'Delhi Stubble-Burning Crisis',
  dateRange: 'November 13–18, 2024',
  peakDate: 'November 18, 2024',
  peakAQI: 491,
  peakCategory: 'Severe Plus',
  grapInvoked: 'GRAP-III invoked November 14, 2024',
  description:
    'The worst air quality event of the 2024 Delhi winter season. Stubble burning in ' +
    'Punjab and Haryana, combined with stagnant NW winds and a shallow boundary layer ' +
    '(< 200 m), caused PM2.5 to peak at 602 µg/m³. CPCB 24-hour average AQI reached ' +
    '491 — Severe Plus category.',
};

export const REPLAY_STATIONS = [
  { id: 'DL001', name: 'Anand Vihar',  lat: 28.6476, lon: 77.3158, type: 'Traffic-dominant' },
  { id: 'DL002', name: 'Narela',        lat: 28.8228, lon: 77.0943, type: 'Industrial' },
  { id: 'DL003', name: 'Bawana',        lat: 28.7972, lon: 77.0589, type: 'Agricultural transport' },
  { id: 'DL004', name: 'RK Puram',      lat: 28.5660, lon: 77.1866, type: 'Residential' },
  { id: 'DL005', name: 'Mandir Marg',   lat: 28.6364, lon: 77.2010, type: 'Background monitoring' },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function diurnal(h, base, amplitude, peakHour = 14) {
  return base + amplitude * Math.sin((Math.PI * (h + 5.5 - peakHour)) / 12);
}

function sin14(h) {
  return Math.sin(2 * Math.PI * (h + 5.5 - 14) / 24);
}

// ─── Hourly data (0-143 = 6 days × 24 hours) ─────────────────────────────────

const makeDay = (dayLabel, hourOffset, cfg) =>
  Array.from({ length: 24 }, (_, h) => {
    const { base, amp, wind, blhBase, blhAmp, fires } = cfg;
    return {
      hourIndex:    hourOffset + h,
      date:         dayLabel,
      hour:         h,
      // Station AQIs — gradient across the city with site-type offsets
      aqi_DL001: Math.min(495, Math.round(base[0] + amp[0] * Math.sin(h * 0.26) + h * cfg.slope[0])),
      aqi_DL002: Math.min(495, Math.round(base[1] + amp[1] * Math.sin(h * 0.26) + h * cfg.slope[1])),
      aqi_DL003: Math.min(495, Math.round(base[2] + amp[2] * Math.sin(h * 0.26) + h * cfg.slope[2])),
      aqi_DL004: Math.min(495, Math.round(base[3] + amp[3] * Math.sin(h * 0.26) + h * cfg.slope[3])),
      aqi_DL005: Math.min(495, Math.round(base[4] + amp[4] * Math.sin(h * 0.26) + h * cfg.slope[4])),
      // Meteorological variables
      wind_speed:    parseFloat((wind.base + wind.amp * Math.sin(h / 2)).toFixed(1)),
      wind_dir:      Math.round(cfg.windDir + 20 * Math.sin(h)),
      temperature:   parseFloat(diurnal(h, cfg.tempBase, cfg.tempAmp).toFixed(1)),
      humidity:      parseFloat(diurnal(h, cfg.humBase, -cfg.humAmp).toFixed(1)),
      // Boundary layer height (proxy for dispersion capacity)
      blh: Math.round(blhBase + blhAmp * Math.max(0, Math.sin(Math.PI * (h - 6) / 12))),
      // Active fire hotspot count (peaks at pre-dawn burn windows)
      active_fires:   (h === 5 || h === 8) ? fires : 0,
      primary_cause: cfg.cause(h),
    };
  });

export const REPLAY_HOURLY_DATA = [
  // Nov 13 — starting moderate-poor; SE background winds, mainly traffic
  ...makeDay('Nov 13', 0, {
    base:  [295, 255, 215, 195, 165], amp: [15, 12, 10, 8, 8],
    slope: [1.8, 1.6, 1.5, 1.2, 1.0],
    wind:  { base: 1.5, amp: 0.5 }, windDir: 110,
    tempBase: 20, tempAmp: 5, humBase: 60, humAmp: 20,
    blhBase: 450, blhAmp: 800, fires: 15,
    cause: () => 'traffic',
  }),
  // Nov 14 — GRAP-III invoked; fires rising, wind turning SE→S
  ...makeDay('Nov 14', 24, {
    base:  [340, 295, 250, 225, 190], amp: [15, 12, 10, 9, 8],
    slope: [2.2, 2.0, 1.8, 1.6, 1.3],
    wind:  { base: 1.2, amp: 0.3 }, windDir: 150,
    tempBase: 19.5, tempAmp: 4.5, humBase: 63, humAmp: 18,
    blhBase: 380, blhAmp: 700, fires: 35,
    cause: (h) => (h >= 18 ? 'agricultural_burning' : 'traffic'),
  }),
  // Nov 15 — escalation; burning dominant throughout
  ...makeDay('Nov 15', 48, {
    base:  [390, 345, 300, 270, 235], amp: [18, 14, 12, 10, 9],
    slope: [1.8, 1.6, 1.8, 1.4, 1.1],
    wind:  { base: 1.3, amp: 0.4 }, windDir: 200,
    tempBase: 18.5, tempAmp: 4.5, humBase: 65, humAmp: 17,
    blhBase: 320, blhAmp: 600, fires: 35,
    cause: () => 'agricultural_burning',
  }),
  // Nov 16 — NW wind shift; Punjab smoke transport intensifies; fires ×3
  ...makeDay('Nov 16', 72, {
    base:  [420, 375, 355, 315, 280], amp: [20, 16, 18, 12, 10],
    slope: [2.0, 1.8, 2.2, 1.6, 1.3],
    wind:  { base: 1.8, amp: 0.5 }, windDir: 280,
    tempBase: 18, tempAmp: 4, humBase: 67, humAmp: 16,
    blhBase: 260, blhAmp: 550, fires: 120,
    cause: () => 'agricultural_burning',
  }),
  // Nov 17 — peak approach; strong NW; BLH collapses at night
  ...makeDay('Nov 17', 96, {
    base:  [450, 420, 435, 375, 330], amp: [22, 18, 20, 14, 12],
    slope: [1.6, 1.4, 1.8, 1.3, 1.0],
    wind:  { base: 2.8, amp: 0.8 }, windDir: 315,
    tempBase: 17.5, tempAmp: 4, humBase: 70, humAmp: 15,
    blhBase: 180, blhAmp: 400, fires: 120,
    cause: () => 'agricultural_burning',
  }),
  // Nov 18 — PEAK (Severe Plus, AQI 491); BLH at minimum
  ...makeDay('Nov 18', 120, {
    base:  [470, 450, 460, 420, 390], amp: [15, 14, 16, 12, 10],
    slope: [0.7, 0.6, 0.8, 0.5, 0.4],
    wind:  { base: 2.8, amp: 0.8 }, windDir: 318,
    tempBase: 17, tempAmp: 3.5, humBase: 72, humAmp: 14,
    blhBase: 140, blhAmp: 300, fires: 45,
    cause: () => 'agricultural_burning',
  }),
];

// ─── Daily summary (used for timeline day-selector UI) ────────────────────────

export const REPLAY_DAILY_SUMMARY = [
  { date: 'Nov 13', avgAqi: 240, peakAqi: 340,  category: 'Poor',        fires: 30,  windDir: 'SE',   grapLevel: null         },
  { date: 'Nov 14', avgAqi: 310, peakAqi: 400,  category: 'Poor',        fires: 70,  windDir: 'SE-S', grapLevel: 'GRAP-III'   },
  { date: 'Nov 15', avgAqi: 360, peakAqi: 432,  category: 'Severe',      fires: 70,  windDir: 'S',    grapLevel: 'GRAP-III'   },
  { date: 'Nov 16', avgAqi: 400, peakAqi: 456,  category: 'Severe',      fires: 240, windDir: 'NW',   grapLevel: 'GRAP-III'   },
  { date: 'Nov 17', avgAqi: 440, peakAqi: 481,  category: 'Severe',      fires: 240, windDir: 'NW',   grapLevel: 'GRAP-III'   },
  { date: 'Nov 18', avgAqi: 475, peakAqi: 491,  category: 'Severe Plus', fires: 90,  windDir: 'NW',   grapLevel: 'GRAP-III+'  },
];
