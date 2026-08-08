# Product Backlog

> Ideas futuras, mejoras, integraciones y roadmap de largo plazo.
> Priorizado pero no comprometido (puede cambiar).

## Backlog Futuro (No Comprometido)

### Feature: Git Webhooks

**Descripción**: Deploy automático cuando se pushea a main/rama especificada

**Historias de Usuario**:
- HU: "Como dev, quiero que devps despliegue automáticamente cuando hago push"
- Criterios: URL webhook en proyecto, validación de payload (GitHub signature), deploy automático, notificación de éxito/fallo

**Estimación**: 8 SP  
**Prioridad**: P1 (high)  
**Complejidad**: Media (webhook validation, signature checking)

**Consideraciones**:
- Usar GitHub webhook secret
- Validar X-Hub-Signature-256
- Queue de deploys si se solapan
- Limitar a commits en rama específica

---

### Feature: Health Checks & Auto-Recovery

**Descripción**: Monitoreo automático de containers y restart si se caen

**Historias de Usuario**:
- "Como ops, quiero que devps detecte si un container se cayó y lo reinicie automáticamente"
- "Como dev, quiero ver el health status de mi proyecto en el dashboard"

**Estimación**: 13 SP  
**Prioridad**: P2 (medium)  
**Complejidad**: Media (polling, state tracking)

**Componentes**:
1. Health check loop (cada 30s)
2. State machine (running → dead → restarting → running)
3. Metrics (uptime, restart count)
4. Alertas (Slack/email)

**Open Questions**:
- ¿Restart automático o solo alertar?
- ¿Limitar reintentos? (ej: máx 3 por hora)
- ¿Notificar al user?

---

### Feature: Automated Backups

**Descripción**: Backups diarios de registry.db y secrets

**Historias de Usuario**:
- "Quiero poder recuperarme de una corrupción de datos"
- "Necesito auditar cambios históricos"

**Estimación**: 5 SP  
**Prioridad**: P2 (medium)  
**Complejidad**: Baja

**Diseño**:
- Cron job: cada 6 horas
- Backup local: `/opt/devps/backups/registry.db.YYYY-MM-DD-HH.gz`
- Retención: últimas 7 días
- S3 (future): replicar a AWS S3 para durability

**Consideraciones**:
- Exclusiones: secrets no encryptados en S3 (solo local)
- Verificación: checksum de cada backup
- Alertas si backup falla

---

### Feature: Logs Centralizados

**Descripción**: Buscar y filtrar logs de todos los proyectos en un lugar

**Historias de Usuario**:
- "Como ops, quiero buscar logs por timestamp, proyecto, nivel de error"
- "Quiero ver logs de múltiples proyectos simultáneamente"

**Estimación**: 13 SP  
**Prioridad**: P3 (low)  
**Complejidad**: Alta

**Opciones**:
1. **Simple**: SQLite con logs (query-able)
2. **Medium**: ELK stack (Elasticsearch + Logstash + Kibana)
3. **Advanced**: Datadog/New Relic (SaaS)

**Recomendación**: Opción 1 para v1 (simple), escalar a ELK después

---

### Feature: Multi-User & Roles

**Descripción**: Soporte para múltiples usuarios con permisos granulares

**Historias de Usuario**:
- "Como admin, quiero invitar a otros users con rol de 'deployer'"
- "Como viewer, quiero ver proyectos pero no deployarlos"

**Estimación**: 21 SP  
**Prioridad**: P3 (low)  
**Complejidad**: Alta (RBAC, audit log)

**Roles**:
- `admin`: Todo (users, projects, settings)
- `deployer`: Crear/actualizar/reiniciar proyectos
- `viewer`: Solo lectura

**Cambios necesarios**:
- Tabla `users` (email, password_hash, role)
- Tabla `project_access` (user_id, project_id, role)
- Auth por email + password (como ahora) O OIDC (future)
- Audit log de cada acción

---

### Feature: Marketplace de Templates

**Descripción**: Boilerplates listos para deployar (Next.js + API, Django, etc.)

