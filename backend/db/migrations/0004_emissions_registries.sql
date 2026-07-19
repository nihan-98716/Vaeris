-- Migration: 0004_emissions_registries
-- Created: 2026-07-19
-- Description: Create construction permits and industrial stack emission registries with PostGIS geometries.

CREATE TABLE IF NOT EXISTS construction_permits (
    permit_id VARCHAR(50) PRIMARY KEY,
    project_name VARCHAR(150) NOT NULL,
    contractor VARCHAR(100),
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_to TIMESTAMP WITH TIME ZONE NOT NULL,
    city VARCHAR(50) DEFAULT 'Delhi',
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_permits_geom ON construction_permits USING gist(geom);

CREATE TABLE IF NOT EXISTS industrial_stacks (
    stack_id VARCHAR(50) PRIMARY KEY,
    facility_name VARCHAR(150) NOT NULL,
    sector VARCHAR(100) NOT NULL,
    is_coal BOOLEAN DEFAULT TRUE,
    stack_height_m FLOAT DEFAULT 45.0,
    city VARCHAR(50) DEFAULT 'Delhi',
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stacks_geom ON industrial_stacks USING gist(geom);
