from typing import Any, Dict

import requests

from backend.config import settings
from backend.logging import logger


class WeatherClient:
    """
    Client for retrieving temperature, wind vector components, and relative humidity.
    """

    def __init__(self):
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
        self.api_key = settings.apis.weather_api_key

    def get_current_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Retrieves current weather details for a specific latitude and longitude.
        """
        logger.info(
            "Fetching weather metrics from OpenWeather", extra={"lat": lat, "lon": lon}
        )

        if not self.api_key:
            logger.warning(
                "No OpenWeather API Key configured. "
                "Weather queries will return empty results."
            )
            return {}

        params = {"lat": lat, "lon": lon, "appid": self.api_key, "units": "metric"}

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            wind = data.get("wind", {})
            metrics = {
                "temperature": data.get("main", {}).get("temp"),
                "humidity": data.get("main", {}).get("humidity"),
                "wind_speed": wind.get("speed"),
                "wind_deg": wind.get("deg"),
            }
            logger.info("Successfully fetched weather metrics", extra=metrics)
            return metrics
        except Exception as e:
            logger.error(
                "Failed to fetch weather metrics",
                exc_info=True,
                extra={"lat": lat, "lon": lon},
            )
            raise e
