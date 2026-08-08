# Hermes Execution Protocol

> Protocolo obligatorio para cualquier feature nueva o cambio arquitectónico.
> Devps sigue SIEMPRE este flujo.

## El Flujo (6 Pasos)

```
┌─────────────────────────────────────────────────────────┐
│  1. CONSTITUCIÓN                                        │
│     ¿Esto respeta los principios y restricciones?      │
│     (No → rechazar; Sí → continuar)                    │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│  2. PRD (Requirements)                                  │
│     ¿Qué exactamente se necesita? ¿Historias de user? │
│     (Documentar criterios de aceptación)               │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│  3. ARQUITECTURA (Design)                               │
│     ¿Cómo encaja en el sistema existente?              │
│     (Diagramas, flujos, nuevos módulos)                │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│  4. DISEÑO (UI/UX)                                      │
│     ¿Cómo se ve/comporta para el usuario?              │
│     (Mockups, componentes, accesibilidad)              │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│  5. IMPLEMENTACIÓN (Code)                               │
│     Escribir código + tests                            │
│     (Linter, tipos, estándares técnicos)               │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│  6. TESTING & VALIDACIÓN (QA)                          │
│     Toda la feature funciona end-to-end               │
│     (Tests pasan, security review, user testing)       │
└─────────────────────────────────────────────────────────┘
```

## Paso 1: CONSTITUCIÓN

**Pregunta**: ¿Esta feature respeta la visión, misión y principios de devps?

**Checklist**:
- [ ] ¿Automatiza algo repetitivo?
- [ ] ¿Mejora la UX o quita complejidad?
- [ ] ¿Mantiene la seguridad?
- [ ] ¿Sigue arquitectura modular?
- [ ] ¿Es observable?
- [ ] ¿Se puede revertir?
- [ ] ¿Evita Kubernetes, manual Nginx config, SSH para ops?
- [ ] ¿No introduce dependencias innecesarias?

**Output**: Decisión: APROBAR o RECHAZAR

**Ejemplo**:
- ✅ "Feature: auto-restart de containers" → Automatiza, mejora UX (menos manual ops)
- ❌ "Feature: agregar Kubernetes support" → Viola restricción "Sin Kubernetes"
- ✅ "Feature: webhooks de GitHub" → Automatiza, observable (registra eventos)

---

## Paso 2: PRD

**Pregunta**: ¿Qué exactamente construimos?

**Documento**: Actualizar `02_PRODUCT_REQUIREMENTS_DOCUMENT.md`

**Checklist**:
- [ ] Funcionalidades listadas (bullet points)
- [ ] 3-5 historias de usuario (As a X, I want Y so that Z)
- [ ] Criterios de aceptación (ACCEPTANCE CRITERIA per HU)
- [ ] Reglas de negocio (si aplica)
- [ ] Priori dades (MoSCoW)
- [ ] Qué NO incluimos en v1

**Output**: PRD claro, sin ambigüedades

**Ejemplo** (Epic: Auto-detect repos):
```
HU-1: Como dev, quiero subir mi repo y que devps lo despliegue automáticamente

Criterios:
  ✓ URL + rama como input
  ✓ Auto-detección de docker-compose.yml
  ✓ Listado de env vars a completar
  ✓ Deploy en 1 click
  ✓ Dominio y SSL automático
  ✓ Timeout si toma > 5min
```

---

## Paso 3: ARQUITECTURA

**Pregunta**: ¿Cómo se implementa sin romper el sistema?

**Documento**: Actualizar `03_SYSTEM_ARCHITECTURE.md`

**Checklist**:
- [ ] Módulos nuevos (si aplica)
- [ ] Cambios en data model (schema)
- [ ] Nuevos endpoints API
- [ ] Flujos diagramados (Mermaid)
- [ ] Decisiones técnicas explicadas
- [ ] Dependencias claras (qué depende de qué)

**Output**: Arquitectura clara, validada con SOLID

**Ejemplo**:
```
Módulos nuevos:
  - repo_analysis.py (clone, parse compose, parse env)
  - secrets_store.py (write env file)

Cambios en DeployRequest:
  + env_file: str | None

Nuevos endpoints:
  GET /dashboard/projects/new
  POST /dashboard/projects/new/analyze
  POST /dashboard/projects/new/deploy
```

---

## Paso 4: DISEÑO (UI/UX)

**Pregunta**: ¿Cómo se vería y se comportaría?

**Documento**: Actualizar `04_DESIGN_SYSTEM.md`

**Checklist**:
- [ ] Mockups (si hay UI)
- [ ] Componentes usados (forms, buttons, cards)
- [ ] Flujo de usuario (step by step)
- [ ] Accesibilidad (WCAG 2.1 AA)
- [ ] Mobile responsivo
- [ ] Dark mode

**Output**: Diseño claro, implementable

**Ejemplo**:
```
Paso 1: Form (GET /dashboard/projects/new)
  - Input: project_name, repo_url, git_ref, compose_file
  - Button: "Analyze Repository"

Paso 2: Review (POST /dashboard/projects/new/analyze)
  - Tabla: servicios detectados + puertos
  - Tabla: env vars (auto-complete, manual)
  - Button: "Deploy Project"

Paso 3: Success (POST /dashboard/projects/new/deploy)
  - Redirect to /dashboard/projects/{name}
```

---

