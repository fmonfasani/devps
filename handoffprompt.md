# Handoff: devps Phase 3b — self-service deploy from the dashboard

## Contexto

`devps` (github.com/fmonfasani/devps) es un control-plane propio que reemplaza a Coolify en una VPS Hetzner compartida (`89.167.96.239`). Es un agente FastAPI + SQLite corriendo como servicio systemd en la VPS (`/opt/devps`), con:
- API bearer-token (`DEVPS_TOKEN`, vive en `/opt/devps/agent.env`)
- Dashboard server-rendered (Jinja2, mismo proceso) con login por sesión
- CLI (`cli/hzploy`, Python stdlib) que pega contra la API
- Deploy = clona repo, asigna puerto (rango 40000-40999), `docker compose up`, escribe vhost nginx + certbot

**El sandbox donde corrés vos no tiene salida SSH.** Todo lo que toca la VPS se hace vía GitHub Actions (`.github/workflows/*.yml` en el repo `devps`, usando `appleboy/ssh-action@7eaf76671a0d7eec5d98ee897acda4f968735a17` — SHA pineada, secrets `HETZNER_HOST`/`HETZNER_USER`/`HETZNER_SSH_KEY`/`HETZNER_SSH_PORT` ya cargados en el repo). Triggereás con `workflow_dispatch` y leés logs por la API de GitHub — **esto es lo que más gasta tokens** (payloads enormes). Minimizalo: pedí `tail_lines` chicos, no repitas `list_workflow_runs` completo si ya tenés el run_id, y agrupá varios comandos en un solo step de un mismo workflow en vez de crear workflows separados por paso.

## Ya está hecho y andando

- **Dashboard público**: `https://devps.webshooks.com/dashboard` — vhost + certificado + `DEVPS_SESSION_HTTPS_ONLY=true` ya activo. Login con el `DEVPS_TOKEN` de siempre.
- Rate limiting de login (5 intentos/5min por IP) en `agent/devps_agent/login_throttle.py`.
- `deploy()` (en `agent/devps_agent/routers/projects.py`) ya soporta `compose_file` y `env_file` (path a un archivo de secretos ya existente en la VPS, pasado a `docker compose --env-file`).
- Migración de wapsell probada en paralelo con éxito (proyecto `wapsell` en el registro, puertos 40000/40001, usando `/opt/waseller/.env.prod` como env_file real) — pendiente el cutover real (necesita plan de continuidad de datos, no arrancar sin eso).

## Bug conocido de infraestructura — no lo repitas

`appleboy/ssh-action` (drone-ssh) **corrompe heredocs (`cat <<EOF`) y a veces bloques `if/then/else`** en el `script:` — inyecta una línea de tracking (`DRONE_SSH_PREV_COMMAND_EXIT_CODE=0`) en medio. Solución que ya funciona: escribir archivos con contenido multilínea via `echo "$BASE64" | base64 -d > archivo` (una sola línea), pasando el base64 por `env:`. Evitar heredocs y bloques condicionales multilínea en scripts SSH de este repo.

## Lo que falta — Fase 3b

El usuario quiere: **loguearse desde el celular en `devps.webshooks.com`, pegar la URL de un repo nuevo, y que devps auto-detecte todo y lo despliegue** — cero SSH, cero CLI, cero compu de escritorio.

Diseño ya decidido (no rediscutir, implementar):

