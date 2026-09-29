from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import Base, engine, get_session
from .detector import detect_anomaly, severity_for
from .models import Incident, Metric, Service
from .schemas import IncidentOut, MetricCreate, MetricOut, ServiceCreate, ServiceOut


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
async def create_service(payload: ServiceCreate, session: AsyncSession = Depends(get_session)):
    existing = await session.scalar(select(Service).where(Service.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Service already exists")

    service = Service(**payload.model_dump())
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return service


@app.get("/services", response_model=list[ServiceOut])
async def list_services(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(Service).order_by(Service.name))
    return list(result)


@app.post("/services/{service_id}/metrics", response_model=MetricOut, status_code=201)
async def ingest_metric(
    service_id: int,
    payload: MetricCreate,
    session: AsyncSession = Depends(get_session),
):
    service = await session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    history_result = await session.scalars(
        select(Metric.value)
        .where(Metric.service_id == service_id, Metric.metric_name == payload.metric_name)
        .order_by(Metric.recorded_at.desc())
        .limit(20)
    )
    history = list(history_result)

    metric = Metric(service_id=service_id, **payload.model_dump())
    session.add(metric)

    if len(history) >= settings.minimum_samples:
        anomalous, mean, z_score = detect_anomaly(history, payload.value, settings.incident_z_threshold)
        if anomalous:
            session.add(
                Incident(
                    service_id=service_id,
                    metric_name=payload.metric_name,
                    observed_value=payload.value,
                    baseline_mean=mean,
                    z_score=z_score,
                    severity=severity_for(z_score),
                )
            )

    await session.commit()
    await session.refresh(metric)
    return metric


@app.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(
    service_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    query = select(Incident).order_by(Incident.created_at.desc())
    if service_id is not None:
        query = query.where(Incident.service_id == service_id)
    result = await session.scalars(query)
    return list(result)


@app.patch("/incidents/{incident_id}/resolve", response_model=IncidentOut)
async def resolve_incident(incident_id: int, session: AsyncSession = Depends(get_session)):
    incident = await session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident.status = "resolved"
    await session.commit()
    await session.refresh(incident)
    return incident
