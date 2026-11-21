from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "signalops_http_requests_total",
    "HTTP requests handled by the API.",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "signalops_http_request_duration_seconds",
    "HTTP request latency by normalized route.",
    ("method", "route"),
)
INGESTION_OUTCOMES = Counter(
    "signalops_ingestion_outcomes_total",
    "Telemetry ingestion outcomes.",
    ("outcome",),
)
INCIDENTS_CREATED = Counter(
    "signalops_incidents_created_total",
    "Incidents created by severity.",
    ("severity",),
)
