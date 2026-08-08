# GitHub Webhooks Setup

Configurar auto-deploy automático cuando se pushea a tu repositorio.

## Cómo Funciona

```
GitHub → Push evento → POST /webhooks/github/{project_name}
                          ↓
                    Validar firma (HMAC-SHA256)
                          ↓
                    Extraer rama, repo, commit
                          ↓
                    ¿Rama = project.git_ref?
                          ↓ Sí
                    Deployer (git pull + docker compose up)
                          ↓
                    Registrar evento
```

## Step 1: Generar Webhook Secret

```bash
# Genera un secreto aleatorio (solo una vez)
python3 -c "import secrets; print(secrets.token_hex(32))"
# Ejemplo: a1b2c3d4e5f6... (64 caracteres)
```

Guarda este secret en la VPS:

```bash
ssh root@89.167.96.239

# Agrega a /opt/devps/agent.env
echo "DEVPS_WEBHOOK_SECRET=a1b2c3d4e5f6..." >> /opt/devps/agent.env

# Reinicia el servicio
sudo systemctl restart devps-agent
```

## Step 2: Crear Webhook en GitHub

En tu repositorio de GitHub:

1. **Settings** → **Webhooks** → **Add webhook**

2. Completa:
   - **Payload URL**: `https://devps.webshooks.com/webhooks/github/{project_name}`
     - Reemplaza `{project_name}` con el nombre del proyecto en devps
     - Ejemplo: `https://devps.webshooks.com/webhooks/github/myapp`
   
   - **Content type**: `application/json`
   
   - **Secret**: (el secret que generaste en Step 1)
   
   - **Events**: 
     - Desmarca "Send me everything"
     - Selecciona solo: **Pushes**
   
   - **Active**: ✅ Asegúrate que esté marcado

3. Click **Add webhook**

## Step 3: Probá el Webhook

Luego de crear el webhook, GitHub muestra una sección "Recent Deliveries":

1. Haz un git push a la rama configurada
2. Ve a Settings → Webhooks → Tu webhook → Recent Deliveries
3. Debería haber un entry con status ✅ 200

Si ves ❌:
- **401**: Token de GitHub inválido
- **400**: Payload inválido o secret incorrecto
- **404**: URL del webhook es incorrecta o proyecto no existe
- **500**: Error interno devps (check logs: `curl https://devps.webshooks.com/projects/{name}/logs`)

## Qué Pasa en un Push

### Push a la rama Correcta (Auto-deploy)

```bash
git push origin main
```

**Resultado**:
1. GitHub envía payload a `/webhooks/github/myapp`
2. devps valida la firma
3. Extrae: rama=main, repo=https://github.com/user/repo.git, commit=abc123
4. Chequea: ¿myapp está configurado para main? → Sí ✅
5. Triggea `POST /projects/myapp/deploy` automáticamente
6. Registra evento: `webhook_deploy: auto-deploy from webhook, git_ref=main`

**Donde ver**:
- Dashboard: https://devps.webshooks.com/dashboard/projects/myapp
- Logs: `hzploy logs myapp`
- Eventos: `hzploy logs myapp` o en dashboard

### Push a Otra Rama (Skip)

```bash
git push origin feature/new-thing
```

**Resultado**:
1. GitHub envía payload
2. devps valida
3. Extrae: rama=feature/new-thing
4. Chequea: ¿myapp usa feature/new-thing? → No ✗
5. **Skip** (sin deployer)
6. Registra evento: `webhook: skipped, branch feature/new-thing not configured`

## Configuración Avanzada

### Múltiples Ramas

Si quieres que auto-deployed tanto `main` como `staging`:

```bash
# Opción 1: Crear 2 proyectos
devps up myapp https://github.com/user/repo.git \
  --ref main \
  --service web=3000 \
  --primary web \
  --domain myapp.com

devps up myapp-staging https://github.com/user/repo.git \
  --ref staging \
  --service web=3000 \
  --primary web \
  --domain myapp-staging.dev

# Luego, 2 webhooks en GitHub:
# - https://devps.webshooks.com/webhooks/github/myapp
# - https://devps.webshooks.com/webhooks/github/myapp-staging
```

### Deshabilitar Auto-Deploy

En GitHub Settings → Webhooks, selecciona el webhook → **Delete**.

O temporalmente, desactiva "Active" sin borrarlo.

