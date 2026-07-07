from typing import Any, Dict, List

import requests

from backend.config import settings
from backend.logging import logger


class OpenAQClient:
    """
    Client for fetching supplementary air quality data from OpenAQ.
    """

    def __init__(self):
        self.base_url = "https://api.openaq.org/v3"
        self.api_key = settings.apis.openaq_api_key

    def get_measurements(
        self, city: str = "Delhi", parameter: str = "pm25", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Queries OpenAQ REST API (v3) for measurements in a specified city/bbox.
        """
        logger.info(
            "Fetching OpenAQ measurements (v3)",
            extra={"city": city, "parameter": parameter},
        )
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        # Bbox covering Delhi NCR
        bbox = "76.8,28.4,77.5,28.9"
        url_locs = f"{self.base_url}/locations"
        params_locs = {
            "bbox": bbox,
            "order_by": "id",
            "sort_order": "desc",
            "limit": 10,
        }

        try:
            response = requests.get(
                url_locs, headers=headers, params=params_locs, timeout=10
            )
            response.raise_for_status()
            locs_data = response.json()

            results = []

            for loc in locs_data.get("results", []):
                loc_id = loc.get("id")
                loc_name = loc.get("name")
                coords = loc.get("coordinates")

                # Map sensor_id -> parameter name
                sensor_to_param = {}
                for s in loc.get("sensors", []):
                    s_id = s.get("id")
                    p_name = s.get("parameter", {}).get("name")
                    if s_id and p_name:
                        sensor_to_param[s_id] = p_name

                # Fetch latest measurements for this location
                url_latest = f"{self.base_url}/locations/{loc_id}/latest"
                try:
                    resp_latest = requests.get(url_latest, headers=headers, timeout=10)
                    resp_latest.raise_for_status()
                    latest_data = resp_latest.json()

                    for item in latest_data.get("results", []):
                        s_id = item.get("sensorsId")
                        p_name = sensor_to_param.get(s_id)
                        val = item.get("value")
                        dt = item.get("datetime", {}).get("utc")

                        if p_name and val is not None:
                            if parameter and p_name != parameter:
                                continue
                            results.append(
                                {
                                    "locationId": loc_id,
                                    "location": loc_name,
                                    "coordinates": coords,
                                    "value": val,
                                    "parameter": p_name,
                                    "date": {"utc": dt},
                                }
                            )
                except Exception:
                    logger.warning(
                        f"Failed to fetch latest measurements for location {loc_id}"
                    )

            logger.info(
                "Successfully fetched OpenAQ v3 measurements",
                extra={"count": len(results)},
            )
            return results[:limit]
        except Exception as e:
            logger.error(
                "Failed to fetch OpenAQ v3 measurements",
                exc_info=True,
                extra={"city": city},
            )
            raise e
