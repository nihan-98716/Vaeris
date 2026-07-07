from typing import Any, Dict, List

import requests

from backend.config import settings
from backend.logging import logger


class FIRMSClient:
    """
    Client for NASA FIRMS (Fire Information for Resource Management System)
    Active Fire detections.
    """

    def __init__(self):
        self.base_url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
        self.api_key = settings.apis.firms_api_key

    def get_active_fires(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        days: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Fetches active fires for a given bounding box in CSV format
        and returns parsed dicts.
        """
        logger.info(
            "Fetching active fire hotspots from NASA FIRMS",
            extra={"bbox": [min_lat, min_lon, max_lat, max_lon], "days": days},
        )

        if not self.api_key:
            logger.warning(
                "No FIRMS API Key configured. "
                "Active fire queries will return empty results."
            )
            return []

        # West, South, East, North ordering for coordinate format string
        area_coords = f"{min_lon},{min_lat},{max_lon},{max_lat}"
        url = f"{self.base_url}/{self.api_key}/MODIS_SP/{area_coords}/{days}"

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()

            csv_data = response.text.strip().split("\n")
            if len(csv_data) <= 1:
                logger.info("No active fires detected in the given bounding box.")
                return []

            headers = csv_data[0].split(",")
            records = []
            for row in csv_data[1:]:
                values = row.split(",")
                if len(values) == len(headers):
                    records.append(dict(zip(headers, values, strict=False)))

            logger.info(
                "Successfully fetched active fires from FIRMS",
                extra={"count": len(records)},
            )
            return records
        except Exception as e:
            logger.error("Failed to fetch FIRMS active fire data", exc_info=True)
            raise e
