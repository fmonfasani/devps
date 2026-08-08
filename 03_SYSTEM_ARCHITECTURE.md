# System Architecture

## C4 Diagram Level 1 (System Context)

```
┌─────────────────────────────────────────────────────────┐
│                       Desarrollador                      │
│                  (git push, navegador)                   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │      GitHub / GitLab       │
        │  (repos, webhooks, auth)   │
        └────────┬───────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────────┐
    │         devps Control Plane         │
    │  (FastAPI + SQLite en /opt/devps)   │
    │                                     │
    │  • Dashboard (server-rendered)      │
    │  • API REST (CLI + integrations)    │
    │  • Deploy orchestration             │
    │  • Registry (metadata)              │
    └────┬────────────────────────┬───────┘
         │                        │
    ┌────▼──────────────┐   ┌─────▼──────────────┐
    │   Docker Daemon   │   │   Nginx + Certbot  │
    │  (compose, CLI)   │   │  (vhosts, SSL)     │
    └───────────────────┘   └────────────────────┘
```

## C4 Diagram Level 2 (Containers)

```
devps = FastAPI server + SQLite + file system

┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐     ┌──────────────────┐            │
│  │  dashboard.py    │     │  routers/        │            │
│  │  (Jinja2 server) │     │  • projects.py   │            │
│  │  • login_form    │     │  • health.py     │            │
│  │  • setup         │     │  • meta.py       │            │
│  │  • projects_page │     └──────────────────┘            │
│  │  • project_detail│                                      │
│  │  • new_project   │     ┌──────────────────┐            │
│  └──────────────────┘     │  auth.py         │            │
│                           │  • hash_password │            │
│  ┌──────────────────┐     │  • verify_pw     │            │
│  │  registry.py     │     └──────────────────┘            │
│  │  • upsert_project│                                      │
│  │  • set_port      │     ┌──────────────────┐            │
│  │  • get_project   │     │  docker_ops.py   │            │
│  │  • log_event     │     │  • clone_or_update            │
│  │  • migrations    │     │  • compose_up    │            │
│  └──────────────────┘     │  • compose_restart           │
│                           └──────────────────┘            │
│  ┌──────────────────┐     ┌──────────────────┐            │
│  │  repo_analysis.py│     │  secrets_store.py│            │
│  │  • clone_shallow │     │  • write_env_file│            │
│  │  • parse_compose │     └──────────────────┘            │
│  │  • parse_env_ex  │                                      │
│  │  • classify_vars │     ┌──────────────────┐            │
│  └──────────────────┘     │  nginx.py        │            │
│                           │  • install_vhost │            │
│                           │  • certbot        │            │
│                           └──────────────────┘            │
└─────────────────────────────────────────────────────────────┘
                        ▲
                        │
        ┌───────────────┴───────────────┐
        │                               │
    ┌───▼───────────┐         ┌────────▼────────┐
    │   SQLite DB   │         │  File System    │
    │  registry.db  │         │  /opt/devps/    │
    │               │         │  • secrets/     │
    │  • projects   │         │  • projects/    │
    │  • ports      │         │  • data/        │
    │  • events     │         └─────────────────┘
    │  • migrations │
    └───────────────┘
```

## Data Model

```sql
projects
├── name (PK)
├── managed_by (devps | adopted)
├── repo_url
├── git_ref
├── git_sha
├── domain
├── status (deploying | deployed | build_failed | adopted | unknown)
├── created_at
└── updated_at

project_ports
├── project_name (FK → projects)
├── service (PK with project_name)
├── host_port (40000-40999)
└── container_port

events
├── id (PK)
├── project_name (FK → projects)
├── kind (deploy | restart | vhost_installed | adopt | migration_*)
├── detail
├── success (bool)
└── created_at

migrations
├── project_name (FK → projects)
├── source_description
├── adopted_at
├── paralleled_at
├── cutover_at
├── decommissioned_at
└── notes
```

## API Endpoints

### Dashboard (public, authenticated)
- `GET /dashboard/login` → Login form
- `POST /dashboard/login` → Validate credentials
- `GET /dashboard/logout` → Clear session
- `GET /dashboard` → Projects list
- `GET /dashboard/projects/new` → New project form (step 1)
- `POST /dashboard/projects/new/analyze` → Auto-detect (step 2)
- `POST /dashboard/projects/new/deploy` → Deploy
- `GET /dashboard/projects/{name}` → Project detail + logs
- `GET /dashboard/setup` → Initial setup form
- `POST /dashboard/setup` → Save credentials
- `GET /dashboard/migrations` → Migration tracking

### Projects API (requires bearer token DEVPS_TOKEN)
- `GET /projects` → List all
- `GET /projects/{name}` → Detail
- `POST /projects/{name}/deploy` → Deploy with DeployRequest
- `POST /projects/{name}/adopt` → Adopt existing container
- `POST /projects/{name}/restart` → Restart docker-compose
- `GET /projects/{name}/logs?tail=200` → Container logs
- `GET /projects/{name}/events?limit=100` → Event timeline
- `GET /projects/{name}/migration` → Migration status
- `POST /projects/{name}/migration` → Update migration step
- `DELETE /projects/{name}` → Deregister project

