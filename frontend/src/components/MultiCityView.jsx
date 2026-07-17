/**
 * frontend/src/components/MultiCityView.jsx
 *
 * Multi-City Comparison Panel (Delhi, Mumbai, Chennai, Bengaluru).
 * Displays a premium national command center grid with local AQI metrics,
 * optimal projected interventions, respiratory risk reductions, and source attributions.
 * Features a comparative bar chart and offline fallback.
 */

import { useState, useEffect } from 'react';
import {
  Activity,
  Layers,
  Sparkles,
  TrendingDown,
  Flame,
  Car,
  Factory,
  ShieldCheck,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
} from 'recharts';

// ─── Local Curated Fallbacks ───────────────────────────────────────────────────

const LOCAL_CITIES_DATA = [
  {
    city_name: "Delhi",
    latitude: 28.6139,
    longitude: 77.2090,
    current_aqi: 320.0,
    primary_cause: "agricultural_burning",
    projected_aqi: 260.0,
    reduction_pct: 18.75,
    health_benefit: 420.0,
    status_level: "high",
    optimal_actions: ["Enforce Stubble Burning Ban", "Enforce Waste Burning Fines"],
  },
  {
    city_name: "Mumbai",
    latitude: 19.0760,
    longitude: 72.8777,
    current_aqi: 145.0,
    primary_cause: "traffic",
    projected_aqi: 110.0,
    reduction_pct: 24.14,
    health_benefit: 280.0,
    status_level: "medium",
    optimal_actions: ["Implement Odd-Even Vehicle Rationing", "Deploy Road Sprinklers"],
  },
  {
    city_name: "Bengaluru",
    latitude: 12.9716,
    longitude: 77.5946,
    current_aqi: 165.0,
    primary_cause: "traffic",
    projected_aqi: 125.0,
    reduction_pct: 24.24,
    health_benefit: 310.0,
    status_level: "medium",
    optimal_actions: ["Implement Odd-Even Vehicle Rationing", "Deploy Road Sprinklers"],
  },
  {
    city_name: "Chennai",
    latitude: 13.0827,
    longitude: 80.2707,
    current_aqi: 115.0,
    primary_cause: "industrial",
    projected_aqi: 92.0,
    reduction_pct: 20.00,
    health_benefit: 190.0,
    status_level: "low",
    optimal_actions: ["Restrict Coal-Fired Industrial Output", "Halt Construction Activities"],
  },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getAqiStyle(aqi) {
  if (aqi <= 50)  return { label: 'Good',          color: 'var(--aqi-good)', bg: 'rgba(110, 231, 168, 0.08)' };
  if (aqi <= 100) return { label: 'Satisfactory',  color: 'var(--aqi-satisfactory)', bg: 'rgba(168, 217, 110, 0.08)' };
  if (aqi <= 200) return { label: 'Moderate',      color: 'var(--aqi-moderate)', bg: 'rgba(232, 210, 110, 0.08)' };
  if (aqi <= 300) return { label: 'Poor',          color: 'var(--aqi-poor)', bg: 'rgba(232, 168, 79, 0.08)' };
  if (aqi <= 400) return { label: 'Very Poor',     color: 'var(--aqi-very-poor)', bg: 'rgba(232, 101, 79, 0.08)' };
  return { label: 'Severe', color: 'var(--aqi-severe)', bg: 'rgba(122, 46, 61, 0.12)' };
}

function getSourceIcon(source) {
  switch (source) {
    case 'agricultural_burning':
      return <Flame size={14} color="#f97316" />;
    case 'traffic':
      return <Car size={14} color="#3b82f6" />;
    case 'industrial':
      return <Factory size={14} color="#a855f7" />;
    default:
      return <Activity size={14} color="var(--color-primary)" />;
  }
}

export default function MultiCityView({ apiBase }) {
  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    async function fetchMultiCity() {
      try {
        const res = await fetch(`${apiBase}/api/v1/multicity`);
        if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
        const result = await res.json();
        if (isMounted) {
          setData(result.cities);
          setIsOffline(false);
          setLoading(false);
        }
      } catch (err) {
        console.warn("Multi-city API failed, using local offline fallbacks:", err);
        if (isMounted) {
          setData(LOCAL_CITIES_DATA);
          setIsOffline(true);
          setLoading(false);
        }
      }
    }

    fetchMultiCity();

    return () => {
      isMounted = false;
    };
  }, [apiBase]);

  // Transform data for double-bar chart
  const chartData = data.map(c => ({
    name: c.city_name,
    "Current AQI": Math.round(c.current_aqi),
    "Projected AQI": Math.round(c.projected_aqi),
    reduction: c.reduction_pct,
  }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header grid info */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={18} color="var(--color-primary)" />
          <div>
            <h2 style={{ fontSize: '15px', fontWeight: 700 }}>National Command Grid</h2>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Comparative smart intervention metrics for major Indian cities</p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <span style={{ fontSize: '10px', background: isOffline ? 'rgba(245, 158, 11, 0.08)' : 'rgba(16, 185, 129, 0.08)', border: `1px solid ${isOffline ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)'}`, padding: '4px 8px', borderRadius: '4px', color: isOffline ? 'var(--color-warning)' : 'var(--color-success)', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
            {isOffline ? <AlertTriangle size={10} /> : <Sparkles size={10} />}
            {isOffline ? "LOCAL SNAPSHOTS ACTIVE" : "LIVE COMPARISON ACTIVE"}
          </span>
        </div>
      </div>

      {/* Grid of 4 City Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
        {loading ? (
          Array(4).fill(0).map((_, i) => (
            <div key={i} className="glass-panel" style={{ height: '220px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ height: '20px', width: '60%', background: 'var(--border-light)', borderRadius: '4px', className: 'pulse-glow' }}></div>
              <div style={{ height: '80px', width: '100%', background: 'var(--border-light)', borderRadius: '6px', className: 'pulse-glow' }}></div>
              <div style={{ height: '20px', width: '40%', background: 'var(--border-light)', borderRadius: '4px', className: 'pulse-glow' }}></div>
            </div>
          ))
        ) : (
          data.map((city, idx) => {
            const currentStyle = getAqiStyle(city.current_aqi);
            const projStyle = getAqiStyle(city.projected_aqi);

            return (
              <div
                key={idx}
                className="glass-panel"
                style={{
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  transition: 'all 0.3s ease',
                  border: `1px solid ${currentStyle.color}25`,
                  boxShadow: `0 4px 20px ${currentStyle.color}05`,
                  position: 'relative',
                  overflow: 'hidden',
                }}
              >
                {/* Subtle city colored glow effect in top corner */}
                <div style={{ position: 'absolute', top: 0, right: 0, width: '60px', height: '60px', background: `radial-gradient(circle, ${currentStyle.color}15 0%, transparent 70%)`, pointerEvents: 'none' }}></div>

                {/* City name and confidence badge */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: 800, color: '#fff' }}>{(city.city_name || city.name || '').toUpperCase()}</h3>
                  <span style={{ fontSize: '9px', textTransform: 'uppercase', color: (city.status_level || 'high') === 'high' ? 'var(--color-success)' : (city.status_level || 'high') === 'medium' ? 'var(--color-warning)' : 'var(--color-danger)', fontWeight: 700 }}>
                    {city.status_level || 'high'} verification
                  </span>
                </div>

                {/* Side-by-Side AQI display */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', background: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-light)', padding: '10px', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <span style={{ fontSize: '8px', color: 'var(--text-muted)', fontWeight: 600 }}>CURRENT AQI</span>
                    <span style={{ fontSize: '18px', fontWeight: 900, color: currentStyle.color }}>{Math.round(city.current_aqi)}</span>
                    <span style={{ fontSize: '8px', color: 'var(--text-muted)' }}>{currentStyle.label}</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', borderLeft: '1px solid var(--border-light)' }}>
                    <span style={{ fontSize: '8px', color: 'var(--text-muted)', fontWeight: 600 }}>PROJECTED AQI</span>
                    <span style={{ fontSize: '18px', fontWeight: 900, color: projStyle.color }}>{Math.round(city.projected_aqi)}</span>
                    <span style={{ fontSize: '8px', color: 'var(--color-success)', fontWeight: 700 }}>-{Math.round(city.reduction_pct || 0)}%</span>
                  </div>
                </div>

                {/* Source attribution indicator */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px' }}>
                  {getSourceIcon(city.primary_cause || 'unknown')}
                  <span style={{ color: 'var(--text-muted)' }}>Dominant source:</span>
                  <strong style={{ color: '#fff', fontSize: '9.5px' }}>{(city.primary_cause || 'unknown').replace('_', ' ').toUpperCase()}</strong>
                </div>

                {/* Indicative health benefit */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10.5px', background: 'rgba(16, 185, 129, 0.04)', border: '1px solid rgba(16, 185, 129, 0.1)', padding: '6px 10px', borderRadius: '6px' }}>
                  <ShieldCheck size={13} color="var(--color-success)" />
                  <span style={{ color: 'var(--text-muted)', fontSize: '9px' }}>Respiratory Risk Reduction:</span>
                  <strong style={{ color: 'var(--color-success)' }}>{Math.round(city.health_benefit || 0)}</strong>
                </div>

                {/* Recommended Municipal interventions */}
                <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: '8px' }}>
                  <span style={{ fontSize: '8.5px', color: 'var(--text-dark)', fontWeight: 700, letterSpacing: '0.5px', display: 'block', marginBottom: '4px' }}>
                    RECOMMENDED DISPATCHES
                  </span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {city.optimal_actions.map((act, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '9.5px', color: 'var(--text-main)' }}>
                        <CheckCircle size={10} color="var(--color-primary)" style={{ flexShrink: 0 }} />
                        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{act}</span>
                      </div>
                    ))}
                  </div>
                </div>

              </div>
            );
          })
        )}
      </div>

      {/* Comparative chart block */}
      {!loading && (
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <TrendingDown size={16} color="var(--color-primary)" />
              <h3 style={{ fontSize: '12.5px', fontWeight: 700, color: '#fff' }}>Comparative Impact Analysis</h3>
            </div>
            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
              Dual-Axis: AQI Levels (Left) vs. Projected Reduction (Right)
            </span>
          </div>

          <div style={{ width: '100%', height: '240px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={chartData}
                margin={{ top: 10, right: 15, left: 10, bottom: 15 }}
                barGap={6}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={10} tickLine={false} />
                <YAxis
                  yAxisId="left"
                  stroke="var(--text-muted)"
                  fontSize={10}
                  tickLine={false}
                  domain={[0, 400]}
                  label={{ value: 'AQI Value', angle: -90, position: 'insideLeft', offset: -5, fill: 'var(--text-dark)', fontSize: 9 }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  stroke="#00f0ff"
                  fontSize={10}
                  tickLine={false}
                  domain={[0, 50]}
                  unit="%"
                  label={{ value: 'Risk Reduction (%)', angle: 90, position: 'insideRight', offset: -5, fill: 'var(--text-dark)', fontSize: 9 }}
                />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-dark)', border: '1px solid var(--border-light)', borderRadius: '8px', fontSize: '11px' }}
                  labelStyle={{ color: 'var(--color-primary)', fontWeight: 'bold' }}
                />
                <Legend verticalAlign="top" height={36} iconSize={10} wrapperStyle={{ fontSize: '10.5px' }} />
                
                <Bar yAxisId="left" dataKey="Current AQI" fill="rgba(249, 115, 22, 0.7)" radius={[4, 4, 0, 0]} barSize={20}>
                  {chartData.map((entry, index) => {
                    const color = getAqiStyle(entry["Current AQI"]).color;
                    return <Cell key={`cell-${index}`} fill={color} fillOpacity={0.3} stroke={color} strokeWidth={1} />;
                  })}
                </Bar>
                
                <Bar yAxisId="left" dataKey="Projected AQI" fill="rgba(16, 185, 129, 0.7)" radius={[4, 4, 0, 0]} barSize={20}>
                  {chartData.map((entry, index) => {
                    const color = getAqiStyle(entry["Projected AQI"]).color;
                    return <Cell key={`cell-proj-${index}`} fill={color} fillOpacity={0.5} stroke={color} strokeWidth={1} />;
                  })}
                </Bar>

                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="reduction"
                  stroke="#00f0ff"
                  strokeWidth={2}
                  dot={{ fill: '#00f0ff', r: 4 }}
                  activeDot={{ r: 6 }}
                  name="Indicative Risk Reduction (%)"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

    </div>
  );
}
