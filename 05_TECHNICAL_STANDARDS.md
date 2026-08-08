# Technical Standards

## SOLID Principles

### S — Single Responsibility
- `auth.py`: Solo hash/verify (no session logic)
- `docker_ops.py`: Solo subprocess wrappers (no business logic)
- `registry.py`: Solo CRUD (no file I/O)
- `repo_analysis.py`: Solo parsing (no deploy logic)
- Cada módulo = 1 responsabilidad clara

### O — Open/Closed
- ✅ Extensible sin tocar core: nuevo router → simplemente agrega ruta
- ✅ deploy() acepta env_file parameter (open for extension)
- ✅ compose_services retorna dict (extensible)

### L — Liskov Substitution
- Interfaces claras (functions, no magic)
- Tipos explícitos: `str`, `Path`, `dict[str, int]`
- No inheritance chains complejas

### I — Interface Segregation
- No métodos que nadie usa
- `registry.py`: cada función es su interfaz
- `docker_ops.py`: funciones independientes

### D — Dependency Injection
- config leído al importar (ok para env vars)
- Pasar Path, no hardcodear rutas
- Funciones puras: f(input) → output (auth, parsing)

## Clean Architecture

```
┌─────────────────────────────────────────┐
│         FastAPI Routes                  │
│      (dashboard.py, routers/)           │
│     (Controllers, HTTP layer)           │
└────────────┬────────────────────────────┘
             │ depends on
             ▼
┌─────────────────────────────────────────┐
│     Business Logic                      │
│  (auth, docker_ops, repo_analysis,      │
│   registry, nginx, secrets_store)       │
│     (Services, Use Cases)               │
└────────────┬────────────────────────────┘
             │ depends on
             ▼
┌─────────────────────────────────────────┐
│     External APIs & Storage             │
│   (subprocess, filesystem, sqlite)      │
│        (Data Layer)                     │
└─────────────────────────────────────────┘

Règle: Inner layers NO dependen de outer layers.
FastAPI y subprocess son "details", no business logic.
```

## OWASP Top 10 Mitigations

| Risk | Mitigation | Status |
|------|-----------|--------|
| **A01: Broken Access Control** | Auth por session (dashboard) + Bearer token (API) | ✅ |
| **A02: Cryptographic Failures** | PBKDF2+salt para passwords, HTTPS enforced | ✅ |
| **A03: Injection** | Subprocess checks, no SQL (SQLite ORM patterns), parametrized | ✅ |
| **A04: Insecure Design** | Credentials nunca en logs, secrets.env aislado | ✅ |
| **A05: Security Misconfiguration** | Config por env vars, no hardcodes, SESSION_HTTPS_ONLY flag | ✅ |
| **A06: Vulnerable & Outdated Components** | Keep deps updated, ruff checks | ✅ |
| **A07: Authentication Failures** | Rate-limiting, secure password hashing, timeout sessions | ✅ |
| **A08: Data Integrity Failures** | Git checksum, signed commits (future) | 🔄 |
| **A09: Logging & Monitoring Failures** | Eventos registrados, logs accesibles | ✅ |
| **A10: SSRF** | Webhook validation (future), DEVPS_TOKEN isolation | 🔄 |

## Code Conventions

### Python

**Naming**
```python
# Functions: snake_case
def hash_password(password: str) -> tuple[str, str]: ...

# Classes: PascalCase (routers no usan clases, FastAPI valida con Pydantic)
class DeployRequest(BaseModel): ...

# Constants: UPPER_SNAKE_CASE
PBKDF2_ITERATIONS = 100_000
PORT_RANGE_START = 40000

# Private: _leading_underscore
def _client_ip(request: Request) -> str: ...
```

**Type Hints**
```python
# Always use explicit types
def parse_compose_services(compose_path: Path) -> dict[str, dict]:
    ...

# Union types
def clone_shallow(repo_url: str, git_ref: str) -> Path:
    ...

# Optional
def get_project(name: str) -> dict[str, Any] | None:
    ...
```

