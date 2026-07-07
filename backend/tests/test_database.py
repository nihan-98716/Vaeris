import sqlite3

import pytest


def get_sqlite_db():
    """
    Initializes an in-memory SQLite database mimicking our PostGIS table constraints
    (without PostGIS geography columns) to verify validation rules in CI.
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Stations Table
    cursor.execute("""
        CREATE TABLE monitoring_stations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL
        );
    """)

    # 2. AQI Measurements Table
    cursor.execute("""
        CREATE TABLE aqi_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT REFERENCES monitoring_stations(id),
            timestamp TEXT NOT NULL,
            aqi REAL CHECK (aqi >= 0.0),
            pm25 REAL CHECK (pm25 >= 0.0),
            pm10 REAL CHECK (pm10 >= 0.0),
            UNIQUE (station_id, timestamp)
        );
    """)

    # 3. Weather Readings Table
    cursor.execute("""
        CREATE TABLE weather_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timestamp TEXT NOT NULL,
            temperature REAL,
            humidity REAL CHECK (humidity >= 0.0 AND humidity <= 100.0),
            wind_speed REAL CHECK (wind_speed >= 0.0),
            wind_deg REAL CHECK (wind_deg >= 0.0 AND wind_deg <= 360.0),
            UNIQUE (latitude, longitude, timestamp)
        );
    """)

    # 4. OSM Road Cache Table
    cursor.execute("""
        CREATE TABLE osm_road_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            min_lat REAL NOT NULL,
            min_lon REAL NOT NULL,
            max_lat REAL NOT NULL,
            max_lon REAL NOT NULL,
            road_count INTEGER NOT NULL CHECK (road_count >= 0),
            UNIQUE (min_lat, min_lon, max_lat, max_lon)
        );
    """)

    conn.commit()
    return conn


def test_database_not_null_constraints():
    conn = get_sqlite_db()
    cursor = conn.cursor()

    # Inserting station missing name (NOT NULL) should fail
    with pytest.raises(sqlite3.IntegrityError) as excinfo:
        cursor.execute("""
            INSERT INTO monitoring_stations (id, name, city, latitude, longitude)
            VALUES ('DL001', NULL, 'Delhi', 28.5, 77.2);
        """)
    assert "NOT NULL constraint failed" in str(excinfo.value)
    conn.close()


def test_database_check_constraints():
    conn = get_sqlite_db()
    cursor = conn.cursor()

    # Insert station first (parent reference)
    cursor.execute("""
        INSERT INTO monitoring_stations (id, name, city, latitude, longitude)
        VALUES ('DL001', 'Anand Vihar', 'Delhi', 28.5, 77.2);
    """)
    conn.commit()

    # Inserting negative AQI should fail
    with pytest.raises(sqlite3.IntegrityError) as excinfo:
        cursor.execute("""
            INSERT INTO aqi_measurements (station_id, timestamp, aqi, pm25, pm10)
            VALUES ('DL001', '2024-11-18T10:00:00Z', -5.0, 10.0, 20.0);
        """)
    assert "CHECK constraint failed" in str(excinfo.value)

    # Inserting out of range humidity should fail
    with pytest.raises(sqlite3.IntegrityError) as excinfo:
        cursor.execute("""
            INSERT INTO weather_readings (latitude, longitude, timestamp, humidity)
            VALUES (28.5, 77.2, '2024-11-18T10:00:00Z', 120.0);
        """)
    assert "CHECK constraint failed" in str(excinfo.value)

    conn.close()


def test_database_unique_constraints():
    conn = get_sqlite_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO monitoring_stations (id, name, city, latitude, longitude)
        VALUES ('DL001', 'Anand Vihar', 'Delhi', 28.5, 77.2);
    """)

    # Insert first AQI record
    cursor.execute("""
        INSERT INTO aqi_measurements (station_id, timestamp, aqi)
        VALUES ('DL001', '2024-11-18T10:00:00Z', 150.0);
    """)
    conn.commit()

    # Insert duplicate station_id + timestamp should fail
    with pytest.raises(sqlite3.IntegrityError) as excinfo:
        cursor.execute("""
            INSERT INTO aqi_measurements (station_id, timestamp, aqi)
            VALUES ('DL001', '2024-11-18T10:00:00Z', 200.0);
        """)
    assert "UNIQUE constraint failed" in str(excinfo.value)

    conn.close()
