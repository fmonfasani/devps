# Audit — VPS Hetzner `89.167.96.239` (`ubuntu-16gb-hel1-1`)

Generado por `.github/workflows/audit.yml` (run manual, solo lectura) el
2026-08-07. Host: Hetzner Helsinki (hel1), Ubuntu 24.04.4 LTS, 61 días de
uptime, 16GB RAM / 150GB disco.

## Resumen ejecutivo

Esta VPS **no es de un solo proyecto** — corre en paralelo:

1. **Coolify** (`/data/coolify` existe, `coolify-db` + `coolify-redis` en
   volúmenes) gestionando ~6-8 sitios de clientes propios, cada uno con su
   propio nginx vhost autogenerado y puertos en el rango `31001-31008`.
2. **Wapsell/pipaas** — gestionado a mano (no por Coolify), 2 contenedores
   (`wapsell-app` en `:3010`, `wapsell-api` en `:8500`), 4 vhosts nginx
   escritos a mano (`wapsell.com`, `app.wapsell.com`, `api.wapsell.com`,
   `pipaas.com` legacy).
3. Un puñado de sitios estáticos / otros proyectos sueltos
   (`fmonfasani.blog`, `webshooks.com`, `luzguffanti.com`, `anamurat.online`,
   `argfy.com`).

**No hay Traefik ni Caddy corriendo.** Todo el reverse-proxy pasa por un
único **nginx del host** (v1.24.0), con ~22 vhosts en
`/etc/nginx/sites-enabled/`, cada uno escrito a mano o generado por
Coolify. No hay ningún control-plane propio todavía — es exactamente el
vacío que `devps` viene a llenar.

## Sistema

| | |
|---|---|
| Host | `ubuntu-16gb-hel1-1` |
| OS | Ubuntu 24.04.4 LTS, kernel 6.8.0-124-generic |
| Uptime | 61 días |
| RAM | 15Gi total, 2.2Gi usados, 13Gi disponibles |
| Disco (`/`) | 150G total, 48G usados (33%), 97G libres |
| IP pública | `89.167.96.239` |
| Redes internas | `10.0.0.1`, `10.0.1.1`...`10.0.6.1` (Docker bridges) + IPv6 |

Nada urgente en recursos — hay margen de sobra en disco y RAM.

## Firewall (ufw) — activo

```
22/tcp    ALLOW  (SSH)
80/tcp    ALLOW  (HTTP)
443/tcp   ALLOW  (HTTPS)
443       ALLOW  (duplicado del anterior, probablemente UDP/QUIC o regla vieja)
9000/tcp  ALLOW  (⚠️ sin proceso escuchando ahí ahora mismo — ver hallazgos)
8080/tcp  ALLOW  "# Healthcheck Dashboard" (⚠️ mismo caso)
```
Todo espejado en IPv6. Default: deny incoming, allow outgoing.

## Puertos realmente escuchando (`ss -tlnp`)

| Puerto | Proceso | Qué es |
|---|---|---|
| 22 | sshd | SSH |
| 80, 443 | nginx | reverse proxy del host (único punto de entrada público) |
| 3010 | docker-proxy → `wapsell-app` | wapsell.com / app.wapsell.com |
| 8500 | docker-proxy → `wapsell-api` | api.wapsell.com / pipaas.com |
| 3020 | docker-proxy → `fmonfasani-app` | fmonfasani.blog |
| 5432 | docker-proxy → `catalaxia-db` | Postgres de otro proyecto (catalaxia) |
| 31001 | docker-proxy → `luzguffanti-web` | luzguffanti.com |
| 31008 | docker-proxy → `anareiki-web` | anamurat.online |
| 127.0.0.53/54:53 | systemd-resolved | DNS local, ignorar |

**Nada** escucha en `9000` ni `8080` pese a estar permitidos en el
firewall, ni tampoco en `31002/31003/31004` pese a que 3 vhosts nginx
(`forrajeria`, `zapateria`, `tienda`.webshooks.com) hacen `proxy_pass` a
esos puertos. Ver hallazgos.

