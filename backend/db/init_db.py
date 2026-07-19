"""
Initialize the Vaeris PostgreSQL/PostGIS schema.

This script executes the checked-in SQL migrations in lexical order. It is
idempotent because the migrations use CREATE ... IF NOT EXISTS guards.
"""

import json
from pathlib import Path

import psycopg2

from backend.config import settings
from backend.logging import logger

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def run_migrations() -> None:
    migration_paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_paths:
        raise FileNotFoundError(f"No SQL migrations found in {MIGRATIONS_DIR}")

    conn = psycopg2.connect(
        host=settings.database.host,
        port=settings.database.port,
        dbname=settings.database.dbname,
        user=settings.database.user,
        password=settings.database.password,
    )
    try:
        with conn:
            with conn.cursor() as cursor:
                for path in migration_paths:
                    logger.info(f"Applying database migration: {path.name}")
                    cursor.execute(path.read_text(encoding="utf-8"))
    finally:
        conn.close()


def seed_database() -> None:
    conn = psycopg2.connect(
        host=settings.database.host,
        port=settings.database.port,
        dbname=settings.database.dbname,
        user=settings.database.user,
        password=settings.database.password,
    )
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM monitoring_stations;")
                if cursor.fetchone()[0] > 0:
                    logger.info("Database already seeded. Skipping snapshot load.")
                    return

                logger.info("Seeding database with offline snapshot history...")
                snapshot_path = (
                    Path(__file__).resolve().parent.parent.parent
                    / "data"
                    / "snapshots"
                    / "delhi_2024-11-13_to_2024-11-18.json"
                )
                if not snapshot_path.exists():
                    logger.error(f"Snapshot file not found at {snapshot_path}")
                    return

                with open(snapshot_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Seed stations
                stations = data.get("metadata", {}).get("stations", [])
                for s in stations:
                    cursor.execute(
                        """
                        INSERT INTO monitoring_stations (id, name, city, latitude, longitude, geom)
                        VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                        ON CONFLICT (id) DO NOTHING;
                        """,
                        (
                            s["id"],
                            s["name"],
                            "Delhi",
                            s["latitude"],
                            s["longitude"],
                            s["longitude"],
                            s["latitude"],
                        ),
                    )

                # Seed AQI measurements
                aqi_data = data.get("aqi_data", [])
                for r in aqi_data:
                    cursor.execute(
                        """
                        INSERT INTO aqi_measurements (station_id, timestamp, aqi, pm25, pm10)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (station_id, timestamp) DO NOTHING;
                        """,
                        (
                            r["station_id"],
                            r["timestamp"],
                            r.get("aqi"),
                            r.get("pm25"),
                            r.get("pm10"),
                        ),
                    )

                # Seed fire hotspots
                fire_data = data.get("fire_data", [])
                for r in fire_data:
                    cursor.execute(
                        """
                        INSERT INTO fire_hotspots (latitude, longitude, geom, brightness, frp, acq_datetime)
                        VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)
                        ON CONFLICT (latitude, longitude, acq_datetime) DO NOTHING;
                        """,
                        (
                            float(r["latitude"]),
                            float(r["longitude"]),
                            float(r["longitude"]),
                            float(r["latitude"]),
                            r.get("brightness"),
                            r.get("frp"),
                            r["acq_datetime"],
                        ),
                    )

                # Seed weather readings
                weather_data = data.get("weather_data", [])
                for r in weather_data:
                    cursor.execute(
                        """
                        INSERT INTO weather_readings (latitude, longitude, geom, timestamp, temperature, humidity, wind_speed, wind_deg)
                        VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s)
                        ON CONFLICT (latitude, longitude, timestamp) DO NOTHING;
                        """,
                        (
                            float(r["latitude"]),
                            float(r["longitude"]),
                            float(r["longitude"]),
                            float(r["latitude"]),
                            r["timestamp"],
                            r.get("temperature"),
                            r.get("humidity"),
                            r.get("wind_speed"),
                            r.get("wind_deg"),
                        ),
                    )

                # Seed a default osm road cache entry to prevent empty joins
                cursor.execute("""
                    INSERT INTO osm_road_cache (min_lat, min_lon, max_lat, max_lon, road_count)
                    VALUES (28.0, 76.5, 29.0, 77.5, 150)
                    ON CONFLICT DO NOTHING;
                    """)

                # Seed Delhi MCD Ward Boundaries
                wards = [
                    ("WARD_DEL_001", "Civil Lines Ward", "Civil Lines Zone", "Delhi", "POLYGON((77.18 28.66, 77.24 28.66, 77.24 28.72, 77.18 28.72, 77.18 28.66))"),
                    ("WARD_DEL_002", "Karol Bagh Ward", "Karol Bagh Zone", "Delhi", "POLYGON((77.15 28.62, 77.21 28.62, 77.21 28.68, 77.15 28.68, 77.15 28.62))"),
                    ("WARD_DEL_003", "Connaught Place Ward", "New Delhi Zone", "Delhi", "POLYGON((77.19 28.58, 77.25 28.58, 77.25 28.64, 77.19 28.64, 77.19 28.58))"),
                    ("WARD_DEL_004", "Dwarka Ward", "Najafgarh Zone", "Delhi", "POLYGON((76.98 28.52, 77.08 28.52, 77.08 28.61, 76.98 28.61, 76.98 28.52))"),
                    ("WARD_DEL_005", "Rohini Ward", "Rohini Zone", "Delhi", "POLYGON((77.05 28.69, 77.16 28.69, 77.16 28.78, 77.05 28.78, 77.05 28.69))"),
                    ("WARD_DEL_006", "Okhla Ward", "Central Zone", "Delhi", "POLYGON((77.22 28.48, 77.32 28.48, 77.32 28.56, 77.22 28.56, 77.22 28.48))"),
                ]
                for w_id, w_name, z_name, city, wkt in wards:
                    cursor.execute(
                        """
                        INSERT INTO ward_boundaries (ward_id, ward_name, zone_name, city, geom)
                        VALUES (%s, %s, %s, %s, ST_GeomFromText(%s, 4326))
                        ON CONFLICT (ward_id) DO NOTHING;
                        """,
                        (w_id, w_name, z_name, city, wkt),
                    )

                logger.info("Successfully seeded database from offline snapshot.")
    except Exception as e:
        logger.error(f"Error seeding database: {e}", exc_info=True)
    finally:
        conn.close()


def main() -> None:
    run_migrations()
    print("Database migrations applied successfully.")
    seed_database()


if __name__ == "__main__":
    main()
