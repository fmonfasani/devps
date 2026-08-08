# Handoff: devps — reemplazar login por token con usuario + contraseña

## Contexto (repo: github.com/fmonfasani/devps, rama main, VPS 89.167.96.239)

Agente FastAPI + SQLite en `/opt/devps` (systemd), dashboard server-rendered Jinja2 en `agent/devps_agent/dashboard.py`, login hoy pega un token largo (`DEVPS_TOKEN`, 64 hex chars) que hay que ir a buscar por SSH cada vez (`grep DEVPS_TOKEN /opt/devps/agent.env`). El usuario quiere loguearse con **usuario + contraseña memorizables**, sin tener que SSHear nunca para conseguir nada.

Fase 3b (auto-detección de repos + deploy desde el dashboard) ya está mergeada en `main` y funcionando — no tocar esa parte.

## Objetivo de esta tarea

Reemplazar el login del **dashboard** (no la API bearer-token que usa `hzploy`/CLI — esa se queda como está, es un credential de máquina) por usuario + contraseña.

## Diseño

1. **`agent/devps_agent/auth.py`** (nuevo, sin FastAPI, testeable solo):
   - `hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]`: usa `hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)` (stdlib, sin dependencia nueva). `salt = os.urandom(16)` si no se pasa. Devuelve `(hash_hex, salt_hex)`.
   - `verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool`: recalcula el hash con la misma sal y compara con `secrets.compare_digest`.

2. **`config.py`**: agregar `DASHBOARD_USERNAME`, `DASHBOARD_PASSWORD_HASH`, `DASHBOARD_PASSWORD_SALT` (leídos de env vars, sin default — si faltan, el agente no debería arrancar el login normal, ver punto 4).

3. **`dashboard.py`**:
   - `login_form`: sacar el campo `token`, poner `username` + `password`.
   - `login_submit`: validar `username == config.DASHBOARD_USERNAME` y `verify_password(password, config.DASHBOARD_PASSWORD_SALT, config.DASHBOARD_PASSWORD_HASH)`. Mismo rate-limit por IP que ya existe en `login_throttle.py` (no tocar esa lógica, solo reusarla).

4. **`templates/login.html`**: reemplazar el input `token` por `username` + `password` (type="password").

5. **Setup inicial de las credenciales** — no hay UI de "crear cuenta", así que hace falta:
   - Un one-off workflow de GitHub Actions (mismo patrón que los demás en `.github/workflows/`, `appleboy/ssh-action` pineado a `7eaf76671a0d7eec5d98ee897acda4f968735a17`) que le pida al usuario un usuario/contraseña como `workflow_dispatch` inputs, calcule el hash **en el runner** (no mandar la contraseña en texto plano al log — usar `env:` para pasarla, nunca interpolarla directo en `script:`), y escriba `DASHBOARD_USERNAME`/`DASHBOARD_PASSWORD_HASH`/`DASHBOARD_PASSWORD_SALT` en `/opt/devps/agent.env`, después reiniciar `devps-agent`.
   - **Cuidado con el bug conocido de drone-ssh**: no usar heredocs multilínea en el `script:` — si hace falta escribir contenido largo, base64 + `echo | base64 -d` en una sola línea (ver commits `c0e461a` y `d723e24` en el historial de `devps` para el patrón exacto que ya funciona).

6. **Tests**: `tests/test_auth.py` — hash/verify con contraseña correcta e incorrecta, sales distintas dan hashes distintos, etc. Seguir el patrón de `tests/test_dashboard_rate_limit.py` (sin fastapi).

## Checklist antes de dar por terminado

- [ ] `pytest` + `ruff check .` verdes en `agent/`
- [ ] Push a `main`
- [ ] Avisar que hace falta correr el workflow de setup de credenciales UNA vez (workflow_dispatch con inputs) y después `bootstrap.yml` para el redeploy del código
- [ ] Confirmar que el login viejo por token deja de aceptar el token como contraseña (que no quede un bypass accidental)
