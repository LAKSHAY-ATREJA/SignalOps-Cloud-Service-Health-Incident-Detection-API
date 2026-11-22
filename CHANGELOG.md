# Changelog

## 2026-11-23 — Correlated database failure contract

- Added a centralized 503 problem response for SQLAlchemy failures.
- Added a bounded retry hint and request-correlated structured logging.
- Added regression coverage proving driver details are not exposed.

## 2026-11-22 — Reasoned incident resolution

- Persisted a bounded operator reason with each incident resolution.
- Made identical resolution retries idempotent and rejected conflicting reasons.
- Added a forward/backward Alembic migration and concurrent PostgreSQL coverage.

## 2026-11-22 — Bounded incident queries

- Added newest-first keyset pagination to incident listing using `before_id`.
- Defaulted responses to 50 rows and enforced a 100-row maximum.
- Added API tests for page boundaries, ordering and invalid limits.

## 2026-11-22 — Auditable incident resolution

- Added persisted incident resolution timestamps through an additive Alembic migration.
- Made resolution idempotent and serialized concurrent updates with a database row lock.
- Added local replay coverage and an eight-request PostgreSQL concurrency test.

## 2026-11-22 — Correlated problem responses

- Added consistent `application/problem+json` responses for HTTP and validation errors.
- Correlated every error body and response header with the same validated request ID.
- Added sanitized validation issue metadata without echoing submitted values.
- Added contract tests for validation, authorization misconfiguration and missing resources.

## 2026-11-22 — Fail-closed API authorization

- Added optional API-key authorization for API and metrics routes.
- Store only SHA-256 key digests in configuration and compare in constant time.
- Return 503 for required-but-invalid authentication configuration.
- Added authorization, invalid-key and misconfiguration integration tests.

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

