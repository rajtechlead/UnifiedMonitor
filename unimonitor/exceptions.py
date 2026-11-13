"""Custom exception hierarchy for UniMonitor."""

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse


class UniMonitorError(Exception):
    """Base exception for all UniMonitor errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: str | None = None) -> None:
        self.message = message
        self.detail = detail or message
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": self.error_code,
            "message": self.message,
            "detail": self.detail,
        }


# ── Authentication & Authorisation ──────────────────────────


class AuthenticationError(UniMonitorError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTHENTICATION_FAILED"


class AuthorisationError(UniMonitorError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "FORBIDDEN"


class TokenExpiredError(AuthenticationError):
    error_code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    error_code = "INVALID_TOKEN"


# ── Resource errors ──────────────────────────────────────────


class NotFoundError(UniMonitorError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"


class ConflictError(UniMonitorError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"


class ValidationError(UniMonitorError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "VALIDATION_ERROR"


# ── Graph / External API errors ──────────────────────────────


class GraphAPIError(UniMonitorError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "GRAPH_API_ERROR"


class GraphPermissionError(GraphAPIError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "GRAPH_PERMISSION_DENIED"


class GraphRateLimitError(GraphAPIError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "GRAPH_RATE_LIMIT"


class GraphTimeoutError(GraphAPIError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "GRAPH_TIMEOUT"


# ── Assessment / GRC errors ──────────────────────────────────


class AssessmentError(UniMonitorError):
    error_code = "ASSESSMENT_ERROR"


class AssessmentAlreadyRunningError(AssessmentError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "ASSESSMENT_ALREADY_RUNNING"


class FrameworkNotFoundError(NotFoundError):
    error_code = "FRAMEWORK_NOT_FOUND"


# ── Database errors ──────────────────────────────────────────


class DatabaseError(UniMonitorError):
    error_code = "DATABASE_ERROR"


# ── FastAPI exception handlers ───────────────────────────────


async def unimonitor_exception_handler(
    request: Request,
    exc: UniMonitorError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "detail": str(exc) if __debug__ else "Contact support.",
        },
    )
