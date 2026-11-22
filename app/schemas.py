from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    owner: str = Field(min_length=2, max_length=120)


class ServiceOut(ServiceCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MetricCreate(BaseModel):
    metric_name: str = Field(
        min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    value: float = Field(allow_inf_nan=False)


class MetricOut(BaseModel):
    id: int
    service_id: int
    metric_name: str
    value: float
    idempotency_key: str
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentOut(BaseModel):
    id: int
    service_id: int
    metric_id: int
    metric_name: str
    observed_value: float
    baseline_mean: float
    z_score: float
    severity: str
    status: str
    created_at: datetime
    resolved_at: datetime | None
    model_config = ConfigDict(from_attributes=True)

