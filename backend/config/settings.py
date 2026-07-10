import os
from pathlib import Path
from typing import Dict

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Resolve project base directory to load .env file
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class DatabaseSettings(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="postgres")
    password: str = Field(default="postgres")
    dbname: str = Field(default="vaeris")


class RedisSettings(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    default_ttl_forecast: int = Field(default=900)  # 15 minutes
    default_ttl_attribution: int = Field(default=1800)  # 30 minutes


class ApiSettings(BaseModel):
    firms_api_key: str = Field(default="")
    weather_api_key: str = Field(default="")
    openaq_api_key: str = Field(default="")


class AttributionSettings(BaseModel):
    fire_search_radius_km: float = Field(default=100.0)
    fire_bearing_tolerance_deg: float = Field(default=30.0)
    transport_speed_tolerance_hours: float = Field(default=3.0)
    road_density_high_traffic_threshold: float = Field(default=0.6)
    aqi_spike_threshold: float = Field(default=15.0)
    stagnant_wind_speed_ms: float = Field(default=1.0)


class Settings(BaseModel):
    database: DatabaseSettings
    redis: RedisSettings
    apis: ApiSettings
    attribution: AttributionSettings
    optimizer_weights: Dict[str, float] = Field(default_factory=dict)

    @classmethod
    def load(cls) -> "Settings":
        db_settings = DatabaseSettings(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            dbname=os.getenv("DB_NAME", "vaeris"),
        )
        redis_settings = RedisSettings(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            default_ttl_forecast=int(os.getenv("REDIS_TTL_FORECAST", "900")),
            default_ttl_attribution=int(os.getenv("REDIS_TTL_ATTRIBUTION", "1800")),
        )
        api_settings = ApiSettings(
            firms_api_key=os.getenv("FIRMS_API_KEY", ""),
            weather_api_key=os.getenv("WEATHER_API_KEY", ""),
            openaq_api_key=os.getenv("OPENAQ_API_KEY", ""),
        )

        weights_file = Path(__file__).parent / "weights.yaml"
        optimizer_weights = {}
        if weights_file.exists():
            with open(weights_file, "r") as f:
                try:
                    weights_data = yaml.safe_load(f)
                    optimizer_weights = weights_data.get("optimizer", {}).get(
                        "weights", {}
                    )
                except yaml.YAMLError:
                    # Fallback defaults if YAML is malformed
                    optimizer_weights = {
                        "aqi": 0.45,
                        "population": 0.25,
                        "health": 0.20,
                        "cost": 0.10,
                    }

        attribution_settings = AttributionSettings(
            fire_search_radius_km=float(
                os.getenv("ATTRIBUTION_FIRE_RADIUS_KM", "100.0")
            ),
            fire_bearing_tolerance_deg=float(
                os.getenv("ATTRIBUTION_FIRE_BEARING_TOLERANCE_DEG", "30.0")
            ),
            transport_speed_tolerance_hours=float(
                os.getenv("ATTRIBUTION_TRANSPORT_SPEED_TOLERANCE_HOURS", "3.0")
            ),
            road_density_high_traffic_threshold=float(
                os.getenv("ATTRIBUTION_ROAD_DENSITY_HIGH_TRAFFIC_THRESHOLD", "0.6")
            ),
            aqi_spike_threshold=float(
                os.getenv("ATTRIBUTION_AQI_SPIKE_THRESHOLD", "15.0")
            ),
            stagnant_wind_speed_ms=float(
                os.getenv("ATTRIBUTION_STAGNANT_WIND_SPEED_MS", "1.0")
            ),
        )

        return cls(
            database=db_settings,
            redis=redis_settings,
            apis=api_settings,
            attribution=attribution_settings,
            optimizer_weights=optimizer_weights,
        )


# Global settings instance
settings = Settings.load()
