# Arquitectura

## Por qué el agente no es un contenedor Docker

El agente necesita escribir vhosts en `/etc/nginx/`, correr `certbot` y
`systemctl reload nginx` **en el host**. Nada de eso funciona de forma
limpia desde dentro de un contenedor sin namespaces compartidos/montajes
privilegiados que agregan más riesgo del que resuelven. Por eso el agente
corre como **servicio systemd directo en la VPS**
(`infra/systemd/devps-agent.service`), instalado por
`infra/scripts/bootstrap.sh`. Todo lo que el agente *gestiona* (los
proyectos) sigue siendo Docker normal, igual que antes.

## Por qué no Traefik (todavía)

El nginx del host ya está andando, bien configurado a mano (ver
`docs/AUDIT.md`) y sirve 22 vhosts sin problemas. Meter Traefik como
segunda capa de proxy en una VPS de producción compartida el mismo día que
se instala el agente es riesgo sin necesidad — el agente genera y recarga
vhosts de nginx directamente. Si más adelante hace falta el auto-discovery
de Traefik (por ejemplo al migrar muchos sitios de Coolify), se evalúa con
el terreno ya mapeado, no a ciegas.

## Las dos formas de que un proyecto entre a `devps`

- **`deploy`** — devps es dueño del ciclo de vida completo: clona el repo,
  hace build, corre `docker compose up`, asigna puertos, escribe el vhost
  de nginx y pide el certificado. Es el camino para proyectos con código en
  un repo (wapsell, ailearning, lo que sigue).
- **`adopt`** — registra un contenedor que **ya existe** (por ejemplo, uno
  que hoy gestiona Coolify) en el registro de devps, sin tocar cómo corre
  ni cómo se rutea el tráfico. Es el primer paso para migrar un sitio fuera
  de Coolify — ver `docs/MIGRATION.md`. No instala vhost ni cambia nada.

## Un solo credential compartido

El agente se autentica con un único bearer token (`DEVPS_TOKEN`), el mismo
para la CLI, para el workflow reusable de GitHub Actions, y para vos. No
hay una clave SSH nueva por proyecto — esa era exactamente la fricción que
`devps` viene a eliminar.

## Puertos

El agente asigna puertos del rango `40000-40999` (configurable), elegido
en `docs/AUDIT.md` para no chocar con el rango de Coolify (`31000-31999`)
ni con ningún puerto ya en uso al momento del audit. El agente mismo
escucha en `127.0.0.1:9400` — confirmado libre en el mismo audit.

## Base de datos

SQLite (`/opt/devps/data/registry.db`), un solo escritor (el agente),
nada de un servicio de base de datos aparte para algo que gestiona a los
demás. Además de `projects`/`project_ports`, guarda:

- **`events`** — log append-only de cada acción (`deploy`, `adopt`,
  `restart`, instalación de vhost), con éxito/fracaso y detalle. Es lo que
  le da historial real al dashboard — un `GET /projects/{name}` solo
  muestra el estado actual, no que un deploy falló dos veces antes de
  funcionar.
- **`migrations`** — un renglón por proyecto en proceso de salir de
  Coolify (o de donde sea), con timestamps por paso
  (`adopted`/`paralleled`/`cutover`/`decommissioned`). `adopt` y `deploy`
  los estampan solos cuando corresponde; `decommissioned` es manual,
  porque el agente no tiene visibilidad de lo que pasa dentro de Coolify.

## El dashboard

Mismo proceso FastAPI, servido en `/dashboard` — no hay build de frontend
ni contenedor aparte. Auth por cookie de sesión firmada con el mismo
`DEVPS_TOKEN` (login = pegar el token una vez en un form, no un header a
mano en cada visita). La cookie se emite sin `Secure` (`https_only=False`)
porque hoy el agente solo es alcanzable por túnel SSH sobre HTTP plano —
hay que pasar a `True` en `main.py` el día que haya un dominio HTTPS
público para el agente.
