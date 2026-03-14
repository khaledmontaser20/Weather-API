"""Pytest fixtures for weather API tests."""

import os

# Set high rate limit for tests (except test_rate_limit_exceeded which uses 2)
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client. Use as context manager to trigger lifespan."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_weatherstack_response() -> dict:
    """Sample successful Weatherstack API response."""
    return {
        "request": {"type": "City", "query": "London, United Kingdom", "unit": "m"},
        "location": {
            "name": "London",
            "country": "United Kingdom",
            "region": "London",
            "lat": "51.517",
            "lon": "-0.106",
            "timezone_id": "Europe/London",
            "localtime": "2025-03-13 14:00",
        },
        "current": {
            "observation_time": "02:00 PM",
            "temperature": 12,
            "weather_code": 116,
            "weather_descriptions": ["Partly cloudy"],
            "wind_speed": 15,
            "humidity": 72,
        },
    }
