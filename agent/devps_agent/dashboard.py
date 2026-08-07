"""Server-rendered dashboard — same process as the API, cookie-session auth
against the same DEVPS_TOKEN. No separate build step, no separate service,
no second credential to manage."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import config, docker_ops, registry

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# No return-type annotations on the route functions below: they mix
# TemplateResponse and RedirectResponse depending on the branch, and
# FastAPI tries to build a Pydantic response model from whatever type hint
# is given, which fails on a Response subclass union. Returning a real
# Response instance already tells Starlette everything it needs — the
# annotation is only for FastAPI's schema generation, which is off anyway
# (include_in_schema=False).


def _authenticated(request: Request) -> bool:
    return bool(request.session.get("authenticated"))


@router.get("/dashboard/login")
def login_form(request: Request):
    if _authenticated(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"session_authenticated": False})


@router.post("/dashboard/login")
def login_submit(request: Request, token: str = Form(...)):
    if token != config.BEARER_TOKEN:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"session_authenticated": False, "error": "Invalid token"},
            status_code=401,
        )
    request.session["authenticated"] = True
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/dashboard/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/dashboard/login", status_code=303)


@router.get("/dashboard")
def projects_page(request: Request):
    if not _authenticated(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "projects.html",
        {"session_authenticated": True, "projects": registry.list_projects()},
    )


@router.get("/dashboard/migrations")
def migrations_page(request: Request):
    if not _authenticated(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "migrations.html",
        {"session_authenticated": True, "migrations": registry.list_migrations()},
    )


@router.get("/dashboard/projects/{name}")
def project_detail_page(request: Request, name: str):
    if not _authenticated(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    project = registry.get_project(name)
    if project is None:
        return templates.TemplateResponse(
            request,
            "projects.html",
            {
                "session_authenticated": True,
                "projects": registry.list_projects(),
                "error": f"{name!r} not found",
            },
            status_code=404,
        )
    logs = docker_ops.container_logs(name, 200) if project["managed_by"] == "devps" else None
    return templates.TemplateResponse(
        request,
        "project_detail.html",
        {
            "session_authenticated": True,
            "project": project,
            "migration": registry.get_migration(name),
            "events": registry.get_events(name, 100),
            "logs": logs,
        },
    )
