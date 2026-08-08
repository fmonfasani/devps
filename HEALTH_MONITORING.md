# Health Monitoring & Auto-Recovery

devps monitorea automáticamente la salud de los contenedores y ejecuta auto-restarts cuando es necesario, con protecciones contra restart loops.

## How It Works

```
Background Loop (every 30s)
    ↓
Check container health (running/dead/unhealthy)
    ↓
If dead → restart (rate limited to 5/hour)
    ↓
If restart fails repeatedly → exponential backoff + alert
```

## Health Check States

- **running**: Container está arriba y saludable
- **dead**: Container no está corriendo
- **unhealthy**: Health check falló (si está configurado en docker-compose.yml)
- **unknown**: Nunca se ejecutó un health check

## Rate Limiting

Auto-restart está limitado a **5 restarts por hora** por proyecto para prevenir restart loops.

Si el contenedor falla más de 5 veces en una hora:
1. Los restarts adicionales son bloqueados
2. Se registra evento: `rate limit exceeded (5/hour), skipping restart`
3. El evento se ve en dashboard y en `hzploy logs`

## Exponential Backoff

Si los health checks fallan repetidamente, devps entra en backoff:

| Fallos Consecutivos | Delay | Descripción |
|---|---|---|
| 1-2 | 30 segundos | Health check intenta nuevamente cada 30s |
| 3-4 | 2 minutos | Enter backoff extended (5 intentos posibles en 10 min) |
| 5+ | 30 minutos | Enter backoff long-term (manual intervention likely needed) |

**Cómo funciona**:
- Cada fallo consecutivo incrementa el contador
- Se salta el health check durante el período de backoff
- Al recuperarse (health check exitoso), el contador se resetea

## Alerting

Devps envía alertas en dos hitos críticos:

### Alert: 3 Failures (2min backoff iniciado)

Cuando el health check falla 3 veces seguidas, se envía:

```
🚨 Health check failed 3 consecutive times.
Entering extended backoff (2 minutes).
```

### Alert: 5+ Failures (30min backoff iniciado)

Cuando el health check falla 5+ veces, se envía:

```
🚨 Health check failed 5+ times.
Entering long backoff (30 minutes).
Manual intervention may be needed.
```

## Configure Alerting

### Slack

Configura en `/opt/devps/agent.env`:

```bash
DEVPS_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

Obtén el webhook URL en Slack:
1. Workspace → Settings & administration → Manage apps
2. Custom Integrations → Incoming Webhooks → Add New
3. Selecciona channel
4. Copy URL

Reinicia devps:
```bash
sudo systemctl restart devps-agent
```

### Email

Configura en `/opt/devps/agent.env`:

```bash
DEVPS_ALERT_EMAIL_TO=admin@example.com
DEVPS_ALERT_EMAIL_FROM=alerts@devps.local
DEVPS_ALERT_SMTP_HOST=smtp.example.com
DEVPS_ALERT_SMTP_PORT=587
```

Reinicia:
```bash
sudo systemctl restart devps-agent
```

## Health Check Dashboard

En el dashboard devps, cada proyecto muestra:

**Health Status**
- Estado actual (running/dead/unhealthy/unknown)
- Número de restarts en la última hora
- Timestamp del último restart
- Timestamp del último health check

**Ejemplo**:
```
Status: running
Restarts (1h): 2
Last Restart: 2025-08-08T14:35:12Z
Last Check: 2025-08-08T14:38:42Z
```

## Configuring Health Checks

Para que devps detecte si un contenedor está "unhealthy", configura healthcheck en `docker-compose.yml`:

```yaml
services:
  web:
    image: myapp:latest
    ports:
      - "3000:3000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 10s
      timeout: 5s
      retries: 2
```

Devps chequea el health status cada 30 segundos. Si es unhealthy:
- Log event `health_check: container unhealthy`
- NO auto-restart (solo log, requiere manual intervention)

## API Reference

### Get Health Status

```bash
curl -H "Authorization: Bearer $DEVPS_TOKEN" \
  https://devps.webshooks.com/projects/{name}/health
```

**Response**:
```json
{
  "project_name": "myapp",
  "health_status": "running",
  "restart_count": 2,
  "last_restart_at": "2025-08-08T14:35:12Z",
  "last_health_check_at": "2025-08-08T14:38:42Z",
  "status": "deployed",
  "managed_by": "devps"
}
```

### Get Health Status (All Projects)

```bash
curl -H "Authorization: Bearer $DEVPS_TOKEN" \
  https://devps.webshooks.com/projects
```

**Response**: Array de health status objects.

## Troubleshooting

### Container Keeps Restarting

**Cause**: Loop de restarts. El contenedor inicia pero inmediatamente falla.

**Diagnosis**:
1. Ver logs: `hzploy logs myapp --tail 50`
2. Ver health events: Dashboard → Project → Event history (buscar `auto_restart`)
3. Verificar estado actual: `curl -s -H "Authorization: Bearer ..." https://devps.webshooks.com/projects/myapp/health`

**Solution**:
1. Si es un bug en código: Fix, push, webhook redeploy
2. Si es infraestructura: Investigar en el container
3. Si es recurso: Aumentar memoria/CPU en docker-compose.yml, redeploy

Si alcanzó rate limit (5 restarts/hora), espera 1 hora o:
```bash
# Manual restart
docker restart devps_myapp_1

# Manual redeploy
hzploy up myapp https://github.com/user/repo.git --ref main ...
```

### Health Check Failures Detected

**Symptom**: Ves alertas de "health check failed 3x", pero container está corriendo.

**Cause**: Algo temporal (network blip, transient resource issue) causó fallos.

**Action**:
1. Espera el backoff (entra automáticamente, no requiere acción)
2. Si persiste después de varias horas: Investigar logs + healthcheck endpoint
3. Reiniciar manualmente si es urgente: `docker restart devps_myapp_1`

### "Entering long backoff (30 minutes)"

**Meaning**: Hubo 5+ health check failures. Manual intervention posiblemente necesaria.

**Next steps**:
1. SSH a la VPS
2. Ver logs: `docker logs devps_myapp_1`
3. Verificar recursos: `docker stats devps_myapp_1`
4. Restart manual: `docker restart devps_myapp_1`
5. O redeploy: `hzploy up myapp ... --ref ...`

## Integration with Migrations

Si estás adoptando un proyecto (migration en progreso):

- **Durante paralleled phase**: Health checks solo para devps-managed projects. Proyectos adopted se monitorean manualmente.
- **Después de cutover**: Cambia `managed_by` a devps, automática health checks comienzan.

Ver: [MIGRATION.md](docs/MIGRATION.md)

## Performance Impact

Health checks corren cada 30 segundos con muy bajo overhead:

- ~10ms por project para `docker inspect`
- Network overhead: ~1KB por request
- No afecta aplicación (solo lee estado, no envia tráfico)

## Future Enhancements

- Custom health check expressions (e.g., "if CPU > 80%")
- Webhook notifications (custom URL on restart)
- Retry strategies (exponential backoff en restart, no solo health checks)
- Cost anomaly detection (auto-scale down if not used)

## See Also

- [WEBHOOKS_SETUP.md](WEBHOOKS_SETUP.md) — Auto-deploy on git push
- [API_EXAMPLES.md](API_EXAMPLES.md) — Full API reference
- docs/[DEPLOYMENT_AND_OPERATIONS.md](docs/DEPLOYMENT_AND_OPERATIONS.md) — Operations guide
