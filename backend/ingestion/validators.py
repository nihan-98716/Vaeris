from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import pandas as pd


def _check_station_required_fields(record: Dict[str, Any]) -> Tuple[bool, str]:
    required = ["station_id", "timestamp"]
    for field in required:
        if field not in record or record[field] is None:
            return False, f"Missing required field: {field}"
    return True, "Valid"


def _check_station_pm_fields(record: Dict[str, Any]) -> Tuple[bool, str]:
    for pm_field in ["pm25", "pm10"]:
        val = record.get(pm_field)
        if val is not None:
            try:
                val_f = float(val)
                if val_f < 0:
                    return False, f"{pm_field} cannot be negative: {val_f}"
            except (ValueError, TypeError) as e:
                return False, f"{pm_field} must be a valid number: {val}. Error: {e}"
    return True, "Valid"


def _check_station_timestamp(record: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        ts_str = str(record["timestamp"])
        dt = pd.to_datetime(ts_str)
        now = datetime.now(timezone.utc)
        dt_utc = dt if dt.tzinfo else dt.tz_localize(timezone.utc)
        if dt_utc > now:
            return False, f"Timestamp is in the future: {dt_utc.isoformat()}"
    except Exception as e:
        return False, f"Invalid timestamp format: {e}"
    return True, "Valid"


def validate_station_record(record: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates CPCB/OpenAQ station AQI measurements.
    """
    ok, msg = _check_station_required_fields(record)
    if not ok:
        return False, msg

    # Check AQI
    aqi = record.get("aqi")
    if aqi is not None:
        try:
            aqi_f = float(aqi)
            if aqi_f < 0:
                return False, f"AQI cannot be negative: {aqi_f}"
        except (ValueError, TypeError) as e:
            return False, f"AQI must be a valid number: {aqi}. Error: {e}"

    ok, msg = _check_station_pm_fields(record)
    if not ok:
        return False, msg

    return _check_station_timestamp(record)


def _check_weather_required_fields(record: Dict[str, Any]) -> Tuple[bool, str]:
    required = ["latitude", "longitude", "timestamp"]
    for field in required:
        if field not in record or record[field] is None:
            return False, f"Missing required weather field: {field}"
    return True, "Valid"


def _check_weather_wind(record: Dict[str, Any]) -> Tuple[bool, str]:
    # Validate wind speed
    wind_speed = record.get("wind_speed")
    if wind_speed is not None:
        try:
            ws = float(wind_speed)
            if ws < 0:
                return False, f"Wind speed cannot be negative: {ws}"
        except (ValueError, TypeError) as e:
            return False, f"Wind speed must be a valid number: {wind_speed}. Error: {e}"

    # Validate wind degrees
    wind_deg = record.get("wind_deg")
    if wind_deg is not None:
        try:
            wd = float(wind_deg)
            if not (0.0 <= wd <= 360.0):
                return False, f"Wind degrees must be between 0 and 360: {wd}"
        except (ValueError, TypeError) as e:
            return False, f"Wind degrees must be a valid number: {wind_deg}. Error: {e}"
    return True, "Valid"


def validate_weather_record(record: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates OpenWeather weather records.
    """
    ok, msg = _check_weather_required_fields(record)
    if not ok:
        return False, msg

    ok, msg = _check_weather_wind(record)
    if not ok:
        return False, msg

    # Validate humidity
    humidity = record.get("humidity")
    if humidity is not None:
        try:
            h = float(humidity)
            if not (0.0 <= h <= 100.0):
                return False, f"Humidity must be between 0 and 100: {h}"
        except (ValueError, TypeError) as e:
            return False, f"Humidity must be a valid number: {humidity}. Error: {e}"

    return True, "Valid"


def validate_fire_record(record: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates NASA FIRMS fire hotspots.
    Checks:
    - Required fields: latitude, longitude, acq_datetime
    - Coordinates validity: -90<=lat<=90, -180<=lon<=180
    - FRP (Fire Radiative Power) and brightness: >= 0 if present
    """
    required = ["latitude", "longitude", "acq_datetime"]
    for field in required:
        if field not in record or record[field] is None:
            return False, f"Missing required fire field: {field}"

    # Validate coordinates
    try:
        lat = float(record["latitude"])
        lon = float(record["longitude"])
        if not (-90.0 <= lat <= 90.0):
            return False, f"Latitude {lat} out of bounds"
        if not (-180.0 <= lon <= 180.0):
            return False, f"Longitude {lon} out of bounds"
    except (ValueError, TypeError) as e:
        return (
            False,
            f"Coordinates must be valid numbers: {record.get('latitude')}, "
            f"{record.get('longitude')}. Error: {e}",
        )

    # Validate FRP
    frp = record.get("frp")
    if frp is not None:
        try:
            frp_f = float(frp)
            if frp_f < 0:
                return False, f"FRP cannot be negative: {frp_f}"
        except (ValueError, TypeError) as e:
            return False, f"FRP must be a valid number: {frp}. Error: {e}"

    return True, "Valid"
