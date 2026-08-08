import asyncio
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, Header, HTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import config, dashboard, health_checks
from .db import init_db
from .routers import health, meta, projects, webhooks


def verify_token(authorization: str = Header(...)) -> None:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, config.BEARER_TOKEN):
        raise HTTPException(status_code=401, detail="invalid or missing bearer token")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    # Start background health check loop
    health_task = asyncio.create_task(health_checks.health_check_loop())
    try:
        yield
    finally:
        health_task.cancel()
        with suppress(asyncio.CancelledError):
            await health_task


app = FastAPI(title="devps agent", lifespan=lifespan)
# The dashboard's login cookie is signed with the same DEVPS_TOKEN — one
# credential for the whole system, not a second secret to generate/rotate.
# See config.SESSION_HTTPS_ONLY for why this isn't hardcoded True.
app.add_middleware(
    SessionMiddleware, secret_key=config.BEARER_TOKEN, https_only=config.SESSION_HTTPS_ONLY
)

app.include_router(health.router)
app.include_router(projects.router, dependencies=[Depends(verify_token)])
app.include_router(meta.router, dependencies=[Depends(verify_token)])
app.include_router(webhooks.router)
app.include_router(dashboard.router)
