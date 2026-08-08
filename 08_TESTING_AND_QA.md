# Testing & QA

## Estrategia de Testing

```
┌────────────────────────────────────────────┐
│         E2E Testing (VPS)                  │
│  (Manual + future automation)              │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│     Integration Testing (FastAPI)        │
│  (httpx, test client)                    │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│       Unit Testing (pytest)               │
│  (Pure functions, isolation)              │
└────────────────────────────────────────────┘
```

## Unit Tests

### Requisitos de Cobertura

| Módulo | Cobertura | Crítico | Razón |
|--------|-----------|---------|-------|
| `auth.py` | 100% | 🔴 SÍ | Seguridad (crypto) |
| `repo_analysis.py` | 95%+ | 🟡 ALTO | Parsing lógica |
| `registry.py` | 90%+ | 🟡 ALTO | CRUD |
| `docker_ops.py` | Mocking OK | 🟡 MEDIO | Subprocess |
| `secrets_store.py` | 80%+ | 🟢 BAJO | File I/O |
| `nginx.py` | 70%+ | 🟢 BAJO | Subprocess |
| `dashboard.py` | Integration | 🟡 ALTO | Routes |

### Ejecutar Tests

```bash
# Todos los tests
pytest tests/ -v

# Solo un archivo
pytest tests/test_auth.py -v

# Con cobertura
pytest tests/ --cov=agent/devps_agent --cov-report=html
# Ver: htmlcov/index.html

# Con markers
pytest -m "not slow" -v  # Skip slow tests
```

### Test Naming Convention

```python
class TestFunctionName:
    def test_happy_path(self): ...
    def test_edge_case_empty_input(self): ...
    def test_error_invalid_format(self): ...
    def test_timing_attack_resistance(self): ...
```

### Fixture Pattern

```python
import pytest
from pathlib import Path

@pytest.fixture
def tmp_compose_file(tmp_path: Path) -> Path:
    """Fixture: temporary docker-compose.yml"""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("""
    services:
      web:
        image: nginx
        ports:
          - "${DEVPS_PORT_WEB:-3000}:3000"
    """)
    return compose_file

def test_parse_services(tmp_compose_file):
    result = parse_compose_services(tmp_compose_file)
    assert "web" in result
```

## Integration Tests

### Dashboard Login Flow

```python
from fastapi.testclient import TestClient
from devps_agent.main import app

client = TestClient(app)

def test_login_success():
    """Test: Login con credenciales correctas"""
    response = client.post(
        "/dashboard/login",
        data={"username": "admin", "password": "correct"}
    )
    assert response.status_code == 303  # Redirect
    assert response.headers["location"] == "/dashboard"

def test_login_rate_limited():
    """Test: Rate-limiting después de 5 fallos"""
    for i in range(6):
        response = client.post(
            "/dashboard/login",
            data={"username": "admin", "password": "wrong"}
        )
    assert response.status_code == 429  # Too many requests

def test_setup_initial_credentials():
    """Test: Flujo completo de setup"""
    # Step 1: Get form
    response = client.get("/dashboard/setup")
    assert response.status_code == 200
    assert "username" in response.text
    
    # Step 2: Submit
    response = client.post(
        "/dashboard/setup",
        data={"username": "admin", "password": "secure123"}
    )
    assert response.status_code == 200
    assert "Credentials saved" in response.text
```

## E2E Testing (Manual en VPS)

### Checklist de Deploy

```
[ ] Bootstrap deployment vía GitHub Actions
    ✓ Code pulled
    ✓ Dependencies installed
    ✓ Service restarted
    
[ ] Dashboard accessible
    ✓ https://devps.webshooks.com/dashboard
    ✓ HTTPS certificate valid
    ✓ Loads en < 2s
    
[ ] Login flow
    ✓ Setup page si credenciales no existen
    ✓ Form acepta username + password
    ✓ Password hasheado (verificar en .env)
    ✓ Redirect al login después de setup
    ✓ Login con credenciales correctas funciona
    ✓ Login con credenciales incorrectas rechaza
    ✓ Rate-limiting después de 5 fallos
    
[ ] New project flow
    ✓ Click "New project"
    ✓ Form: repo_url, git_ref, compose_file
    ✓ Click "Analyze"
    ✓ Servicios detectados correctamente
    ✓ Env vars listadas
    ✓ Click "Deploy"
    ✓ Deploy completa sin errores
    ✓ Proyecto listado en /dashboard
    ✓ Vhost Nginx creado
    ✓ SSL certificate asignado
    
[ ] Project detail
    ✓ Logs accesibles (últimas 200 líneas)
    ✓ Timeline de eventos visible
    ✓ Status = deployed
    ✓ Dominio accesible desde navegador
    
[ ] Mobile responsivo
    ✓ Login page en mobile (viewport)
    ✓ Dashboard projects en mobile
    ✓ Forms usables sin scroll horizontal
    ✓ Buttons > 44px (touch target)
```

