# devps — qué es y cómo está armado

Documento para pasarle a otro agente y pedirle mejoras de funcionalidad, arquitectura o estética. Repo: `github.com/fmonfasani/devps`, rama `main`. VPS: Hetzner `89.167.96.239`.

## Qué es

Un control-plane propio para reemplazar a Coolify en una VPS compartida donde conviven varios proyectos (sitios de clientes gestionados por Coolify, apps propias hand-deployed como wapsell, sitios estáticos). El objetivo: subir un proyecto nuevo, o migrar uno viejo de Coolify, sin tener que abrir una sesión SSH nueva, limpiar contenedores a mano, o configurar nginx/certbot manualmente cada vez. Un solo credential (nada de gestión de API keys por proyecto salvo las que el proyecto mismo necesite).

## Arquitectura técnica

**El agente** (`agent/devps_agent/`): FastAPI + Uvicorn, corre como servicio systemd directo en el host de la VPS (no en un contenedor — necesita tocar nginx/certbot/systemctl del host directamente). Puerto interno `9400`.

- **Registro** (`db.py`, `registry.py`): SQLite en `/opt/devps/data/registry.db`. Tablas: `projects` (nombre, repo, rama, sha, dominio, status, managed_by: `devps`|`adopted`), `project_ports` (servicio → puerto asignado), `events` (historial append-only de deploys/adopts/restarts, éxito/falla), `migrations` (una fila por proyecto en migración, timestamps de `adopted`/`paralleled`/`cutover`/`decommissioned`).
- **Puertos**: rango propio `40000-40999` (Coolify usa `31000-31999`, no compiten). `ports.py` asigna el primero libre.
- **Deploy** (`routers/projects.py`, `docker_ops.py`): clona/actualiza el repo por git, arma env vars `DEVPS_PORT_<SERVICIO>` por cada servicio declarado, corre `docker compose build && up -d`. Soporta `compose_file` custom y `env_file` (secretos ya existentes en la VPS, nunca generados/vistos por la API en texto — solo la ruta viaja).
- **Adopt**: registra un contenedor ya corriendo (ej. gestionado por Coolify) sin tocar cómo corre — primer paso del runbook de migración (`docs/MIGRATION.md`), visibilidad sin riesgo.
- **nginx + certbot** (`nginx.py`): escribe vhost, pide certificado Let's Encrypt vía webroot, recarga nginx — todo idempotente, mismo patrón manual que ya no hay que repetir a mano.
- **Auth**: un solo `DEVPS_TOKEN` (bearer, para la API/CLI). El dashboard usa el mismo token hoy vía cookie de sesión firmada — **en proceso de cambiar a usuario+contraseña** (ver handoff pendiente) para no tener que ir a buscarlo por SSH.
- **Rate limiting** (`login_throttle.py`): 5 intentos fallidos / 5 min por IP en el login, desde que el dashboard quedó público.

**El dashboard** (`dashboard.py` + `templates/*.html`): mismo proceso FastAPI, server-rendered con Jinja2, sin build step ni framework JS. Páginas: lista de proyectos (con último evento), detalle de proyecto (timeline completo + logs + estado de migración), tabla de migraciones, y **Fase 3b recién agregada**: `/dashboard/projects/new` — formulario en 2 pasos donde pegás una URL de repo, devps clona superficial, lee `docker-compose.yml` (detecta servicios/puertos vía el patrón `${DEVPS_PORT_X}`) y `.env.example` (detecta variables requeridas, auto-genera las que son secretos internos como passwords/claves de cifrado, deja en blanco las que dependen de un proveedor externo como API keys), mostrás/editás todo, y con un click deploya.

**La CLI** (`cli/hzploy`): Python stdlib puro (sin pip install), mismos comandos que la API (`up`, `adopt`, `list`, `logs`, `restart`, `rm`). Pensada para correr desde la VPS misma, tu compu, o encadenada a un túnel SSH.

**Público real**: `https://devps.webshooks.com` — vhost + certificado propio, HTTPS-only, ya no depende de túnel SSH.

**Puente para SSH**: como el entorno donde vive el agente conversacional (yo) no tiene salida SSH directa, todo lo que toca la VPS pasa por GitHub Actions (`workflow_dispatch` + `appleboy/ssh-action` pineado a un SHA). Esto es propio de cómo yo opero el sistema, no es parte de la arquitectura de devps en sí.

## Estado actual (qué está hecho)

- Fase 1: agente + CLI + workflow reusable de deploy.
- Fase 2: dashboard con historial de eventos y tracking de migraciones.
- Fase 3a: dominio propio + HTTPS + login rate-limited.
- Fase 3b: auto-detección de repos + generación de secretos + deploy de un click desde el dashboard.
- Migración real de wapsell probada en paralelo (funciona), cutover real pendiente (falta plan de continuidad de datos).
- 6 proyectos "adoptados" con visibilidad (2 de ellos, `luzguffanti`/`anareiki`, gestionados por Coolify; el resto hand-managed).
- En curso: login por usuario+contraseña (reemplaza el token).

## Estética actual

Templates Jinja2 con CSS inline en `base.html` — tema oscuro simple, sin librería de diseño (no Tailwind, no Bootstrap), tablas básicas, badges de color por estado. Funcional pero minimalista — nunca se invirtió tiempo en pulir la UI. Viewport meta agregado recién para que no se vea roto en celular, pero no hay media queries reales ni testing en mobile más allá de eso.

## Dónde hay margen de mejora (para pedirle ideas al otro agente)

- **Funcionalidad**: notificaciones (deploy falló → avisar), logs en vivo (hoy es snapshot, no streaming), rollback con un click, resource usage (CPU/RAM por proyecto), multi-usuario si en algún momento hace falta compartir acceso.
- **Arquitectura**: hoy todo es un solo proceso/SQLite — sirve para el volumen actual, pero preguntarle al agente si conviene separar el analizador de repos (Fase 3b) en un worker aparte para no bloquear el request principal en clones grandes.
- **Estética**: layout responsive de verdad (no solo viewport meta), mejor jerarquía visual en la tabla de proyectos/migraciones, quizás un dashboard de resumen (cuántos proyectos, cuántos con certificado por vencer, etc.) en vez de solo listas planas.
