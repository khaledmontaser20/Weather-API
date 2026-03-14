"""Weather API request and response schemas."""

from pydantic import BaseModel, Field


class WeatherResponse(BaseModel):
    """Normalized weather response from the API."""

    location: str = Field(..., description="City name")
    country: str = Field(..., description="Country name")
    temperature: int = Field(..., description="Current temperature in Celsius")
    description: str = Field(..., description="Weather description")
    humidity: int = Field(..., description="Humidity percentage")
    wind_speed: int = Field(..., description="Wind speed in km/h")
    observation_time: str = Field(..., description="Local observation time")
