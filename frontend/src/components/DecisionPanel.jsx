import { useState, useEffect } from 'react';
import { ShieldCheck, Users, DollarSign, Timer, AlertTriangle, Cpu, Heart } from 'lucide-react';

export default function DecisionPanel({ baselineAqi = 245, apiBase = "http://localhost:8000" }) {
  const [budget, setBudget] = useState(4000);
  const [inspectors, setInspectors] = useState(6);
  const [maxTravelTime, setMaxTravelTime] = useState(3.0);
  
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  // Function to run optimizer
  const fetchOptimizedDecisions = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = `${apiBase}/api/v1/decision?budget=${budget}&inspectors=${inspectors}&max_travel_time_hours=${maxTravelTime}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setResults(data);
      } else {
        const errData = await res.json();
        setError(errData.detail || "Failed to execute decision optimization solver.");
      }
    } catch (err) {
      setError("Unable to connect to the optimizer API. Using local offline solver simulation.");
      // Fallback offline greedy solver simulation for local development
      runOfflineSimulation();
    } finally {
      setLoading(false);
    }
  };

  // Offline simulation fallback
  const runOfflineSimulation = () => {
    const catalog = [
      { id: "stubble_burning_enforcement", name: "Enforce Stubble Burning Ban", cost: 1500, inspectors_required: 4, travel_time_hours: 2.5, aqi_reduction: 45, population_affected: 800000 },
      { id: "halt_construction", name: "Halt Construction Activities", cost: 800, inspectors_required: 2, travel_time_hours: 1.0, aqi_reduction: 20, population_affected: 500000 },
      { id: "road_sprinklers", name: "Deploy Road Sprinklers & Anti-Smog Guns", cost: 500, inspectors_required: 1, travel_time_hours: 0.5, aqi_reduction: 12, population_affected: 300000 },
      { id: "odd_even_rationing", name: "Implement Odd-Even Vehicle Rationing", cost: 3000, inspectors_required: 10, travel_time_hours: 1.5, aqi_reduction: 35, population_affected: 2000000 },
      { id: "restrict_industries", name: "Restrict Coal-Fired Industrial Output", cost: 2500, inspectors_required: 3, travel_time_hours: 2.0, aqi_reduction: 30, population_affected: 1200000 },
      { id: "waste_burning_fines", name: "Enforce Waste Burning Fines", cost: 300, inspectors_required: 1, travel_time_hours: 0.8, aqi_reduction: 8, population_affected: 250000 }
    ];

    // Filter by travel time
    const filtered = catalog.filter(item => item.travel_time_hours <= maxTravelTime);
    
    // Calculate health benefit and scores (simplified mock scoring)
    const scored = filtered.map(item => {
      const healthBenefit = Math.round(item.aqi_reduction * 0.0104 * item.population_affected);
      return {
        ...item,
        health_benefit: healthBenefit,
        score: Math.round((item.aqi_reduction / item.cost) * 1000 * 100) / 100 // score proportional to efficiency
      };
    });

    // Sort by score descending
    scored.sort((a, b) => b.score - a.score);

    // Greedy select
    let curCost = 0;
    let curInspectors = 0;
    const selected = [];
    
    for (const item of scored) {
      if (curCost + item.cost <= budget && curInspectors + item.inspectors_required <= inspectors) {
        selected.push(item);
        curCost += item.cost;
        curInspectors += item.inspectors_required;
      }
    }

    const totalAqiReduction = selected.reduce((sum, item) => sum + item.aqi_reduction, 0);
    const totalPopulation = selected.reduce((sum, item) => sum + item.population_affected, 0);
    const totalHealthBenefit = selected.reduce((sum, item) => sum + item.health_benefit, 0);

    setResults({
      selected_interventions: selected,
      total_aqi_reduction: totalAqiReduction,
      total_cost: curCost,
      total_inspectors_used: curInspectors,
      total_population_affected: totalPopulation,
      total_health_benefit: totalHealthBenefit,
      remaining_budget: budget - curCost,
      remaining_inspectors: inspectors - curInspectors,
      disclaimer: "Indicative respiratory exposure risk, estimated using published WHO/Lancet exposure-response coefficients. Not a clinical or epidemiological forecast."
    });
  };

  // Run on mount or when inputs change
  useEffect(() => {
    fetchOptimizedDecisions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [budget, inspectors, maxTravelTime]);

  const projectedAqi = Math.max(0, Math.round(baselineAqi - (results?.total_aqi_reduction || 0)));

  return (
    <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={16} color="var(--color-primary)" />
          <span style={{ fontSize: '13px', fontWeight: '600', letterSpacing: '0.5px' }}>RESOURCE-CONSTRAINED DECISION OPTIMIZER</span>
        </div>
        <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: '700', textTransform: 'uppercase', background: 'rgba(0, 240, 255, 0.08)', padding: '2px 8px', borderRadius: '4px' }}>
          Multi-Objective Knapsack
        </div>
      </div>

      {/* Constraints Sliders Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', background: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-light)', borderRadius: '8px', padding: '12px' }}>
        
        {/* Budget Slider */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <DollarSign size={10} color="var(--color-primary)" />
            BUDGET (RUPEES)
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <input 
              type="range" 
              min="500" 
              max="10000" 
              step="500"
              value={budget} 
              onChange={(e) => setBudget(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--color-primary)' }}
            />
            <span style={{ fontSize: '11px', fontWeight: '700', minWidth: '40px', textAlign: 'right' }}>₹{budget}</span>
          </div>
        </div>

        {/* Inspectors Slider */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Users size={10} color="var(--color-secondary)" />
            INSPECTORS
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <input 
              type="range" 
              min="1" 
              max="15" 
              step="1"
              value={inspectors} 
              onChange={(e) => setInspectors(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--color-secondary)' }}
            />
            <span style={{ fontSize: '11px', fontWeight: '700', minWidth: '20px', textAlign: 'right' }}>{inspectors}</span>
          </div>
        </div>

        {/* Dispatch Window / Radius Slider */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Timer size={10} color="var(--color-warning)" />
            DISPATCH WINDOW
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <input 
              type="range" 
              min="0.5" 
              max="4.0" 
              step="0.5"
              value={maxTravelTime} 
              onChange={(e) => setMaxTravelTime(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--color-warning)' }}
            />
            <span style={{ fontSize: '11px', fontWeight: '700', minWidth: '35px', textAlign: 'right' }}>{maxTravelTime}h</span>
          </div>
        </div>

      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--color-warning)', padding: '6px 10px', background: 'rgba(245, 158, 11, 0.05)', borderRadius: '6px', border: '1px solid rgba(245, 158, 11, 0.15)' }}>
          <AlertTriangle size={12} />
          <span>{error}</span>
        </div>
      )}

      {/* Before / After Projection Panel */}
      {results && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '12px', background: 'rgba(0, 240, 255, 0.02)', border: '1px solid var(--border-light)', borderRadius: '8px', padding: '12px' }}>
          
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '4px' }}>
            <span style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: '600' }}>EXPECTED IMPACT SCENARIO</span>
            <div style={{ fontSize: '20px', fontWeight: '800', fontFamily: 'var(--font-family-display)' }}>
              {results.selected_interventions.length > 0 ? (
                <span style={{ color: 'var(--color-success)' }}>
                  -{results.total_aqi_reduction} AQI Points
                </span>
              ) : (
                <span style={{ color: 'var(--text-muted)' }}>No Action Taken</span>
              )}
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <ShieldCheck size={10} color="var(--color-success)" />
              <span>Projected optimization results</span>
            </div>
          </div>

          <div style={{ borderLeft: '1px solid var(--border-light)', paddingLeft: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)' }}>
              <span>Without Intervention:</span>
              <span style={{ fontWeight: '700', color: 'var(--text-main)' }}>{baselineAqi} (Projected AQI)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)' }}>
              <span>With Recommendation:</span>
              <span style={{ fontWeight: '700', color: 'var(--color-success)' }}>{projectedAqi} (Projected AQI)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)', borderTop: '1px dashed var(--border-light)', paddingTop: '4px', marginTop: '2px' }}>
              <span>Expected Reduction:</span>
              <span style={{ fontWeight: '800', color: 'var(--color-primary)' }}>{results.total_aqi_reduction} points</span>
            </div>
          </div>

        </div>
      )}

      {/* Selected Optimal Recommendations List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: '600', letterSpacing: '0.5px' }}>OPTIMIZED INTERVENTION STEPS</div>
        
        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div className="shimmer" style={{ width: '100%', height: '50px' }}></div>
            <div className="shimmer" style={{ width: '100%', height: '50px' }}></div>
          </div>
        ) : results && results.selected_interventions.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {results.selected_interventions.map((item, idx) => (
              <div 
                key={item.id} 
                style={{ 
                  background: 'rgba(255,255,255,0.015)', 
                  border: '1px solid var(--border-light)', 
                  padding: '10px 12px', 
                  borderRadius: '6px', 
                  fontSize: '11px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                {/* Ranking index indicator */}
                <div style={{ position: 'absolute', top: '0', right: '0', background: 'rgba(0, 240, 255, 0.08)', borderBottomLeftRadius: '6px', padding: '2px 8px', fontSize: '9px', fontWeight: '700', color: 'var(--color-primary)' }}>
                  RANK #{idx + 1}
                </div>

                <div style={{ fontWeight: '700', color: 'var(--text-main)', paddingRight: '50px' }}>
                  {item.name}
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: '10px', lineHeight: '1.4' }}>
                  {item.description}
                </div>

                {/* Sub-metrics */}
                <div style={{ display: 'flex', gap: '16px', borderTop: '1px solid rgba(255,255,255,0.02)', paddingTop: '6px', marginTop: '2px', fontSize: '9px', color: 'var(--text-muted)' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <DollarSign size={10} color="var(--color-primary)" />
                    Cost: ₹{item.cost}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <Users size={10} color="var(--color-secondary)" />
                    Staff: {item.inspectors_required}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <Timer size={10} color="var(--color-warning)" />
                    Dispatch: {item.travel_time_hours}h
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <Heart size={10} color="#f43f5e" />
                    Health Benefit: {item.health_benefit}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ border: '1px dashed var(--border-light)', borderRadius: '6px', padding: '16px', textAlign: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
            No interventions can be selected under the current resource constraints.
          </div>
        )}
      </div>

      {/* Aggregate solver metadata footer */}
      {results && results.selected_interventions.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', borderTop: '1px solid var(--border-light)', paddingTop: '10px', fontSize: '10px', color: 'var(--text-muted)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            <span>Total Cost Deployed: <strong>₹{results.total_cost}</strong> (₹{results.remaining_budget} left)</span>
            <span>Total Inspectors Active: <strong>{results.total_inspectors_used}</strong> ({results.remaining_inspectors} idle)</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', textAlign: 'right' }}>
            <span>Total Population Benefited: <strong>{results.total_population_affected.toLocaleString()}</strong></span>
            <span>Indicative Health Benefit: <strong>{results.total_health_benefit}</strong></span>
          </div>
        </div>
      )}

      {/* Disclaimer */}
      {results && (
        <div style={{ fontSize: '8px', color: 'var(--text-dark)', lineHeight: '1.3', borderTop: '1px solid rgba(255,255,255,0.02)', paddingTop: '8px', fontStyle: 'italic' }}>
          * {results.disclaimer}
        </div>
      )}

    </div>
  );
}
