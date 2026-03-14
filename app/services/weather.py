"""Weather service: business logic, caching, and response mapping."""

import asyncio
import logging
from typing import Any

from cachetools import TTLCache
from pydantic import ValidationError

from app.clients.weatherstack import WeatherstackClient, WeatherstackError
from app.config import settings
from app.schemas.weather import WeatherResponse

logger = logging.getLogger(__name__)

# In-memory TTL cache; disabled when CACHE_TTL_SECONDS is 0
_cache: TTLCache[str, WeatherResponse] | None = None
# Prevents thundering herd: concurrent requests for same city wait for first fetch
_fetch_lock: asyncio.Lock = asyncio.Lock()


def _get_cache() -> TTLCache[str, WeatherResponse] | None:
    """Return the cache instance if caching is enabled."""
    global _cache
    if settings.cache_ttl_seconds <= 0:
        return None
    if _cache is None:
        _cache = TTLCache(maxsize=100, ttl=settings.cache_ttl_seconds)
    return _cache


def _normalize_city(city: str) -> str:
    """Normalize city for cache key: strip whitespace and lowercase."""
    return city.strip().lower()


def _map_weatherstack_to_response(data: dict[str, Any]) -> WeatherResponse:
    """Map raw Weatherstack API response to WeatherResponse schema."""
    try:
        location = data.get("location") or {}
        current = data.get("current") or {}
        descriptions = current.get("weather_descriptions") or []
        description = descriptions[0] if descriptions else ""

        return WeatherResponse(
            location=location.get("name", ""),
            country=location.get("country", ""),
            temperature=current.get("temperature", 0),
            description=description,
            humidity=current.get("humidity", 0),
            wind_speed=current.get("wind_speed", 0),
            observation_time=location.get("localtime", ""),
        )
    except ValidationError as e:
        logger.warning("weatherstack_error error=invalid_response msg=%s", str(e))
        raise WeatherstackError("Weather service returned invalid data") from e


class WeatherService:
    """Service for fetching weather with caching."""

    def __init__(self, client: WeatherstackClient) -> None:
        self._client = client

    async def get_weather(self, city: str) -> WeatherResponse:
        """
        Get weather for a city. Uses cache when enabled; normalizes city before lookup.
        Uses a lock to prevent thundering herd when multiple requests miss cache for same city.
        """
        normalized = _normalize_city(city)
        cache = _get_cache()

        if cache is not None and normalized in cache:
            logger.info("cache_hit city=%s", normalized)
            return cache[normalized]

        async with _fetch_lock:
            if cache is not None and normalized in cache:
                logger.info("cache_hit city=%s", normalized)
                return cache[normalized]
            logger.info("weatherstack_call city=%s", city)
            raw = await self._client.get_current_weather(city)
            response = _map_weatherstack_to_response(raw)
            if cache is not None:
                cache[normalized] = response
            return response
