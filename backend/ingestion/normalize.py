from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Union

import pandas as pd

from backend.logging import logger


def parse_to_utc(
    ts_value: Union[str, int, float], source_format: str = "auto"
) -> datetime:
    """
    Parses various timestamp formats (epochs, ISO-8601, IST strings)
    and returns a timezone-aware UTC datetime.
    """
    if isinstance(ts_value, (int, float)):
        # Treat numbers as unix epochs
        return datetime.fromtimestamp(ts_value, tz=timezone.utc)

    ts_str = str(ts_value).strip()

    if source_format == "cpcb":
        # CPCB datetimes are in Indian Standard Time (IST, UTC+5:30)
        # Formats commonly include "dd-mm-yyyy HH:MM:SS" or "yyyy-mm-dd HH:MM:SS"
        for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
            try:
                dt_ist = datetime.strptime(ts_str, fmt)
                dt_utc = dt_ist - timedelta(hours=5, minutes=30)
                return dt_utc.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

    if source_format == "firms":
        # FIRMS dates are YYYY-MM-DD and times are HHMM (UTC)
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H%M")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # Default fallback using pandas parsing
    try:
        dt = pd.to_datetime(ts_str)
        if dt.tzinfo is None:
            return dt.tz_localize(timezone.utc)
        return dt.tz_convert(timezone.utc)
    except Exception as e:
        logger.error(
            "Failed to parse timestamp to UTC",
            extra={"ts_value": ts_value},
            exc_info=True,
        )
        raise ValueError(f"Could not parse timestamp {ts_value}: {e}") from e


def normalize_crs(lat: Union[str, float], lon: Union[str, float]) -> Dict[str, float]:
    """
    Validates coordinates and ensures they conform to EPSG:4326 (WGS 84).
    Returns float representations of the validated coordinates.
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)

        if not (-90.0 <= lat_f <= 90.0):
            raise ValueError(f"Latitude {lat_f} out of bounds [-90, 90]")
        if not (-180.0 <= lon_f <= 180.0):
            raise ValueError(f"Longitude {lon_f} out of bounds [-180, 180]")

        return {"latitude": lat_f, "longitude": lon_f}
    except Exception as e:
        logger.error(
            "Coordinate CRS validation failed",
            extra={"lat": lat, "lon": lon},
            exc_info=True,
        )
        raise ValueError(f"Invalid coordinate layout: {e}") from e


def _normalize_records_list(
    records: List[Dict[str, Any]], timestamp_key: str, value_keys: List[str]
) -> List[Dict[str, Any]]:
    """
    Helper function to filter and convert list of records to standardized UTC format.
    """
    normalized_records = []
    for r in records:
        try:
            utc_dt = parse_to_utc(r[timestamp_key])
            new_r = {timestamp_key: utc_dt}
            for vk in value_keys:
                if vk in r and r[vk] is not None:
                    new_r[vk] = float(r[vk])
            normalized_records.append(new_r)
        except Exception:
            # Skip invalid/malformed records
            continue
    return normalized_records


def resample_time_series(
    records: List[Dict[str, Any]],
    timestamp_key: str,
    value_keys: List[str],
    freq: str = "1h",
    agg_method: str = "mean",
) -> List[Dict[str, Any]]:
    """
    Groups mismatched time-series records into a clean hourly temporal grid.
    Handles missing values and aggregations cleanly using pandas.
    """
    if not records:
        return []

    logger.info(
        "Resampling time-series data", extra={"count": len(records), "freq": freq}
    )

    normalized_records = _normalize_records_list(records, timestamp_key, value_keys)

    if not normalized_records:
        return []

    df = pd.DataFrame(normalized_records)
    df.set_index(timestamp_key, inplace=True)

    resampler = df.resample(freq)
    resampled_df = resampler.sum() if agg_method == "sum" else resampler.mean()

    resampled_df.reset_index(inplace=True)

    result = []
    for _, row in resampled_df.iterrows():
        # Exclude intervals where all resampled values are NaN
        if row[value_keys].isna().all():
            continue

        row_dict = {timestamp_key: row[timestamp_key].isoformat()}
        for vk in value_keys:
            val = row[vk]
            row_dict[vk] = None if pd.isna(val) else float(val)
        result.append(row_dict)

    return result