## Docker

**Versión:** Docker 29.5.2, Compose v5.1.3.

**Contenedores corriendo** (6 visibles vía `docker ps -a` — ninguno detenido):

| Nombre | Imagen | Puerto host | Estado |
|---|---|---|---|
| `wapsell-app` | wapsell-app:latest | 127.0.0.1:3010 | healthy, 8 días |
| `wapsell-api` | wapsell-api:latest | 127.0.0.1:8500 | healthy, 7 semanas |
| `fmonfasani-app` | fmonfasani-app:latest | 127.0.0.1:3020 | healthy, 3 semanas |
| `catalaxia-db` | postgres:16 | 127.0.0.1:5432 | healthy, 3 semanas |
| `luzguffanti-web` | 001-luzguffanti-web | 127.0.0.1:31001 | running, 7 semanas (sin healthcheck) |
| `anareiki-web` | 0008-anareiki-web:latest | 127.0.0.1:31008 | healthy, 7 semanas |

Uso de recursos: todos livianos (77-208 MiB de RAM cada uno, <0.3% CPU en
el snapshot). Ningún contenedor cerca de su límite de memoria.

**Proyectos `docker compose ls`:**

| Proyecto | Servicios | Config |
|---|---|---|
| `wapsell` | 2 (app + api) | `/opt/wapsell/docker-compose.yml` |
| `fmonfasani` | 1 | `/opt/fmonfasani/docker-compose.yml` |
| `0008-anareiki` | 1 | `/infra/projects/0008-anareiki/docker-compose.yml` |
| `0009-catalaxia` | 1 | `/infra/projects/0009-catalaxia/docker-compose.yml` |
| `001-luzguffanti` | 1 | `/infra/projects/001-luzguffanti/docker-compose.yml` |

Nota: el proyecto `wapsell` solo tiene 2 servicios (app + api) — no aparece
un servicio de Postgres/Redis propio corriendo pese a que existen volúmenes
`wapsell_wapsell-db` y `pipaas_pipaas_pg`/`pipaas_pg_data`/`pipaas_redis_data`
(de un despliegue anterior, probablemente). Vale confirmar si la API está
usando esos datos vía una conexión externa o si corre sin persistencia real
ahora mismo.

**Volúmenes:** ~30 volúmenes con nombre, la mayoría con prefijo de proyecto
reconocible (`pipaas_*`, `wapsell_*`, `webshooks_*`, `anareiki_*`,
`agencia-web-b2b_*`, `coolify-*`, `backend_*`). Varios con hashes
sin nombre (probablemente volúmenes anónimos huérfanos de contenedores ya
borrados) — candidatos a `docker volume prune`, a revisar antes de borrar.

**`/opt/` (proyectos de nivel superior en disco, fuera de Coolify):**
`agencia-web-b2b`, `fmonfasani`, `scraper_ml_inmuebles`, `wapsell`,
`waseller` (repo legacy pre-rename), `webshooks`, y un
`webshooks.bak-20260515-0008` (backup viejo, candidato a limpieza si ya no
hace falta).

## Reverse proxy — nginx (único, sin Traefik/Caddy)

nginx 1.24.0, 22 vhosts en `sites-enabled/`. Tres grupos:

**Gestionados por Coolify** (puertos `31001-31008`, vhosts autogenerados,
todos con el patrón `proxy_pass http://127.0.0.1:3100X`):
`luzguffanti.com` + `media.luzguffanti.com`, `forrajeria.webshooks.com`,
`zapateria.webshooks.com` (+ alias `tienda`, `aldana`, `valentino`,
`electronica`, `api.argfy.com`, `argfy.com` — comparten certificado con
`mateo.webshooks.com`), `webshooks.com` (estático), `coolify.webshooks.com`
(el propio panel de Coolify), `anamurat.online`.

