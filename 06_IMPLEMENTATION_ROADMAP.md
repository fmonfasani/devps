# Implementation Roadmap

## Épicas

### Epic 1: Dashboard Core (DONE ✅)
**Objetivo**: Dashboard production-ready con auth segura

**Fases**:
1. ✅ Setup inicial (username + password)
2. ✅ Auto-detección de repos (Fase 3b)
3. ✅ Deploy desde dashboard
4. ✅ Login seguro (rate-limiting, PBKDF2)

**Dependencias**: Ninguna (foundation)

---

### Epic 2: API & CLI (IN PROGRESS 🔄)
**Objetivo**: Poder deployer/manage via API y CLI

**Fases**:
1. ✅ API endpoints (CRUD proyectos)
2. ✅ Bearer token auth
3. 🔄 CLI `hzploy` (Python)
4. 🔄 Deploy via API

**Dependencias**: Epic 1

---

### Epic 3: Git Webhooks (BLOCKED 📋)
**Objetivo**: Auto-deploy en cada git push

**Fases**:
1. Webhook endpoint: `POST /webhooks/github`
2. Payload validation (signature check)
3. Trigger deploy automáticamente
4. Rollback si falla

**Dependencias**: Epic 2

**Blocker**: Necesita webhook secret en config

---

### Epic 4: Health & Recovery (TODO 📝)
**Objetivo**: Detección automática de fallos y restart

**Fases**:
1. Health checks (docker inspect)
2. Auto-restart si container muere
3. Alertas (Slack/email)
4. Metrics (CPU, memoria, uptime)

**Dependencias**: Epic 1

---

### Epic 5: Migrations (DONE ✅)
**Objetivo**: Facilitar migración Coolify → devps

**Fases**:
1. ✅ Adopt: registrar container existente
2. ✅ Paralleled: deployar en devps sin traffic
3. ✅ Cutover: mover traffic a devps
4. ✅ Decommissioned: marcar como migrado

**Dependencias**: Epic 1

---

### Epic 6: Observabilidad (IN PROGRESS 🔄)
**Objetivo**: Logs, eventos, dashboards

**Fases**:
1. ✅ Event log (cada acción registrada)
2. ✅ Container logs (tail accesible en dashboard)
3. 🔄 Search en eventos (timestamp, tipo)
4. 📋 Métricas (uptime, deploy frequency)

**Dependencias**: Epic 1

---

### Epic 7: Backups & Disaster (TODO 📝)
**Objetivo**: Data persistence y recovery

**Fases**:
1. Backup automático de registry.db (diario)
2. Backup de /opt/devps/secrets (encrypted)
3. Restore procedure
4. Disaster recovery runbook

**Dependencias**: Epic 1

---

### Epic 8: Multi-Tenancy (FUTURE 🔮)
**Objetivo**: Múltiples usuarios/equipos

**Fases**:
1. User roles (admin, deployer, viewer)
2. Project ownership
3. Audit log por usuario
4. Permissions matrix

**Dependencias**: Epic 4 (later versions)

---

## Roadmap de Milestones

### Milestone 1: MVP (DONE ✅)
**Fecha**: Agosto 2026
**Criterios**:
- ✅ Dashboard funcional (login, setup, new project)
- ✅ Deploy automático desde UI
- ✅ Auth segura (PBKDF2, rate-limiting)
- ✅ Tests para core modules
- ✅ Documentación (constitución, arquitectura)

**Épicas**: 1, 5 (core de migrations)

---

### Milestone 2: API-First (PLANNED 📋)
**Fecha**: Septiembre 2026
**Criterios**:
- API endpoints CRUD
- CLI hzploy funcional
- Webhooks de GitHub
- Deploy via API

**Épicas**: 2, 3

**Effort**: 2 semanas

---

### Milestone 3: Resilience (PLANNED 📋)
**Fecha**: Octubre 2026
**Criterios**:
- Health checks automáticos
- Auto-restart de containers muertos
- Alertas funcionales
- Runbook de disaster recovery

**Épicas**: 4, 7

**Effort**: 1.5 semanas

---

### Milestone 4: Scale (FUTURE 🔮)
**Fecha**: Q1 2027
**Criterios**:
- Backups automáticos
- Multi-user support (roles)
- Performance optimized
- Load testing passed

**Épicas**: 8

**Effort**: 4 semanas

---

## Dependencias Críticas

```
Epic 1 (Dashboard) 🚩 FOUNDATION
    ├─→ Epic 2 (API & CLI)
    │   ├─→ Epic 3 (Webhooks)
    │   └─→ Epic 4 (Health)
    │
    ├─→ Epic 5 (Migrations) ✅ DONE
    │   └─→ Epic 2 (for cutover flow)
    │
    ├─→ Epic 6 (Observability)
    │   └─→ Epic 4 (alertas)
    │
    └─→ Epic 7 (Backups)
        └─→ Epic 2 (backup API)
```

## Velocidad & Burn-down

### Backlog Actual (Story Points estimados)

| Épica | Status | SP Restantes | Prioridad |
|-------|--------|--------------|-----------|
| 1: Dashboard | ✅ DONE | 0 | P0 |
| 2: API & CLI | 🔄 60% | 10 | P1 |
| 3: Webhooks | 📋 0% | 13 | P1 |
| 4: Health | 📋 0% | 8 | P2 |
| 5: Migrations | ✅ DONE | 0 | P1 |
| 6: Observability | 🔄 50% | 5 | P2 |
| 7: Backups | 📋 0% | 5 | P2 |
| 8: Multi-tenant | 🔮 0% | 21 | P3 |

**Total Backlog**: ~62 SP  
**Velocidad estimada**: ~13 SP/semana  
**ETA**: 5 semanas para P1+P2  

## Decisiones Pendientes

- [ ] Usar pgbouncer si escalamos a PostgreSQL (Epic 8)
- [ ] Bucket S3 para backups o local storage (Epic 7)
- [ ] Slack vs Email vs ambos (Epic 4)
- [ ] Rate-limit per user o global (Epic 8)
- [ ] Kubernetes support (descartar o future?)

## Comunicación de cambios

Cada épica cerrada:
1. Actualizar docs (Architecture, PRD)
2. Release notes en GitHub
3. Changelog en /docs
4. Notification a users (si es feature)
