"""Server-rendered dashboard — same process as the API, cookie-session auth
against the same DEVPS_TOKEN. No separate build step, no separate service,
no second credential to manage."""

import hashlib
import os
import binascii
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from . import auth, config, docker_ops, github_ops, login_throttle, rbac, registry, repo_analysis, secrets_store
from .models import DeployRequest
from .routers.health_status import list_health
from .routers.projects import deploy as deploy_project
from .db import connect

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
    request.session.clear()
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


@router.get("/dashboard/health")
def health_status_page(request: Request):
    if not _authenticated(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "health_status.html",
        {"session_authenticated": True, "health_data": list_health()},
    )


@router.get("/dashboard/users")
def users_page(request: Request):
    if not _authenticated(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    user = _get_user(request)
    if not user or user.get("role") != "admin":
        return templates.TemplateResponse(
            request,
            "base.html",
            {"session_authenticated": True, "content": "<p>Access denied. Admin only.</p>"},
        )

    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "session_authenticated": True,
            "users": registry.list_users(),
            "current_user": user,
        },
    )


@router.post("/dashboard/users/create")
async def create_user_endpoint(request: Request):
    if not _authenticated(request):
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    user = _get_user(request)
    if not user or user.get("role") != "admin":
        return JSONResponse({"success": False, "error": "Admin only"}, status_code=403)

    try:
        data = await request.json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        role = data.get("role", "viewer").strip()

        if not username or not password:
            return JSONResponse({"success": False, "error": "Username and password required"})

        if role not in ["admin", "deployer", "viewer"]:
            return JSONResponse({"success": False, "error": "Invalid role"})

        # Check if user exists
        if registry.get_user(username):
            return JSONResponse({"success": False, "error": "User already exists"})

        # Hash password
        salt = os.urandom(16)
        salt_hex = binascii.hexlify(salt).decode()
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        hash_hex = binascii.hexlify(hash_obj).decode()

        # Create user
        registry.create_user(username, hash_hex, salt_hex, role, created_by=user["username"])
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/dashboard/users/update-role")
async def update_user_role_endpoint(request: Request):
    if not _authenticated(request):
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    user = _get_user(request)
    if not user or user.get("role") != "admin":
        return JSONResponse({"success": False, "error": "Admin only"}, status_code=403)

    try:
        data = await request.json()
        username = data.get("username", "").strip()
        role = data.get("role", "").strip()

        if not username or not role:
            return JSONResponse({"success": False, "error": "Username and role required"})

        if role not in ["admin", "deployer", "viewer"]:
            return JSONResponse({"success": False, "error": "Invalid role"})

        registry.update_user_role(username, role)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/dashboard/users/delete")
async def delete_user_endpoint(request: Request):
    if not _authenticated(request):
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    user = _get_user(request)
    if not user or user.get("role") != "admin":
        return JSONResponse({"success": False, "error": "Admin only"}, status_code=403)

    try:
        data = await request.json()
        username = data.get("username", "").strip()

        if not username:
            return JSONResponse({"success": False, "error": "Username required"})

        if username == user["username"]:
            return JSONResponse({"success": False, "error": "Cannot delete yourself"})

        registry.delete_user(username)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.get("/dashboard/api/logs/{project_name}")
async def get_logs_endpoint(request: Request, project_name: str):
    if not _authenticated(request):
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    user = _get_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    project = registry.get_project(project_name)
    if not project:
        return JSONResponse({"success": False, "error": "Project not found"}, status_code=404)

    try:
        rbac.require_permission(user["username"], "view_project", project_name)
    except rbac.RBACError:
        return JSONResponse({"success": False, "error": "Access denied"}, status_code=403)

    tail = int(request.query_params.get("tail", 200))
    tail = max(10, min(tail, 1000))

    try:
        logs = docker_ops.container_logs(project_name, tail)
        return JSONResponse({"success": True, "logs": logs})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/dashboard/api/restart/{project_name}")