**Historias de Usuario**:
- "Como dev nuevo, quiero deployar un Next.js starter sin escribir código"
- "Como community, quiero compartir un template para mi stack"

**Estimación**: 13 SP  
**Prioridad**: P3 (low)  
**Complejidad**: Media

**Estructura**:
```
devps-templates/
├── next-api/
│   ├── docker-compose.yml
│   ├── .env.example
│   └── README.md
├── django-postgres/
├── fastapi-redis/
└── ...
```

**Flow**:
1. Dashboard: "Use template" button
2. Input: app name
3. Clone from devps-templates repo
4. Deploy automáticamente

---

### Feature: Rollback UI

**Descripción**: Volver a un commit anterior con 1 click

**Historias de Usuario**:
- "Última versión rompió la app, quiero volver a main~1"
- "Mostrar diff de qué cambió"

**Estimación**: 8 SP  
**Prioridad**: P2 (medium)  
**Complejidad**: Baja

**UI**:
- Dashboard: "Recent commits" dropdown
- Click: Confirmar rollback
- Backend: `git reset --hard <commit>`
- Auto-redeploy con ese commit

---

### Feature: Alertas (Slack/Email)

**Descripción**: Notificaciones de eventos importantes

**Eventos**:
- ✅ Deploy started/finished/failed
- ✅ Health check failed (future)
- ✅ Storage full warning
- ✅ Certificate renewing soon

**Estimación**: 8 SP  
**Prioridad**: P2 (medium)  
**Complejidad**: Media

**Canales**:
- Email: SMTP config
- Slack: Webhook URL
- Discord: Webhook URL

**Configuración**:
- Por evento (que notifique qué)
- Por proyecto (notificar solo x proyecto)
- Por user (notificar solo a admin)

---

### Feature: Performance Metrics

**Descripción**: CPU, memoria, uptime, deploy frequency

**Historias de Usuario**:
- "Quiero ver trending de performance de mis apps"
- "Alertas si CPU > 80% por 5 min"

**Estimación**: 13 SP  
**Prioridad**: P3 (low)  
**Complejidad**: Alta

**Métricas**:
```
Per project:
  - CPU usage (avg, peak)
  - Memory usage (avg, peak)
  - Uptime %
  - Restart count

Global:
  - Deploy frequency
  - Deploy success rate
  - Average deploy time
```

**Visualización**:
- Grafana dashboards
- Time-series data (InfluxDB or Prometheus)

---

### Feature: Custom Nginx Rules (Manual)

**Descripción**: Permitir customizar vhost Nginx sin tocar la consola

**Consideración**: Dentro de límites seguros (no permitir exec, etc.)

**Estimación**: 13 SP  
**Prioridad**: P3 (low)  
**Complejidad**: Media (validación, testing)

**UI**:
- Dashboard: "Custom Nginx config" textarea
- Validar sintaxis antes de aplicar
- Muestra warning: "esto puede romper tu app"

**Limitaciones**:
- No permitir `exec`
- No permitir cambiar puerto o upstreams principales
- Whitelist de directivas permitidas

---

### Feature: SSL Certificate Management

**Descripción**: Renovación automática, alertas, custom certs

**Estimación**: 5 SP  
**Prioridad**: P2 (medium)  
**Complejidad**: Baja (certbot already handles renewal)

**Cambios**:
- Alertar 30 días antes de expiración
- Dashboard: mostrar cert expiry
- Permitir subir custom cert (future)

---

### Feature: Docker Registry Integration

**Descripción**: Pull images privadas desde registry autenticado

**Historias de Usuario**:
- "Quiero deployar mi imagen de Docker Hub privada"

**Estimación**: 8 SP  
**Prioridad**: P3 (low)  
**Complejidad**: Media

**Implementación**:
- Stores credentials en secrets
- Pasa como `docker login` antes de compose up

---

### Feature: API Rate Limiting Customizable

**Descripción**: Control granular de rate-limits por endpoint

**Estimación**: 5 SP  
**Prioridad**: P3 (low)  
**Complejidad**: Baja

