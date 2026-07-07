from typing import Any, Dict, List

import requests

from backend.config import settings
from backend.logging import logger


class OpenAQClient:
    """
    Client for fetching supplementary air quality data from OpenAQ.
    """

    def __init__(self):
        self.base_url = "https://api.openaq.org/v2/measurements"
        self.api_key = settings.apis.openaq_api_key

    def get_measurements(
        self, city: str = "Delhi", parameter: str = "pm25", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Queries OpenAQ REST API for pm25 measurements in a specified city.
        """
        logger.info(
            "Fetching OpenAQ measurements", extra={"city": city, "parameter": parameter}
        )
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        params = {
            "city": city,
            "parameter": parameter,
            "limit": limit,
            "order_by": "datetime",
            "sort": "desc",
        }

        try:
            response = requests.get(
                self.base_url, headers=headers, params=params, timeout=10
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            logger.info(
                "Successfully fetched OpenAQ measurements",
                extra={"count": len(results)},
            )
            return results
        except Exception as e:
            logger.error(
                "Failed to fetch OpenAQ measurements",
                exc_info=True,
                extra={"city": city},
            )
            raise e
