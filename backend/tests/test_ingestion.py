from datetime import datetime, timedelta, timezone

from backend.ingestion.validators import (
    validate_fire_record,
    validate_station_record,
    validate_weather_record,
)


def test_validate_station_record_valid():
    record = {
        "station_id": "DL001",
        "timestamp": "2024-11-18T10:00:00Z",
        "aqi": 312,
        "pm25": 150.5,
        "pm10": 280.0,
    }
    is_valid, msg = validate_station_record(record)
    assert is_valid
    assert msg == "Valid"


def test_validate_station_record_invalid():
    # Test missing required field
    is_valid, msg = validate_station_record({"aqi": 100})
    assert not is_valid
    assert "Missing required field" in msg

    # Test negative AQI
    record = {
        "station_id": "DL001",
        "timestamp": "2024-11-18T10:00:00Z",
        "aqi": -5,
    }
    is_valid, msg = validate_station_record(record)
    assert not is_valid
    assert "cannot be negative" in msg

    # Test future timestamp
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    record = {"station_id": "DL001", "timestamp": future_time, "aqi": 100}
    is_valid, msg = validate_station_record(record)
    assert not is_valid
    assert "in the future" in msg


def test_validate_weather_record_valid():
    record = {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "timestamp": "2024-11-18T10:00:00Z",
        "wind_speed": 4.5,
        "wind_deg": 180,
        "humidity": 45,
    }
    is_valid, msg = validate_weather_record(record)
    assert is_valid
    assert msg == "Valid"


def test_validate_weather_record_invalid():
    # Invalid wind degree
    record = {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "timestamp": "2024-11-18T10:00:00Z",
        "wind_deg": 400,
    }
    is_valid, msg = validate_weather_record(record)
    assert not is_valid
    assert "must be between 0 and 360" in msg


def test_validate_fire_record_valid():
    record = {
        "latitude": 29.5,
        "longitude": 76.2,
        "acq_datetime": "2024-11-18T05:30:00Z",
        "frp": 12.5,
    }
    is_valid, msg = validate_fire_record(record)
    assert is_valid
    assert msg == "Valid"


def test_validate_fire_record_invalid():
    # Latitude out of bounds
    record = {
        "latitude": 100.0,
        "longitude": 76.2,
        "acq_datetime": "2024-11-18T05:30:00Z",
    }
    is_valid, msg = validate_fire_record(record)
    assert not is_valid
    assert "Latitude 100.0 out of bounds" in msg
