"""HTTP client for Weatherstack API — HTTP only, no business logic."""

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


def _is_retryable(error: Exception) -> bool:
    """Return True for transient failures: network errors, timeouts. Not 4xx."""
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code >= 500
    if isinstance(error, (httpx.TimeoutException, httpx.RequestError)):
        return True
    return False


class WeatherstackAuthError(Exception):
    """Raised when Weatherstack returns 401 or 403."""

    pass


class WeatherstackRateLimitError(Exception):
    """Raised when Weatherstack returns 429."""

    pass


class CityNotFoundError(Exception):
    """Raised when city is not found or query is invalid."""

    pass


class WeatherstackError(Exception):
    """Raised for 5xx, timeout, or other upstream failures."""

    pass


class WeatherstackClient:
    """HTTP-only client for Weatherstack current weather API."""

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = settings.weatherstack_base_url.rstrip("/")
        self._api_key = settings.weatherstack_api_key
        self._timeout = httpx.Timeout(settings.weatherstack_request_timeout)
        self._max_attempts = 1 + settings.retry_max_retries
        self._initial_delay = settings.retry_initial_delay
        self._http_client = http_client

    async def get_current_weather(self, city: str) -> dict[str, Any]:
        """
        Fetch current weather for a city from Weatherstack.
        Returns raw JSON response dict.
        Raises domain exceptions on HTTP or API errors.
        Retries on transient failures (network, timeout, 5xx) with exponential backoff.
        """
        url = f"{self._base_url}/current"
        params = {"access_key": self._api_key, "query": city}
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                if self._http_client is not None:
                    response = await self._http_client.get(url, params=params)
                else:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.get(url, params=params)
            except httpx.TimeoutException as e:
                last_error = e
                if _is_retryable(e) and attempt < self._max_attempts:
                    delay = self._initial_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "weatherstack_retry city=%s attempt=%s/%s error=timeout delay=%.1fs",
                        city,
                        attempt,
                        self._max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.warning("weatherstack_error city=%s error=timeout", city)
                raise WeatherstackError("Request timed out") from e
            except httpx.RequestError as e:
                last_error = e
                if _is_retryable(e) and attempt < self._max_attempts:
                    delay = self._initial_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "weatherstack_retry city=%s attempt=%s/%s error=%s delay=%.1fs",
                        city,
                        attempt,
                        self._max_attempts,
                        str(e),
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.warning("weatherstack_error city=%s error=%s", city, str(e))
                raise WeatherstackError(str(e)) from e

            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.warning(
                    "weatherstack_error city=%s error=invalid_json status=%s",
                    city,
                    response.status_code,
                )
                if response.status_code >= 500:
                    if attempt < self._max_attempts:
                        delay = self._initial_delay * (2 ** (attempt - 1))
                        logger.warning(
                            "weatherstack_retry city=%s attempt=%s/%s status=%s delay=%.1fs",
                            city,
                            attempt,
                            self._max_attempts,
                            response.status_code,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                raise WeatherstackError("Weather service returned invalid response") from e

            if response.status_code == 401 or response.status_code == 403:
                logger.warning(
                    "weatherstack_error city=%s error=auth_failed status=%s",
                    city,
                    response.status_code,
                )
                raise WeatherstackAuthError("Weather service authentication failed")

            if response.status_code == 429:
                logger.warning("weatherstack_error city=%s error=rate_limit", city)
                raise WeatherstackRateLimitError("Weather service rate limit exceeded")

            if response.status_code >= 500:
                if attempt < self._max_attempts:
                    delay = self._initial_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "weatherstack_retry city=%s attempt=%s/%s status=%s delay=%.1fs",
                        city,
                        attempt,
                        self._max_attempts,
                        response.status_code,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.warning(
                    "weatherstack_error city=%s error=upstream status=%s",
                    city,
                    response.status_code,
                )
                raise WeatherstackError("Weather service unavailable")

            if not data.get("success", True):
                self._raise_for_api_error(data, city)

            return data

        logger.warning(
            "weatherstack_error city=%s error=all_retries_exhausted",
            city,
        )
        msg = "Weather service unavailable"
        if last_error:
            raise WeatherstackError(msg) from last_error
        raise WeatherstackError(msg)

    def _raise_for_api_error(self, data: dict[str, Any], city: str) -> None:
        """Map Weatherstack error payload to domain exceptions."""
        error = data.get("error", {})
        code = error.get("code")
        error_type = str(error.get("type", "")).lower()
        info = str(error.get("info", ""))

        if code in (101,) or "unauthorized" in error_type or "forbidden" in error_type:
            logger.warning("weatherstack_error city=%s error=auth_failed info=%s", city, info)
            raise WeatherstackAuthError("Weather service authentication failed")

        if code == 429 or "too_many" in error_type or "usage_limit" in error_type:
            logger.warning("weatherstack_error city=%s error=rate_limit info=%s", city, info)
            raise WeatherstackRateLimitError("Weather service rate limit exceeded")

        if (
            code in (404, 601, 615)
            or "not_found" in error_type
            or "missing_query" in error_type
            or "request_failed" in error_type
        ):
            logger.warning("weatherstack_error city=%s error=city_not_found info=%s", city, info)
            raise CityNotFoundError("City not found")

        logger.warning(
            "weatherstack_error city=%s error=%s code=%s info=%s",
            city,
            error_type,
            code,
            info,
        )
        raise WeatherstackError(info or "Weather service unavailable")
