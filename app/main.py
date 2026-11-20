from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_session
from .detector import detect_anomaly, severity_for
from .models import Incident, Metric, Service
from .schemas import IncidentOut, MetricCreate, MetricOut, ServiceCreate, ServiceOut

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ServiceFilter = Annotated[int | None, Query()]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Stable producer event identifier; unique within a service.",
    ),
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="SignalOps API",
    version="1.0.0",
    description="Cloud service health monitoring with lightweight automated incident detection.",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
async def create_service(payload: ServiceCreate, session: SessionDep):
    existing = await session.scalar(select(Service).where(Service.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Service already exists")

    service = Service(**payload.model_dump())
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return service


@app.get("/services", response_model=list[ServiceOut])
async def list_services(session: SessionDep):
    result = await session.scalars(select(Service).order_by(Service.name))
    return list(result)


@app.post(
    "/services/{service_id}/metrics",
    response_model=MetricOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {"description": "Idempotent replay of an existing metric"},
        status.HTTP_409_CONFLICT: {
            "description": "Idempotency key was already used for a different payload"
        },
    },
)
async def ingest_metric(
    service_id: int,
    payload: MetricCreate,
    response: Response,
    idempotency_key: IdempotencyKey,
    session: SessionDep,
):
    service = await session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    existing = await session.scalar(
        select(Metric).where(
            Metric.service_id == service_id,
            Metric.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.metric_name != payload.metric_name or existing.value != payload.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used for a different metric payload",
            )
        response.status_code = status.HTTP_200_OK
        return existing

    history_result = await session.scalars(
        select(Metric.value)
        .where(Metric.service_id == service_id, Metric.metric_name == payload.metric_name)
        .order_by(Metric.recorded_at.desc())
        .limit(20)
    )
    history = list(history_result)

    metric = Metric(
        service_id=service_id,
        idempotency_key=idempotency_key,
        **payload.model_dump(),
    )
    session.add(metric)
    try:
        await session.flush()

        if len(history) >= settings.minimum_samples:
            anomalous, mean, z_score = detect_anomaly(
                history,
                payload.value,
                settings.incident_z_threshold,
            )
            if anomalous:
                session.add(
                    Incident(
                        service_id=service_id,
                        metric_id=metric.id,
                        metric_name=payload.metric_name,
                        observed_value=payload.value,
                        baseline_mean=mean,
                        z_score=z_score,
                        severity=severity_for(z_score),
                    )
                )
        await session.commit()
    except IntegrityError:
        # A concurrent request may win the unique-key race after the initial
        # lookup. Roll back the whole transaction (including any incident),
        # then return the committed winner only when its payload is identical.
        await session.rollback()
        existing = await session.scalar(
            select(Metric).where(
                Metric.service_id == service_id,
                Metric.idempotency_key == idempotency_key,
            )
        )
        if (
            existing is None
            or existing.metric_name != payload.metric_name
            or existing.value != payload.value
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key conflict",
            )
        response.status_code = status.HTTP_200_OK
        return existing
    await session.refresh(metric)
    return metric


@app.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(
    session: SessionDep,
    service_id: ServiceFilter = None,
):
    query = select(Incident).order_by(Incident.created_at.desc())
    if service_id is not None:
        query = query.where(Incident.service_id == service_id)
    result = await session.scalars(query)
    return list(result)


@app.patch("/incidents/{incident_id}/resolve", response_model=IncidentOut)
async def resolve_incident(incident_id: int, session: SessionDep):
    incident = await session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident.status = "resolved"
    await session.commit()
    await session.refresh(incident)
    return incident