## Troubleshooting

### "Invalid webhook signature"

**Causa**: Secret en GitHub no coincide con DEVPS_WEBHOOK_SECRET en la VPS.

**Solución**:
1. Regenera secret: `python3 -c "import secrets; print(secrets.token_hex(32))"`
2. Actualiza en GitHub webhook settings
3. Actualiza en `/opt/devps/agent.env` 
4. `sudo systemctl restart devps-agent`

### "Project not found"

**Causa**: El URL tiene el nombre de proyecto incorrecto.

**Check**:
```bash
hzploy list  # Ver nombres exactos
```

**Fix**: Actualiza GitHub webhook URL.

### "Branch not configured for auto-deploy"

**Causa**: Empujaste a una rama que no está configurada.

**Información**: Solo la rama configurada en `--ref` al crear el proyecto auto-despliega.

**Ejemplo**: Si creaste el proyecto con `--ref main`, solo `git push origin main` despliega.

**Para agregar más ramas**: Crea proyectos adicionales con diferentes refs.

### Deploy Falló (502 Error)

**Causa**: Error en docker compose, repo inaccesible, etc.

**Solución**:
1. `hzploy logs myapp --tail 100` — ver detalles del error
2. `hzploy logs myapp | grep ERROR`
3. Arregla el problema
4. `git push` nuevamente (o manualmente: `hzploy up myapp ...`)

## Seguridad

- **Firma validada**: GitHub + devps usan HMAC-SHA256
- **No hay token expuesto**: El secret nunca viaja en URLs, solo en headers
- **Rate limiting**: Próximamente (future epic)
- **Log audit**: Cada webhook registra qué pasó

## Flujo Completo: Ejemplo

```bash
# 1. Setup inicial
git clone https://github.com/user/myapp.git
cd myapp

# 2. Deploy primera vez (desde CLI)
hzploy up myapp https://github.com/user/myapp.git \
  --ref main \
  --service web=3000 \
  --primary web \
  --domain myapp.com

# 3. Generar secret
python3 -c "import secrets; print(secrets.token_hex(32))"
# → a1b2c3d4e5f6...

# 4. Agregar a VPS
ssh root@89.167.96.239
echo "DEVPS_WEBHOOK_SECRET=a1b2c3d4e5f6..." >> /opt/devps/agent.env
sudo systemctl restart devps-agent
exit

# 5. Crear webhook en GitHub
# https://github.com/user/myapp/settings/hooks
# Payload URL: https://devps.webshooks.com/webhooks/github/myapp
# Secret: a1b2c3d4e5f6...
# Events: Pushes
# Active: ✅

# 6. Probar
echo "# Test" >> README.md
git add README.md
git commit -m "Test webhook"
git push origin main

# 7. Verificar
# Dashboard: https://devps.webshooks.com/dashboard/projects/myapp
# Debería mostrar deployment reciente

# Próximos pushes: Auto-deployan sin hacer nada 🎉
```

## Próximo: Rollback Automático

Cuando una épica de "auto-recovery" esté lista, podrá:
- Health checks cada 30s
- Si container se cae → auto-restart
- Si CPU > 80% → alertar
- Si múltiples crashes → rollback a commit anterior

Por ahora: manual via `hzploy restart myapp` o `hzploy up myapp ... --ref <commit-anterior>`.

## API Reference

### Webhook Endpoint

```
POST /webhooks/github/{project_name}
Headers:
  X-Hub-Signature-256: sha256=<hmac>
  Content-Type: application/json

Body: GitHub push payload
```

### Response

**200 OK - Deployed**:
```json
{
  "status": "deployed",
  "project": "myapp",
  "branch": "main",
  "commit": "abc123...",
  "git_sha": "abc123def456..."
}
```

**200 OK - Skipped**:
```json
{
  "status": "skipped",
  "reason": "branch staging not configured for auto-deploy",
  "project": "myapp"
}
```

**400 Bad Request**:
```json
{"detail": "Invalid webhook signature"}
```

or

```json
{"detail": "Invalid GitHub payload: missing repository or ref"}
```

## Documentación

- [GitHub Webhooks Docs](https://docs.github.com/en/developers/webhooks-and-events/webhooks/about-webhooks)
- [GitHub Push Event Payload](https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#push)
- devps API: [API_EXAMPLES.md](API_EXAMPLES.md)
