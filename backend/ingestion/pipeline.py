from datetime import datetime, timezone
from typing import Any, Dict, List

from backend.db.connection import get_db_cursor
from backend.ingestion.cpcb_client import CPCBClient
from backend.ingestion.firms_client import FIRMSClient
from backend.ingestion.normalize import parse_to_utc
from backend.ingestion.openaq_client import OpenAQClient
from backend.ingestion.osm_client import OSMClient
from backend.ingestion.validators import (
    validate_fire_record,
    validate_station_record,
    validate_weather_record,
)
from backend.ingestion.weather_client import WeatherClient
from backend.logging import logger


def save_monitoring_stations(stations: List[Dict[str, Any]]):
    """
    Saves monitoring station metadata into PostGIS.
    """
    query = """
        INSERT INTO monitoring_stations (id, name, city, latitude, longitude, geom)
        VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            geom = EXCLUDED.geom;
    """
    with get_db_cursor() as cursor:
        for s in stations:
            cursor.execute(
                query,
                (
                    s["id"],
                    s["name"],
                    s["city"],
                    s["longitude"],
                    s["latitude"],
                    s["longitude"],
                    s["latitude"],
                ),
            )


def save_aqi_measurements(records: List[Dict[str, Any]]):
    """
    Saves AQI station measurements.
    """
    query = """
        INSERT INTO aqi_measurements (station_id, timestamp, aqi, pm25, pm10)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (station_id, timestamp) DO NOTHING;
    """
    with get_db_cursor() as cursor:
        for r in records:
            cursor.execute(
                query,
                (
                    r["station_id"],
                    r["timestamp"],
                    r.get("aqi"),
                    r.get("pm25"),
                    r.get("pm10"),
                ),
            )


def save_fire_hotspots(records: List[Dict[str, Any]]):
    """
    Saves active fire coordinates.
    """
    query = """
        INSERT INTO fire_hotspots (
            latitude, longitude, geom, brightness, frp, acq_datetime
        )
        VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)
        ON CONFLICT (latitude, longitude, acq_datetime) DO NOTHING;
    """
    with get_db_cursor() as cursor:
        for r in records:
            cursor.execute(
                query,
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


def save_weather_readings(records: List[Dict[str, Any]]):
    """
    Saves weather metrics.
    """
    query = """
        INSERT INTO weather_readings (
            latitude, longitude, geom, timestamp,
            temperature, humidity, wind_speed, wind_deg
        )
        VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s)
        ON CONFLICT (latitude, longitude, timestamp) DO NOTHING;
    """
    with get_db_cursor() as cursor:
        for r in records:
            cursor.execute(
                query,
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


class IngestionPipeline:
    """
    Orchestrator for managing CPCB, OpenAQ, FIRMS, Weather, and OSM client pulls
    with fallback logging.
    """

    def __init__(self):
        self.cpcb = CPCBClient()
        self.openaq = OpenAQClient()
        self.firms = FIRMSClient()
        self.weather = WeatherClient()
        self.osm = OSMClient()

    def _ingest_osm(self, bbox: List[float]) -> bool:
        try:
            road_count = self.osm.get_road_count(bbox[0], bbox[1], bbox[2], bbox[3])
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO osm_road_cache (
                        min_lat, min_lon, max_lat, max_lon, road_count
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (min_lat, min_lon, max_lat, max_lon) DO UPDATE SET
                        road_count = EXCLUDED.road_count,
                        fetched_at = CURRENT_TIMESTAMP;
                    """,
                    (bbox[0], bbox[1], bbox[2], bbox[3], road_count),
                )
            return True
        except Exception:
            logger.error("OSM road density ingestion failed", exc_info=True)
            return False

    def _ingest_weather(self, center_lat: float, center_lon: float) -> bool:
        try:
            w = self.weather.get_current_weather(center_lat, center_lon)
            if w:
                w["latitude"] = center_lat
                w["longitude"] = center_lon
                w["timestamp"] = datetime.now(timezone.utc).isoformat()

                ok, msg = validate_weather_record(w)
                if ok:
                    save_weather_readings([w])
                else:
                    logger.warning(f"Weather record validation failed: {msg}")
            return True
        except Exception:
            logger.error("Weather data ingestion failed", exc_info=True)
            return False

    def _ingest_firms(self, bbox: List[float]) -> bool:
        try:
            fires = self.firms.get_active_fires(bbox[0], bbox[1], bbox[2], bbox[3])
            valid_fires = []
            for f in fires:
                f["acq_datetime"] = f"{f['acq_date']} {f['acq_time']}"
                f["acq_datetime"] = parse_to_utc(
                    f["acq_datetime"], source_format="firms"
                ).isoformat()

                ok, msg = validate_fire_record(f)
                if ok:
                    valid_fires.append(f)
            if valid_fires:
                save_fire_hotspots(valid_fires)
            return True
        except Exception:
            logger.error("FIRMS fire ingestion failed", exc_info=True)
            return False

    def _ingest_aqi(self, city: str, center_lat: float, center_lon: float) -> bool:
        try:
            results = self.openaq.get_measurements(city=city, limit=20)
            valid_aqi = []
            valid_stations = []
            for r in results:
                station_id = f"openaq_{r.get('locationId')}"
                station = {
                    "id": station_id,
                    "name": r.get("location", "OpenAQ Station"),
                    "city": city,
                    "latitude": r.get("coordinates", {}).get("latitude"),
                    "longitude": r.get("coordinates", {}).get("longitude"),
                }
                if not station["latitude"] or not station["longitude"]:
                    station["latitude"] = center_lat
                    station["longitude"] = center_lon

                aqi_val = r.get("value")
                meas = {
                    "station_id": station_id,
                    "timestamp": parse_to_utc(r.get("date", {}).get("utc")).isoformat(),
                    "aqi": aqi_val,
                    "pm25": aqi_val if r.get("parameter") == "pm25" else None,
                    "pm10": aqi_val if r.get("parameter") == "pm10" else None,
                }

                ok_st, msg_st = validate_station_record(meas)
                if ok_st:
                    valid_stations.append(station)
                    valid_aqi.append(meas)

            if valid_stations:
                save_monitoring_stations(valid_stations)
            if valid_aqi:
                save_aqi_measurements(valid_aqi)
            return True
        except Exception:
            logger.error("OpenAQ/CPCB ingestion failed", exc_info=True)
            return False

    def run_ingestion_cycle(
        self, city: str = "Delhi", bbox: List[float] = None
    ) -> Dict[str, bool]:
        """
        Runs a full cycle over the data sources, catching errors gracefully.
        """
        if bbox is None:
            bbox = [28.0, 76.5, 29.0, 77.5]

        center_lat = (bbox[0] + bbox[2]) / 2
        center_lon = (bbox[1] + bbox[3]) / 2

        status_osm = self._ingest_osm(bbox)
        status_weather = self._ingest_weather(center_lat, center_lon)
        status_firms = self._ingest_firms(bbox)
        status_aqi = self._ingest_aqi(city, center_lat, center_lon)

        return {
            "cpcb": status_aqi,
            "openaq": status_aqi,
            "firms": status_firms,
            "weather": status_weather,
            "osm": status_osm,
        }
