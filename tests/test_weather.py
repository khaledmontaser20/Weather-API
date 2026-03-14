"""Unit tests for the weather API endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.clients.weatherstack import CityNotFoundError, WeatherstackError


def test_get_weather_success(client: TestClient, mock_weatherstack_response: dict) -> None:
    """Successful weather request returns 200 and correct schema."""
    with patch(
        "app.clients.weatherstack.WeatherstackClient.get_current_weather",
        new_callable=AsyncMock,
        return_value=mock_weatherstack_response,
    ):
        response = client.get("/weather", params={"city": "London"})

    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "London"
    assert data["country"] == "United Kingdom"
    assert data["temperature"] == 12
    assert data["description"] == "Partly cloudy"
    assert data["humidity"] == 72
    assert data["wind_speed"] == 15
    assert data["observation_time"] == "2025-03-13 14:00"


def test_get_weather_missing_city(client: TestClient) -> None:
    """Missing city parameter returns 422."""
    response = client.get("/weather")
    assert response.status_code == 422
    assert "detail" in response.json()


def test_get_weather_city_too_short(client: TestClient) -> None:
    """City with length < 2 returns 422."""
    response = client.get("/weather", params={"city": "A"})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_get_weather_weatherstack_api_error(client: TestClient) -> None:
    """Weatherstack API error returns 502."""
    with patch(
        "app.clients.weatherstack.WeatherstackClient.get_current_weather",
        new_callable=AsyncMock,
        side_effect=WeatherstackError("Weather service unavailable"),
    ):
        response = client.get("/weather", params={"city": "ErrorTestCity"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Weather service unavailable"


def test_get_weather_city_not_found(client: TestClient) -> None:
    """City not found returns 404."""
    with patch(
        "app.clients.weatherstack.WeatherstackClient.get_current_weather",
        new_callable=AsyncMock,
        side_effect=CityNotFoundError("City not found"),
    ):
        response = client.get("/weather", params={"city": "NonExistentCity"})

    assert response.status_code == 404
    assert response.json()["detail"] == "City not found"


def test_get_weather_caching(client: TestClient, mock_weatherstack_response: dict) -> None:
    """Two identical requests call Weatherstack API only once (cache hit on second)."""
    mock_get = AsyncMock(return_value=mock_weatherstack_response)

    with patch(
        "app.clients.weatherstack.WeatherstackClient.get_current_weather",
        mock_get,
    ):
        response1 = client.get("/weather", params={"city": "Paris"})
        response2 = client.get("/weather", params={"city": "Paris"})

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json() == response2.json()
    assert mock_get.call_count == 1