## Security Testing

### Checklist OWASP

```
[ ] A01: Broken Access Control
    ✓ Sin auth → redirect a /dashboard/setup o /dashboard/login
    ✓ Token inválido → rechazado
    ✓ Session expira
    
[ ] A02: Cryptographic Failures
    ✓ Passwords hasheados + salt (PBKDF2, 100k iteraciones)
    ✓ HTTPS enforced (SESSION_HTTPS_ONLY=true)
    ✓ Secrets no en logs
    
[ ] A03: Injection
    ✓ SQL: Solo prepared statements (sqlite3 con ?)
    ✓ Subprocess: Lista de args, no interpolación
    ✓ Jinja2: Auto-escape habilitado
    
[ ] A04: Insecure Design
    ✓ Rate-limiting en login (5/5min per IP)
    ✓ Passwords nunca en texto plano
    ✓ Env file: chmod 600
    
[ ] A05: Security Misconfiguration
    ✓ Config por env vars (no hardcodes)
    ✓ Secrets no en git (verify: git log --all -p | grep PASSWORD)
    ✓ Dependencies updated (pip freeze)
    
[ ] A07: Authentication Failures
    ✓ Password complexity: no requiere (let user choose)
    ✓ Session timeout: FastAPI default (24h?)
    ✓ Brute force: Rate-limiting activo
    
[ ] A09: Logging & Monitoring
    ✓ Cada deploy registrado
    ✓ Cada login registrado
    ✓ Secrets NO en logs
```

### Manual Security Tests

```bash
# 1. Verificar que no hay secrets en git
git log --all -p | grep -i "password\|secret\|token" 
# Resultado esperado: ninguno

# 2. Verificar permisos en agent.env
ssh user@vps "ls -la /opt/devps/agent.env"
# Resultado esperado: -rw------- (600)

# 3. Verificar rate-limiting
for i in {1..10}; do
  curl -X POST https://devps.webshooks.com/dashboard/login \
    -d "username=x&password=wrong" -s -o /dev/null -w "%{http_code}\n"
done
# Resultado esperado: 401 401 401 401 401 429 429 429...

# 4. Verificar PBKDF2
psql -c "SELECT password_hash FROM users LIMIT 1;"
# No debería ser el password en texto plano
```

## Performance Testing

### Targets

| Métrica | Target | Método |
|---------|--------|--------|
| Login form load | < 200ms | ab -n 100 https://devps.webshooks.com/dashboard/login |
| Deploy start | < 500ms | time curl -X POST /projects/x/deploy |
| Project list | < 100ms | Medidor en browser DevTools |
| Nginx install | < 5s | Medir en logs |

### Herramientas

```bash
# Apache Bench
ab -n 100 -c 10 https://devps.webshooks.com/dashboard/login

# curl timing
curl -w "@curl-format.txt" https://devps.webshooks.com/dashboard

# Browser DevTools
# Network tab → medir Load time
```

## DoD (Definition of Done)

Feature NO se considera terminada hasta:

- [x] Código escrito y mergeado
- [x] Tests unitarios pasan (pytest)
- [x] Linter pasa (ruff check)
- [x] Coverage > target (--cov-report)
- [x] Integration tests (si aplica)
- [x] Deployed a VPS (bootstrap.yml)
- [x] Manual E2E testing completado
- [x] Security review passed
- [x] Documentación actualizada
- [x] Changelog escrito
- [x] Aceptación del usuario (si aplica)

## CI/CD Pipeline

```yaml
# .github/workflows/test.yml (future)
name: Test & Lint

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: cd agent && pip install -e ".[dev]"
      
      - name: Lint
        run: cd agent && ruff check .
      
      - name: Tests
        run: cd agent && pytest tests/ --cov=devps_agent
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Roadmap de Testing

- [ ] CI pipeline con GitHub Actions
- [ ] E2E tests automatizados (Playwright)
- [ ] Load testing (k6 or Apache Bench)
- [ ] Security scanning (bandit, safety)
- [ ] Accessibility scanning (axe)
