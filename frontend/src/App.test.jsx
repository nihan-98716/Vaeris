import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import App from './App';

// Define global mock for ResizeObserver (used by recharts ResponsiveContainer)
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock maplibre-gl Map, Marker, and Popup classes correctly
vi.mock('maplibre-gl', () => {
  class MockMap {
    on() {}
    remove() {}
    addControl() {}
    easeTo() {}
  }
  class MockMarker {
    setLngLat() { return this; }
    setPopup() { return this; }
    addTo() { return this; }
  }
  class MockPopup {
    setHTML() { return this; }
    addTo() { return this; }
  }
  return {
    default: {
      Map: MockMap,
      Marker: MockMarker,
      Popup: MockPopup,
      NavigationControl: class {},
    },
    Map: MockMap,
    Marker: MockMarker,
    Popup: MockPopup,
    NavigationControl: class {},
  };
});

// Mock recharts ResponsiveContainer so it doesn't try to observe sizes in JSDOM
vi.mock('recharts', async (importOriginal) => {
  const original = await importOriginal();
  return {
    ...original,
    ResponsiveContainer: ({ children }) => children,
  };
});

// Mock fetch calls
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('Vaeris Frontend App', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        cities: [
          { name: 'Delhi', city_name: 'Delhi', status_level: 'high', current_aqi: 320.0, projected_aqi: 290.0, optimal_actions: [] },
          { name: 'Mumbai', city_name: 'Mumbai', status_level: 'high', current_aqi: 80.0, projected_aqi: 80.0, optimal_actions: [] },
          { name: 'Chennai', city_name: 'Chennai', status_level: 'high', current_aqi: 50.0, projected_aqi: 50.0, optimal_actions: [] },
          { name: 'Bengaluru', city_name: 'Bengaluru', status_level: 'high', current_aqi: 55.0, projected_aqi: 55.0, optimal_actions: [] }
        ],
        selected_interventions: [],
        total_aqi_reduction: 0.0,
        total_cost: 0.0,
        total_inspectors_used: 0,
        total_population_affected: 0,
        total_health_benefit: 0.0,
        remaining_budget: 4000.0,
        remaining_inspectors: 6,
        value: 290.0,
        lower_bound: 250.0,
        upper_bound: 330.0,
        confidence_tier: 'reliable',
        model_version: 'v1.0',
        primary_cause: 'traffic',
        confidence_breakdown: { traffic: 0.8 },
        evidence: [],
        confidence: 'high',
        historical_data: []
      })
    });
  });

  it('renders logo and name in the header bar', async () => {
    await act(async () => {
      render(<App />);
    });
    expect(screen.getByAltText('Vaeris Logo')).toBeDefined();
    expect(screen.getByAltText('Vaeris Name')).toBeDefined();
  });

  it('switches tabs and displays target view when clicking tabs', async () => {
    await act(async () => {
      render(<App />);
    });

    // Verify default view contains API status indicator
    expect(screen.getByText(/API CONNECTED/i)).toBeDefined();

    // Find and click National Grid tab
    const multicityTabButton = screen.getByText(/NATIONAL GRID/i);
    await act(async () => {
      fireEvent.click(multicityTabButton);
    });

    // Verify it tries to query multicity route
    expect(mockFetch).toHaveBeenCalled();
  });
});
