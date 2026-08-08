# PRD — Product Requirements Document

## Funcionalidades Core (MVP)

### 1. Dashboard Web
- [ ] Login seguro (username + password, rate-limited)
- [ ] Setup inicial de credenciales
- [ ] Listado de proyectos desplegados
- [ ] Detalle de cada proyecto (logs, eventos, estado)
- [ ] UI responsiva (mobile-first)

### 2. Auto-Detección de Repos
- [ ] Clonar repo shallow por URL + rama
- [ ] Parsear docker-compose.yml
- [ ] Detectar variables de entorno (.env.example)
- [ ] Clasificar secretos auto-generables vs manuales
- [ ] Preview antes de deploy

### 3. Deploy Automático
- [ ] Asignar puertos (rango 40000-40999)
- [ ] Escribir vhost Nginx + certificados SSL (certbot)
- [ ] Pasar env vars a docker compose
- [ ] Ejecutar docker compose up -d --build
- [ ] Registrar en registry (SQLite)

### 4. Observabilidad
- [ ] Logs de cada deploy
- [ ] Timeline de eventos por proyecto
- [ ] Health checks de containers
- [ ] Estado del proyecto (deployed, failed, running)
- [ ] Alertas via email/Slack (future)

### 5. Migrations (Coolify → devps)
- [ ] Adopción de containers ya running
- [ ] Tracking: adopted → paralleled → cutover → decommissioned
- [ ] Rollback a Coolify si falla

### 6. API Pública
- [ ] Bearer token auth (DEVPS_TOKEN)
- [ ] Endpoints CRUD para proyectos
- [ ] Triggear deploy via API
- [ ] Read logs/events via API
- [ ] CLI hzploy pega contra esto

## Historias de Usuario

### HU-1: Como desarrollador, quiero deployer mi proyecto sin SSH
**Cuando**: Hago push a main
**Quiero**: Que devps lo clone, analice, configure y despliegue automáticamente
**Criterios**:
- El repo tiene docker-compose.yml
- Las env vars se auto-completan o se piden por UI
- En 2 minutos está live con dominio y SSL

### HU-2: Como startup, quiero multiple proyectos en 1 VPS
**Cuando**: Tengo 3 apps diferentes
**Quiero**: Cada una en su puerto, su dominio, su .env
**Criterios**:
- Cero conflictos de puerto
- Cero conflictos de dominio
- Cada proyecto aislado

### HU-3: Como admin, quiero revertir un deploy
**Cuando**: El último deploy es un desastre
**Quiero**: Ir a un commit anterior y que devps lo redepliegue
**Criterios**:
- Listado de commits recientes
- Revert = git checkout + redeploy
- El estado anterior se restaura

## Reglas de Negocio

1. **Seguridad por defecto**
   - Nunca loguear credenciales en texto plano
   - Rate-limiting en login (5 intentos / 5 min por IP)
   - Passwords hasheadas con PBKDF2 + salt único

2. **Sin SSH para ops normales**
   - Deploy, restart, logs, config: todo por dashboard
   - SSH solo para setup inicial y emergencies

3. **Reversibilidad**
   - Todo cambio debe poder deshacerse
   - Git es la fuente de verdad
   - Rollback = checkout anterior + redeploy

4. **Observabilidad**
   - Cada acción queda registrada (evento + timestamp)
   - Logs accesibles en dashboard
   - No hay "magia" oculta

## Prioridades (MoSCoW)

### Must Have
- Dashboard login + setup
- Auto-detección de repos
- Deploy con docker-compose
- Nginx vhost + SSL
- Logs y eventos

### Should Have
- Webhooks de git
- Health checks automáticos
- Rollback UI
- Multi-dominio

### Could Have
- Email alerts
- Slack integration
- Backups automáticos
- Migration wizard Coolify

### Won't Have (v1)
- Kubernetes support
- Load balancing
- Auto-scaling
- Custom Nginx rules (manual config)

## Criterios de Aceptación

- ✅ Linter (ruff) sin warnings
- ✅ 100% cobertura de tests (core modules)
- ✅ Mobile responsivo (viewport metadata)
- ✅ Rate-limiting funcional
- ✅ Reverts funcionales en git
- ✅ Docs completos (architecture, setup, usage)
- ✅ OWASP top 10 mitigado
