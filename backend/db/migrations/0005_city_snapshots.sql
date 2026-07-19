-- Migration: 0005_city_snapshots
-- Created: 2026-07-19
-- Description: Create city_daily_snapshots table for 30-day longitudinal multi-city trend tracking.

CREATE TABLE IF NOT EXISTS city_daily_snapshots (
    id SERIAL PRIMARY KEY,
    city_name VARCHAR(50) NOT NULL,
    record_date DATE NOT NULL,
    avg_aqi FLOAT NOT NULL,
    primary_cause VARCHAR(50) NOT NULL,
    reduction_pct FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_city_date UNIQUE (city_name, record_date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_city_date ON city_daily_snapshots (city_name, record_date DESC);
