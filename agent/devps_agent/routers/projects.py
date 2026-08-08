from fastapi import APIRouter, HTTPException

from .. import config, docker_ops, nginx, ports, registry
from ..models import AdoptRequest, DeployRequest, MigrationStepRequest

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

    existing = registry.get_project(name)
    was_adopted = existing is not None and existing["managed_by"] == "adopted"

    if existing is None:
        # events/project_ports both FK-reference projects.name — this row
        # has to exist before the very first log_event/set_port call below,
        # in case the clone itself fails and we need to record that.
        registry.upsert_project(
            name, "devps", req.repo_url, req.git_ref, None, req.domain, "deploying"
        )

    try:
        git_sha = docker_ops.clone_or_update(req.repo_url, project_dir, req.git_ref)
    except docker_ops.CommandError as e:
        registry.log_event(name, "deploy", f"git error: {e}", success=False)
        raise HTTPException(502, f"git error: {e}") from e

    existing_ports = {p["service"]: p["host_port"] for p in (existing or {}).get("ports", [])}

    allocated: dict[str, int] = {}
    env: dict[str, str] = {}
    for service, container_port in req.services.items():
        host_port = existing_ports.get(service) or ports.allocate_port()
        registry.set_port(name, service, host_port, container_port)
        allocated[service] = host_port
        env[f"DEVPS_PORT_{service.upper()}"] = str(host_port)

    try:
        docker_ops.compose_up(project_dir, req.compose_file, env, req.env_file)
    except docker_ops.CommandError as e:
        registry.upsert_project(
            name, "devps", req.repo_url, req.git_ref, git_sha, req.domain, "build_failed"
        )
        registry.log_event(name, "deploy", f"docker compose failed: {e}", success=False)
        raise HTTPException(502, f"docker compose failed: {e}") from e

    registry.upsert_project(
        name, "devps", req.repo_url, req.git_ref, git_sha, req.domain, "deployed"
    )
    registry.log_event(name, "deploy", f"git_sha={git_sha} ports={allocated}", success=True)

    # A project that was only `adopt`-ed before now has devps actually
    # building and running it. If this call also carries a domain, that's
    # the moment traffic moves — the cutover. Without a domain, it's a
    # parallel build that isn't live yet. See docs/MIGRATION.md.
    if was_adopted:
        registry.touch_migration(name, "cutover" if req.domain else "paralleled")

    if req.domain:
        if req.primary_service is None:
            # Unreachable in practice — DeployRequest's validator already
            # requires primary_service whenever domain is set — but this
            # guards the dict access below without relying on `assert`,
            # which `python -O` would strip.
            raise HTTPException(500, "primary_service missing despite domain being set")
        try:
            nginx.install_vhost(req.domain, allocated[req.primary_service])
            registry.log_event(name, "vhost_installed", req.domain, success=True)
        except nginx.NginxError as e:
            registry.log_event(name, "vhost_installed", str(e), success=False)
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

    # project_ports.project_name FK-references projects.name, so the project
    # row has to exist before set_port() below.
    registry.upsert_project(name, "adopted", domain=req.domain, status="adopted")

    port_bindings = (info.get("NetworkSettings") or {}).get("Ports") or {}
    for container_port_proto, bindings in port_bindings.items():
        if not bindings:
            continue
        container_port = int(container_port_proto.split("/")[0])
        host_port = int(bindings[0]["HostPort"])
        registry.set_port(name, "main", host_port, container_port)

    registry.log_event(name, "adopt", f"container={req.container_name}", success=True)
    registry.touch_migration(name, "adopted", source_description=f"container {req.container_name}")

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
        registry.log_event(name, "restart", str(e), success=False)
        raise HTTPException(502, str(e)) from e
    registry.log_event(name, "restart", None, success=True)
    return {"status": "restarted"}


@router.get("/{name}/logs")
def logs(name: str, tail: int = 200) -> dict:
    project = registry.get_project(name)
    if project is None:
        raise HTTPException(404, "not found")
    return {"logs": docker_ops.container_logs(name, tail)}


@router.get("/{name}/events")
def project_events(name: str, limit: int = 100) -> list[dict]:
    project = registry.get_project(name)
    if project is None:
        raise HTTPException(404, "not found")
    return registry.get_events(name, limit)


@router.get("/{name}/migration")
def get_migration(name: str) -> dict:
    migration = registry.get_migration(name)
    if migration is None:
        raise HTTPException(404, "no migration tracked for this project")
    return migration


@router.post("/{name}/migration")
def migration_step(name: str, req: MigrationStepRequest) -> dict:
    """Stamp a migration step by hand — mainly for `decommissioned`, which
    the agent has no way to detect on its own (see MigrationStepRequest)."""
    project = registry.get_project(name)
    if project is None:
        raise HTTPException(404, "not found")
    registry.touch_migration(name, req.step, notes=req.notes)
    registry.log_event(name, f"migration_{req.step}", req.notes, success=True)
    return registry.get_migration(name)


@router.delete("/{name}")
def deregister(name: str) -> dict:
    """Removes the project from devps's registry only. Does not stop
    containers or delete anything on disk — deliberately the safe direction
    (you can always re-adopt), the destructive direction needs its own
    explicit endpoint if it's ever needed."""
    registry.delete_project(name)
    return {"status": "deregistered"}
