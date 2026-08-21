from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import ApplicationError


def register_application_error_handlers(app: FastAPI) -> None:
    """Map typed application failures to one stable JSON error envelope."""

    @app.exception_handler(ApplicationError)
    async def application_error_handler(_request: Request, error: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=error.http_status,
            content={
                "detail": str(error),
                "error": {"code": error.code, "message": str(error), "context": error.context},
            },
        )