**Por defecto**:
- Login: 5/5min per IP ✅ (ya implementado)
- Deploy: 10/hour per user (future)
- API: 100/hour per token (future)

---

### Feature: Scheduled Deploys

**Descripción**: "Deployar mi app cada domingo a las 3am"

**Estimación**: 8 SP  
**Prioridad**: P3 (low)  
**Complejidad**: Media

**UI**:
- Cron-like schedule input
- Runs: `POST /projects/{name}/deploy` automáticamente

---

### Feature: Cost Calculator

**Descripción**: Estimar y mostrar costos (Hetzner + overheads)

**Estimación**: 3 SP  
**Prioridad**: P3 (low)  
**Complejidad**: Baja

**Datos**:
- Costo base VPS
- Costo por proyecto (storage, memory)
- Proyección mensual

---

## Integraciones Futuras

### GitHub Integration

- ✅ Webhook signature validation (futura)
- Merge queue integration (future)
- Protected branches (future)
- Deployment status checks (future)

### Cloud Providers

- AWS S3: Backups
- DigitalOcean: Migration target
- Linode: Alternative VPS provider

### Monitoring

- Prometheus: Metrics
- Grafana: Dashboards
- PagerDuty: Incidents
- Datadog: Full observability

### Communication

- Slack: Notifications, commands (`/devps deploy myapp`)
- Discord: Same as Slack
- Telegram: Alerts
- Email: SMTP backend

### Other

- GitHub Pages: Docs hosting
- Sentry: Error tracking
- Vercel/Netlify: Static site deployment
- CloudFlare: CDN, DDoS protection

---

## Roadmap de Largo Plazo (12+ meses)

### Q1 2027 (Jan-Mar)
- [ ] API & CLI robusta (Epic 2)
- [ ] Webhooks funcionales (Epic 3)
- [ ] Health checks + auto-recovery (Epic 4)

### Q2 2027 (Apr-Jun)
- [ ] Backups automatizados (Epic 7)
- [ ] Logs centralizados
- [ ] Multi-user roles

### Q3 2027 (Jul-Sep)
- [ ] Marketplace de templates
- [ ] Performance metrics + Grafana
- [ ] Alertas (Slack, email)

### Q4 2027 (Oct-Dec)
- [ ] Migration tool Coolify → devps
- [ ] Enterprise features (SSO, audit)
- [ ] SaaS version? (devps.cloud)

---

## Descartes (Won't Do)

- ❌ Kubernetes support (violates constitution)
- ❌ Manual Nginx config in UI (security risk)
- ❌ Auto-scaling (out of scope for single VPS)
- ❌ GUI builder (outside devps scope)
- ❌ Machine learning ops (overkill)

---

## Community & OSS

### Cómo Contribuir

```bash
# Fork & clone
git clone https://github.com/YOUR_USERNAME/devps.git
cd devps

# Branch
git checkout -b feature/my-feature

# Dev setup
cd agent
python3.11 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Code + tests
pytest tests/
ruff check .

# PR
git push origin feature/my-feature
# Abrir PR en GitHub
```

### Areas donde se Necesita Help

- 📝 Documentación (traducción, ejemplos)
- 🧪 Tests (coverage, integration)
- 🎨 Diseño (accesibilidad, dark mode)
- 🐛 Bugs (report en GitHub Issues)
- 🚀 Mejoras (propose en Discussions)

### Discussion Topics (Future)

- [ ] Kubernetes support (¿sí o no?)
- [ ] SaaS version (devps.cloud)
- [ ] Self-hosted vs managed
- [ ] License (MIT vs Copyleft?)

---

## Financiamiento (Future)

**Opciones**:
1. OSS puro (no profit)
2. SaaS devps.cloud (hosted, paid)
3. Sponsors & donations
4. Enterprise support (consulting)
5. Marketplace revenue share

**Decision**: TBD (focus en product quality first)

---

## Última actualización

**Fecha**: Agosto 2026  
**Mantenedor**: fmonfasani  
**Próxima review**: Octubre 2026
