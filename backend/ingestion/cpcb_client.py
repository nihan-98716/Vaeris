import os
from typing import Any, Dict, List

import requests

from backend.logging import logger


class CPCBClient:
    """
    Client for retrieving ground-truth air quality readings from the CPCB CAAQMS portal.
    """

    def __init__(self):
        self.base_url = (
            "https://api.data.gov.in/resource/3b01bcb8-0b16-412f-b44c-a725d6287f62"
        )
        self.api_key = os.getenv("OGD_API_KEY", "")

    def get_realtime_aqi(self, city: str = "Delhi") -> List[Dict[str, Any]]:
        """
        Retrieves real-time CAAQMS station readings for a given city from OGD.
        """
        logger.info("Fetching real-time CPCB AQI data", extra={"city": city})
        if not self.api_key:
            logger.warning("No OGD API Key configured. Returning empty list.")
            return []

        params = {
            "api-key": self.api_key,
            "format": "json",
            "filters[city]": city,
            "limit": 100,
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            records = data.get("records", [])
            logger.info(
                "Successfully fetched CPCB records", extra={"count": len(records)}
            )
            return records
        except Exception as e:
            logger.error(
                "Failed to fetch CPCB AQI data", exc_info=True, extra={"city": city}
            )
            raise e
