# hzploy — CLI for devps

Herramienta de línea de comandos para deployar y gestionar proyectos en devps desde terminal (VPS, Mac, Linux, Windows).

## Instalación

### Opción 1: Descargar el script (recomendado)

```bash
# Descargar
curl -o hzploy https://raw.githubusercontent.com/fmonfasani/devps/main/cli/hzploy
chmod +x hzploy

# Usar
./hzploy login https://devps.webshooks.com <token>
./hzploy list
```

### Opción 2: Python directo

```bash
python cli/hzploy login https://devps.webshooks.com <token>
python cli/hzploy list
```

### Opción 3: Agregar al PATH

```bash
# Copiar a ~/.local/bin/ (o /usr/local/bin/ si eres root)
cp cli/hzploy ~/.local/bin/
chmod +x ~/.local/bin/hzploy

# Ahora funciona desde cualquier lado
hzploy login https://devps.webshooks.com <token>
hzploy list
```

## Configuración

### Via `hzploy login` (recomendado)

```bash
hzploy login https://devps.webshooks.com <tu-token>
```

Guarda en `~/.hzploy/config` (chmod 600 para seguridad).

### Via Variables de Entorno

```bash
export DEVPS_URL=https://devps.webshooks.com
export DEVPS_TOKEN=<tu-token>

hzploy list  # Usa env vars, no ~/.hzploy/config
```

Las env vars **siempre prevalecen** sobre `~/.hzploy/config`.

## Comandos

### 1. `hzploy login <url> <token>`

Guardar credenciales localmente.

```bash
hzploy login https://devps.webshooks.com abc123def456...
# saved config to /Users/user/.hzploy/config
```

### 2. `hzploy list`

Listar todos los proyectos.

```bash
hzploy list
# OUTPUT:
# myapp                devps    deployed    myapp.example.com  web:40001, api:40002
# legacy               adopted  adopted     old.example.com    main:3000
```

### 3. `hzploy up <name> <repo_url> [options]`

Deployar un proyecto desde git.

**Ejemplo básico:**

```bash
hzploy up myapp https://github.com/user/myapp.git \
  --service web=3000 \
  --primary web \
  --domain myapp.example.com
```

**Parámetros:**

| Flag | Descripción | Defecto |
|------|-------------|---------|
| `<name>` | Nombre del proyecto (único en devps) | - |
| `<repo_url>` | URL del repositorio git | - |
| `--ref <rama>` | Rama/tag a clonar | `main` |
| `--service name=puerto` | Servicio y puerto contenedor (repetible) | - |
| `--primary <name>` | Qué servicio recibe el dominio | - |
| `--domain <dominio>` | Dominio público (SSL automático) | - |
| `--compose-file <path>` | Path a docker-compose.yml | `docker-compose.yml` |
| `--env-file <path>` | Path a .env en la VPS | - |

**Ejemplo con múltiples servicios:**

```bash
hzploy up myapp https://github.com/user/myapp.git \
  --ref develop \
  --service web=3000 \
  --service api=8000 \
  --primary web \
  --domain myapp.dev \
  --compose-file docker/compose.prod.yml
```

**Ejemplo con env-file (secretos pre-existentes):**

```bash
# Primero, subes el .env a la VPS (vía dashboard o SSH)
# /opt/devps/secrets/myapp.env

hzploy up myapp https://github.com/user/myapp.git \
  --service web=3000 \
  --primary web \
  --domain myapp.example.com \
  --env-file /opt/devps/secrets/myapp.env
```

### 4. `hzploy adopt <name> <container_name> [--domain <dominio>]`

Registrar un container ya corriendo (ej: Coolify) bajo devps.

```bash
# Primero, ves qué containers corren
docker ps
# CONTAINER ID   NAMES
# abc123         coolify_myapp_1

# Lo adoptas
hzploy adopt myapp coolify_myapp_1

# Opcional: le asignas un dominio (no cambia traffic aún)
hzploy adopt myapp coolify_myapp_1 --domain myapp.example.com

# Más tarde, cuando quieras hacer cutover:
# hzploy up myapp <repo_url> ... --domain myapp.example.com
# (esto mueve el traffic a devps)
```

### 5. `hzploy logs <name> [--tail <lineas>]`

Ver logs del último container.

```bash
hzploy logs myapp
# [output de 200 últimas líneas]

hzploy logs myapp --tail 50
# [últimas 50 líneas]

hzploy logs myapp --tail 1000 | grep ERROR
# [filtrar en tu terminal]
```

### 6. `hzploy restart <name>`

Reiniciar el proyecto (docker compose restart).

```bash
hzploy restart myapp
# {'status': 'restarted'}
```

### 7. `hzploy rm <name>`

Deregistrar proyecto de devps (NO detiene containers, NO borra datos).

```bash
hzploy rm myapp
# {'status': 'deregistered'}

# El container sigue corriendo, pero devps ya no lo maneja
```

## Ejemplos Completos

### Caso 1: Deploy simple (app Python + Redis)

