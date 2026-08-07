# Subir un proyecto nuevo a la VPS

Asume que el agente ya está corriendo (ver `infra/scripts/bootstrap.sh` /
`docs/ARCHITECTURE.md`) y que tenés `DEVPS_TOKEN`.

## Opción A — por CLI, ahora mismo

```bash
python cli/hzploy login https://TU-DOMINIO-DEL-AGENTE <DEVPS_TOKEN>
# (hasta que el agente tenga su propio dominio público, corré esto
# encadenado a un túnel SSH: ssh -L 9400:127.0.0.1:9400 root@89.167.96.239,
# y usá http://127.0.0.1:9400 como URL)

python cli/hzploy up mi-proyecto https://github.com/tuusuario/mi-repo.git \
    --service web=3000 \
    --primary web \
    --domain mi-proyecto.tudominio.com
```

## Opción B — desde GitHub Actions (recomendado para lo tuyo)

En el repo del proyecto, agregar `.github/workflows/deploy.yml`:

```yaml
name: Deploy
on:
  push: { branches: [main] }
  workflow_dispatch: {}

jobs:
  deploy:
    uses: fmonfasani/devps/.github/workflows/deploy-reusable.yml@main
    with:
      project_name: mi-proyecto
      repo_url: https://github.com/tuusuario/mi-repo.git
      services: '{"web": 3000}'
      primary_service: web
      domain: mi-proyecto.tudominio.com
    secrets:
      HETZNER_HOST: ${{ secrets.HETZNER_HOST }}
      HETZNER_USER: ${{ secrets.HETZNER_USER }}
      HETZNER_SSH_KEY: ${{ secrets.HETZNER_SSH_KEY }}
      DEVPS_TOKEN: ${{ secrets.DEVPS_TOKEN }}
```

Mientras no haya una Organización de GitHub con secrets compartidos, cada
repo necesita sus propias copias de esos 4 secrets (los mismos valores que
ya usás para el agente). Con una Org, se cargan una sola vez y `secrets:
inherit` alcanza.

## Qué pasa en el medio

1. El agente clona (o actualiza) el repo en `/opt/devps/projects/<nombre>`.
2. Asigna un puerto libre del rango `40000-40999` por cada servicio
   declarado (o reusa el que ya tenía, en un redeploy).
3. `docker compose up -d --build`.
4. Si mandaste `domain`, escribe el vhost de nginx y pide el certificado
   con certbot (la primera vez; los redeploys solo actualizan el vhost).
5. Queda registrado — `hzploy list`, o `/dashboard` (login con
   `DEVPS_TOKEN`) lo muestra con su puerto, dominio, estado, y el historial
   completo de eventos (incluidos los deploys que fallaron, no solo el
   estado actual).
