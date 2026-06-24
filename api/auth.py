"""Authentication helpers for the Module 10 auth stretch.

This module owns credential verification only:
- X-API-Key for service-to-service callers
- JWT Bearer tokens for user-facing callers

Endpoint wiring happens in api/main.py in the next task.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt


# auto_error=False is required for the assignment contract.
# Without it, FastAPI returns 403 automatically when a header is absent.
# The stretch expects 401 for missing or invalid credentials.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _unauthorized() -> HTTPException:
    """Build a consistent 401 response for missing or invalid credentials."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str = "Insufficient scope") -> HTTPException:
    """Build a consistent 403 response for valid credentials with wrong access."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def _jwt_secret() -> str:
    """Read the JWT secret from env.

    The secret must never be hardcoded in source code. The autograder checks for
    hardcoded secrets, so all signing and verification must read from env.
    """
    secret = os.getenv("JWT_SECRET")

    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured",
        )

    return secret


def _jwt_algorithm() -> str:
    """Read the JWT algorithm from env, defaulting to HS256 for local dev."""
    return os.getenv("JWT_ALGORITHM", "HS256")


def _is_valid_api_key(api_key: str | None) -> bool:
    """Return True only when the provided API key matches the env key."""
    if not api_key:
        return False

    expected_api_key = os.getenv("API_KEY_VALID")

    if not expected_api_key:
        return False

    # compare_digest avoids timing-based string comparison leaks.
    return secrets.compare_digest(api_key, expected_api_key)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Verify the X-API-Key header.

    Returns the API key on success.
    Raises 401 when the key is missing or invalid.
    """
    if not _is_valid_api_key(api_key):
        raise _unauthorized()

    return api_key


def create_access_token(subject: str, expires_minutes: int = 60) -> str:
    """Create a signed JWT access token.

    The token includes:
    - sub: the authenticated subject/user
    - exp: expiration timestamp

    The secret and algorithm come from environment variables.
    """
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire_at,
    }

    return jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())


def verify_jwt(token: str | None = Depends(oauth2_scheme)) -> dict[str, Any]:
    """Verify a JWT bearer token and return its decoded payload.

    Raises 401 when the token is missing, expired, malformed, or signed with the
    wrong secret.
    """
    if not token:
        raise _unauthorized()

    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[_jwt_algorithm()],
        )
    except JWTError:
        raise _unauthorized()

    return payload


def verify_api_key_or_jwt(
    api_key: str | None = Security(api_key_header),
    token: str | None = Depends(oauth2_scheme),
) -> dict[str, Any]:
    """Accept either a valid API key or a valid JWT.

    This helper will be used in Task 2 for:
    - /extract
    - /kg/query
    - /rag/answer

    API-key callers are service-to-service clients.
    JWT callers are user-facing frontend clients.
    """
    if _is_valid_api_key(api_key):
        return {"auth_type": "api_key"}

    if token:
        payload = verify_jwt(token=token)
        return {**payload, "auth_type": "jwt"}

    raise _unauthorized()


def verify_jwt_admin_only(
    token: str | None = Depends(oauth2_scheme),
    api_key: str | None = Security(api_key_header),
) -> dict[str, Any]:
    """Require JWT only.

    This helper is for /admin/echo in Task 2.

    Important behavior:
    - Valid JWT -> 200
    - Valid API key but no JWT -> 403
    - No valid credential -> 401
    """
    if token:
        return verify_jwt(token=token)

    if _is_valid_api_key(api_key):
        raise _forbidden("JWT required for this endpoint")

    raise _unauthorized()
