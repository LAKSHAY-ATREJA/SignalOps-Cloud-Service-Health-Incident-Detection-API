import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_api_key
from .config import settings
from .database import check_database, get_session
from .detector import detect_anomaly, severity_for
from .models import Incident, Metric, Service
from .observability import HTTP_DURATION, HTTP_REQUESTS, INCIDENTS_CREATED, INGESTION_OUTCOMES
from .schemas import (
    IncidentOut,
    IncidentResolution,
    MetricCreate,
    MetricOut,
    ServiceCreate,
    ServiceOut,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
Authenticated = Annotated[None, Depends(require_api_key)]
ServiceFilter = Annotated[int | None, Query()]
IncidentLimit = Annotated[int, Query(ge=1, le=100)]
IncidentCursor = Annotated[int | None, Query(ge=1)]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Stable producer event identifier; unique within a service.",
    ),
]
LOGGER = logging.getLogger("signalops.http")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="SignalOps API",
    version="1.0.0",
    description="Cloud service health monitoring with lightweight automated incident detection.",
    lifespan=lifespan,
)


@app.middleware("http")
async def observe_request(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_id if REQUEST_ID_PATTERN.fullmatch(supplied_id) else str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    route = getattr(request.scope.get("route"), "path", "unmatched")
    HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
    HTTP_DURATION.labels(request.method, route).observe(elapsed)
    response.headers["X-Request-ID"] = request_id
    LOGGER.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status": response.status_code,
                "duration_ms": round(elapsed * 1000, 3),
            }
        )
    )
    return response


def problem_response(
    request: Request,
    status_code: int,
    detail: str,
    *,
    errors: list[dict] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": "about:blank",
        "title": HTTPStatus(status_code).phrase,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
        "request_id": getattr(request.state, "request_id", None),
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=headers,
        media_type="application/problem+json",
    )


@app.exception_handler(HTTPException)
async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return problem_response(request, exc.status_code, detail, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "location": [str(part) for part in error["loc"]],
            "message": error["msg"],
            "code": error["type"],
        }
        for error in exc.errors()
    ]
    return problem_response(
        request,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Request validation failed",
        errors=errors,
    )


@app.get("/health", include_in_schema=False)
@app.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness() -> dict[str, str]:
    try:
        await check_database()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
async def metrics(_: Authenticated) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
async def create_service(payload: ServiceCreate, session: SessionDep, _: Authenticated):
    existing = await session.scalar(select(Service).where(Service.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Service already exists")

    service = Service(**payload.model_dump())
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return service


@app.get("/services", response_model=list[ServiceOut])
async def list_services(session: SessionDep, _: Authenticated):
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
    _: Authenticated,
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
            INGESTION_OUTCOMES.labels("conflict").inc()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used for a different metric payload",
            )
        INGESTION_OUTCOMES.labels("replay").inc()
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
                severity = severity_for(z_score)
                session.add(
                    Incident(
                        service_id=service_id,
                        metric_id=metric.id,
                        metric_name=payload.metric_name,
                        observed_value=payload.value,
                        baseline_mean=mean,
                        z_score=z_score,
                        severity=severity,
                    )
                )
                INCIDENTS_CREATED.labels(severity).inc()
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
            INGESTION_OUTCOMES.labels("conflict").inc()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key conflict",
            )
        INGESTION_OUTCOMES.labels("replay").inc()
        response.status_code = status.HTTP_200_OK
        return existing
    INGESTION_OUTCOMES.labels("created").inc()
    await session.refresh(metric)
    return metric


@app.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(
    session: SessionDep,
    _: Authenticated,
    service_id: ServiceFilter = None,
    limit: IncidentLimit = 50,
    before_id: IncidentCursor = None,
):
    query = select(Incident).order_by(Incident.id.desc()).limit(limit)
    if service_id is not None:
        query = query.where(Incident.service_id == service_id)
    if before_id is not None:
        query = query.where(Incident.id < before_id)
    result = await session.scalars(query)
    return list(result)


@app.patch("/incidents/{incident_id}/resolve", response_model=IncidentOut)
async def resolve_incident(
    incident_id: int,
    payload: IncidentResolution,
    session: SessionDep,
    _: Authenticated,
):
    incident = await session.scalar(
        select(Incident).where(Incident.id == incident_id).with_for_update()
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status != "resolved":
        incident.status = "resolved"
        incident.resolved_at = func.now()
        incident.resolution_reason = payload.reason
        await session.commit()
        await session.refresh(incident)
    elif incident.resolution_reason != payload.reason:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Incident was already resolved with a different reason",
        )
    return incident

