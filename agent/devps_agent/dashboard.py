"""Server-rendered dashboard — same process as the API, cookie-session auth
against the same DEVPS_TOKEN. No separate build step, no separate service,
no second credential to manage."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import config, docker_ops, registry, repo_analysis, secrets_store
from .models import DeployRequest
from .routers.projects import deploy as deploy_project

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


@router.get("/dashboard/projects/new")
def new_project_form(request: Request):
    if not _authenticated(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    return templates.TemplateResponse(
        request, "new_project_form.html", {"session_authenticated": True}
    )


@router.post("/dashboard/projects/new/analyze")
def analyze_project(
    request: Request,
    project_name: str = Form(...),
    repo_url: str = Form(...),
    git_ref: str = Form("main"),
    compose_file: str = Form("docker-compose.yml"),
):
    if not _authenticated(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    try:
        repo_dir = repo_analysis.clone_shallow(repo_url, git_ref)
        compose_path = repo_dir / compose_file

        if not compose_path.exists():
            return templates.TemplateResponse(
                request,
                "new_project_form.html",
                {
                    "session_authenticated": True,
                    "project_name": project_name,
                    "repo_url": repo_url,
                    "git_ref": git_ref,
                    "compose_file": compose_file,
                    "error": f"{compose_file} not found in repo",
                },
                status_code=400,
            )

        services = repo_analysis.parse_compose_services(compose_path)
        env_vars = repo_analysis.parse_env_example(repo_dir)
        classified_vars = repo_analysis.classify_and_generate(env_vars)

        return templates.TemplateResponse(
            request,
            "new_project_review.html",
            {
                "session_authenticated": True,
                "project_name": project_name,
                "repo_url": repo_url,
                "git_ref": git_ref,
                "compose_file": compose_file,
                "services": services,
                "variables": classified_vars,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "new_project_form.html",
            {
                "session_authenticated": True,
                "project_name": project_name,
                "repo_url": repo_url,
                "git_ref": git_ref,
                "compose_file": compose_file,
                "error": f"Failed to analyze repo: {e!s}",
            },
            status_code=400,
        )


@router.post("/dashboard/projects/new/deploy")
async def deploy_new_project(
    request: Request,
    project_name: str = Form(...),
    repo_url: str = Form(...),
    git_ref: str = Form("main"),
    compose_file: str = Form("docker-compose.yml"),
    domain: str = Form(None),
    primary_service: str = Form(None),
):
    if not _authenticated(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    try:
        # Parse form data for services and variables
        form_data = await request.form()
        services = {}
        env_vars = {}

        # Extract services (format: service_<name>=<container_port>)
        for key, value in form_data.items():
            if key.startswith("service_"):
                service_name = key[8:]  # Remove "service_" prefix
                services[service_name] = int(value)
            elif key.startswith("var_"):
                var_name = key[4:]  # Remove "var_" prefix
                if value:  # Only include if not empty
                    env_vars[var_name] = value

        if not services:
            raise ValueError("No services specified")

        # Write secrets file
        env_file_path = secrets_store.write_env_file(project_name, env_vars)

        # Create deploy request
        deploy_req = DeployRequest(
            repo_url=repo_url,
            git_ref=git_ref,
            compose_file=compose_file,
            env_file=env_file_path,
            domain=domain if domain else None,
            services=services,
            primary_service=primary_service if primary_service else None,
        )

        # Call deploy function directly (not through HTTP)
        deploy_project(project_name, deploy_req)

        return RedirectResponse(f"/dashboard/projects/{project_name}", status_code=303)

    except Exception as e:
        return templates.TemplateResponse(
            request,
            "projects.html",
            {
                "session_authenticated": True,
                "projects": registry.list_projects(),
                "error": f"Deploy failed: {e!s}",
            },
            status_code=400,
        )
