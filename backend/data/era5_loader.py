"""
backend/data/era5_loader.py

Loads ERA5 single-level NetCDF files and extracts boundary layer height (blh),
total precipitation (tp), and surface pressure (sp) for a given lat/lon point
and time range.

The file is expected to have:
    Dimensions: valid_time, latitude, longitude
    Variables:
        blh  (valid_time, latitude, longitude)  — Boundary layer height, metres
        tp   (valid_time, latitude, longitude)  — Total precipitation, metres/hour
        sp   (valid_time, latitude, longitude)  — Surface pressure, Pa

Usage:
    from backend.data.era5_loader import ERA5Loader
    loader = ERA5Loader("data/raw/reanalysis-era5-single-levels-timeseries-sfcym9to2oh.nc")
    df = loader.extract_for_station(lat=28.566, lon=77.186, timestamps=my_series)
    # df has columns: timestamp, blh_m, precipitation_mm, surface_pressure_hpa
"""

from __future__ import annotations

import os
from datetime import timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Default path relative to workspace root (can be overridden via env var)
_DEFAULT_ERA5_PATH = os.environ.get(
    "ERA5_NC_PATH",
    str(
        Path(__file__).resolve().parents[2]
        / "data"
        / "raw"
        / "reanalysis-era5-single-levels-timeseries-sfcym9to2oh.nc"
    ),
)


class ERA5Loader:
    """
    Lazy-loading wrapper around one ERA5 single-level NetCDF file.
    Loads the file once into memory on first use, then serves per-station
    nearest-neighbour interpolated time series with no additional I/O.

    Thread-safety: read-only after __init__, safe to share.
    """

    def __init__(self, nc_path: Optional[str] = None) -> None:
        self.nc_path = Path(nc_path or _DEFAULT_ERA5_PATH)
        if not self.nc_path.exists():
            raise FileNotFoundError(
                f"ERA5 NetCDF not found at: {self.nc_path}\n"
                "Download ERA5 hourly single-level data from https://cds.climate.copernicus.eu "
                "and set ERA5_NC_PATH or place it at data/raw/"
            )
        self._loaded = False

    def _load(self) -> None:
        """Load the NetCDF file into memory arrays (called lazily once)."""
        if self._loaded:
            return

        try:
            import netCDF4 as nc4
        except ImportError as e:
            raise ImportError(
                "netCDF4 is required for ERA5 loading. Install it with: pip install netCDF4"
            ) from e

        ds = nc4.Dataset(str(self.nc_path))

        # Time — convert to UTC-aware pandas DatetimeIndex
        raw_times = nc4.num2date(
            ds.variables["valid_time"][:],
            ds.variables["valid_time"].units,
            only_use_cftime_datetimes=False,
        )
        self._times = pd.DatetimeIndex(
            [
                pd.Timestamp(
                    t.year,
                    t.month,
                    t.day,
                    t.hour,
                    t.minute,
                    t.second,
                    tzinfo=timezone.utc,
                )
                for t in raw_times
            ]
        )

        # Spatial grids
        self._lats = np.array(ds.variables["latitude"][:])
        self._lons = np.array(ds.variables["longitude"][:])

        # Data arrays — shape (time, lat, lon)
        self._blh = np.array(ds.variables["blh"][:])  # metres
        # Total precipitation in ERA5 is accumulated hourly metres; treat as mm/h
        self._tp = np.array(ds.variables["tp"][:]) * 1000.0  # m → mm

        if "sp" in ds.variables:
            self._sp = np.array(ds.variables["sp"][:]) / 100.0  # Pa → hPa
        else:
            self._sp = None

        ds.close()
        self._loaded = True

    def _nearest_indices(self, lat: float, lon: float):
        """Return the (lat_idx, lon_idx) of the nearest grid cell."""
        lat_idx = int(np.argmin(np.abs(self._lats - lat)))
        lon_idx = int(np.argmin(np.abs(self._lons - lon)))
        return lat_idx, lon_idx

    def extract_for_timestamps(
        self,
        lat: float,
        lon: float,
        timestamps: pd.DatetimeIndex,
    ) -> pd.DataFrame:
        """
        Returns a DataFrame indexed by the provided UTC timestamps with columns:
            blh_m               — boundary layer height in metres
            precipitation_mm    — hourly precipitation in mm
            surface_pressure_hpa — surface pressure in hPa (or NaN if not in file)

        Missing timestamps (not in ERA5) are filled with NaN.

        Args:
            lat: Station latitude (degrees north).
            lon: Station longitude (degrees east).
            timestamps: UTC-aware pandas DatetimeIndex to extract for.
        """
        self._load()

        lat_idx, lon_idx = self._nearest_indices(lat, lon)

        # Build a lookup Series: ERA5_time → array index
        era5_index = pd.Series(np.arange(len(self._times)), index=self._times)

        # Normalise input timestamps to UTC hourly (drop sub-hourly component)
        ts_hourly = timestamps.tz_convert("UTC").floor("h")

        # Align: find ERA5 row indices for each requested timestamp
        row_indices = era5_index.reindex(
            ts_hourly
        ).values  # NaN where not found → float

        valid_mask = ~np.isnan(row_indices)
        row_indices_int = np.where(valid_mask, row_indices.astype(int), 0)

        blh_vals = np.where(
            valid_mask, self._blh[row_indices_int, lat_idx, lon_idx], np.nan
        )
        tp_vals = np.where(
            valid_mask, self._tp[row_indices_int, lat_idx, lon_idx], np.nan
        )

        result = pd.DataFrame(
            {
                "blh_m": blh_vals,
                "precipitation_mm": tp_vals,
            },
            index=timestamps,
        )

        if self._sp is not None:
            result["surface_pressure_hpa"] = np.where(
                valid_mask,
                self._sp[row_indices_int, lat_idx, lon_idx],
                np.nan,
            )
        else:
            result["surface_pressure_hpa"] = np.nan

        return result

    def merge_into_df(
        self, df: pd.DataFrame, lat_col="latitude", lon_col="longitude"
    ) -> pd.DataFrame:
        """
        Convenience method: given a flat station DataFrame with columns
        [timestamp, latitude, longitude, ...], merges ERA5 columns into it.

        Processes each unique (lat, lon) pair separately (one nearest-cell
        lookup per unique station location).

        Existing 'boundary_layer_height' and 'precipitation' columns are
        REPLACED with real ERA5 values (NaN fallback if timestamp is outside
        the ERA5 file range).
        """
        self._load()

        df = df.copy()

        # Ensure timestamp is UTC-aware
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

        result_parts = []
        for (lat, lon), group in df.groupby([lat_col, lon_col], sort=False):
            era5 = self.extract_for_timestamps(
                lat=float(lat),
                lon=float(lon),
                timestamps=pd.DatetimeIndex(group["timestamp"]),
            )
            era5 = era5.reset_index(drop=True)
            group = group.reset_index(drop=True)
            group["boundary_layer_height"] = era5["blh_m"]
            group["precipitation"] = era5["precipitation_mm"].clip(lower=0.0)
            group["surface_pressure_hpa"] = era5["surface_pressure_hpa"]
            result_parts.append(group)

        return (
            pd.concat(result_parts, ignore_index=True)
            .sort_values(["station_id", "timestamp"])
            .reset_index(drop=True)
        )


@lru_cache(maxsize=1)
def get_default_loader() -> ERA5Loader:
    """
    Returns a singleton ERA5Loader using the default file path.
    Cached so the file is only loaded once per process.
    """
    return ERA5Loader()
