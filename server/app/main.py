"""FastAPI application: routers, CORS and the error handlers that give every error one shape."""

import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, pay, shift_templates, time_entries
from app.config import get_settings
from app.core.errors import DomainError, ErrorCode, Unauthorized, error_body

logger = logging.getLogger("app")

INTERNAL_ERROR_MESSAGE = "Something went wrong on our side."

health_router = APIRouter(prefix="/api", tags=["health"])


@health_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    application = FastAPI(title="Shibutzim API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(application)
    application.include_router(health_router)
    application.include_router(auth.router)
    application.include_router(time_entries.router)
    application.include_router(pay.router)
    application.include_router(shift_templates.router)
    return application


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(DomainError)
    async def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(error, Unauthorized) else None
        return JSONResponse(status_code=error.status_code, content=error.to_body(), headers=headers)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        details = {"errors": jsonable_encoder(error.errors())}
        body = error_body(ErrorCode.validation_error, "Request validation failed.", details)
        return JSONResponse(status_code=422, content=body)

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        body = error_body(ErrorCode.internal_error, INTERNAL_ERROR_MESSAGE)
        return JSONResponse(status_code=500, content=body)


app = create_app()
