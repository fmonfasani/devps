from fastapi import APIRouter, HTTPException

from .. import config, docker_ops, nginx, ports, registry
from ..models import AdoptRequest, DeployRequest

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects() -> list[dict]:
    return registry.list_projects()


@router.get("/{name}")
def get_project(name: str) -> dict:
    project = registry.get_project(name)
    if project is None:
        raise HTTPException(404, "not found")
    return project


@router.post("/{name}/deploy")
def deploy(name: str, req: DeployRequest) -> dict:
    project_dir = config.PROJECTS_DIR / name
    config.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        git_sha = docker_ops.clone_or_update(req.repo_url, project_dir, req.git_ref)
    except docker_ops.CommandError as e:
        raise HTTPException(502, f"git error: {e}") from e

    existing = registry.get_project(name)
    existing_ports = {p["service"]: p["host_port"] for p in (existing or {}).get("ports", [])}

    allocated: dict[str, int] = {}
    env: dict[str, str] = {}
    for service, container_port in req.services.items():
        host_port = existing_ports.get(service) or ports.allocate_port()
        registry.set_port(name, service, host_port, container_port)
        allocated[service] = host_port
        env[f"DEVPS_PORT_{service.upper()}"] = str(host_port)

    try:
        docker_ops.compose_up(project_dir, req.compose_file, env)
    except docker_ops.CommandError as e:
        registry.upsert_project(
            name, "devps", req.repo_url, req.git_ref, git_sha, req.domain, "build_failed"
        )
        raise HTTPException(502, f"docker compose failed: {e}") from e

    registry.upsert_project(
        name, "devps", req.repo_url, req.git_ref, git_sha, req.domain, "deployed"
    )

    if req.domain:
        if req.primary_service is None:
            # Unreachable in practice — DeployRequest's validator already
            # requires primary_service whenever domain is set — but this
            # guards the dict access below without relying on `assert`,
            # which `python -O` would strip.
            raise HTTPException(500, "primary_service missing despite domain being set")
        try:
            nginx.install_vhost(req.domain, allocated[req.primary_service])
        except nginx.NginxError as e:
            raise HTTPException(502, f"deployed, but nginx vhost failed: {e}") from e

    return registry.get_project(name)


@router.post("/{name}/adopt")
def adopt(name: str, req: AdoptRequest) -> dict:
    """Register an already-running container (e.g. one Coolify manages)
    under devps for visibility, WITHOUT touching how it currently runs or
    routes traffic. This is step one of migrating a site off Coolify — see
    docs/MIGRATION.md. It does not install an nginx vhost; the container
    keeps being served however it is today until an explicit cutover."""
    info = docker_ops.inspect_container(req.container_name)
    if info is None:
        raise HTTPException(404, f"container {req.container_name!r} not found")

    port_bindings = (info.get("NetworkSettings") or {}).get("Ports") or {}
    for container_port_proto, bindings in port_bindings.items():
        if not bindings:
            continue
        container_port = int(container_port_proto.split("/")[0])
        host_port = int(bindings[0]["HostPort"])
        registry.set_port(name, "main", host_port, container_port)

    registry.upsert_project(name, "adopted", domain=req.domain, status="adopted")
    return registry.get_project(name)


@router.post("/{name}/restart")
def restart(name: str) -> dict:
    project = registry.get_project(name)
    if project is None:
        raise HTTPException(404, "not found")
    if project["managed_by"] != "devps":
        raise HTTPException(
            400,
            "this project was adopted, not deployed by devps — restart it "
            "wherever it's actually managed (e.g. Coolify) until it's migrated",
        )
    try:
        docker_ops.compose_restart(config.PROJECTS_DIR / name, "docker-compose.yml")
    except docker_ops.CommandError as e:
        raise HTTPException(502, str(e)) from e
    return {"status": "restarted"}


@router.get("/{name}/logs")
def logs(name: str, tail: int = 200) -> dict:
    project = registry.get_project(name)
    if project is None:
        raise HTTPException(404, "not found")
    return {"logs": docker_ops.container_logs(name, tail)}


@router.delete("/{name}")
def deregister(name: str) -> dict:
    """Removes the project from devps's registry only. Does not stop
    containers or delete anything on disk — deliberately the safe direction
    (you can always re-adopt), the destructive direction needs its own
    explicit endpoint if it's ever needed."""
    registry.delete_project(name)
    return {"status": "deregistered"}