1. **`agent/devps_agent/repo_analysis.py`** (módulo nuevo, sin FastAPI — testeable como `registry.py`):
   - `clone_shallow(repo_url, git_ref) -> Path`: clona a un tempdir (`tempfile.mkdtemp()`), `git clone --depth 1 --branch <ref> <url> <dir>`.
   - `parse_compose_services(compose_path) -> dict[str, dict]`: parsea YAML (agregar `pyyaml` a `pyproject.toml`, no está declarado hoy). Por cada service, busca en su `ports:` el patrón `${DEVPS_PORT_<NOMBRE>...}:<puerto_contenedor>` con regex `\$\{DEVPS_PORT_([A-Z0-9_]+)(?::-\d+)?\}:(\d+)`. Si un servicio no sigue esa convención, igual listarlo pero marcarlo como "necesita edición manual" — el repo de prueba del usuario debería escribir sus `ports:` así: `"127.0.0.1:${DEVPS_PORT_WEB:-3000}:3000"` (mismo patrón que ya usa `wapsell-saas`).
   - `parse_env_example(repo_dir) -> list[str]`: lee `.env.example` en la raíz (o al lado del compose_file), devuelve nombres de variables sin valor/con placeholder.
   - `classify_and_generate(var_names) -> dict[str, dict]`: por cada var, `generatable = True` si termina en uno de `PASSWORD, ENCRYPTION_KEY, SESSION_SECRET, JWT_SECRET, AUTH_SECRET, COOKIE_SECRET, CSRF_SECRET, VERIFY_TOKEN, SALT` o contiene `INTERNAL`. Si generatable, `value = secrets.token_hex(24)`. Si no, `value = None` (el usuario lo completa a mano — típicamente API keys de terceros, imposibles de inventar).

2. **`agent/devps_agent/secrets_store.py`**: `write_env_file(project_name, values: dict[str,str]) -> str` — escribe a `/opt/devps/secrets/<project_name>.env`, `chmod 600`, devuelve el path (para pasarlo como `env_file` al deploy).

3. **Rutas nuevas en `agent/devps_agent/dashboard.py`** (todas requieren `_authenticated`):
   - `GET /dashboard/projects/new`: form paso 1 — nombre, repo URL, rama (default main), compose file (default `docker-compose.yml`).
   - `POST /dashboard/projects/new/analyze`: llama `clone_shallow` + `parse_compose_services` + `parse_env_example` + `classify_and_generate`, renderiza form paso 2 con todo pre-completado (servicios/puertos editables, variables generadas visibles con botón "regenerar", variables externas vacías marcadas "necesita tu valor"), + campo dominio opcional + select de `primary_service`.
   - `POST /dashboard/projects/new/deploy`: junta los datos del form paso 2, llama `secrets_store.write_env_file(...)`, arma un `DeployRequest` y **llama directo a la función `deploy()` de `routers/projects.py`** (es una función sync normal, se puede importar y llamar sin pasar por HTTP) — no dupliques esa lógica. Redirige a `/dashboard/projects/{name}` al terminar.

4. **Templates nuevos**: `new_project_form.html` (paso 1), `new_project_review.html` (paso 2) — mismo estilo que los templates existentes (`base.html` define el CSS, extender de ahí).

5. **Mobile**: agregar `<meta name="viewport" content="width=device-width, initial-scale=1">` a `base.html` (hoy no está — sin esto se ve mal en celular).

6. **Nav**: agregar link "New project" en el `<nav>` de `base.html`.

7. **Tests**: para `repo_analysis.py` y `secrets_store.py` (lógica pura, sin fastapi) — seguir el patrón de `tests/test_ports.py`/`tests/test_registry.py`.

## Reglas del repo (ya establecidas, no romper)

- Commits van directo a `main` en `devps` (repo propio del usuario, sin PR review formal ahí — sí se usa PR review en `wapsell-saas`).
- Correr `pytest` + `ruff check .` en `agent/` antes de cada commit.
- Después de cada cambio en `agent/`, redesplegar con el workflow `bootstrap.yml` (`workflow_dispatch`) para que el systemd service tome el código nuevo.
- No usar heredocs multilínea en `script:` de ssh-action (ver bug arriba).
- Nunca hardcodear secretos en logs de workflow ni en código — todo por `secrets.*` de GitHub o generado server-side.

## Primer paso sugerido al arrancar

Verificar que `agent/pyproject.toml` no tenga ya `pyyaml`, agregarlo, y arrancar por `repo_analysis.py` + sus tests (no depende de nada más, se puede validar solo con `pytest` sin tocar la VPS todavía).
