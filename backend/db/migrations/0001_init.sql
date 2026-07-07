-- Migration: 0001_init
-- Created: 2026-07-07
-- Description: Initialize core tables, PostGIS geometries, indices, and constraints.

CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Monitoring Stations Table
CREATE TABLE IF NOT EXISTS monitoring_stations (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stations_geom ON monitoring_stations USING gist(geom);

-- 2. AQI Measurements Table (Hourly CAAQMS Ground-Truth)
CREATE TABLE IF NOT EXISTS aqi_measurements (
    id SERIAL PRIMARY KEY,
    station_id VARCHAR(100) REFERENCES monitoring_stations(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    aqi DOUBLE PRECISION CHECK (aqi >= 0.0),
    pm25 DOUBLE PRECISION CHECK (pm25 >= 0.0),
    pm10 DOUBLE PRECISION CHECK (pm10 >= 0.0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_station_timestamp UNIQUE (station_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_aqi_timestamp ON aqi_measurements(timestamp);
CREATE INDEX IF NOT EXISTS idx_aqi_station_timestamp ON aqi_measurements(station_id, timestamp);

-- 3. NASA FIRMS Fire Hotspots Table
CREATE TABLE IF NOT EXISTS fire_hotspots (
    id SERIAL PRIMARY KEY,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    brightness DOUBLE PRECISION,
    frp DOUBLE PRECISION,
    acq_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fire_location_time UNIQUE (latitude, longitude, acq_datetime)
);

CREATE INDEX IF NOT EXISTS idx_fire_geom ON fire_hotspots USING gist(geom);
CREATE INDEX IF NOT EXISTS idx_fire_acq_datetime ON fire_hotspots(acq_datetime);

-- 4. OpenWeather Weather Readings Table
CREATE TABLE IF NOT EXISTS weather_readings (
    id SERIAL PRIMARY KEY,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION CHECK (humidity >= 0.0 AND humidity <= 100.0),
    wind_speed DOUBLE PRECISION CHECK (wind_speed >= 0.0),
    wind_deg DOUBLE PRECISION CHECK (wind_deg >= 0.0 AND wind_deg <= 360.0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_weather_coords_time UNIQUE (latitude, longitude, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_weather_geom ON weather_readings USING gist(geom);
CREATE INDEX IF NOT EXISTS idx_weather_timestamp ON weather_readings(timestamp);

-- 5. OSM Road Cache Table
CREATE TABLE IF NOT EXISTS osm_road_cache (
    id SERIAL PRIMARY KEY,
    min_lat DOUBLE PRECISION NOT NULL,
    min_lon DOUBLE PRECISION NOT NULL,
    max_lat DOUBLE PRECISION NOT NULL,
    max_lon DOUBLE PRECISION NOT NULL,
    road_count INTEGER NOT NULL CHECK (road_count >= 0),
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_osm_bbox UNIQUE (min_lat, min_lon, max_lat, max_lon)
);
