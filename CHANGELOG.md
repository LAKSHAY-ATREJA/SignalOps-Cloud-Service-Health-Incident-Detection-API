# Changelog

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

