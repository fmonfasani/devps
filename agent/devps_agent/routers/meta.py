"""Cross-project views: the global event feed and the migrations table."""

from fastapi import APIRouter

from .. import registry

router = APIRouter(tags=["meta"])


@router.get("/events")
def list_events(limit: int = 200) -> list[dict]:
    return registry.list_events(limit)


@router.get("/migrations")
def list_migrations() -> list[dict]:
    return registry.list_migrations()
