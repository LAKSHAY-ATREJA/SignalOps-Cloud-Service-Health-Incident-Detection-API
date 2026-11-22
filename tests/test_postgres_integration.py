import asyncio
import os

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app

DATABASE_URL = os.getenv("SIGNALOPS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="SIGNALOPS_TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


@pytest_asyncio.fixture
async def postgres_client():
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE incidents, metrics, services RESTART IDENTITY CASCADE")
        )

    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


async def test_postgres_serializes_concurrent_idempotent_ingestion(postgres_client):
    created = await postgres_client.post(
        "/services", json={"name": "payments-api", "owner": "Platform Team"}
    )
    assert created.status_code == 201
    service_id = created.json()["id"]
    payload = {"metric_name": "latency_ms", "value": 83.5}
    headers = {"Idempotency-Key": "concurrent-producer-event-0001"}

    responses = await asyncio.gather(
        *[
            postgres_client.post(
                f"/services/{service_id}/metrics", json=payload, headers=headers
            )
            for _ in range(8)
        ]
    )

    assert sorted(response.status_code for response in responses) == [200] * 7 + [201]
    assert len({response.json()["id"] for response in responses}) == 1


async def test_postgres_serializes_concurrent_incident_resolution(postgres_client):
    created = await postgres_client.post(
        "/services", json={"name": "resolution-api", "owner": "Platform Team"}
    )
    service_id = created.json()["id"]
    for index, value in enumerate([99.0, 100.0, 101.0, 99.0, 100.0]):
        await postgres_client.post(
            f"/services/{service_id}/metrics",
            json={"metric_name": "latency_ms", "value": value},
            headers={"Idempotency-Key": f"resolution-baseline-{index:04d}"},
        )
    await postgres_client.post(
        f"/services/{service_id}/metrics",
        json={"metric_name": "latency_ms", "value": 140.0},
        headers={"Idempotency-Key": "resolution-anomaly-0001"},
    )
    incident_id = (await postgres_client.get("/incidents")).json()[0]["id"]

    responses = await asyncio.gather(
        *[
            postgres_client.patch(
                f"/incidents/{incident_id}/resolve",
                json={"reason": "Automated failover restored database health"},
            )
            for _ in range(8)
        ]
    )

    assert {response.status_code for response in responses} == {200}
    assert {response.json()["status"] for response in responses} == {"resolved"}
    assert len({response.json()["resolved_at"] for response in responses}) == 1
    assert {response.json()["resolution_reason"] for response in responses} == {
        "Automated failover restored database health"
    }
    assert responses[0].json()["resolved_at"] is not None
