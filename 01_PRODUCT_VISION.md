# Product Vision

## El Producto

**devps** es un control-plane AI-Native que automatiza el ciclo de vida completo de un proyecto en una VPS: desde el análisis del código fuente, pasando por la detección automática de configuración, deployment, monitoring, hasta el mantenimiento continuo.

## Usuarios

- **DevOps Engineers**: Quieren automatizar el deploy sin escribir Dockerfiles ni configurar Nginx manualmente
- **Developers**: Quieren ir de código a producción en minutos, sin tocar infraestructura
- **Startups / Solopreneurs**: No pueden pagar DevOps a tiempo completo, necesitan algo simple y automático
- **Equipos pequeños**: Quieren focus en features, no en operaciones

## Mercado

Espacio: deployment automation (AWS, Heroku, Render, Fly.io son competencia).

**Diferencial**: devps es open-source, corrés en tu propia VPS, no hay vendor lock-in, todo es observable, cero SSH requerido para operaciones normales.

## Propuesta de Valor

| Para | Entrega |
|------|---------|
| Devs | Deploy en minutos, auto-config, sin SSH, cero frustración |
| Startups | Infraestructura simple, barata (1 VPS), observable |
| DevOps | Herramienta extensible, modular, que respeta principios SOLID |

## Casos de Uso

1. **Fast API + React**: Dev hace push → devps clona, detecta docker-compose, despliega, expone con Nginx
2. **Múltiples proyectos**: Mismo usuario, misma VPS, cada uno en su puerto, cada uno con su dominio
3. **Secretos**: Auto-genera passwords, el user completa API keys → devps escribe `.env`, docker compose lo lee
4. **Updates**: Git push → webhook → devps re-clona, re-despliega, cero downtime
5. **Rollback**: Anterior commit está en git, revert → devps re-clona esa versión

## Objetivos Estratégicos (12 meses)

- [ ] Dashboard production-ready con auth segura (lo que estamos haciendo ahora)
- [ ] Auto-deploy via git webhooks
- [ ] Health checks y restarts automáticos
- [ ] Logs centralizados y searchables
- [ ] Backups automáticos de datos
- [ ] Migration tool: de Coolify/Heroku → devps sin downtime
- [ ] Marketplace de templates (boilerplates)
- [ ] CLI robusto para power users
