"""Unified error envelope:

{"error": {"code": "TODO_NOT_FOUND", "message": "...", "details": {}, "request_id": "req_..."}}
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

CODE_BY_STATUS = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
}


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:8]}"


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def not_found(code: str = "NOT_FOUND", message: str = "resource not found") -> APIError:
    return APIError(404, code, message)


def invalid(code: str = "VALIDATION_ERROR", message: str = "invalid", details=None) -> APIError:
    return APIError(422, code, message, details)


def envelope(code: str, message: str, details: Any = None, request_id: str | None = None) -> dict:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    body["error"]["request_id"] = request_id
    return body


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(request: Request, exc: APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(
                exc.code, exc.message, exc.details, getattr(request.state, "request_id", None)
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = CODE_BY_STATUS.get(exc.status_code, "ERROR")
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(code, message, None, getattr(request.state, "request_id", None)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            field = ".".join(
                str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")
            )
            details.append(
                {
                    "field": field,
                    "message": err.get("msg", "invalid value"),
                    "type": err.get("type"),
                }
            )
        return JSONResponse(
            status_code=422,
            content=envelope(
                "VALIDATION_ERROR",
                "request validation failed",
                details,
                getattr(request.state, "request_id", None),
            ),
        )
