from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException

from . import config
from .db import init_db
from .routers import health, projects


def verify_token(authorization: str = Header(...)) -> None:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != config.BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="invalid or missing bearer token")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="devps agent", lifespan=lifespan)
app.include_router(health.router)
app.include_router(projects.router, dependencies=[Depends(verify_token)])
