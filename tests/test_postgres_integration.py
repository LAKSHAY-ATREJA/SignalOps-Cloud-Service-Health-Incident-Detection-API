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
