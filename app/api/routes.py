"""Weather API routes."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.limiter import limiter
from app.schemas.weather import WeatherResponse
from app.services.weather import WeatherService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def get_weather_service(request: Request) -> WeatherService:
    """Dependency: returns WeatherService instance with configured client."""
    from app.clients.weatherstack import WeatherstackClient

    http_client = getattr(request.app.state, "httpx_client", None)
    client = WeatherstackClient(settings, http_client=http_client)
    return WeatherService(client)


@router.get("/weather", response_model=WeatherResponse)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def get_weather(
    request: Request,
    city: Annotated[
        str,
        Query(min_length=2, max_length=50, description="City name"),
    ],
    service: Annotated[WeatherService, Depends(get_weather_service)],
) -> WeatherResponse:
    """Get current weather for a city."""
    logger.info("weather_request city=%s", city)
    return await service.get_weather(city)
