# Changelog

## 2026-11-21 — PostgreSQL concurrency verification

- Added a real PostgreSQL 16 service to CI and run Alembic against it.
- Added an eight-request concurrent replay test proving one create and seven identical replays.
- Kept the integration test explicitly gated by a dedicated test database URL.

## 2026-11-21 — Operability and failure visibility

- Added separate liveness and database-backed readiness probes.
- Added bounded-cardinality Prometheus metrics for HTTP traffic, ingestion outcomes and incidents.
- Added validated correlation IDs and structured request logs.
- Added failure-path tests for database unavailability and invalid request identifiers.

All notable changes to SignalOps are documented in this file.

The project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Producer-scoped idempotency keys for metric ingestion
- Database uniqueness enforcement for concurrent request retries
- Alembic migration history and migration validation in CI
- End-to-end API tests for replay, conflict and incident deduplication

### Changed

- Container startup now applies pending migrations before serving traffic

## [1.0.0] - 2026-09-29

### Added

- FastAPI-based asynchronous REST API
- Service registration and listing endpoints
- Generic service-metric ingestion
- Rolling metric baselines
- Configurable z-score anomaly detection
- Automatic incident generation
- Severity classification for detected anomalies
- Incident filtering and resolution
- SQLAlchemy 2.x asynchronous persistence
- PostgreSQL production configuration
- SQLite local-development support
- Dockerfile and Docker Compose setup
- Environment-based configuration
- Pytest coverage for core anomaly-detection behaviour
- Ruff linting configuration
- GitHub Actions CI workflow
- Interactive OpenAPI / Swagger documentation
- Project documentation and MIT licence

