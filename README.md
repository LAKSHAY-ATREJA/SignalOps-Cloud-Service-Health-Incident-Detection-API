# SignalOps

[![CI](https://github.com/LAKSHAY-ATREJA/SignalOps-Cloud-Service-Health-Incident-Detection-API/actions/workflows/ci.yml/badge.svg)](https://github.com/LAKSHAY-ATREJA/SignalOps-Cloud-Service-Health-Incident-Detection-API/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**SignalOps** is a production-oriented backend service for monitoring cloud services, ingesting operational telemetry, and automatically creating incidents when new measurements deviate sharply from recent behaviour.

The project is intentionally compact enough to understand quickly while using patterns found in real backend systems: asynchronous API endpoints, typed validation, database persistence, containerised infrastructure, automated tests, linting, and continuous integration.

## What it does

SignalOps provides a simple monitoring pipeline:

1. Register a service that should be monitored.
2. Ingest metrics such as latency, CPU usage, memory usage, or error rate.
3. Build a rolling baseline from recent observations.
4. Compare incoming values against that baseline using a z-score.
5. Automatically create a severity-classified incident when an anomaly is detected.
6. Query and resolve incidents through the REST API.

## Features

- Asynchronous REST API built with FastAPI
- Service registration and discovery
- Generic telemetry ingestion for arbitrary metric names
- Rolling 20-sample baselines per service and metric
- Configurable z-score anomaly detection
- Automatic `medium`, `high`, and `critical` severity classification
- Incident listing, filtering, and resolution
- SQLAlchemy 2.x asynchronous persistence
- PostgreSQL support for containerised deployments
- SQLite support for zero-configuration local development
- Docker and Docker Compose setup
- Interactive OpenAPI / Swagger documentation
- Pytest coverage for the core detector
- Ruff linting
- GitHub Actions CI

## Architecture

```text
                 +----------------------+
                 | Metric Producer      |
                 | app / service / job  |
                 +----------+-----------+
                            |
                            | HTTP / JSON
                            v
                 +----------------------+
                 | FastAPI REST API     |
                 +----------+-----------+
                            |
              +-------------+-------------+
              |                           |
              v                           v
   +----------------------+     +----------------------+
   | Pydantic Validation  |     | Anomaly Detector     |
   +----------------------+     | rolling baseline     |
                                | z-score evaluation   |
                                +----------+-----------+
                                           |
                                           v
                                +----------------------+
                                | Incident Creation    |
                                +----------+-----------+
                                           |
                                           v
                                +----------------------+
                                | SQLAlchemy Async ORM |
                                +----------+-----------+
                                           |
                                           v
                                +----------------------+
                                | PostgreSQL / SQLite  |
                                +----------------------+
```

## Tech stack

| Area | Technology |
|---|---|
| API | FastAPI |
| Language | Python 3.11+ |
| Validation | Pydantic |
| ORM | SQLAlchemy 2.x async |
| Production database | PostgreSQL + asyncpg |
| Local database | SQLite + aiosqlite |
| Containers | Docker, Docker Compose |
| Testing | Pytest, pytest-asyncio |
| Linting | Ruff |
| CI | GitHub Actions |

## Project structure

```text
signalops/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── workflows/
│       └── ci.yml
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── detector.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── tests/
│   └── test_detector.py
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── Dockerfile
├── LICENSE
├── README.md
├── docker-compose.yml
└── pyproject.toml
```

## Quick start

### Option 1 — Local Python

Clone the repository and enter the project directory:

```bash
git clone https://github.com/LAKSHAY-ATREJA/SignalOps-Cloud-Service-Health-Incident-Detection-API.git
cd signalops
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it.

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -e ".[dev]"
```

Start the API:

```bash
uvicorn app.main:app --reload
```

The API is available at:

```text
http://localhost:8000
```

Interactive Swagger documentation:

```text
http://localhost:8000/docs
```

### Option 2 — Docker + PostgreSQL

Start the complete stack:

```bash
docker compose up --build
```

SignalOps will be available at:

```text
http://localhost:8000
```

Stop the stack with:

```bash
docker compose down
```

## Configuration

SignalOps uses environment-based configuration. Copy the example file if you want to customise local settings:

```bash
cp .env.example .env
```

Default values allow the application to run locally without additional configuration.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Health/liveness check |
| `POST` | `/services` | Register a monitored service |
| `GET` | `/services` | List registered services |
| `POST` | `/services/{service_id}/metrics` | Ingest a metric observation |
| `GET` | `/incidents` | List incidents, optionally filtered by service |
| `PATCH` | `/incidents/{incident_id}/resolve` | Resolve an incident |

## Example workflow

### 1. Register a service

```bash
curl -X POST http://localhost:8000/services \
  -H "Content-Type: application/json" \
  -d '{"name":"checkout-api","owner":"Platform Team"}'
```

### 2. Build a baseline

```bash
for value in 98 101 100 99 102 100 101 99; do
  curl -X POST http://localhost:8000/services/1/metrics \
    -H "Content-Type: application/json" \
    -d "{\"metric_name\":\"latency_ms\",\"value\":$value}"
done
```

### 3. Send an abnormal value

```bash
curl -X POST http://localhost:8000/services/1/metrics \
  -H "Content-Type: application/json" \
  -d '{"metric_name":"latency_ms","value":180}'
```

### 4. Inspect incidents

```bash
curl http://localhost:8000/incidents
```

### 5. Resolve an incident

```bash
curl -X PATCH http://localhost:8000/incidents/1/resolve
```

## Detection model

For each `(service, metric)` pair, SignalOps takes the most recent observations as a baseline. Once the minimum sample count has been reached, it calculates:

```text
z = |observed_value - baseline_mean| / baseline_standard_deviation
```

If the z-score crosses the configured incident threshold, SignalOps persists a new incident. Higher z-scores result in higher incident severity.

The detector is intentionally transparent and deterministic. It is easy to test, reason about, and replace later with more advanced methods such as EWMA, Isolation Forest, or time-series models without changing the API contract.

## Quality checks

Run tests:

```bash
pytest -q
```

Run linting:

```bash
ruff check .
```

Both checks also run automatically in GitHub Actions on pushes and pull requests.

## Roadmap

Planned directions include:

- Prometheus-compatible metrics endpoint
- Webhook and Slack-style alert delivery
- API-key authentication and rate limiting
- Redis-backed ingestion queue
- Grafana dashboard integration
- Terraform deployment to AWS ECS/Fargate
- More advanced time-series anomaly detection

## Release

The first stable release is **v1.0.0**, covering the core service-registration, telemetry-ingestion, anomaly-detection, incident-management, containerisation, testing, and CI workflow.

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Author

**Lakshay Atreja**

GitHub: [@LAKSHAY-ATREJA](https://github.com/LAKSHAY-ATREJA)

## License

Released under the [MIT License](LICENSE).