### Health & Meta (public, unauthenticated)
- `GET /health` → Liveness probe
- `GET /meta` → Version, uptime, project count

## Deployment Architecture

```
┌──────────────────────────────────────────┐
│    GitHub Workflows (CI/CD)              │
├──────────────────────────────────────────┤
│  • bootstrap.yml: Deploy código a /opt   │
│  • setup-credentials.yml: Setup inicial  │
│  • Uses: appleboy/ssh-action (pineado)   │
└──────────────┬───────────────────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │  VPS 89.167.96.239       │
    ├──────────────────────────┤
    │  /opt/devps/             │
    │  ├── agent.env           │
    │  ├── data/               │
    │  │   └── registry.db     │
    │  ├── projects/           │
    │  │   ├── {proyecto1}/    │
    │  │   ├── {proyecto2}/    │
    │  │   └── {proyectoN}/    │
    │  └── secrets/            │
    │      ├── proj1.env       │
    │      └── proj2.env       │
    │                          │
    │  systemd service:        │
    │  devps-agent             │
    │  (uvicorn + FastAPI)     │
    └──────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
    ┌───────┐     ┌──────────┐
    │Docker │     │ Nginx    │
    │ daemon│     │ + Certbot│
    └───────┘     └──────────┘
```

## Flujos Principales

### Flow 1: Deploy nuevo proyecto desde dashboard
```
User (dashboard)
  │
  ├─→ GET /dashboard/projects/new
  │     ↓ Form: repo_url, git_ref, compose_file
  │
  ├─→ POST /dashboard/projects/new/analyze
  │     ↓ repo_analysis.clone_shallow(url, ref)
  │     ↓ parse_compose_services(docker-compose.yml)
  │     ↓ parse_env_example(.env.example)
  │     ↓ classify_and_generate(vars)
  │     ↓ TemplateResponse con servicios + vars editables
  │
  ├─→ POST /dashboard/projects/new/deploy
  │     ↓ auth.hash_password(password)
  │     ↓ secrets_store.write_env_file(/opt/devps/secrets/{name}.env)
  │     ↓ DeployRequest(repo_url, services, env_file, domain)
  │     ↓ deploy(name, DeployRequest) → docker compose up
  │     ↓ nginx.install_vhost(domain, host_port) → certbot
  │     ↓ registry.upsert_project(status=deployed)
  │     ↓ Redirect to /dashboard/projects/{name}
```

### Flow 2: Deploy via API (CLI / webhook)
```
External system (CLI hzploy / GitHub webhook)
  │
  ├─→ POST /projects/{name}/deploy
  │     Authorization: Bearer {DEVPS_TOKEN}
  │     Body: DeployRequest
  │     ↓ docker_ops.clone_or_update(repo_url, project_dir, git_ref)
  │     ↓ docker_ops.compose_up(project_dir, compose_file, env, env_file)
  │     ↓ nginx.install_vhost(domain, host_port)
  │     ↓ registry.upsert_project + log_event
  │     ↓ Response: Project detail
```

### Flow 3: Migration Coolify → devps
```
User: POST /projects/{name}/adopt
  ├─→ docker_ops.inspect_container(container_name)
  ├─→ registry.upsert_project(managed_by=adopted)
  ├─→ registry.set_port(service=main, host_port, container_port)
  ├─→ registry.touch_migration(adopted_at=now)
  └─→ Ahora devps ve el proyecto, pero no lo toca
  
  Cuando user hace POST /projects/{name}/deploy con domain:
  ├─→ docker_ops.compose_up(...)
  ├─→ nginx.install_vhost(...) ← TRAFFIC CUTOVER
  ├─→ registry.touch_migration(cutover_at=now)
  └─→ ¡Listo! La app está live en devps
```

## Decisiones Técnicas Clave

| Decisión | Alternativa | Razón |
|----------|-------------|-------|
| FastAPI | Django, Flask | Lightweight, async, OpenAPI docs |
| SQLite | PostgreSQL | MVP no necesita escala horizontal, archivos en /opt |
| Jinja2 server-rendered | React SPA | Cero JS, mismo proceso, session auth nativa |
| PBKDF2 + salt | bcrypt | stdlib, no nueva dependencia, 100k iteraciones = secure |
| docker compose | Dockerfile individual | Proyecto ya tiene compose, simplifica workflow |
| Bearer token (API) | OAuth2 | Máquina-a-máquina, no usuario interactivo |
| docker exec | systemd unit files | Devps no pisa servicios del OS, solo containers |
| Nginx vhosts generados | manual config | Seguridad + automatización, zero SSH |
| Git checkout para rollback | snapshots | Trusting git como fuente de verdad |