**Gestionados a mano (wapsell/pipaas)**, con comentarios explicando el
diseño (SameSite cookies entre subdominios, HMAC de Meta sin buffering,
etc.) — código prolijo, vale la pena preservar ese nivel de detalle en lo
que arme `devps`:
`wapsell.com` + `app.wapsell.com` → `:3010`, `api.wapsell.com` +
`pipaas.com` (legacy, mismo backend que api.wapsell.com) → `:8500`.

**Sueltos:** `fmonfasani.blog`, `default` (catch-all 404).

## TLS (certbot) — 11 certificados

Todos ECDSA, renovación automática asumida vía el timer de certbot.

| Dominio | Vence en |
|---|---|
| **`zapateria.webshooks.com`** (cubre 7 dominios) | **7 días — 2026-08-15** ⚠️ |
| `wapsell.com` | 26 días |
| `api.wapsell.com` | 33 días |
| `app.wapsell.com` | 33 días |
| `mateo.webshooks.com` (cubre 4 dominios) | 35 días |
| `anamurat.online` | 81 días |
| `pipaas.com` | 81 días |
| `luzguffanti.com`, `media.luzguffanti.com` | 63-64 días |
| `webshooks.com`, `coolify.webshooks.com`, `fmonfasani.blog` | 64 días |

## Coolify

`/data/coolify` existe, contenedores `coolify-db`/`coolify-redis` con
volumen propio. No apareció ningún contenedor con nombre literal
`coolify` en el filtro de `docker ps` que usé (puede estar corriendo con
otro naming interno) — para el inventario completo de Coolify hace falta
mirar desde su propio dashboard, no solo desde `docker ps`.

## systemd / cron

Servicios relevantes activos: `docker.service`, `nginx.service`. Ni Caddy
ni Traefik como servicio.

Cron de root:
```
0 8 * * *   POST a localhost:31008/api/reminders (anareiki)
30 3 * * *  backup-postgres.sh (aparece DOS VECES — ver hallazgos)
0 */6 * * * backup-db.sh → wapsell-backup.log
```

## Hallazgos y acciones sugeridas

1. **⚠️ Urgente: renovar `zapateria.webshooks.com`** — vence en 7 días,
   cubre 7 dominios de un mismo cliente. Si el timer de certbot no lo
   renueva solo antes, hay que intervenir a mano.
2. **Reglas de firewall sin dueño**: `9000/tcp` y `8080/tcp` están
   permitidos mundialmente en ufw pero nada escucha ahí ahora. O hay un
   servicio caído que debería estar arriba, o son reglas viejas — vale la
   pena confirmar antes de que `devps` empiece a reservar puertos nuevos,
   para no asumir que están libres.
3. **3 vhosts de Coolify (`forrajeria`, `zapateria`, `tienda`) apuntan a
   puertos (31002-31004) que no aparecen escuchando** en la captura — o
   esos sitios están caídos ahora mismo (valdría un `curl` de chequeo), o
   Coolify los levanta bajo demanda.
4. **Cron duplicado**: `backup-postgres.sh` de wapsell aparece dos veces
   idéntico en el crontab de root — probablemente un cron job registrado
   dos veces por error (correr dos backups simultáneos no rompe nada grave,
   pero es ruido a limpiar).
5. **wapsell sin Postgres/Redis propio corriendo** pese a tener volúmenes
   de datos — confirmar si es intencional (¿usa un Postgres externo?) antes
   de asumir el patrón para `devps`.
6. **Volúmenes Docker anónimos (hashes largos, sin nombre de proyecto)** —
   candidatos a limpieza, pero requieren confirmar que no pertenecen a
   contenedores parados (no vistos en `docker ps -a`, que sí incluye
   parados) antes de borrar.
7. **Puertos ya ocupados que `devps` debe evitar al asignar nuevos**:
   `3010, 3020, 5432, 8500, 31001, 31008` (+ probablemente `31002-31007`
   aunque no se vieron escuchando en este snapshot) — el rango
   `31000-31999` es "territorio de Coolify", mejor que `devps` reserve un
   rango totalmente distinto (ej. `40000-40999`) para no competir por el
   mismo espacio.
