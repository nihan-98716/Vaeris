/**
 * frontend/src/components/ReplayTimeline.jsx
 *
 * Historical replay timeline for the Nov 13-18 2024 Delhi Stubble-Burning Crisis.
 * Works fully OFFLINE — all data is embedded via replayEvent.js, no network calls.
 *
 * Features:
 *  - Day-by-day selector with AQI severity indicators and GRAP level badges
 *  - Animated play/pause that auto-advances through the 6-day event
 *  - Hourly AQI line chart (all 5 monitoring stations) with reference lines
 *  - Key event annotations: GRAP-III, NW wind shift, Peak AQI 491
 *  - Station legend, weather stats row, offline badge
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import {
  Play,
  Pause,
  RotateCcw,
  Wind,
  Flame,
  AlertTriangle,
  Clock,
  WifiOff,
} from 'lucide-react';
import {
  REPLAY_EVENT_METADATA,
  REPLAY_STATIONS,
  REPLAY_HOURLY_DATA,
  REPLAY_DAILY_SUMMARY,
} from '../data/replayEvent';

// ─── Constants ─────────────────────────────────────────────────────────────────

const STATION_COLORS = ['#00f0ff', '#a855f7', '#f59e0b', '#10b981', '#f43f5e'];
const STATION_NAMES  = ['Anand Vihar', 'Narela', 'Bawana', 'RK Puram', 'Mandir Marg'];
const AQI_KEYS = ['aqi_DL001', 'aqi_DL002', 'aqi_DL003', 'aqi_DL004', 'aqi_DL005'];

const KEY_EVENTS = [
  { date: 'Nov 14', label: 'GRAP-III Invoked',   color: '#ef4444' },
  { date: 'Nov 16', label: 'NW Wind Shift',       color: '#a855f7' },
  { date: 'Nov 18', label: 'Peak AQI 491 ⚠',    color: '#dc2626' },
];

function getAqiColor(aqi) {
  if (aqi <= 50)  return '#10b981';
  if (aqi <= 100) return '#84cc16';
  if (aqi <= 200) return '#f59e0b';
  if (aqi <= 300) return '#f97316';
  if (aqi <= 400) return '#ef4444';
  return '#dc2626';
}

// ─── Custom Tooltip ─────────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div
      style={{
        background: 'rgba(6,10,19,0.96)',
        border: '1px solid rgba(0,240,255,0.2)',
        borderRadius: 8,
        padding: '10px 14px',
        fontSize: 11,
        minWidth: 160,
      }}
    >
      <p style={{ color: '#00f0ff', fontWeight: 700, marginBottom: 6 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, margin: '2px 0' }}>
          {p.name}: <strong>{p.value}</strong> AQI
        </p>
      ))}
    </div>
  );
}

// ─── Component ─────────────────────────────────────────────────────────────────

export default function ReplayTimeline() {
  const [selectedDayIdx, setSelectedDayIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const playIntervalRef = useRef(null);

  const days = REPLAY_DAILY_SUMMARY;
  const selectedDay = days[selectedDayIdx];

  // Hourly data for the active day
  const dayHourlyData = REPLAY_HOURLY_DATA.filter(d => d.date === selectedDay.date);

  // Chart series: one entry per hour
  const chartData = dayHourlyData.map(d => ({
    hour: `${String(d.hour).padStart(2, '0')}:00`,
    [STATION_NAMES[0]]: d.aqi_DL001,
    [STATION_NAMES[1]]: d.aqi_DL002,
    [STATION_NAMES[2]]: d.aqi_DL003,
    [STATION_NAMES[3]]: d.aqi_DL004,
    [STATION_NAMES[4]]: d.aqi_DL005,
  }));

  // Auto-play: advance one day every 2 s
  const advanceDay = useCallback(() => {
    setSelectedDayIdx(prev => {
      if (prev >= days.length - 1) {
        setIsPlaying(false);
        return prev;
      }
      return prev + 1;
    });
  }, [days.length]);

  useEffect(() => {
    if (isPlaying) {
      playIntervalRef.current = setInterval(advanceDay, 2000);
    } else {
      clearInterval(playIntervalRef.current);
    }
    return () => clearInterval(playIntervalRef.current);
  }, [isPlaying, advanceDay]);

  const handleReset = () => {
    setIsPlaying(false);
    setSelectedDayIdx(0);
  };

  const keyEvent    = KEY_EVENTS.find(e => e.date === selectedDay.date);
  const avgAqiColor = getAqiColor(selectedDay.avgAqi);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, height: '100%' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Clock size={16} color="var(--color-primary)" />
          <div>
            <span style={{ fontSize: 13, fontWeight: 700 }}>HISTORICAL EVENT REPLAY</span>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 8 }}>
              {REPLAY_EVENT_METADATA.dateRange}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Offline badge */}
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              background: 'rgba(16,185,129,0.08)',
              border: '1px solid rgba(16,185,129,0.2)',
              borderRadius: 20, padding: '3px 9px', fontSize: 10, color: '#10b981',
            }}
          >
            <WifiOff size={10} />
            <span>OFFLINE DATA</span>
          </div>

          <button
            id="replay-reset-btn"
            onClick={handleReset}
            title="Reset to Day 1"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid var(--border-light)',
              borderRadius: 6, padding: '5px 8px', cursor: 'pointer',
              display: 'flex', alignItems: 'center',
            }}
          >
            <RotateCcw size={12} color="var(--text-muted)" />
          </button>

          <button
            id="replay-play-btn"
            onClick={() => setIsPlaying(p => !p)}
            style={{
              background: isPlaying ? 'rgba(239,68,68,0.1)' : 'rgba(0,240,255,0.1)',
              border: `1px solid ${isPlaying ? 'rgba(239,68,68,0.3)' : 'rgba(0,240,255,0.3)'}`,
              borderRadius: 6, padding: '5px 14px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6, fontSize: 11,
              color: isPlaying ? '#ef4444' : 'var(--color-primary)',
              fontWeight: 700, transition: 'all 0.2s ease',
            }}
          >
            {isPlaying ? <Pause size={12} /> : <Play size={12} />}
            {isPlaying ? 'PAUSE' : 'PLAY EVENT'}
          </button>
        </div>
      </div>

      {/* ── Day selector timeline ── */}
      <div style={{ display: 'flex', gap: 6 }}>
        {days.map((day, idx) => {
          const isSelected = idx === selectedDayIdx;
          const dayColor   = getAqiColor(day.avgAqi);
          const event      = KEY_EVENTS.find(e => e.date === day.date);
          return (
            <button
              key={day.date}
              id={`replay-day-${day.date.replace(' ', '-')}`}
              onClick={() => { setSelectedDayIdx(idx); setIsPlaying(false); }}
              style={{
                flex: 1, padding: '8px 4px', borderRadius: 8, cursor: 'pointer',
                background: isSelected ? `${dayColor}16` : 'rgba(255,255,255,0.02)',
                border: `1px solid ${isSelected ? dayColor : 'var(--border-light)'}`,
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                transition: 'all 0.2s ease', position: 'relative',
                boxShadow: isSelected ? `0 0 12px ${dayColor}20` : 'none',
              }}
            >
              {event && (
                <div
                  style={{
                    position: 'absolute', top: -5, right: -5,
                    width: 10, height: 10, borderRadius: '50%',
                    background: event.color, border: '2px solid var(--bg-color)',
                  }}
                />
              )}
              <span style={{ fontSize: 10, fontWeight: 600, color: isSelected ? dayColor : 'var(--text-muted)' }}>
                {day.date}
              </span>
              <span
                style={{
                  fontSize: 18, fontWeight: 900,
                  fontFamily: 'var(--font-family-display)',
                  color: dayColor,
                }}
              >
                {day.avgAqi}
              </span>
              <span style={{ fontSize: 8, color: isSelected ? dayColor : 'var(--text-dark)', textTransform: 'uppercase' }}>
                {day.category}
              </span>
              {day.grapLevel && (
                <span
                  style={{
                    fontSize: 7, background: 'rgba(239,68,68,0.1)',
                    color: '#ef4444', padding: '1px 4px', borderRadius: 3,
                    border: '1px solid rgba(239,68,68,0.2)',
                  }}
                >
                  {day.grapLevel}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── Key event banner ── */}
      {keyEvent ? (
        <div
          style={{
            display: 'flex', alignItems: 'flex-start', gap: 10,
            background: `${keyEvent.color}0e`,
            border: `1px solid ${keyEvent.color}28`,
            borderRadius: 8, padding: '10px 14px',
          }}
        >
          <AlertTriangle size={15} color={keyEvent.color} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <span style={{ fontSize: 12, color: keyEvent.color, fontWeight: 700 }}>
              KEY EVENT: {keyEvent.label}
            </span>
            <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, lineHeight: 1.4 }}>
              {REPLAY_EVENT_METADATA.description.slice(0, 120)}…
            </p>
          </div>
        </div>
      ) : (
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid var(--border-light)',
            borderRadius: 8, padding: '8px 14px', fontSize: 11, color: 'var(--text-muted)',
          }}
        >
          <Clock size={12} />
          {REPLAY_EVENT_METADATA.eventName} — Day {selectedDayIdx + 1} of {days.length}
        </div>
      )}

      {/* ── Stats row ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {[
          { label: 'AVG AQI',      value: selectedDay.avgAqi,  color: avgAqiColor,  icon: null },
          { label: 'PEAK AQI',     value: selectedDay.peakAqi, color: getAqiColor(selectedDay.peakAqi), icon: null },
          { label: 'FIRE HOTSPOTS', value: selectedDay.fires,  color: '#f59e0b',    icon: <Flame size={9} color="#f59e0b" /> },
          { label: 'WIND DIR',     value: selectedDay.windDir, color: '#a855f7',    icon: <Wind  size={9} color="#a855f7" /> },
        ].map((stat, i) => (
          <div
            key={i}
            style={{
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid var(--border-light)',
              borderRadius: 8, padding: '10px 8px', textAlign: 'center',
            }}
          >
            <div
              style={{
                fontSize: 8, color: 'var(--text-muted)', fontWeight: 600,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 3,
                marginBottom: 4,
              }}
            >
              {stat.icon}{stat.label}
            </div>
            <div
              style={{
                fontSize: 20, fontWeight: 900, color: stat.color,
                fontFamily: 'var(--font-family-display)',
              }}
            >
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* ── Hourly AQI chart ── */}
      <div style={{ flex: 1, minHeight: 0 }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 6 }}>
          HOURLY AQI — {selectedDay.date} · ALL MONITORING STATIONS
        </div>
        <ResponsiveContainer width="100%" height={175}>
          <LineChart data={chartData} margin={{ top: 5, right: 8, left: -22, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="hour"
              stroke="var(--text-dark)"
              fontSize={9}
              tickLine={false}
              interval={5}
            />
            <YAxis
              stroke="var(--text-dark)"
              fontSize={9}
              tickLine={false}
              domain={[50, 500]}
            />
            <Tooltip content={<ChartTooltip />} />
            <ReferenceLine
              y={300}
              stroke="rgba(249,115,22,0.35)"
              strokeDasharray="4 3"
              label={{ value: 'Poor', fill: '#f97316', fontSize: 8, position: 'insideTopLeft' }}
            />
            <ReferenceLine
              y={400}
              stroke="rgba(239,68,68,0.35)"
              strokeDasharray="4 3"
              label={{ value: 'V.Poor', fill: '#ef4444', fontSize: 8, position: 'insideTopLeft' }}
            />
            {STATION_NAMES.map((name, i) => (
              <Line
                key={name}
                type="monotone"
                dataKey={name}
                stroke={STATION_COLORS[i]}
                strokeWidth={i === 0 ? 2.5 : 1.5}
                dot={false}
                name={name}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* ── Station legend ── */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {REPLAY_STATIONS.map((s, i) => (
          <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10 }}>
            <span
              style={{
                width: 22, height: 2,
                background: STATION_COLORS[i],
                display: 'inline-block', borderRadius: 1,
              }}
            />
            <span style={{ color: 'var(--text-muted)' }}>{s.name}</span>
            <span style={{ color: 'var(--text-dark)', fontSize: 9 }}>({s.type})</span>
          </div>
        ))}
      </div>

    </div>
  );
}
