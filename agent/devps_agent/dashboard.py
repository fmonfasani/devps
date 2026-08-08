"""Server-rendered dashboard — same process as the API, cookie-session auth
against the same DEVPS_TOKEN. No separate build step, no separate service,
no second credential to manage."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import auth, config, docker_ops, login_throttle, rbac, registry, repo_analysis, secrets_store
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


def _client_ip(request: Request) -> str:
    # Set unconditionally by devps's own nginx vhost template
    # (nginx.py's _VHOST_TEMPLATE) — falls back to the direct TCP peer for
    # the SSH-tunnel-to-127.0.0.1 path, which doesn't go through nginx.
    return request.headers.get("x-real-ip") or (
        request.client.host if request.client else "unknown"
    )


def _authenticated(request: Request) -> bool:
    return bool(request.session.get("username"))


def _get_user(request: Request) -> dict | None:
    """Get current authenticated user from session."""
    username = request.session.get("username")
    if not username:
        return None
    return registry.get_user(username)


@router.get("/dashboard/login")
def login_form(request: Request):
    if _authenticated(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"session_authenticated": False})


@router.post("/dashboard/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    ip = _client_ip(request)
    if login_throttle.is_rate_limited(ip):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"session_authenticated": False, "error": "Too many attempts — try again later"},
            status_code=429,
        )

    user = registry.get_user(username)
    if not user or not auth.verify_password(password, user["password_salt"], user["password_hash"]):
        login_throttle.record_failure(ip)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"session_authenticated": False, "error": "Invalid username or password"},
            status_code=401,
        )

    login_throttle.record_success(ip)
    request.session["username"] = username
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/dashboard/logout")
def logout(request: Request):
    username = request.session.get("username")
    request.session.clear()
    if username:
        registry.log_event(None, "dashboard_logout", f"user {username} logged out", success=True)
    return RedirectResponse("/dashboard/login", status_code=303)


@router.get("/dashboard")
def projects_page(request: Request):
    if not _authenticated(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    user = _get_user(request)
    if not user:
        return RedirectResponse("/dashboard/login", status_code=303)

    try:
        # Show projects based on user role
        projects = rbac.list_user_projects(user["username"])
    except rbac.RBACError:
        projects = []

    return templates.TemplateResponse(
        request,
        "projects.html",
        {"session_authenticated": True, "projects": projects, "user": user},
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

    user = _get_user(request)
    if not user:
        return RedirectResponse("/dashboard/login", status_code=303)

    project = registry.get_project(name)
    if project is None:
        return templates.TemplateResponse(
            request,
            "projects.html",
            {
                "session_authenticated": True,
                "projects": rbac.list_user_projects(user["username"]),
                "error": f"{name!r} not found",
                "user": user,
            },
            status_code=404,
        )

    # Check if user can view this project
    try:
        rbac.require_permission(user["username"], "view_project", name)
    except rbac.RBACError:
        return templates.TemplateResponse(
            request,
            "projects.html",
            {
                "session_authenticated": True,
                "projects": rbac.list_user_projects(user["username"]),
                "error": f"You don't have permission to view {name!r}",
                "user": user,
            },
            status_code=403,
        )

    logs = docker_ops.container_logs(name, 200) if project["managed_by"] == "devps" else None
    health_events = [e for e in registry.get_events(name, 100) if e["kind"] == "auto_restart"]

    return templates.TemplateResponse(
        request,
        "project_detail.html",
        {
            "session_authenticated": True,
            "project": project,
            "migration": registry.get_migration(name),
            "events": registry.get_events(name, 100),
            "health_events": health_events,
            "logs": logs,
            "user": user,
        },
    )


@router.get("/dashboard/projects/new")
def new_project_form(request: Request):
    if not _authenticated(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    user = _get_user(request)
    if not user:
        return RedirectResponse("/dashboard/login", status_code=303)

    # Check if user can create projects
    try:
        rbac.require_permission(user["username"], "create_project")
    except rbac.RBACError:
        return templates.TemplateResponse(
            request,
            "projects.html",
            {
                "session_authenticated": True,
                "projects": rbac.list_user_projects(user["username"]),
                "error": "You don't have permission to create projects",
                "user": user,
            },
            status_code=403,
        )

    return templates.TemplateResponse(
        request, "new_project_form.html", {"session_authenticated": True, "user": user}
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

    user = _get_user(request)
    if not user:
        return RedirectResponse("/dashboard/login", status_code=303)

    # Check if user can create projects
    try:
        rbac.require_permission(user["username"], "create_project")
    except rbac.RBACError:
        return templates.TemplateResponse(
            request,
            "projects.html",
            {
                "session_authenticated": True,
                "projects": rbac.list_user_projects(user["username"]),
                "error": "You don't have permission to create projects",
                "user": user,
            },
            status_code=403,
        )

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

        # Set project owner after deployment
        from .db import connect
        with connect() as conn:
            conn.execute(
                "UPDATE projects SET owner = ?, created_by = ? WHERE name = ?",
                (user["username"], user["username"], project_name),
            )

        return RedirectResponse(f"/dashboard/projects/{project_name}", status_code=303)

    except Exception as e:
        user_obj = user if user else {}
        return templates.TemplateResponse(
            request,
            "projects.html",
            {
                "session_authenticated": True,
                "projects": rbac.list_user_projects(user["username"]) if user else [],
                "error": f"Deploy failed: {e!s}",
                "user": user_obj,
            },
            status_code=400,
        )


@router.get("/dashboard/setup")
def setup_form(request: Request):
    if config.DASHBOARD_USERNAME and config.DASHBOARD_PASSWORD_HASH:
        return RedirectResponse("/dashboard/login", status_code=303)
    return templates.TemplateResponse(
        request, "setup.html", {"session_authenticated": False}
    )


@router.post("/dashboard/setup")
def setup_submit(
    request: Request, username: str = Form(...), password: str = Form(...)
):
    if config.DASHBOARD_USERNAME and config.DASHBOARD_PASSWORD_HASH:
        return RedirectResponse("/dashboard/login", status_code=303)

    if not username or not password:
        return templates.TemplateResponse(
            request,
            "setup.html",
            {
                "session_authenticated": False,
                "error": "Username and password are required",
            },
            status_code=400,
        )

    try:
        hash_hex, salt_hex = auth.hash_password(password)

        env_file = Path(config.DATA_DIR.parent / "agent.env")
        env_lines = []
        if env_file.exists():
            with open(env_file) as f:
                env_lines = [
                    line for line in f.readlines()
                    if not line.startswith("DEVPS_DASHBOARD_")
                ]

        with open(env_file, "w") as f:
            f.writelines(env_lines)
            f.write(f"DEVPS_DASHBOARD_USERNAME={username}\n")
            f.write(f"DEVPS_DASHBOARD_PASSWORD_HASH={hash_hex}\n")
            f.write(f"DEVPS_DASHBOARD_PASSWORD_SALT={salt_hex}\n")

        env_file.chmod(0o600)

        return templates.TemplateResponse(
            request,
            "setup.html",
            {
                "session_authenticated": False,
                "success": "Credentials saved! Refresh the page in a few seconds.",
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request,
            "setup.html",
            {"session_authenticated": False, "error": f"Setup failed: {e!s}"},
            status_code=500,
        )