## Paso 5: IMPLEMENTACIÓN

**Pregunta**: ¿El código es seguro, testeable y mantenible?

**Documento**: Código en `agent/devps_agent/`

**Checklist**:
- [ ] Código escrito
- [ ] Módulos siguen SOLID
- [ ] Tipos explícitos (type hints)
- [ ] No secrets hardcodeados
- [ ] Linter pasa (ruff check .)
- [ ] Tests escritos (pytest)
- [ ] Docs actualizadas
- [ ] Commit messages claros

**Output**: Código mergeable

**Ejemplo**:
```python
# ✅ repo_analysis.py
def parse_compose_services(compose_path: Path) -> dict[str, dict]:
    """Parse docker-compose.yml and extract services."""
    with open(compose_path) as f:
        compose = yaml.safe_load(f) or {}
    
    services = {}
    for service_name, config in compose.get("services", {}).items():
        if isinstance(config, dict) and (ports := config.get("ports")):
            # Extract container port from ports list
            services[service_name] = {...}
    
    return services

# ✅ tests/test_repo_analysis.py
def test_parse_services_with_devps_convention():
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("""
    services:
      web:
        image: nginx
        ports:
          - "${DEVPS_PORT_WEB:-3000}:3000"
    """)
    
    result = parse_compose_services(compose_file)
    assert result["web"]["container_port"] == 3000
    assert result["web"]["host_port_var"] == "WEB"
```

---

## Paso 6: TESTING & VALIDACIÓN

**Pregunta**: ¿Realmente funciona end-to-end?

**Documento**: `08_TESTING_AND_QA.md` (plan de pruebas)

**Checklist**:
- [ ] Unit tests pasan (pytest)
- [ ] Linter pasa (ruff)
- [ ] Probado en VPS (si applicapplicable)
- [ ] Security review completada
- [ ] User testing (si time permits)
- [ ] Documentación actualizada
- [ ] Changelog escrito

**Output**: Feature DONE, production-ready

**Ejemplo**:
```bash
# Paso 5: Código listo
pytest tests/test_repo_analysis.py -v  # ✅ 11 passed
ruff check agent/                       # ✅ All checks passed

# Paso 6: Deploy y test
bootstrap.yml (GitHub Actions)          # Despliega a VPS
https://devps.webshooks.com/dashboard   # Test manualmente
  → Form (new project)
  → Submit URL + rama
  → Review servicios + env vars
  → Deploy
  → Verificar logs
```

---

## Aplicación Práctica

### Ejemplo Real: Feature "Setup desde Dashboard"

```
1. CONSTITUCIÓN
   ✓ Automatiza el setup (no necesita SSH ni workflow manual)
   ✓ Mejora UX (todo desde navegador)
   → APROBAR

2. PRD
   ✓ HU: "Como user, quiero configurar credenciales desde dashboard"
   ✓ Criterios: Username + password, guardados en agent.env, auto-redirect al login
   → DOCUMENTO ESCRITO

3. ARQUITECTURA
   ✓ Nuevos endpoints: GET/POST /dashboard/setup
   ✓ Cambios en config.py: leer DEVPS_DASHBOARD_*
   ✓ Nuevo template: setup.html
   → FLUJO DIAGRAMADO

4. DISEÑO
   ✓ Form: username + password inputs
   ✓ Success message + auto-redirect
   → MOCKUP LISTO

5. IMPLEMENTACIÓN
   ✓ setup_form() y setup_submit() en dashboard.py
   ✓ setup.html template
   ✓ Tests para auth.py
   ✓ ruff check ✅, pytest ✅
   → CODE MERGED

6. TESTING
   ✓ Probado en VPS
   ✓ Security review: PBKDF2, no logs, 600 permisos en .env
   → FEATURE LIVE
```

---

## Automatización del Protocolo

**Checklist en repo**:
```markdown
# Devps Feature Checklist

- [ ] Step 1: Constitución (respeta principios?)
- [ ] Step 2: PRD (qué se construye?)
- [ ] Step 3: Arquitectura (cómo se conecta?)
- [ ] Step 4: Diseño (cómo se ve?)
- [ ] Step 5: Implementación (código testeable?)
- [ ] Step 6: Testing (funciona end-to-end?)

## Files updated:
- [ ] 01_PRODUCT_VISION.md
- [ ] 02_PRODUCT_REQUIREMENTS_DOCUMENT.md
- [ ] 03_SYSTEM_ARCHITECTURE.md
- [ ] 04_DESIGN_SYSTEM.md
- [ ] 05_TECHNICAL_STANDARDS.md
- [ ] Code in agent/devps_agent/
- [ ] Tests in tests/
- [ ] 08_TESTING_AND_QA.md
```

---

## Cuándo SALTAR pasos

❌ NUNCA saltar ningún paso  
❌ No ir directo de Constitución a Código (falta contexto)  
❌ No hacer Testing sin Implementación clara  

✅ Si la feature es muy pequeña (1-2 líneas), haz los 6 pasos igual (toma 10min max)  
✅ Si necesitas cambiar el Paso 3, regresa al Paso 2 y actualiza

---

## Cuando una feature está DONE

✅ Todos los 6 pasos documentados  
✅ Código + tests en main  
✅ Documentación actualizada  
✅ Probado en VPS  
✅ Security review passed  
✅ Changelog escrito  
✅ Anunciado a users (si applicable)