async def restart_container_endpoint(request: Request, project_name: str):
    if not _authenticated(request):
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    user = _get_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    project = registry.get_project(project_name)
    if not project:
        return JSONResponse({"success": False, "error": "Project not found"}, status_code=404)

    try:
        rbac.require_permission(user["username"], "edit_project", project_name)
    except rbac.RBACError:
        return JSONResponse({"success": False, "error": "Access denied"}, status_code=403)

    if project["managed_by"] != "devps":
        return JSONResponse({"success": False, "error": "Project not managed by devps"})

    try:
        project_dir = Path(config.PROJECTS_DIR) / project_name
        docker_ops.compose_restart(project_dir, "docker-compose.yml")

        from datetime import datetime
        with connect() as conn:
            conn.execute(
                "INSERT INTO events (project_name, kind, detail, success, created_at, created_by) VALUES (?, ?, ?, ?, ?, ?)",
                (project_name, "manual_restart", f"Restarted by {user['username']}", 1, datetime.utcnow().isoformat() + "Z", user['username']),
            )

        return JSONResponse({"success": True, "message": "Container restarted"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.get("/dashboard/api/settings/{project_name}")
async def get_settings_endpoint(request: Request, project_name: str):
    if not _authenticated(request):
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    user = _get_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    project = registry.get_project(project_name)
    if not project:
        return JSONResponse({"success": False, "error": "Project not found"}, status_code=404)

    try:
        rbac.require_permission(user["username"], "edit_project", project_name)
    except rbac.RBACError:
        return JSONResponse({"success": False, "error": "Access denied"}, status_code=403)

    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT alert_email, alert_slack, alert_enabled FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()

        if not row:
            return JSONResponse({"success": False, "error": "Project not found"})

        return JSONResponse({
            "success": True,
            "alert_email": row[0] or "",
            "alert_slack": row[1] or "",
            "alert_enabled": bool(row[2]),
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/dashboard/api/settings/{project_name}")
async def update_settings_endpoint(request: Request, project_name: str):
    if not _authenticated(request):
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    user = _get_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    project = registry.get_project(project_name)
    if not project:
        return JSONResponse({"success": False, "error": "Project not found"}, status_code=404)

    try:
        rbac.require_permission(user["username"], "edit_project", project_name)
    except rbac.RBACError:
        return JSONResponse({"success": False, "error": "Access denied"}, status_code=403)

    try:
        data = await request.json()
        alert_email = (data.get("alert_email") or "").strip()
        alert_slack = (data.get("alert_slack") or "").strip()
        alert_enabled = bool(data.get("alert_enabled"))

        with connect() as conn:
            conn.execute(
                "UPDATE projects SET alert_email = ?, alert_slack = ?, alert_enabled = ? WHERE name = ?",
                (alert_email or None, alert_slack or None, alert_enabled, project_name),
            )

        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/dashboard/api/mute-alerts/{project_name}")
async def mute_alerts_endpoint(request: Request, project_name: str):
    if not _authenticated(request):
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    user = _get_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    project = registry.get_project(project_name)
    if not project:
        return JSONResponse({"success": False, "error": "Project not found"}, status_code=404)

    try:
        rbac.require_permission(user["username"], "edit_project", project_name)
    except rbac.RBACError:
        return JSONResponse({"success": False, "error": "Access denied"}, status_code=403)

    try:
        from datetime import datetime, timedelta
        data = await request.json()
        hours = int(data.get("hours", 1))
        hours = max(1, min(hours, 24))

        mute_until = datetime.utcnow() + timedelta(hours=hours)
        mute_until_str = mute_until.isoformat() + "Z"

        with connect() as conn:
            conn.execute(
                "UPDATE projects SET alert_muted_until = ? WHERE name = ?",
                (mute_until_str, project_name),
            )

        return JSONResponse({"success": True, "muted_until": mute_until_str})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/dashboard/api/unmute-alerts/{project_name}")
async def unmute_alerts_endpoint(request: Request, project_name: str):
    if not _authenticated(request):
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    user = _get_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    project = registry.get_project(project_name)
    if not project:
        return JSONResponse({"success": False, "error": "Project not found"}, status_code=404)

    try:
        rbac.require_permission(user["username"], "edit_project", project_name)
    except rbac.RBACError:
        return JSONResponse({"success": False, "error": "Access denied"}, status_code=403)

    try:
        with connect() as conn:
            conn.execute(
                "UPDATE projects SET alert_muted_until = NULL WHERE name = ?",
                (project_name,),
            )

        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


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
        request, "new_project_simple.html", {"session_authenticated": True, "user": user}
    )


@router.post("/dashboard/api/create-project-auto")
async def create_project_auto_endpoint(request: Request):
    """Create project: auto-generate GitHub repo + deploy."""
    if not _authenticated(request):
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    user = _get_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

    try:
        rbac.require_permission(user["username"], "create_project")
    except rbac.RBACError:
        return JSONResponse({"success": False, "error": "Permission denied"}, status_code=403)

    try:
        data = await request.json()
        project_name = (data.get("project_name") or "").strip()

        if not project_name:
            return JSONResponse({"success": False, "error": "Project name required"})

        if not project_name.isalnum() and "-" not in project_name and "_" not in project_name:
            return JSONResponse({"success": False, "error": "Invalid project name (alphanumeric, -, _)"})

        # Check if project exists
        if registry.get_project(project_name):
            return JSONResponse({"success": False, "error": "Project already exists"})

        # Create GitHub repo
        github_token = config.GITHUB_TOKEN
        if not github_token:
            return JSONResponse({"success": False, "error": "GitHub token not configured"})

        repo_url = github_ops.create_repo(project_name, github_token, f"Auto-generated by devps")

        # Clone and init repo
        project_dir = Path(config.PROJECTS_DIR) / project_name
        docker_ops.clone_or_update(repo_url, project_dir, "main")
        github_ops.init_repo_with_compose(project_dir, project_name)

        # Deploy
        deploy_req = DeployRequest(
            repo_url=repo_url,
            git_ref="main",
            compose_file="docker-compose.yml",
            env_file=None,
            domain=None,
            services={"app": 3000},
            primary_service="app",
        )

        deploy_project(project_name, deploy_req)

        # Set owner
        with connect() as conn:
            conn.execute(
                "UPDATE projects SET owner = ?, created_by = ? WHERE name = ?",
                (user["username"], user["username"], project_name),
            )

        return JSONResponse({
            "success": True,
            "project_name": project_name,
            "repo_url": repo_url,
            "message": "Project created and deployed!"
        })

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


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
