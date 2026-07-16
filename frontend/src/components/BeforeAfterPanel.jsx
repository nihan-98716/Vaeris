/**
 * frontend/src/components/BeforeAfterPanel.jsx
 *
 * Before/After comparison panel: shows current AQI vs "Projected AQI" after
 * the optimal intervention set is applied.
 *
 * Labels: always "PROJECTED AQI" — never "Actual".
 * Health benefit: always "Indicative Health Benefit" — never "DALY".
 *
 * Data flow:
 *   1. Calls /api/v1/decision/scenario (chains optimizer + approximation)
 *   2. Falls back gracefully to a local estimate if the API is unavailable
 *   3. Never blocks the UI — shows loading skeletons while fetching
 */

import { useState, useEffect } from 'react';
import {
  ArrowDown,
  TrendingDown,
  Target,
  Users,
  DollarSign,
  CheckCircle2,
  AlertCircle,
  Info,
} from 'lucide-react';

// ─── Constants ─────────────────────────────────────────────────────────────────

const DEFAULT_BUDGET    = 4000;
const DEFAULT_INSPECTORS = 6;
const DEFAULT_TRAVEL    = 3.0;

// Source-specific offline reduction estimates (when API unavailable)
const OFFLINE_REDUCTIONS = {
  agricultural_burning: { reduction: 53, interventions: [
    { id: 'stubble_burning_enforcement', name: 'Enforce Stubble Burning Ban',    aqi_reduction: 45, cost: 1500, population_affected: 800000,  health_benefit: 420 },
    { id: 'waste_burning_fines',         name: 'Enforce Waste Burning Fines',     aqi_reduction: 8,  cost: 300,  population_affected: 250000,   health_benefit: 95 },
  ]},
  traffic: { reduction: 47, interventions: [
    { id: 'odd_even_rationing',          name: 'Implement Odd-Even Vehicle Rationing', aqi_reduction: 35, cost: 3000, population_affected: 2000000, health_benefit: 380 },
    { id: 'road_sprinklers',             name: 'Deploy Road Sprinklers & Anti-Smog Guns', aqi_reduction: 12, cost: 500, population_affected: 300000, health_benefit: 92 },
  ]},
  industrial: { reduction: 50, interventions: [
    { id: 'restrict_industries',         name: 'Restrict Coal-Fired Industrial Output', aqi_reduction: 30, cost: 2500, population_affected: 1200000, health_benefit: 340 },
    { id: 'halt_construction',           name: 'Halt Construction Activities',         aqi_reduction: 20, cost: 800,  population_affected: 500000,  health_benefit: 175 },
  ]},
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getAqiCategory(aqi) {
  if (aqi <= 50)  return { label: 'Good',         color: '#10b981' };
  if (aqi <= 100) return { label: 'Satisfactory', color: '#84cc16' };
  if (aqi <= 200) return { label: 'Moderate',     color: '#f59e0b' };
  if (aqi <= 300) return { label: 'Poor',         color: '#f97316' };
  if (aqi <= 400) return { label: 'Very Poor',    color: '#ef4444' };
  return { label: 'Severe', color: '#dc2626' };
}

const CONFIDENCE_COLORS = { high: '#10b981', medium: '#f59e0b', low: '#ef4444' };

// ─── Component ─────────────────────────────────────────────────────────────────

export default function BeforeAfterPanel({ currentAqi, primaryCause, apiBase }) {
  const [decisionData, setDecisionData] = useState(null);
  const [scenarioData, setScenarioData] = useState(null);
  const [loading, setLoading]           = useState(true);
  const [apiOk, setApiOk]               = useState(false);

  const baselineAqi = Math.round(currentAqi || 300);
  const cause       = primaryCause || 'traffic';

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    async function fetchScenario() {
      try {
        const url =
          `${apiBase}/api/v1/decision/scenario` +
          `?current_aqi=${baselineAqi}` +
          `&budget=${DEFAULT_BUDGET}` +
          `&inspectors=${DEFAULT_INSPECTORS}` +
          `&max_travel_time_hours=${DEFAULT_TRAVEL}` +
          `&primary_cause=${cause}`;

        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (isMounted) {
          setScenarioData({
            projected_aqi:       data.projected_aqi,
            reduction_applied:   data.reduction_applied,
            source_weight_factor: data.source_weight_factor,
            confidence:          data.confidence,
            current_aqi:         data.current_aqi,
            percent_reduction:   data.percent_reduction,
          });
          setDecisionData(data.decision);
          setApiOk(true);
        }
      } catch {
        // Graceful offline fallback
        if (!isMounted) return;
        setApiOk(false);

        const fallback  = OFFLINE_REDUCTIONS[cause] || OFFLINE_REDUCTIONS.traffic;
        const reduction = fallback.reduction;
        const projected = Math.max(10, baselineAqi - reduction);

        setScenarioData({
          projected_aqi:       projected,
          reduction_applied:   reduction,
          source_weight_factor: cause === 'agricultural_burning' ? 0.85 : 0.7,
          confidence:          'medium',
          current_aqi:         baselineAqi,
          percent_reduction:   parseFloat(((reduction / baselineAqi) * 100).toFixed(1)),
        });
        setDecisionData({
          selected_interventions:   fallback.interventions,
          total_aqi_reduction:      fallback.interventions.reduce((s, i) => s + i.aqi_reduction, 0),
          total_cost:               fallback.interventions.reduce((s, i) => s + i.cost, 0),
          total_health_benefit:     fallback.interventions.reduce((s, i) => s + i.health_benefit, 0),
          total_population_affected: fallback.interventions.reduce((s, i) => s + i.population_affected, 0),
          total_inspectors_used:    2,
          remaining_budget:         DEFAULT_BUDGET - fallback.interventions.reduce((s, i) => s + i.cost, 0),
          remaining_inspectors:     DEFAULT_INSPECTORS - 2,
        });
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    fetchScenario();
    return () => { isMounted = false; };
  }, [baselineAqi, cause, apiBase]);

  // ── Loading skeleton ──
  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="shimmer" style={{ height: 120, borderRadius: 10 }} />
        <div className="shimmer" style={{ height: 52,  borderRadius: 8 }} />
        <div className="shimmer" style={{ height: 44,  borderRadius: 8 }} />
        <div className="shimmer" style={{ height: 44,  borderRadius: 8 }} />
      </div>
    );
  }

  const beforeCat  = getAqiCategory(baselineAqi);
  const afterCat   = scenarioData ? getAqiCategory(scenarioData.projected_aqi) : null;
  const confColor  = scenarioData ? (CONFIDENCE_COLORS[scenarioData.confidence] ?? '#f59e0b') : '#f59e0b';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* ── Split AQI comparison ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 44px 1fr', gap: 8, alignItems: 'center' }}>

        {/* Before */}
        <div
          style={{
            background: `${beforeCat.color}10`,
            border:     `1px solid ${beforeCat.color}30`,
            borderRadius: 10, padding: '16px 12px', textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 4 }}>
            CURRENT AQI
          </div>
          <div
            style={{
              fontSize: 38, fontWeight: 900,
              fontFamily: 'var(--font-family-display)',
              color: beforeCat.color,
            }}
          >
            {baselineAqi}
          </div>
          <div style={{ fontSize: 11, fontWeight: 700, color: beforeCat.color }}>
            {beforeCat.label}
          </div>
        </div>

        {/* Arrow + reduction % */}
        <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
          <ArrowDown size={22} color="#10b981" />
          {scenarioData && (
            <span style={{ fontSize: 10, fontWeight: 800, color: '#10b981' }}>
              −{scenarioData.percent_reduction}%
            </span>
          )}
        </div>

        {/* After / Projected */}
        {scenarioData && afterCat ? (
          <div
            style={{
              background: `${afterCat.color}10`,
              border:     `1px solid ${afterCat.color}30`,
              borderRadius: 10, padding: '16px 12px', textAlign: 'center',
              position: 'relative',
            }}
          >
            <div style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 4 }}>
              PROJECTED AQI
            </div>
            <div
              style={{
                fontSize: 38, fontWeight: 900,
                fontFamily: 'var(--font-family-display)',
                color: afterCat.color,
              }}
            >
              {Math.round(scenarioData.projected_aqi)}
            </div>
            <div style={{ fontSize: 11, fontWeight: 700, color: afterCat.color }}>
              {afterCat.label}
            </div>
            {/* Confidence badge */}
            <div
              style={{
                position: 'absolute', top: 6, right: 6,
                fontSize: 8, fontWeight: 700, textTransform: 'uppercase',
                background: `${confColor}14`,
                color:      confColor,
                border:     `1px solid ${confColor}28`,
                borderRadius: 4, padding: '1px 5px',
              }}
            >
              {scenarioData.confidence} conf.
            </div>
          </div>
        ) : (
          <div
            style={{
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid var(--border-light)',
              borderRadius: 10, padding: 16, textAlign: 'center',
            }}
          >
            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Calculating…</span>
          </div>
        )}
      </div>

      {/* ── Indicative health benefit callout ── */}
      {decisionData && (
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 12,
            background: 'rgba(16,185,129,0.06)',
            border: '1px solid rgba(16,185,129,0.15)',
            borderRadius: 8, padding: '10px 14px',
          }}
        >
          <TrendingDown size={18} color="#10b981" style={{ flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 600 }}>
              INDICATIVE HEALTH BENEFIT
            </div>
            <div style={{ fontSize: 13, fontWeight: 800, color: '#10b981', marginTop: 1 }}>
              {decisionData.total_health_benefit?.toFixed(0)} pts &mdash;{' '}
              {(decisionData.total_population_affected / 1e6).toFixed(2)}M people reached
            </div>
          </div>
        </div>
      )}

      {/* ── Recommended interventions list ── */}
      {decisionData?.selected_interventions?.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div
            style={{
              fontSize: 9, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.5px',
            }}
          >
            RECOMMENDED INTERVENTIONS
          </div>
          {decisionData.selected_interventions.map(item => (
            <div
              key={item.id}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid var(--border-light)',
                borderRadius: 7, padding: '8px 12px', gap: 8,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, flex: 1, minWidth: 0 }}>
                <CheckCircle2 size={12} color="#10b981" style={{ flexShrink: 0 }} />
                <span
                  style={{
                    fontSize: 11, color: 'var(--text-main)', fontWeight: 600,
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}
                >
                  {item.name}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 10, fontSize: 10, color: 'var(--text-muted)', flexShrink: 0 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  <Target size={9} /> −{item.aqi_reduction}
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  <Users size={9} /> {(item.population_affected / 1000).toFixed(0)}k
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  <DollarSign size={9} /> ₹{item.cost.toLocaleString()}
                </span>
              </div>
            </div>
          ))}

          {/* Budget / inspectors summary */}
          {decisionData.total_cost != null && (
            <div
              style={{
                display: 'flex', gap: 14, fontSize: 10, color: 'var(--text-muted)',
                padding: '6px 4px',
              }}
            >
              <span>Total cost: <strong style={{ color: 'var(--text-main)' }}>₹{decisionData.total_cost?.toLocaleString()}</strong></span>
              <span>Inspectors: <strong style={{ color: 'var(--text-main)' }}>{decisionData.total_inspectors_used} deployed</strong></span>
              <span>Remaining budget: <strong style={{ color: '#10b981' }}>₹{decisionData.remaining_budget?.toLocaleString()}</strong></span>
            </div>
          )}
        </div>
      )}

      {/* ── Disclaimer + data source note ── */}
      <div
        style={{
          display: 'flex', alignItems: 'flex-start', gap: 6,
          fontSize: 10, color: 'var(--text-dark)', lineHeight: 1.4,
        }}
      >
        <Info size={10} style={{ flexShrink: 0, marginTop: 1 }} />
        <span>
          Projected AQI is an indicative estimate. Actual outcomes depend on meteorological
          conditions and enforcement fidelity.{' '}
          {apiOk
            ? <span style={{ color: '#10b981' }}><CheckCircle2 size={9} style={{ display: 'inline', verticalAlign: 'middle' }} /> Live optimizer recommendation.</span>
            : <span style={{ color: '#f59e0b' }}><AlertCircle  size={9} style={{ display: 'inline', verticalAlign: 'middle' }} /> Offline approximation mode.</span>}
        </span>
      </div>

    </div>
  );
}
