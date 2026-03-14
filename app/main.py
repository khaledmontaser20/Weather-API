"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.clients.weatherstack import (
    CityNotFoundError,
    WeatherstackAuthError,
    WeatherstackError,
    WeatherstackRateLimitError,
)
from app.config import settings
from app.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create and close shared httpx client."""
    timeout = httpx.Timeout(settings.weatherstack_request_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        app.state.httpx_client = client
        yield
    # Client closed automatically when exiting context


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return 429 with consistent API error format."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."},
    )


# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Weather API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(router, tags=["weather"])


@app.exception_handler(WeatherstackAuthError)
async def handle_auth_error(
    _request: Request, _exc: WeatherstackAuthError
) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": "Weather service authentication failed"},
    )


@app.exception_handler(WeatherstackRateLimitError)
async def handle_rate_limit_error(
    _request: Request, _exc: WeatherstackRateLimitError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "Weather service rate limit exceeded"},
    )


@app.exception_handler(CityNotFoundError)
async def handle_city_not_found(
    _request: Request, _exc: CityNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": "City not found"},
    )


@app.exception_handler(WeatherstackError)
async def handle_weatherstack_error(
    _request: Request, _exc: WeatherstackError
) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": "Weather service unavailable"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
