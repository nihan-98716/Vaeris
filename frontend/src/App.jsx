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
  Tooltip,
  BarChart,
  Bar,
  Cell
} from 'recharts';
import { 
  Wind, 
  Flame, 
  Activity, 
  AlertTriangle, 
  MapPin, 
  Layers, 
  Clock, 
  TrendingUp,
  TrendingDown,
  Cpu,
  Info,
  ShieldCheck
} from 'lucide-react';

const API_BASE = "http://localhost:8000";

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

function App() {
  const [selectedCoord, setSelectedCoord] = useState({ lat: 28.5919, lon: 77.2272 });
  const [selectedStation, setSelectedStation] = useState(REPRESENTATIVE_STATIONS[1]); // Lodhi Road default
  const [forecast, setForecast] = useState(null);
  const [attribution, setAttribution] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiConnected, setApiConnected] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  // Phase 7: tab navigation
  const [activeTab, setActiveTab] = useState('live'); // 'live' | 'replay' | 'before-after'
  const [liveTime, setLiveTime] = useState(new Date());

  const mapContainer = useRef(null);
  const map = useRef(null);
  const markersRef = useRef([]);

  useEffect(() => {
    const timer = setInterval(() => {
      setLiveTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Trigger MapLibre canvas resize when returning to 'live' tab to prevent blank maps
  useEffect(() => {
    if (activeTab === 'live' && map.current) {
      setTimeout(() => {
        if (map.current) {
          map.current.resize();
        }
      }, 80);
    }
  }, [activeTab]);

  // Check API health on mount
  useEffect(() => {
    async function checkApiConnection() {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) {
          setApiConnected(true);
        } else {
          setApiConnected(false);
        }
      } catch (err) {
        setApiConnected(false);
      }
    }
    checkApiConnection();
  }, []);

  // Fetch forecast and attribution whenever coordinate updates
  useEffect(() => {
    let isMounted = true;
    async function fetchData() {
      setLoading(true);
      setErrorMessage(null);
      try {
        // Query forecast
        const forecastUrl = `${API_BASE}/api/v1/forecast?latitude=${selectedCoord.lat}&longitude=${selectedCoord.lon}&horizon_hours=24`;
        const attributionUrl = `${API_BASE}/api/v1/attribution?latitude=${selectedCoord.lat}&longitude=${selectedCoord.lon}`;

        let forecastData = null;
        let attributionData = null;

        try {
          const [fRes, aRes] = await Promise.all([
            fetch(forecastUrl),
            fetch(attributionUrl)
          ]);
          if (fRes.ok && aRes.ok) {
            forecastData = await fRes.json();
            attributionData = await aRes.json();
            setApiConnected(true);
          } else {
            setApiConnected(false);
          }
        } catch (err) {
          setApiConnected(false);
        }

        // Fallback/Mock data if offline or API failed
        if (!forecastData || !attributionData) {
          await new Promise(resolve => setTimeout(resolve, 50)); // simulate minimal network delay
          
          // Generate mock parameters relative to selected coordinates
          const baseAqi = selectedStation ? selectedStation.aqi : 160;
          forecastData = {
            value: baseAqi + (Math.random() * 40 - 15),
            lower_bound: baseAqi - 30,
            upper_bound: baseAqi + 50,
            confidence_tier: baseAqi > 200 ? "experimental" : "reliable",
            model_version: "v_mvp_fallback",
            horizon_hours: 24
          };

          attributionData = {
            primary_cause: baseAqi > 220 ? "agricultural_burning" : baseAqi > 160 ? "traffic" : "industrial",
            confidence_breakdown: {
              traffic: baseAqi > 220 ? 0.2 : baseAqi > 160 ? 0.65 : 0.25,
              agricultural_burning: baseAqi > 220 ? 0.75 : baseAqi > 160 ? 0.15 : 0.05,
              industrial: baseAqi > 220 ? 0.05 : baseAqi > 160 ? 0.20 : 0.70
            },
            evidence: baseAqi > 220 ? [
              "NASA FIRMS registered active hotspots upwind (36km East)",
              "Dominant East wind vector (8.5 km/h) favors cross-state transport",
              "AQI spike of +45 index points matches transport speed travel window"
            ] : baseAqi > 160 ? [
              "High road density segment count (0.85) exceeds baseline thresholds",
              "Local PM2.5 rise coincides with peak commute window (08:00 - 10:00 IST)"
            ] : [
              "Industrial zone land-use category confirmed via OSM spatial join",
              "AQI elevation persistent outside commuter/traffic peak windows"
            ],
            degraded_sources: []
          };
        }

        if (isMounted) {
          setForecast(forecastData);
          setAttribution(attributionData);
        }
      } catch (err) {
        if (isMounted) {
          setErrorMessage("Failed to fetch intelligence data. Running in offline mockup mode.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [selectedCoord, selectedStation]);

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

    // Add navigation controls
    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');

    // Add click event for custom coordinate selection
    map.current.on('click', (e) => {
      const lat = parseFloat(e.lngLat.lat.toFixed(4));
      const lon = parseFloat(e.lngLat.lng.toFixed(4));
      
      // Look up if clicked near any defined station
      let matched = null;
      for (const s of REPRESENTATIVE_STATIONS) {
        // approx 1.5km range
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

    // Draw representative station markers
    REPRESENTATIVE_STATIONS.forEach((s) => {
      // Create HTML element for custom marker design
      const el = document.createElement('div');
      el.className = 'station-marker';
      el.style.width = '24px';
      el.style.height = '24px';
      el.style.borderRadius = '50%';
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.justifyContent = 'center';
      el.style.cursor = 'pointer';
      
      // Color coding based on AQI severity
      const color = s.aqi > 200 ? '#ef4444' : s.aqi > 150 ? '#f59e0b' : '#10b981';
      el.style.background = color;
      el.style.border = '2px solid rgba(255, 255, 255, 0.8)';
      el.style.boxShadow = `0 0 12px ${color}`;
      
      // Label inner HTML
      el.innerHTML = `<span style="font-size: 8px; font-weight: bold; color: #000;">${s.aqi}</span>`;
      
      // Setup click handler
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        setSelectedCoord({ lat: s.lat, lon: s.lon });
        setSelectedStation(s);
      });

      // Add to map
      const marker = new maplibregl.Marker(el)
        .setLngLat([s.lon, s.lat])
        .setPopup(new maplibregl.Popup({ offset: 15 }).setHTML(
          `<div style="color: #111; font-family: sans-serif; font-size: 12px; padding: 4px;">
            <strong>${s.name}</strong><br/>
            Type: ${s.type}<br/>
            Current AQI: <strong>${s.aqi}</strong>
          </div>`
        ))
        .addTo(map.current);

      markersRef.current.push(marker);
    });

    return () => {
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
    
    // Extrapolate values out to T+24
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

  // Format attribution confidences into an array for Recharts
  const barChartData = React.useMemo(() => {
    if (!attribution || !attribution.confidence_breakdown) return [];
    return Object.entries(attribution.confidence_breakdown).map(([source, conf]) => ({
      name: source === "agricultural_burning" ? "Crop Burning" : source.charAt(0).toUpperCase() + source.slice(1),
      confidence: Math.round(conf * 100),
      rawKey: source
    })).sort((a, b) => b.confidence - a.confidence);
  }, [attribution]);

  // Get AQI category details
  const getAqiCategory = (aqi) => {
    if (aqi <= 50) return { label: "Good", color: "#10b981", bg: "rgba(16, 185, 129, 0.15)" };
    if (aqi <= 100) return { label: "Satisfactory", color: "#84cc16", bg: "rgba(132, 204, 22, 0.15)" };
    if (aqi <= 200) return { label: "Moderate", color: "#f59e0b", bg: "rgba(245, 158, 11, 0.15)" };
    if (aqi <= 300) return { label: "Poor", color: "#f97316", bg: "rgba(249, 115, 22, 0.15)" };
    return { label: "Severe", color: "#ef4444", bg: "rgba(239, 68, 68, 0.15)" };
  };

  const aqiDetails = getAqiCategory(selectedStation ? selectedStation.aqi : 160);

  // ── Tab definitions ──────────────────────────────────────────────────────────
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
          <div style={{ background: 'linear-gradient(135deg, #00f0ff, #a855f7)', padding: '6px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Wind size={24} color="#000" />
          </div>
          <div>
            <h1 style={{ fontFamily: 'var(--font-family-display)', fontSize: '20px', fontWeight: '800', tracking: 'wide', background: 'linear-gradient(90deg, #00f0ff, #fff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              VAERIS
            </h1>
            <p style={{ fontSize: '10px', color: 'var(--text-muted)', tracking: 'widest' }}>URBAN AIR QUALITY COMMAND CENTER</p>
          </div>
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

          {/* Map Canvas */}
          <div ref={mapContainer} style={{ flex: 1, width: '100%', height: '100%' }} />

          {/* Floating Instructions Legend */}
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
          
          {/* Location Title Header */}
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
              {forecast && !loading && (
                <div style={{ display: 'flex', gap: '8px', fontSize: '10px' }}>
                  <span style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-light)', padding: '2px 6px', borderRadius: '4px', color: 'var(--text-muted)' }}>
                    MODEL: {forecast.model_version}
                  </span>
                  <span style={{ background: forecast.confidence_tier === 'reliable' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)', border: `1px solid ${forecast.confidence_tier === 'reliable' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)'}`, padding: '2px 6px', borderRadius: '4px', color: forecast.confidence_tier === 'reliable' ? 'var(--color-success)' : 'var(--color-warning)' }}>
                    {forecast.confidence_tier.toUpperCase()}
                  </span>
                </div>
              )}
            </div>

            {loading ? (
              /* Shimmering chart placeholder */
              <div className="shimmer" style={{ width: '100%', height: '180px', borderRadius: '8px' }}></div>
            ) : (
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
            )}
          </div>

          {/* Source Attribution Panel */}
          <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px', flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Cpu size={16} color="var(--color-primary)" />
                <span style={{ fontSize: '13px', fontWeight: '600' }}>CAUSAL SOURCE ATTRIBUTION</span>
              </div>
              {attribution && !loading && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: attribution.primary_cause === 'agricultural_burning' ? 'var(--color-warning)' : attribution.primary_cause === 'traffic' ? 'var(--color-secondary)' : 'var(--color-primary)' }}>
                  {attribution.primary_cause === 'agricultural_burning' ? <Flame size={12} /> : <Activity size={12} />}
                  <span style={{ fontWeight: '700', textTransform: 'uppercase' }}>
                    {attribution.primary_cause === 'agricultural_burning' ? 'Agricultural Burning' : attribution.primary_cause}
                  </span>
                </div>
              )}
            </div>

            {loading ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
                <div className="shimmer" style={{ width: '40%', height: '14px' }}></div>
                <div className="shimmer" style={{ width: '100%', height: '80px' }}></div>
                <div className="shimmer" style={{ width: '100%', height: '40px' }}></div>
              </div>
            ) : attribution ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
                
                {/* Confidence Bar Chart */}
                <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '16px', alignItems: 'center' }}>
                  <div style={{ height: '90px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={barChartData} layout="vertical" margin={{ top: 0, right: 10, left: -25, bottom: 0 }}>
                        <XAxis type="number" stroke="none" tick={false} />
                        <YAxis dataKey="name" type="category" stroke="var(--text-muted)" fontSize={10} tickLine={false} width={80} />
                        <Tooltip
                          contentStyle={{ backgroundColor: 'var(--bg-color)', borderColor: 'var(--border-light)', borderRadius: '6px', fontSize: '11px' }}
                          formatter={(value) => [`${value}%`, 'Weight']}
                        />
                        <Bar dataKey="confidence" radius={4} barSize={8}>
                          {barChartData.map((entry, index) => {
                            let color = 'var(--color-primary)';
                            if (entry.rawKey === 'agricultural_burning') color = 'var(--color-warning)';
                            if (entry.rawKey === 'traffic') color = 'var(--color-secondary)';
                            return <Cell key={`cell-${index}`} fill={color} />;
                          })}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div style={{ background: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-light)', borderRadius: '8px', padding: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: '600' }}>PRIMARY ATTRIBUTION CAUSE</div>
                    <div style={{ fontSize: '14px', fontWeight: '800', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: attribution.primary_cause === 'agricultural_burning' ? 'var(--color-warning)' : attribution.primary_cause === 'traffic' ? 'var(--color-secondary)' : 'var(--color-primary)' }}></span>
                      {attribution.primary_cause === 'agricultural_burning' ? 'Crop Burning' : attribution.primary_cause.charAt(0).toUpperCase() + attribution.primary_cause.slice(1)}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <ShieldCheck size={10} color="var(--color-success)" />
                      <span>Evidence verified by rules</span>
                    </div>
                  </div>
                </div>

                {/* Evidence Log List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: '600', letterSpacing: '0.5px' }}>TRACEABLE CAUSAL EVIDENCE LOGS</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {attribution.evidence.map((item, idx) => (
                      <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', background: 'rgba(255,255,255,0.015)', border: '1px solid var(--border-light)', padding: '8px 10px', borderRadius: '6px', fontSize: '11px' }}>
                        <span style={{ color: 'var(--color-primary)', marginTop: '2px' }}>➔</span>
                        <span style={{ color: 'var(--text-main)', lineHeight: '1.4' }}>{item}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Degraded Sources Warnings */}
                {attribution.degraded_sources && attribution.degraded_sources.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.15)', padding: '8px 10px', borderRadius: '6px', fontSize: '11px', color: 'var(--color-danger)' }}>
                    <AlertTriangle size={12} />
                    <span>Missing/degraded signals: {attribution.degraded_sources.join(', ')}</span>
                  </div>
                )}
              </div>
            ) : null}
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
          {/* Left — explanation */}
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

          {/* Right — live panel */}
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

      {/* 3. Footer / Operations status */}
      <footer style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-dark)' }}>
        <span>VAERIS OPERATIONAL SUITE v0.1.0-MVP · Phase 10</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Clock size={10} /> Delhi Local Time: {liveTime.toLocaleTimeString()} (UTC+5:30)
        </span>
      </footer>

    </div>
  );
}

export default App;