**Comments**
- No docstrings multi-line (solo one-liner si el WHY no es obvio)
- No comments que repitan el código
- Comentarios para WHY, no WHAT

**Formatting**
- Line length: 100 chars (ruff default)
- Indentation: 4 spaces
- Imports: organized, sorted alphabetically por ruff

### Error Handling

**Prefer exceptions over return codes**
```python
# Good
try:
    docker_ops.compose_up(...)
except docker_ops.CommandError as e:
    registry.log_event(name, "deploy", f"failed: {e}", success=False)
    raise HTTPException(502, str(e))

# Bad
result = docker_ops.compose_up(...)
if result.returncode != 0:
    ...
```

**Boundary validation only**
```python
# Only validate at system boundaries (HTTP, subprocess)
# Trust internal code (registry.upsert_project assumes name exists in the right context)

# HTTP input: MUST validate
if not config.DASHBOARD_USERNAME:
    raise HTTPException(503, "not configured")

# Internal call: trust it
registry.upsert_project(name, ...)  # assume name is valid
```

## Logging & Events

### Event Types (registry.log_event)

```python
# Deploy related
log_event(project, "deploy", f"git_sha={sha} ports={ports}", success=True)
log_event(project, "deploy", f"docker compose failed: {e}", success=False)

# Nginx related
log_event(project, "vhost_installed", domain, success=True)
log_event(project, "vhost_installed", error_msg, success=False)

# Adoption/Migration
log_event(project, "adopt", f"container={name}", success=True)
log_event(project, "migration_adopted", notes, success=True)

# Restart
log_event(project, "restart", None, success=True)
```

### What NOT to log

❌ Passwords en texto plano  
❌ Env vars secretas  
❌ Tokens en texto plano  
❌ Private SSH keys  
❌ Database credentials  

## Git Conventions

### Commit Messages
```
<type>: <short summary> (< 70 chars)

<detailed explanation if needed (< 100 chars per line)>

Fixes #123
Relates to #456
```

**Types**: feature, fix, refactor, test, docs, perf, chore

### Branches
- `main`: production-ready code
- Feature branches: feature/auto-detect-repos, feature/webhooks
- Hotfix branches: hotfix/security-vuln

### No force-push to main

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Dashboard login | < 200ms | TBD |
| Deploy start | < 500ms | TBD |
| Project list | < 100ms | TBD |
| Nginx vhost install | < 5s | TBD |
| Docker compose up | Depends on image | TBD |

## Security Review Checklist

- [ ] No secrets hardcoded
- [ ] Input validation at boundaries only
- [ ] Password hashing + salt
- [ ] Rate limiting on auth endpoints
- [ ] HTTPS forced (except local dev)
- [ ] CSRF protection (FastAPI middleware)
- [ ] SQL injection mitigated (parameterized)
- [ ] XSS mitigated (Jinja2 auto-escape)
- [ ] Subprocess args not user-controlled (docker_ops uses subprocess.run with list args)
- [ ] File paths validated (no path traversal)

## Testing Standards

### Coverage Requirements
- `auth.py`: 100% (crypto critical)
- `repo_analysis.py`: 95%+ (parsing logic)
- `registry.py`: 90%+ (CRUD)
- `docker_ops.py`: Mocking is acceptable (subprocess interaction)
- `dashboard.py`: Integration tests (FastAPI)

### Test Naming
```python
class TestHashPassword:
    def test_hash_password_generates_salt(self): ...
    def test_hash_password_with_custom_salt(self): ...
```

### Avoid in Tests
- Mocking stdlib (use real functions)
- Mocking database (use real SQLite :memory:)
- Slow sleeps (use fixtures, monkeypatch time if needed)

## Definition of Done (DoD)

- [ ] Code written
- [ ] Tests pass (pytest)
- [ ] Linter passes (ruff check .)
- [ ] Commit message is clear
- [ ] No secrets committed
- [ ] OWASP checklist reviewed
- [ ] Documentation updated
- [ ] Tested on VPS (if applicable)
