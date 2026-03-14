# Weather API

A production-ready REST API for fetching current weather data by city, built with FastAPI.

## 1. Project Overview

The Weather API provides a simple interface to retrieve weather information for any city. It integrates with the [Weatherstack API](https://weatherstack.com/) to fetch real-time data and exposes it through a normalized, consistent schema.

**What it solves:**

- Abstracts the Weatherstack API behind a clean, stable contract
- Reduces external API calls via in-memory caching
- Protects the upstream service with rate limiting and retries
- Handles transient failures (network errors, timeouts, 5xx) with exponential backoff

---

## 2. Architecture

The project uses a **layered architecture** with clear separation of concerns:

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **API** | `app/api/routes.py` | HTTP endpoints, request validation, dependency injection |
| **Service** | `app/services/weather.py` | Business logic, caching, response mapping |
| **Client** | `app/clients/weatherstack.py` | HTTP communication with Weatherstack, error mapping |

**Cross-cutting features:**

- **Caching**: In-memory TTL cache (configurable) per normalized city to reduce API calls
- **Rate limiting**: SlowAPI per-client IP on `/weather` (configurable requests/minute)
- **Retries**: Exponential backoff for transient failures (timeouts, 5xx, network errors)

---

## 3. Project Structure

```
weather-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, lifespan, exception handlers
│   ├── config.py            # Pydantic Settings (env vars)
│   ├── limiter.py            # SlowAPI rate limiter config
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py         # GET /weather endpoint
│   ├── clients/
│   │   ├── __init__.py
│   │   └── weatherstack.py   # HTTP client for Weatherstack
│   ├── services/
│   │   ├── __init__.py
│   │   └── weather.py        # Caching, mapping, orchestration
│   └── schemas/
│       ├── __init__.py
│       └── weather.py        # Pydantic request/response models
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Pytest fixtures
│   └── test_weather.py       # Unit tests
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 4. Requirements

- **Python** 3.12+ (tested with 3.12, 3.14)
- **Docker** (optional, for containerized deployment)

---

## 5. Environment Variables

Configuration is done via environment variables. Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEATHERSTACK_API_KEY` | Yes | — | API key from [weatherstack.com](https://weatherstack.com) |
| `WEATHERSTACK_BASE_URL` | No | `https://api.weatherstack.com` | Weatherstack API base URL |
| `WEATHERSTACK_REQUEST_TIMEOUT` | No | `10` | HTTP timeout in seconds |
| `CACHE_TTL_SECONDS` | No | `600` | Cache TTL in seconds (0 = disable) |
| `RATE_LIMIT_PER_MINUTE` | No | `2` | Max requests per minute per client IP |
| `RETRY_MAX_RETRIES` | No | `3` | Number of retries for transient failures |
| `RETRY_INITIAL_DELAY` | No | `0.5` | Initial backoff delay in seconds |

> `.env` is gitignored. Never commit API keys.

---

## 6. Running the Application Locally

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment (set WEATHERSTACK_API_KEY in .env)
cp .env.example .env
# Edit .env and add your API key

# 4. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **API**: http://localhost:8000  
- **Interactive docs**: http://localhost:8000/docs  
- **Health check**: http://localhost:8000/health  

---

## 7. Running with Docker

```bash
# Build and run
docker-compose up --build

# Or run detached
docker-compose up -d --build
```

The service listens on port 8000. Environment variables are loaded from `.env`. A healthcheck runs every 30 seconds.

---

## 8. API Usage

### Get weather by city

```
GET /weather?city=<city_name>
```

| Parameter | Type | Validation | Description |
|-----------|------|------------|-------------|
| `city` | string | required, 2–50 chars | City name (e.g. London, New York) |

**Example request:**

```bash
curl "http://localhost:8000/weather?city=London"
```

**Example response (200 OK):**

```json
{
  "location": "London",
  "country": "United Kingdom",
  "temperature": 12,
  "description": "Partly cloudy",
  "humidity": 72,
  "wind_speed": 15,
  "observation_time": "2025-03-13 14:00"
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 422 | Invalid or missing `city` (validation error) |
| 429 | Rate limit exceeded |
| 404 | City not found |
| 502 | Weather service unavailable (upstream error) |
| 503 | Weather service rate limit exceeded |

---

## 9. Running Tests

```bash
# Set API key for config validation
WEATHERSTACK_API_KEY=test pytest tests/ -v

# With coverage (if pytest-cov installed)
WEATHERSTACK_API_KEY=test pytest tests/ -v --cov=app
```

Tests mock the Weatherstack client and cover success, validation, errors, and caching behavior.

---

## 10. Assumptions & Trade-offs

| Assumption / Trade-off | Rationale |
|------------------------|------------|
| **In-memory cache** | Keeps the solution self-contained with no external dependencies. Suitable for single-instance deployment. Trade-off: cache is not shared across replicas and is lost on restart. |
| **IP-based rate limiting** | Simple and effective for protecting the upstream API. Assumes clients sit behind stable IPs; rate limits do not follow clients behind shared NATs. |
| **Environment-based configuration** | Pydantic Settings with `.env` provides a familiar, twelve-factor approach. Production deployments would typically use a secrets manager. |
| **No authentication** | Not required by the task; the API is designed to be placed behind an API gateway or proxy that adds auth if needed. |
| **Single upstream provider** | Weatherstack is the only weather provider. Adding another would require an abstraction layer (strategy pattern or adapter) for swappable backends. |

---

## 11. Production Improvements

If extending this API for production use, the following improvements would be considered:

- **Distributed caching**: Replace in-memory cache with Redis (or similar) for cache sharing across instances and persistence across restarts.
- **Observability**: Add structured logging, metrics (e.g. Prometheus), and distributed tracing (OpenTelemetry) for debugging and SLA monitoring.
- **Resilience**: Implement a circuit breaker for the Weatherstack client to fail fast when the upstream is degraded.
- **Authentication & authorization**: Add API key or JWT validation, either in-app or at the edge (API gateway).
- **Request validation**: Consider geocoding city names to a canonical form to reduce cache fragmentation (e.g. "London" vs "london").