```bash
# Archivo: docker-compose.yml
# services:
#   web:
#     image: python:3.11
#     ports:
#       - "${DEVPS_PORT_WEB:-3000}:3000"
#   redis:
#     image: redis:7
#     ports:
#       - "${DEVPS_PORT_REDIS:-6379}:6379"

hzploy up myapp https://github.com/user/myapp.git \
  --service web=3000 \
  --service redis=6379 \
  --primary web \
  --domain myapp.com
```

### Caso 2: Deploy desde rama de staging

```bash
hzploy up myapp-staging https://github.com/user/myapp.git \
  --ref staging \
  --service web=3000 \
  --primary web \
  --domain myapp-staging.dev
```

### Caso 3: Monitoreo en loop

```bash
# Check status cada 10 segundos
while true; do
  clear
  echo "=== $(date) ==="
  hzploy list
  hzploy logs myapp --tail 10
  sleep 10
done
```

### Caso 4: Deploy con .env pre-existente

```bash
# Primero, guardas secretos en la VPS (vía dashboard /dashboard/setup)
# O por SSH:
# ssh root@vps "cat > /opt/devps/secrets/myapp.env << 'EOF'
# DATABASE_URL=postgres://...
# API_KEY=secret123
# EOF"

# Luego, deployas usando ese archivo
hzploy up myapp https://github.com/user/myapp.git \
  --service web=3000 \
  --primary web \
  --domain myapp.com \
  --env-file /opt/devps/secrets/myapp.env
```

## Obtener el Token

Tu `DEVPS_TOKEN` está en el dashboard. Opciones:

1. **Dashboard**: https://devps.webshooks.com/dashboard → Settings (future)
2. **SSH a la VPS**: 
   ```bash
   ssh root@89.167.96.239
   cat /opt/devps/agent.env | grep DEVPS_TOKEN
   ```
3. **Env var ya existe**: 
   ```bash
   echo $DEVPS_TOKEN
   ```

## Troubleshooting

### "not logged in"

```bash
# ✅ Opción 1: Hacer login
hzploy login https://devps.webshooks.com your_token

# ✅ Opción 2: Usar env vars
export DEVPS_URL=https://devps.webshooks.com
export DEVPS_TOKEN=your_token
hzploy list

# ✅ Opción 3: Verificar config
cat ~/.hzploy/config
```

### "HTTP 502: git error"

El repo URL es inválido o no es accesible desde la VPS.

```bash
# Verificar que el URL funciona
git clone https://github.com/user/repo.git /tmp/test
# Si falla → URL inválido o permisos

# Si usas repo privado, agrega SSH key a la VPS
ssh -i ~/.ssh/id_ed25519 root@vps
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
```

### "HTTP 502: docker compose failed"

El docker-compose.yml tiene un error o las imágenes no existen.

```bash
# Ver detalles
hzploy logs myapp --tail 100 | grep ERROR

# Validar compose localmente
docker compose -f docker-compose.yml config
```

### "HTTP 404: not found"

El proyecto no existe. Usa `hzploy list` para ver los existentes.

```bash
hzploy list
# Si no está en la lista → usa "up" para crearlo
```

## Configuración Avanzada

### Alias en .bashrc / .zshrc

```bash
alias hzploy="python ~/.local/bin/hzploy"
# O si lo copiaste a /usr/local/bin:
alias hzploy="/usr/local/bin/hzploy"
```

### Script de Deploy Automático

```bash
#!/bin/bash
# deploy.sh

set -e

REPO="https://github.com/user/myapp.git"
PROJECT="myapp"
DOMAIN="myapp.com"

echo "Deploying $PROJECT..."
hzploy up $PROJECT $REPO \
  --service web=3000 \
  --primary web \
  --domain $DOMAIN

echo "✅ Deploy complete!"
hzploy logs $PROJECT --tail 20
```

### Integración con GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to devps

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy
        env:
          DEVPS_URL: ${{ secrets.DEVPS_URL }}
          DEVPS_TOKEN: ${{ secrets.DEVPS_TOKEN }}
        run: |
          python cli/hzploy up myapp ${{ github.repository }} \
            --ref ${{ github.sha }} \
            --service web=3000 \
            --primary web \
            --domain myapp.com
```

## Seguridad

- **Config local**: `~/.hzploy/config` guardado con `chmod 600` (solo lectura usuario)
- **Env vars**: Precedencia sobre config → usa para CI/CD
- **Tokens**: Nunca commitees a git (usa secrets en GitHub Actions)
- **HTTPS solo**: El CLI valida SSL por defecto

## Límites Conocidos

- No es posible deployar desde URL privados sin configurar SSH en la VPS
- El CLI no valida docker-compose.yml (devps lo hace en la VPS)
- No hay progress bar (futures: agregar con emoji/spinner)
- Config guardado en disco (futures: usar keychain)

## Roadmap

- [ ] Progress bar animado
- [ ] Credentials en system keychain (macOS, Linux, Windows)
- [ ] Tab completion (bash, zsh, fish)
- [ ] JSON output flag (`--json`)
- [ ] Watch mode (`hzploy watch myapp`)
- [ ] Shell login interactivo

## License

MIT (same as devps)
