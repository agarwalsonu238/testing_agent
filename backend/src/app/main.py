from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import require_api_key
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import (
    BlockedError,
    ConflictError,
    DomainError,
    NotFoundError,
    PreconditionError,
)
from app.integrations.http_probe import HttpProbe
from app.services.findings import IgnoreList
from app.services.run_manager import RunManager
from app.services.run_store import RunStore

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    BlockedError: status.HTTP_409_CONFLICT,
    PreconditionError: status.HTTP_412_PRECONDITION_FAILED,
}


async def _domain_error(_: Request, exc: Exception) -> JSONResponse:
    code = next(
        (c for t, c in _STATUS_BY_ERROR.items() if isinstance(exc, t)),
        status.HTTP_400_BAD_REQUEST,
    )
    return JSONResponse(status_code=code, content={"detail": str(exc)})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient() as client:
        app.state.probe = HttpProbe(client)
        yield
        await app.state.run_manager.shutdown()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    store = RunStore(settings.runs_dir, settings.runs_keep)
    store.mark_interrupted()
    app.state.run_manager = RunManager(store, IgnoreList(settings.runs_dir / "ignored.json"))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(DomainError, _domain_error)
    app.include_router(
        api_router, prefix=settings.api_v1_prefix, dependencies=[Depends(require_api_key)]
    )
    return app


app = create_app()
