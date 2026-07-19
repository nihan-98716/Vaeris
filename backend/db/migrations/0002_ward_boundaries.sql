-- Migration: 0002_ward_boundaries
-- Created: 2026-07-19
-- Description: Create ward boundaries table with PostGIS polygon geometries and spatial indexing.

CREATE TABLE IF NOT EXISTS ward_boundaries (
    ward_id VARCHAR(50) PRIMARY KEY,
    ward_name VARCHAR(100) NOT NULL,
    zone_name VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL DEFAULT 'Delhi',
    geom GEOMETRY(Polygon, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ward_geom ON ward_boundaries USING gist(geom);
CREATE INDEX IF NOT EXISTS idx_ward_city ON ward_boundaries(city);
