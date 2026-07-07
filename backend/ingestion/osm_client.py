import requests

from backend.logging import logger


class OSMClient:
    """
    Client for querying the OpenStreetMap Overpass API to extract road density metrics.
    """

    def __init__(self):
        self.base_url = "https://overpass-api.de/api/interpreter"

    def get_road_count(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> int:
        """
        Queries Overpass to find the total count of roads in a bounding box.
        """
        logger.info(
            "Fetching OSM highway counts for bounding box",
            extra={"bbox": [min_lat, min_lon, max_lat, max_lon]},
        )

        # Overpass query to count highway elements in the bbox
        # Bbox parameters order: south, west, north, east
        overpass_query = f"""
        [out:json];
        (
          way["highway"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out count;
        """

        try:
            response = requests.post(
                self.base_url, data={"data": overpass_query}, timeout=15
            )
            response.raise_for_status()
            data = response.json()

            elements = data.get("elements", [])
            count = 0
            if elements:
                count = int(elements[0].get("tags", {}).get("ways", 0))

            logger.info(
                "Successfully fetched OSM highway count", extra={"count": count}
            )
            return count
        except Exception as e:
            logger.error("Failed to fetch OSM road density data", exc_info=True)
            raise e
