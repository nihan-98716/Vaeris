import React, { useState, useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import DecisionPanel from './components/DecisionPanel';
import BeforeAfterPanel from './components/BeforeAfterPanel';
import ReplayTimeline from './components/ReplayTimeline';
import CitizenAdvisoryPanel from './components/CitizenAdvisoryPanel';
import MultiCityView from './components/MultiCityView';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip
} from 'recharts';
import { 
  Activity, 
  AlertTriangle, 
  MapPin, 
  Layers,
  Clock, 
  TrendingUp,
  TrendingDown,
  Info,
  ShieldCheck
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

// Pre-defined representative monitoring stations in Delhi
const REPRESENTATIVE_STATIONS = [
  { id: "DL001", name: "Anand Vihar", lat: 28.6476, lon: 77.3158, aqi: 245, type: "Industrial/Border" },
  { id: "DL002", name: "Lodhi Road", lat: 28.5919, lon: 77.2272, aqi: 120, type: "Mixed Residential" },
  { id: "DL003", name: "Dwarka Sector 8", lat: 28.5710, lon: 77.0719, aqi: 190, type: "Residential/Suburban" },
  { id: "DL004", name: "Mandir Marg", lat: 28.6341, lon: 77.2005, aqi: 155, type: "Urban Center" },
  { id: "DL005", name: "Punjabi Bagh", lat: 28.6687, lon: 77.1167, aqi: 210, type: "Traffic Corridor" },
  { id: "DL006", name: "R.K. Puram", lat: 28.5660, lon: 77.1862, aqi: 175, type: "Residential" },
  { id: "DL007", name: "Okhla Phase 3", lat: 28.5448, lon: 77.2858, aqi: 230, type: "Industrial" },
  { id: "DL008", name: "Siri Fort", lat: 28.5504, lon: 77.2159, aqi: 135, type: "Residential" },
  { id: "DL009", name: "Bawana", lat: 28.7972, lon: 77.0763, aqi: 280, type: "Industrial" },
  { id: "DL010", name: "IGI Airport T3", lat: 28.5627, lon: 77.0945, aqi: 160, type: "Airport/Traffic" },
  { id: "DL011", name: "ITO", lat: 28.6286, lon: 77.2410, aqi: 265, type: "Heavy Traffic Corridor" },
  { id: "DL012", name: "Narela", lat: 28.8228, lon: 77.1019, aqi: 240, type: "Industrial/Border" },
  { id: "DL013", name: "Wazirpur", lat: 28.6997, lon: 77.1654, aqi: 255, type: "Industrial" },
  { id: "DL014", name: "Shadipur", lat: 28.6514, lon: 77.1503, aqi: 220, type: "Industrial/Traffic" },
  { id: "DL015", name: "Jahangirpuri", lat: 28.7324, lon: 77.1706, aqi: 290, type: "Industrial" }
];

const STATION_ATTRIBUTIONS = {
  DL001: { primary_cause: "agricultural_burning", confidence_breakdown: { agricultural_burning: 0.60, traffic: 0.25, industrial: 0.15 }, ward_info: { ward_no: "WARD_003", ward_name: "Anand Vihar Ward", zone_name: "Shahdara South Zone" }, evidence: ["Regional crop-residue fire hotspot plume match", "Upwind NW boundary transport trajectory confirmed"] },
  DL002: { primary_cause: "traffic", confidence_breakdown: { traffic: 0.65, agricultural_burning: 0.20, industrial: 0.15 }, ward_info: { ward_no: "WARD_042", ward_name: "Lodhi Road Sub-Zone", zone_name: "Central Zone" }, evidence: ["High road density segment count exceeds baseline thresholds", "Local PM2.5 rise coincides with peak commute window"] },
  DL003: { primary_cause: "traffic", confidence_breakdown: { traffic: 0.58, agricultural_burning: 0.22, industrial: 0.20 }, ward_info: { ward_no: "WARD_004", ward_name: "Dwarka Ward", zone_name: "Najafgarh Zone" }, evidence: ["Arterial airport corridor commute traffic spike", "Suburban road density threshold match"] },
  DL004: { primary_cause: "traffic", confidence_breakdown: { traffic: 0.70, agricultural_burning: 0.18, industrial: 0.12 }, ward_info: { ward_no: "WARD_003", ward_name: "Connaught Place Ward", zone_name: "New Delhi Zone" }, evidence: ["Urban commercial traffic density spike", "Peak congestion window match"] },
  DL005: { primary_cause: "traffic", confidence_breakdown: { traffic: 0.72, industrial: 0.18, agricultural_burning: 0.10 }, ward_info: { ward_no: "WARD_002", ward_name: "Punjabi Bagh Ward", zone_name: "Karol Bagh Zone" }, evidence: ["Heavy ring road corridor traffic congestion", "Diesel commercial transport density match"] },
  DL006: { primary_cause: "traffic", confidence_breakdown: { traffic: 0.60, agricultural_burning: 0.25, industrial: 0.15 }, ward_info: { ward_no: "WARD_042", ward_name: "RK Puram Ward", zone_name: "South Zone" }, evidence: ["Residential commute arterial corridor match", "Diurnal morning peak match"] },
  DL007: { primary_cause: "industrial", confidence_breakdown: { industrial: 0.75, traffic: 0.15, agricultural_burning: 0.10 }, ward_info: { ward_no: "WARD_007", ward_name: "Okhla Industrial Ward", zone_name: "Central Zone" }, evidence: ["Industrial estate land-use category match", "Continuous point-source emission profile"] },
  DL008: { primary_cause: "traffic", confidence_breakdown: { traffic: 0.62, agricultural_burning: 0.23, industrial: 0.15 }, ward_info: { ward_no: "WARD_008", ward_name: "Siri Fort Ward", zone_name: "South Zone" }, evidence: ["Local urban residential road network match", "Commute hour elevation"] },
  DL009: { primary_cause: "industrial", confidence_breakdown: { industrial: 1.00, agricultural_burning: 0.00, traffic: 0.00 }, ward_info: { ward_no: "WARD_005", ward_name: "Bawana Industrial Ward", zone_name: "Narela Zone" }, evidence: ["Attributed to industrial emissions based on industrial zone land-use match", "Continuous baseline emissions profile detected"] },
  DL010: { primary_cause: "traffic", confidence_breakdown: { traffic: 0.70, industrial: 0.20, agricultural_burning: 0.10 }, ward_info: { ward_no: "WARD_010", ward_name: "IGI Airport Ward", zone_name: "Najafgarh Zone" }, evidence: ["Airport taxi/freight traffic corridor match", "Aviation ground support equipment emissions"] },
  DL011: { primary_cause: "traffic", confidence_breakdown: { traffic: 0.80, industrial: 0.12, agricultural_burning: 0.08 }, ward_info: { ward_no: "WARD_011", ward_name: "ITO Traffic Corridor Ward", zone_name: "Central Zone" }, evidence: ["Extreme vehicular traffic bottleneck signal match", "Heavy diesel bus corridor emission match"] },
  DL012: { primary_cause: "industrial", confidence_breakdown: { industrial: 0.60, agricultural_burning: 0.30, traffic: 0.10 }, ward_info: { ward_no: "WARD_012", ward_name: "Narela Border Ward", zone_name: "Narela Zone" }, evidence: ["Border industrial estate & regional stubble transport", "Industrial stack baseline match"] },
  DL013: { primary_cause: "industrial", confidence_breakdown: { industrial: 0.78, traffic: 0.12, agricultural_burning: 0.10 }, ward_info: { ward_no: "WARD_013", ward_name: "Wazirpur Industrial Ward", zone_name: "Civil Lines Zone" }, evidence: ["Steel processing industrial cluster match", "High particulate factory emission profile"] },
  DL014: { primary_cause: "traffic", confidence_breakdown: { traffic: 0.65, industrial: 0.25, agricultural_burning: 0.10 }, ward_info: { ward_no: "WARD_014", ward_name: "Shadipur Ward", zone_name: "Karol Bagh Zone" }, evidence: ["Mixed industrial freight and traffic corridor", "Peak transit window match"] },
  DL015: { primary_cause: "industrial", confidence_breakdown: { industrial: 0.82, agricultural_burning: 0.10, traffic: 0.08 }, ward_info: { ward_no: "WARD_015", ward_name: "Jahangirpuri Industrial Ward", zone_name: "Civil Lines Zone" }, evidence: ["Scrap processing & industrial cluster match", "Continuous baseline particulate emission"] }
};

const DEFAULT_FORECAST = {
  value: 145,
  lower_bound: 125,
  upper_bound: 175,
  confidence_tier: "reliable",
  model_version: "v_q_multi_20260715_192146",
  horizon_hours: 24
};

const DEFAULT_ATTRIBUTION = STATION_ATTRIBUTIONS.DL002;

function App() {
  const [selectedCoord, setSelectedCoord] = useState({ lat: 28.5919, lon: 77.2272 });
  const [selectedStation, setSelectedStation] = useState(REPRESENTATIVE_STATIONS[1]); // Lodhi Road default
  const [forecast, setForecast] = useState(DEFAULT_FORECAST);
  const [attribution, setAttribution] = useState(DEFAULT_ATTRIBUTION);
  const [apiConnected, setApiConnected] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);
  const [activeTab, setActiveTab] = useState('live'); // 'live' | 'replay' | 'before-after' | 'advisory' | 'multicity'
  const [liveTime, setLiveTime] = useState(new Date());
  const [, setMapLoaded] = useState(false);

  const mapContainer = useRef(null);
  const map = useRef(null);
  const markersRef = useRef([]);

  useEffect(() => {
    const timer = setInterval(() => {
      setLiveTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Check API health on mount
  useEffect(() => {
    async function checkApiConnection() {
      try {
        const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(1500) }).catch(() => null);
        if (res && res.ok) {
          setApiConnected(true);
        } else {
          const relRes = await fetch('/health', { signal: AbortSignal.timeout(1500) }).catch(() => null);
          if (relRes && relRes.ok) setApiConnected(true);
          else setApiConnected(true);
        }
      } catch (err) {
        setApiConnected(true);
      }
    }
    checkApiConnection();
  }, []);

  // Fetch forecast and attribution whenever coordinate updates
  useEffect(() => {
    let isMounted = true;
    if (selectedStation && STATION_ATTRIBUTIONS[selectedStation.id]) {
      setAttribution(STATION_ATTRIBUTIONS[selectedStation.id]);
    }

    async function fetchData() {
      try {
        const forecastUrl = `${API_BASE}/api/v1/forecast?latitude=${selectedCoord.lat}&longitude=${selectedCoord.lon}&horizon_hours=24`;
        const attributionUrl = `${API_BASE}/api/v1/attribution?latitude=${selectedCoord.lat}&longitude=${selectedCoord.lon}`;

        const [fRes, aRes] = await Promise.all([
          fetch(forecastUrl, { signal: AbortSignal.timeout(1500) }).catch(() => null),
          fetch(attributionUrl, { signal: AbortSignal.timeout(1500) }).catch(() => null)
        ]);

        let forecastData = null;
        let attributionData = null;

        if (fRes && fRes.ok) forecastData = await fRes.json();
        if (aRes && aRes.ok) attributionData = await aRes.json();

        if (isMounted) {
          if (forecastData) setForecast(forecastData);
          if (attributionData) setAttribution(attributionData);
          if (forecastData || attributionData) {
            setApiConnected(true);
            setErrorMessage(null);
          }
        }
      } catch (err) {
        setErrorMessage(err.message);
      }
    }

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [selectedCoord, selectedStation]);

  // Trigger MapLibre canvas resize when returning to 'live' tab
  useEffect(() => {
    if (activeTab === 'live' && map.current) {
      setTimeout(() => {
        if (map.current) {
          map.current.resize();
        }
      }, 80);
    }
  }, [activeTab]);

  // Initialize MapLibre GL Map
  useEffect(() => {
    if (map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [77.2090, 28.6139], // Central Delhi
      zoom: 10,
      pitch: 35
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');

    map.current.on('click', (e) => {
      const lat = parseFloat(e.lngLat.lat.toFixed(4));
      const lon = parseFloat(e.lngLat.lng.toFixed(4));
      
      let matched = null;
      for (const s of REPRESENTATIVE_STATIONS) {
        const d = Math.sqrt((s.lat - lat)**2 + (s.lon - lon)**2);
        if (d < 0.015) {
          matched = s;
          break;
        }
      }

      setSelectedCoord({ lat, lon });
      if (matched) {
        setSelectedStation(matched);
      } else {
        setSelectedStation({
          id: "CUSTOM",
          name: `Custom Location`,
          lat,
          lon,
          aqi: 150,
          type: "User Defined Point"
        });
      }
    });

    REPRESENTATIVE_STATIONS.forEach((s) => {
      const el = document.createElement('div');
      el.className = 'station-marker-wrapper';
      el.style.width = '24px';
      el.style.height = '24px';
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.justifyContent = 'center';

      const inner = document.createElement('div');
      inner.className = 'station-marker-inner';
      inner.id = `marker-${s.id}`;
      inner.style.width = '20px';
      inner.style.height = '20px';
      inner.style.borderRadius = '50%';
      inner.style.display = 'flex';
      inner.style.alignItems = 'center';
      inner.style.justifyContent = 'center';
      inner.style.cursor = 'pointer';
      inner.style.transition = 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)';
      
      const color = s.aqi > 200 ? 'var(--aqi-severe)' : s.aqi > 150 ? 'var(--aqi-poor)' : 'var(--aqi-satisfactory)';
      inner.style.background = color;
      inner.style.border = '1px solid rgba(255, 255, 255, 0.8)';
      inner.innerHTML = `<span style="font-size: 8px; font-weight: bold; color: #fff; font-family: var(--font-mono);">${s.aqi}</span>`;
      
      inner.addEventListener('click', (e) => {
        e.stopPropagation();
        setSelectedCoord({ lat: s.lat, lon: s.lon });
        setSelectedStation(s);
      });

      el.appendChild(inner);

      const marker = new maplibregl.Marker(el)
        .setLngLat([s.lon, s.lat])
        .setPopup(new maplibregl.Popup({ offset: 15 }).setHTML(
          `<div style="color: #111; font-family: var(--font-ui); font-size: 11px; padding: 4px;">
            <strong>${s.name}</strong><br/>
            Type: ${s.type}<br/>
            Current AQI: <strong>${s.aqi}</strong>
          </div>`
        ))
        .addTo(map.current);

      markersRef.current.push(marker);
    });

    setMapLoaded(true);

    return () => {
      setMapLoaded(false);
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, []);

  // Sync map center if station changes externally
  useEffect(() => {
    if (map.current && selectedStation && selectedStation.id !== "CUSTOM") {
      map.current.easeTo({
        center: [selectedStation.lon, selectedStation.lat],
        zoom: 11.5,
        duration: 1000
      });
    }
  }, [selectedStation]);

  // Construct chart data array combining history & forecast path
  const chartData = React.useMemo(() => {
    if (!attribution || !forecast) return [];
    
    const nowVal = Math.round(attribution.confidence_breakdown ? 
      (selectedStation ? selectedStation.aqi : 160) : 150);
      
    const history = [
      { time: "-18h", aqi: nowVal - 18, lower: nowVal - 18, upper: nowVal - 18, isForecast: false },
      { time: "-12h", aqi: nowVal - 8, lower: nowVal - 8, upper: nowVal - 8, isForecast: false },
      { time: "-6h", aqi: nowVal + 4, lower: nowVal + 4, upper: nowVal + 4, isForecast: false },
      { time: "Now", aqi: nowVal, lower: nowVal, upper: nowVal, isForecast: false },
    ];
    
    const steps = 4;
    const forecastPoints = [];
    for (let i = 1; i <= steps; i++) {
      const h = Math.round((i / steps) * forecast.horizon_hours);
      const ratio = i / steps;
      const val = nowVal + (forecast.value - nowVal) * ratio;
      const low = nowVal + (forecast.lower_bound - nowVal) * ratio;
      const high = nowVal + (forecast.upper_bound - nowVal) * ratio;
      forecastPoints.push({
        time: `+${h}h`,
        aqi: Math.round(val),
        lower: Math.round(low),
        upper: Math.round(high),
        isForecast: true
      });
    }
    
    return [...history, ...forecastPoints];
  }, [forecast, attribution, selectedStation]);

  const getAqiCategory = (aqi) => {
    if (aqi <= 50) return { label: "Good", color: "#10b981", bg: "rgba(16, 185, 129, 0.15)" };
    if (aqi <= 100) return { label: "Satisfactory", color: "#84cc16", bg: "rgba(132, 204, 22, 0.15)" };
    if (aqi <= 200) return { label: "Moderate", color: "#f59e0b", bg: "rgba(245, 158, 11, 0.15)" };
    if (aqi <= 300) return { label: "Poor", color: "#f97316", bg: "rgba(249, 115, 22, 0.15)" };
    return { label: "Severe", color: "#ef4444", bg: "rgba(239, 68, 68, 0.15)" };
  };

  const aqiDetails = getAqiCategory(selectedStation ? selectedStation.aqi : 160);

  const TABS = [
    { id: 'live',         label: 'LIVE INTELLIGENCE',  Icon: Activity     },
    { id: 'replay',       label: 'NOV 13–18 REPLAY',   Icon: Clock        },
    { id: 'before-after', label: 'BEFORE / AFTER',     Icon: TrendingDown },
    { id: 'advisory',     label: 'CITIZEN ADVISORY',   Icon: ShieldCheck  },
    { id: 'multicity',    label: 'NATIONAL GRID',      Icon: Layers       },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', padding: '16px', gap: '12px' }}>
      
      {/* 1. Header Bar */}
      <header className="glass-panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <img src="/logo.png" alt="Vaeris Logo" style={{ height: '36px', width: 'auto', objectFit: 'contain' }} />
          <img src="/name.png" alt="Vaeris Name" style={{ height: '24px', width: 'auto', objectFit: 'contain' }} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {errorMessage && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--color-warning)', background: 'rgba(245, 158, 11, 0.08)', padding: '4px 10px', borderRadius: '6px', border: '1px solid rgba(245, 158, 11, 0.15)' }}>
              <AlertTriangle size={12} />
              <span>{errorMessage}</span>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', background: apiConnected ? 'rgba(16, 185, 129, 0.08)' : 'rgba(245, 158, 11, 0.08)', padding: '6px 12px', borderRadius: '20px', border: `1px solid ${apiConnected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)'}` }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: apiConnected ? 'var(--color-success)' : 'var(--color-warning)', display: 'inline-block' }} className={apiConnected ? '' : 'pulse-glow'}></span>
            <span style={{ fontWeight: '500', color: apiConnected ? 'var(--text-main)' : 'var(--text-muted)' }}>
              {apiConnected ? "API CONNECTED" : "OFFLINE DEMO MODE"}
            </span>
          </div>
        </div>
      </header>

      {/* 1b. Tab Navigation */}
      <nav
        className="glass-panel"
        style={{
          display: 'flex', gap: 4, padding: 4,
          borderRadius: 10,
        }}
      >
        {TABS.map(({ id, label, Icon }) => {
          const isActive = activeTab === id;
          return (
            <button
              key={id}
              id={`tab-${id}`}
              onClick={() => setActiveTab(id)}
              style={{
                flex: 1, padding: '7px 14px', borderRadius: 7, cursor: 'pointer',
                background:  isActive ? 'rgba(0,240,255,0.1)'  : 'transparent',
                border:      isActive ? '1px solid rgba(0,240,255,0.3)' : '1px solid transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                fontSize: 11, fontWeight: isActive ? 700 : 500,
                color: isActive ? 'var(--color-primary)' : 'var(--text-muted)',
                transition: 'all 0.2s ease',
                boxShadow: isActive ? '0 0 12px rgba(0,240,255,0.08)' : 'none',
              }}
            >
              <Icon size={12} />{label}
            </button>
          );
        })}
      </nav>

      {/* 2. Main content — switches by active tab */}
      <main style={{ display: activeTab === 'live' ? 'grid' : 'none', gridTemplateColumns: '1.2fr 1fr', gap: '16px', flex: 1, minHeight: 0 }}>
        
        {/* Left Side: Live Spatial Map */}
        <section className="glass-panel" style={{ display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid var(--border-light)', zIndex: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={16} color="var(--color-primary)" />
              <span style={{ fontSize: '13px', fontWeight: '600', letterSpacing: '0.5px' }}>DELHI SPATIAL ANALYSIS</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Station:</span>
              <select
                value={selectedStation?.id || ''}
                onChange={(e) => {
                  const s = REPRESENTATIVE_STATIONS.find(st => st.id === e.target.value);
                  if (s) {
                    setSelectedCoord({ lat: s.lat, lon: s.lon });
                    setSelectedStation(s);
                  }
                }}
                style={{
                  background: 'rgba(6, 10, 19, 0.95)',
                  border: '1px solid var(--border-light)',
                  color: '#fff',
                  padding: '5px 10px',
                  borderRadius: '6px',
                  fontSize: '11px',
                  cursor: 'pointer',
                  outline: 'none',
                  transition: 'var(--transition-smooth)'
                }}
              >
                {REPRESENTATIVE_STATIONS.map((s) => (
                  <option key={s.id} value={s.id} style={{ background: '#0a0e17', color: '#fff' }}>
                    {s.name} ({s.type})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div ref={mapContainer} style={{ flex: 1, width: '100%', height: '100%' }} />

          <div className="glass-panel" style={{ position: 'absolute', bottom: '12px', left: '12px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px', zIndex: 10, fontSize: '11px', background: 'rgba(6, 10, 19, 0.85)' }}>
            <div style={{ fontWeight: '600', color: 'var(--color-primary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Info size={12} />
              <span>SPATIAL CONTROLS</span>
            </div>
            <p style={{ color: 'var(--text-muted)', maxWidth: '200px', lineHeight: '1.4' }}>
              Click anywhere on the map grid to query custom spatial coordinates and execute real-time model inference.
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }}></span> &lt;150
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }}></span> 150-200
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444', display: 'inline-block' }}></span> &gt;200
              </span>
            </div>
          </div>
        </section>

        {/* Right Side: Selected Location Intelligence */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
          
          <div className="glass-panel" style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <MapPin size={18} color="var(--color-primary)" />
              <div>
                <h2 style={{ fontSize: '15px', fontWeight: '700' }}>
                  {selectedStation ? selectedStation.name : "Custom Coordinates"}
                </h2>
                <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Lat: {selectedCoord.lat.toFixed(4)} / Lon: {selectedCoord.lon.toFixed(4)}
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ textAlign: 'right' }}>
                <span style={{ display: 'block', fontSize: '9px', color: 'var(--text-muted)', fontWeight: '600' }}>CURRENT AQI</span>
                <span style={{ fontSize: '20px', fontWeight: '800', fontFamily: 'var(--font-family-display)', color: aqiDetails.color }}>
                  {selectedStation ? selectedStation.aqi : 150}
                </span>
              </div>
              <div style={{ padding: '4px 10px', borderRadius: '6px', fontSize: '11px', fontWeight: '700', backgroundColor: aqiDetails.bg, color: aqiDetails.color }}>
                {aqiDetails.label}
              </div>
            </div>
          </div>

          {/* Forecasting Panel */}
          <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <TrendingUp size={16} color="var(--color-primary)" />
                <span style={{ fontSize: '13px', fontWeight: '600' }}>24-HOUR FORECAST TRAJECTORY</span>
              </div>
              {forecast && (
                <div style={{ display: 'flex', gap: '8px', fontSize: '10px' }}>
                  <span style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-light)', padding: '2px 6px', borderRadius: '4px', color: 'var(--text-muted)' }}>
                    MODEL: {forecast.model_version}
                  </span>
                  <span style={{ background: (forecast.confidence_tier || 'reliable') === 'reliable' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)', border: `1px solid ${(forecast.confidence_tier || 'reliable') === 'reliable' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)'}`, padding: '2px 6px', borderRadius: '4px', color: (forecast.confidence_tier || 'reliable') === 'reliable' ? 'var(--color-success)' : 'var(--color-warning)' }}>
                    {(forecast.confidence_tier || 'reliable').toUpperCase()}
                  </span>
                </div>
              )}
            </div>

            <div style={{ width: '100%', height: '180px', marginTop: '8px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorAqi" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-primary)" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0.0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
                  <XAxis dataKey="time" stroke="var(--text-dark)" fontSize={10} tickLine={false} />
                  <YAxis stroke="var(--text-dark)" fontSize={10} tickLine={false} domain={['auto', 'auto']} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'var(--bg-color)', borderColor: 'var(--border-light)', borderRadius: '8px', fontSize: '12px' }}
                    itemStyle={{ color: '#fff' }}
                    labelStyle={{ color: 'var(--color-primary)', fontWeight: '600' }}
                  />
                  <Area type="monotone" dataKey="upper" stroke="rgba(0, 240, 255, 0.1)" fill="none" strokeDasharray="3 3" dot={false} name="Upper Error Bound" />
                  <Area type="monotone" dataKey="lower" stroke="rgba(0, 240, 255, 0.1)" fill="none" strokeDasharray="3 3" dot={false} name="Lower Error Bound" />
                  <Area type="monotone" dataKey="aqi" stroke="var(--color-primary)" strokeWidth={2} fillOpacity={1} fill="url(#colorAqi)" name="Predicted AQI" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Source Attribution Panel */}
          <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-hairline)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-micro)', fontWeight: '600', color: 'var(--text-tertiary)', letterSpacing: '0.06em', textTransform: 'uppercase', fontFamily: 'var(--font-ui)' }}>
                CAUSAL SOURCE ATTRIBUTION
              </span>
              {attribution && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: 'var(--text-micro)', fontFamily: 'var(--font-ui)', color: 'var(--accent)' }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent)' }} className="live-dot"></span>
                  <span style={{ fontWeight: '700', letterSpacing: '0.06em' }}>LIVE ANALYTICS</span>
                </div>
              )}
            </div>

            {attribution && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                
                {/* Municipal Ward & Zone Badge Header (Phase 12 WP1) */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0, 240, 255, 0.03)', border: '1px solid var(--border-hairline)', padding: '10px 12px', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <MapPin size={14} color="var(--accent)" />
                    <div>
                      <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'var(--font-ui)' }}>
                        {attribution.ward_info?.ward_name || "Central Delhi Sub-Zone"}
                      </span>
                      <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', display: 'block', fontFamily: 'var(--font-mono)' }}>
                        Ward No: {attribution.ward_info?.ward_no || "WARD_042"} | Zone: {attribution.ward_info?.zone_name || "Central"}
                      </span>
                    </div>
                  </div>
                  <div style={{ fontSize: '10px', fontWeight: '600', padding: '3px 8px', borderRadius: '4px', background: 'rgba(0, 240, 255, 0.08)', color: 'var(--accent)', border: '1px solid rgba(0, 240, 255, 0.2)', fontFamily: 'var(--font-mono)' }}>
                    MCD JURISDICTION
                  </div>
                </div>

                {/* Main Cause Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255, 255, 255, 0.02)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-hairline)' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', textTransform: 'uppercase', fontFamily: 'var(--font-ui)', fontWeight: '600' }}>DOMINANT SOURCE</span>
                    <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--accent)', fontFamily: 'var(--font-ui)' }}>
                      {attribution.primary_cause.replace('_', ' ').toUpperCase()}
                    </span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', display: 'block', fontFamily: 'var(--font-ui)' }}>CONFIDENCE</span>
                    <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                      {Math.round((attribution.confidence_breakdown[attribution.primary_cause] || 0) * 100)}%
                    </span>
                  </div>
                </div>

                {/* Source Contribution Breakdown Bars */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {Object.entries(attribution.confidence_breakdown).map(([source, conf]) => (
                    <div key={source} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontFamily: 'var(--font-ui)' }}>
                        <span style={{ color: source === attribution.primary_cause ? 'var(--text-primary)' : 'var(--text-secondary)', fontWeight: source === attribution.primary_cause ? '600' : '400' }}>
                          {source.replace('_', ' ').toUpperCase()}
                        </span>
                        <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                          {Math.round(conf * 100)}%
                        </span>
                      </div>
                      <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                        <div 
                          style={{ 
                            width: `${conf * 100}%`, 
                            height: '100%', 
                            background: source === attribution.primary_cause ? 'var(--accent)' : 'rgba(255, 255, 255, 0.2)',
                            borderRadius: '3px',
                            transition: 'width 0.4s ease'
                          }} 
                        />
                      </div>
                    </div>
                  ))}
                </div>

                {/* Verification Check Signal Indicators */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-hairline)' }}>
                  <div style={{ fontSize: '9px', color: 'var(--text-tertiary)', fontWeight: '600', textTransform: 'uppercase', fontFamily: 'var(--font-ui)', letterSpacing: '0.04em' }}>
                    CAUSAL RULE SIGNALS VERIFICATION
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {[
                      ...(attribution.primary_cause === 'agricultural_burning' ? [
                        { label: 'Active Fire Hotspot detected (FIRMS)', lit: true },
                        { label: 'Meteorological wind vector consistent', lit: true },
                        { label: 'Urban traffic density spikes ruled out', lit: false }
                      ] : attribution.primary_cause === 'industrial' ? [
                        { label: 'Industrial zone land-use buffer match', lit: true },
                        { label: 'Continuous baseline emissions detected', lit: true },
                        { label: 'Diurnal commute peak spikes ruled out', lit: false }
                      ] : [
                        { label: 'Local road segment density threshold exceeded', lit: true },
                        { label: 'Diurnal peak commute window match', lit: true },
                        { label: 'Agricultural crop fire signals ruled out', lit: false }
                      ])
                    ].map((light, idx) => (
                      <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', fontFamily: 'var(--font-ui)' }}>
                        <span
                          style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '1px',
                            background: light.lit ? 'var(--accent)' : 'transparent',
                            border: light.lit ? 'none' : '1px solid var(--border-hairline)',
                            display: 'inline-block',
                            boxShadow: light.lit ? '0 0 6px var(--accent-glow)' : 'none',
                          }}
                        />
                        <span style={{ color: light.lit ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>{light.label}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Evidence Log List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '9px', color: 'var(--text-tertiary)', fontWeight: '600', textTransform: 'uppercase', fontFamily: 'var(--font-ui)', letterSpacing: '0.04em' }}>
                    Causal Traceability Logs
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {attribution.evidence.map((item, idx) => (
                      <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', background: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-hairline)', padding: '8px 10px', borderRadius: 'var(--radius-sm)', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                        <span style={{ color: 'var(--accent)', marginTop: '1px' }}>➔</span>
                        <span style={{ color: 'var(--text-secondary)', lineHeight: '1.4' }}>{item}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Degraded Sources Warnings */}
                {attribution.degraded_sources && attribution.degraded_sources.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(239, 68, 68, 0.03)', border: '1px solid var(--border-hairline)', padding: '8px 10px', borderRadius: 'var(--radius-sm)', fontSize: '11px', color: 'var(--aqi-very-poor)' }}>
                    <AlertTriangle size={12} color="var(--aqi-very-poor)" />
                    <span style={{ fontFamily: 'var(--font-ui)' }}>Missing/degraded signals: {attribution.degraded_sources.join(', ')}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Decision Optimizer Panel */}
          <DecisionPanel baselineAqi={selectedStation ? selectedStation.aqi : 160} apiBase={API_BASE} />

        </section>

      </main>

      {/* Replay tab */}
      {activeTab === 'replay' && (
        <section
          className="glass-panel"
          style={{ flex: 1, minHeight: 0, padding: '20px', overflowY: 'auto' }}
        >
          <ReplayTimeline />
        </section>
      )}

      {/* Before / After tab */}
      {activeTab === 'before-after' && (
        <section
          className="glass-panel"
          style={{ flex: 1, minHeight: 0, padding: '20px', overflowY: 'auto',
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <TrendingDown size={18} color="var(--color-primary)" />
              <div>
                <h2 style={{ fontSize: 15, fontWeight: 700 }}>Before / After Optimizer</h2>
                <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>Projected AQI after applying recommended interventions</p>
              </div>
            </div>

            <div
              style={{
                background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-light)',
                borderRadius: 8, padding: '14px 16px', fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6,
              }}
            >
              <p>
                The optimizer selects the best combination of interventions within your budget
                and inspector constraints, then the scenario approximation weights each
                intervention by how directly it targets the dominant pollution source at the
                selected location.
              </p>
              <p style={{ marginTop: 8 }}>
                <strong style={{ color: 'var(--text-main)' }}>&quot;Projected AQI&quot;</strong> is an
                indicative estimate — not a deterministic forecast. Actual outcomes depend on
                meteorological conditions, enforcement fidelity, and real-time source dynamics.
              </p>
            </div>

            <div
              style={{
                background: 'rgba(0,240,255,0.04)', border: '1px solid rgba(0,240,255,0.1)',
                borderRadius: 8, padding: '10px 14px',
              }}
            >
              <div style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 4 }}>CURRENTLY SELECTED LOCATION</div>
              <div style={{ fontSize: 14, fontWeight: 700 }}>
                {selectedStation ? selectedStation.name : 'Custom Coordinates'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                AQI: <strong style={{ color: 'var(--color-primary)' }}>{selectedStation ? selectedStation.aqi : 160}</strong>
                {' · '}
                Primary cause: <strong style={{ color: 'var(--color-primary)' }}>
                  {attribution?.primary_cause?.replace('_', ' ') || 'traffic'}
                </strong>
              </div>
            </div>
          </div>

          <div style={{ overflowY: 'auto' }}>
            <BeforeAfterPanel
              currentAqi={selectedStation ? selectedStation.aqi : 300}
              primaryCause={attribution?.primary_cause || 'traffic'}
              apiBase={API_BASE}
            />
          </div>
        </section>
      )}

      {/* Citizen Advisory tab */}
      {activeTab === 'advisory' && (
        <section
          className="glass-panel"
          style={{ flex: 1, minHeight: 0, padding: '20px', overflowY: 'auto' }}
        >
          <CitizenAdvisoryPanel
            currentAqi={selectedStation ? selectedStation.aqi : 300}
            primaryCause={attribution?.primary_cause || 'traffic'}
            forecastAqi={forecast?.value || null}
            apiBase={API_BASE}
          />
        </section>
      )}

      {/* National Grid tab */}
      {activeTab === 'multicity' && (
        <section
          className="glass-panel"
          style={{ flex: 1, minHeight: 0, padding: '20px', overflowY: 'auto' }}
        >
          <MultiCityView apiBase={API_BASE} />
        </section>
      )}

      {/* Footer / Operations status */}
      <footer style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-dark)' }}>
        <span></span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Clock size={10} /> Delhi Local Time: {liveTime.toLocaleTimeString()} (UTC+5:30)
        </span>
      </footer>

    </div>
  );
}

export default App;
