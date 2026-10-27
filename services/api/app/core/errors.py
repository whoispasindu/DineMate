import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas import ErrorResponse

HTTP_CODES = {
    400: "validation_error",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def not_found(entity: str, entity_id: str) -> ApiError:
    return ApiError(404, "not_found", f"{entity} not found.", {f"{entity.lower()}_id": entity_id})


NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse}}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


def _error(request: Request, status: int, code: str, message: str, details: dict[str, Any] | None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details}, "request_id": _request_id(request)}
    return JSONResponse(status_code=status, content=body)


def install_error_handling(app: FastAPI) -> None:
    @app.middleware("http")
    async def assign_request_id(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request.state.request_id = f"req_{uuid.uuid4().hex[:8]}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _error(request, exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_CODES.get(exc.status_code, "error")
        return _error(request, exc.status_code, code, str(exc.detail), None)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = {"errors": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]}
        return _error(request, 422, "validation_error", "Request is not valid.", details)
