# Multi-User Support & RBAC

devps ahora soporta múltiples usuarios con roles y permisos basados en RBAC (Role-Based Access Control).

## Roles

Tres roles jerárquicos disponibles:

- **admin** (Nivel 3): Acceso completo
  - Crear/editar/eliminar usuarios
  - Ver todos los proyectos
  - Administrar cualquier proyecto
  - Cambiar roles de usuarios
  
- **deployer** (Nivel 2): Crear y gestionar propios proyectos
  - Crear nuevos proyectos
  - Desplegar/redeplegar sus propios proyectos
  - Ver todos los proyectos (lectura)
  - Editar solo sus propios proyectos
  
- **viewer** (Nivel 1): Solo lectura
  - Ver todos los proyectos
  - Ver logs y eventos
  - Ver estado de salud
  - Sin permisos de escritura

## Primeros Pasos

### 1. Crear Usuario Admin

El primer usuario debe crearse manualmente en la base de datos o via API. Luego puede crear otros usuarios:

```bash
# SSH a la VPS
ssh root@89.167.96.239

# Acceder a la DB
sqlite3 /opt/devps/data/registry.db

# Crear usuario admin
INSERT INTO users (username, password_hash, password_salt, role, created_at)
VALUES ('admin', '<hash>', '<salt>', 'admin', datetime('now'));
```

Para generar hash+salt, usa Python en la VPS:

```bash
python3 -c "
from devps_agent import auth
hash_hex, salt_hex = auth.hash_password('tu_contraseña')
print(f'Hash: {hash_hex}')
print(f'Salt: {salt_hex}')
"
```

### 2. Administrar Usuarios

Desde el dashboard (si eres admin):

1. Ve a **Users** (futuro; por ahora vía API)
2. Click **New User**
3. Completa:
   - Username
   - Password
   - Role (admin/deployer/viewer)
4. Click **Create**

### 3. Verificar Permisos

Cada acción verifica permisos automáticamente:

```
GET /dashboard → usuario "viewer" ve todos proyectos
POST /dashboard/projects/new → usuario "viewer" → ❌ 403 Forbidden
```

## Permisos por Acción

| Acción | Admin | Deployer | Viewer |
|--------|-------|----------|--------|
| create_user | ✅ | ❌ | ❌ |
| list_users | ✅ | ❌ | ❌ |
| delete_user | ✅ | ❌ | ❌ |
| create_project | ✅ | ✅ | ❌ |
| deploy_project (propio) | ✅ | ✅ | ❌ |
| deploy_project (otro) | ✅ | ❌ | ❌ |
| edit_project (propio) | ✅ | ✅ | ❌ |
| delete_project | ✅ | ❌ | ❌ |
| view_project | ✅ | ✅ | ✅ |
| view_logs | ✅ | ✅ | ✅ |
| view_events | ✅ | ✅ | ✅ |
| view_health | ✅ | ✅ | ✅ |

## Ownership

Cada proyecto tiene un owner (el usuario que lo creó):

- **Admin**: Puede ver/editar todos los proyectos
- **Deployer**: Solo puede editar sus propios proyectos
- **Viewer**: Solo puede ver (sin edición)

Ejemplo:
```
Usuario: juan (deployer)
Crea: proyect-a
→ owner = juan, created_by = juan

Usuario: maria (deployer)
Ve proyecto-a: ✅ Lectura
Intenta redeploy proyecto-a: ❌ Forbidden (no owner)
```

## Auditoría

Cada evento registra quién lo creó:

```
events table:
  id | project_name | kind | detail | created_by | created_at
  1  | myapp        | deploy | ... | juan | 2025-08-08T15:30:00Z
  2  | myapp        | health_check | ... | (auto-task) | 2025-08-08T15:35:00Z
```

Admins pueden auditar por usuario:

```bash
# Ver eventos de un usuario
curl -H "Authorization: Bearer $DEVPS_TOKEN" \
  https://devps.webshooks.com/events?created_by=juan
```

## API Reference

### Get Current User

```bash
curl -H "Authorization: Bearer $DEVPS_TOKEN" \
  https://devps.webshooks.com/auth/me
```

**Response**:
```json
{
  "username": "juan",
  "role": "deployer",
  "created_at": "2025-08-01T10:00:00Z"
}
```

### List Users (Admin Only)

```bash
curl -H "Authorization: Bearer $DEVPS_TOKEN" \
  https://devps.webshooks.com/users
```

**Response**:
```json
[
  {"username": "admin", "role": "admin", "created_at": "2025-08-01T09:00:00Z"},
  {"username": "juan", "role": "deployer", "created_at": "2025-08-01T10:00:00Z"},
  {"username": "maria", "role": "viewer", "created_at": "2025-08-02T11:00:00Z"}
]
```

### Create User (Admin Only)

```bash
curl -X POST -H "Authorization: Bearer $DEVPS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "carlos",
    "password": "secure-password",
    "role": "deployer"
  }' \
  https://devps.webshooks.com/users
```

### Change User Role (Admin Only)

```bash
curl -X PATCH -H "Authorization: Bearer $DEVPS_TOKEN" \
  https://devps.webshooks.com/users/juan \
  -d '{"role": "admin"}'
```

### Delete User (Admin Only)

```bash
curl -X DELETE -H "Authorization: Bearer $DEVPS_TOKEN" \
  https://devps.webshooks.com/users/carlos
```

**Note**: Deleting a user orphans their projects (owner → NULL) but keeps the projects.

## Security Notes

- Passwords: PBKDF2-SHA256 con 100k iterations, salt aleatorio
- Session: Cookie firmada con DEVPS_TOKEN, HTTPS-only en production
- RBAC checks: En cada ruta, antes de acceso a datos
- Audit trail: Cada cambio registra username + timestamp
- No shared credentials: Cada usuario tiene su propia contraseña

## Migration from Single-User

Si estabas usando el antiguo DEVPS_TOKEN login:

1. Crear usuarios admin/deployer/viewer
2. Compartir dashboard URL `https://devps.webshooks.com/dashboard`
3. Cada usuario inicia sesión con username/password
4. API sigue usando bearer token (CLI no cambia)

Dashboard y API ahora soportan multi-user. CLI (`hzploy`) sigue usando `DEVPS_TOKEN` como antes (no cambios).

## Troubleshooting

### "Invalid username or password"

1. Verifica que el usuario existe: `sqlite3 ... SELECT * FROM users WHERE username = '...';`
2. Verifica que la contraseña es correcta (rehaz el hash y compara)
3. Verifica que el usuario no fue borrado

### "You don't have permission to..."

1. Verifica el rol del usuario: `SELECT role FROM users WHERE username = '...';`
2. Verifica la matriz de permisos arriba
3. Para deployer: verifica que eres owner del proyecto (SELECT owner FROM projects WHERE name = '...';)

### Admin locked out

Si el admin perdió acceso:

```bash
ssh root@89.167.96.239
sqlite3 /opt/devps/data/registry.db

# Reset admin password
UPDATE users SET password_hash = '...', password_salt = '...' 
WHERE username = 'admin';
```

Genera nuevo hash+salt con Python como se muestra arriba.

## Future Enhancements

- Teams/groups (múltiples deployersper equipo)
- Project-level permissions (más granular)
- OAuth2/OIDC (integración LDAP, Google, etc.)
- Session timeout configurable
- Two-factor authentication
- Password policy enforcement

## See Also

- [rbac.py](agent/devps_agent/rbac.py) — Lógica de permisos
- [registry.py](agent/devps_agent/registry.py) — User CRUD
- [dashboard.py](agent/devps_agent/dashboard.py) — Rutas con autorización
