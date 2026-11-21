import hashlib
import re
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from .config import settings

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def configured_key_hashes() -> tuple[str, ...]:
    hashes = tuple(
        item.strip().lower()
        for item in settings.api_key_sha256.split(",")
        if item.strip()
    )
    if any(not SHA256_PATTERN.fullmatch(item) for item in hashes):
        raise RuntimeError("SIGNALOPS_API_KEY_SHA256 contains an invalid SHA-256 digest")
    return hashes


async def require_api_key(
    api_key: Annotated[str | None, Depends(API_KEY_HEADER)],
) -> None:
    if not settings.auth_required:
        return
    try:
        configured = configured_key_hashes()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Authentication is misconfigured") from exc
    if not configured:
        raise HTTPException(status_code=503, detail="Authentication is misconfigured")
    candidate = hashlib.sha256((api_key or "").encode()).hexdigest()
    if not any(secrets.compare_digest(candidate, expected) for expected in configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
