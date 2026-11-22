import hashlib

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_session
from app.main import app


@pytest_asyncio.fixture
async def client(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()


async def _create_service(client):
    response = await client.post(
        "/services", json={"name": "checkout-api", "owner": "Platform Team"}
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_incident(client, service_id, metric_name, key_prefix):
    for index, value in enumerate([99.0, 100.0, 101.0, 99.0, 100.0]):
        response = await client.post(
            f"/services/{service_id}/metrics",
            json={"metric_name": metric_name, "value": value},
            headers={"Idempotency-Key": f"{key_prefix}-baseline-{index:04d}"},
        )
        assert response.status_code == 201
    response = await client.post(
        f"/services/{service_id}/metrics",
        json={"metric_name": metric_name, "value": 140.0},
        headers={"Idempotency-Key": f"{key_prefix}-anomaly-0001"},
    )
    assert response.status_code == 201


@pytest_asyncio.fixture
async def service_id(client):
    return await _create_service(client)


async def test_metric_replay_is_idempotent(client, service_id):
    payload = {"metric_name": "latency_ms", "value": 101.5}
    headers = {"Idempotency-Key": "producer-event-0001"}

    first = await client.post(
        f"/services/{service_id}/metrics", json=payload, headers=headers
    )
    replay = await client.post(
        f"/services/{service_id}/metrics", json=payload, headers=headers
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json() == first.json()


async def test_reused_key_with_changed_payload_is_rejected(client, service_id):
    headers = {"Idempotency-Key": "producer-event-0002"}
    first = await client.post(
        f"/services/{service_id}/metrics",
        json={"metric_name": "latency_ms", "value": 100.0},
        headers=headers,
    )
    conflict = await client.post(
        f"/services/{service_id}/metrics",
        json={"metric_name": "latency_ms", "value": 180.0},
        headers=headers,
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert "different metric payload" in conflict.json()["detail"]


async def test_metric_payload_rejects_unsafe_name(client, service_id):
    response = await client.post(
        f"/services/{service_id}/metrics",
        json={"metric_name": "latency ms!", "value": 100.0},
        headers={"Idempotency-Key": "invalid-event-0001"},
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["detail"] == "Request validation failed"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert response.json()["errors"][0]["code"] == "string_pattern_mismatch"


async def test_anomalous_replay_creates_exactly_one_incident(client, service_id):
    for index, value in enumerate([99.0, 100.0, 101.0, 99.0, 100.0]):
        response = await client.post(
            f"/services/{service_id}/metrics",
            json={"metric_name": "latency_ms", "value": value},
            headers={"Idempotency-Key": f"baseline-event-{index:04d}"},
        )
        assert response.status_code == 201

    payload = {"metric_name": "latency_ms", "value": 140.0}
    headers = {"Idempotency-Key": "anomaly-event-0001"}
    created = await client.post(
        f"/services/{service_id}/metrics", json=payload, headers=headers
    )
    replay = await client.post(
        f"/services/{service_id}/metrics", json=payload, headers=headers
    )
    incidents = await client.get(f"/incidents?service_id={service_id}")

    assert created.status_code == 201
    assert replay.status_code == 200
    assert incidents.status_code == 200
    assert len(incidents.json()) == 1
    assert incidents.json()[0]["observed_value"] == 140.0


async def test_incident_listing_uses_bounded_keyset_pagination(client, service_id):
    await _create_incident(client, service_id, "latency_ms", "page-latency")
    await _create_incident(client, service_id, "error_rate", "page-errors")

    first_page = await client.get("/incidents?limit=1")
    first_id = first_page.json()[0]["id"]
    second_page = await client.get(f"/incidents?limit=1&before_id={first_id}")
    invalid_limit = await client.get("/incidents?limit=101")

    assert first_page.status_code == second_page.status_code == 200
    assert len(first_page.json()) == len(second_page.json()) == 1
    assert second_page.json()[0]["id"] < first_id
    assert invalid_limit.status_code == 422
    assert invalid_limit.headers["content-type"].startswith(
        "application/problem+json"
    )


async def test_operational_endpoints_expose_readiness_metrics_and_request_ids(client):
    live = await client.get("/health/live", headers={"X-Request-ID": "probe-123"})
    ready = await client.get("/health/ready")
    metrics = await client.get("/metrics")

    assert live.status_code == 200
    assert live.headers["X-Request-ID"] == "probe-123"
    assert ready.json() == {"status": "ready"}
    assert "signalops_http_requests_total" in metrics.text
    assert 'route="/health/live"' in metrics.text


async def test_readiness_fails_closed_when_database_is_unavailable(client, monkeypatch):
    async def unavailable():
        raise OperationalError("SELECT 1", {}, RuntimeError("database offline"))

    monkeypatch.setattr("app.main.check_database", unavailable)
    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.parametrize("request_id", ["contains spaces", "x" * 65])
async def test_invalid_request_id_is_replaced(client, request_id):
    response = await client.get("/health/live", headers={"X-Request-ID": request_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != request_id


async def test_api_key_authentication_fails_closed(client, monkeypatch):
    digest = hashlib.sha256(b"portfolio-test-key").hexdigest()
    monkeypatch.setattr("app.auth.settings.auth_required", True)
    monkeypatch.setattr("app.auth.settings.api_key_sha256", digest)

    missing = await client.get("/services")
    invalid = await client.get("/services", headers={"X-API-Key": "wrong"})
    allowed = await client.get(
        "/services", headers={"X-API-Key": "portfolio-test-key"}
    )
    live = await client.get("/health/live")

    assert missing.status_code == 401
    assert missing.headers["WWW-Authenticate"] == "ApiKey"
    assert invalid.status_code == 401
    assert allowed.status_code == 200
    assert live.status_code == 200


async def test_required_auth_without_valid_hashes_returns_503(client, monkeypatch):
    monkeypatch.setattr("app.auth.settings.auth_required", True)
    monkeypatch.setattr("app.auth.settings.api_key_sha256", "not-a-digest")
    response = await client.get("/services", headers={"X-API-Key": "any-key"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Authentication is misconfigured"
    assert response.json()["status"] == 503
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


async def test_not_found_problem_is_correlated_without_internal_details(client):
    response = await client.patch(
        "/incidents/999/resolve",
        json={"reason": "Investigated and found no matching incident"},
        headers={"X-Request-ID": "incident-request-123"},
    )
    body = response.json()
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert body == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "Incident not found",
        "instance": "/incidents/999/resolve",
        "request_id": "incident-request-123",
    }


async def test_incident_resolution_is_idempotent_and_preserves_audit_time(
    client, service_id
):
    for index, value in enumerate([99.0, 100.0, 101.0, 99.0, 100.0]):
        await client.post(
            f"/services/{service_id}/metrics",
            json={"metric_name": "latency_ms", "value": value},
            headers={"Idempotency-Key": f"resolve-baseline-{index:04d}"},
        )
    await client.post(
        f"/services/{service_id}/metrics",
        json={"metric_name": "latency_ms", "value": 140.0},
        headers={"Idempotency-Key": "resolve-anomaly-0001"},
    )
    incident_id = (await client.get("/incidents")).json()[0]["id"]

    blank = await client.patch(
        f"/incidents/{incident_id}/resolve", json={"reason": "   "}
    )
    payload = {"reason": "Database failover completed and latency recovered"}
    first = await client.patch(f"/incidents/{incident_id}/resolve", json=payload)
    replay = await client.patch(f"/incidents/{incident_id}/resolve", json=payload)
    conflict = await client.patch(
        f"/incidents/{incident_id}/resolve",
        json={"reason": "A different operator explanation"},
    )

    assert blank.status_code == 422
    assert first.status_code == replay.status_code == 200
    assert first.json()["status"] == "resolved"
    assert first.json()["resolved_at"] is not None
    assert first.json()["resolution_reason"] == payload["reason"]
    assert replay.json()["resolved_at"] == first.json()["resolved_at"]
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == (
        "Incident was already resolved with a different reason"
    )
