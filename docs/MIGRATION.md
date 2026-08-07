# Migrar un sitio fuera de Coolify

Nunca big-bang. Sitio por sitio, sin cortar tráfico real hasta confirmar
que el reemplazo funciona.

## Piloto sugerido: `webshooks.com`

Es estático (sin backend, sin base de datos) — el candidato de menor
riesgo para validar el proceso completo antes de tocar sitios con más
tráfico o de más valor para un cliente.

## Paso a paso

### 1. Adoptar (solo visibilidad, cero riesgo)

```bash
hzploy adopt webshooks-static <nombre-del-contenedor-actual> --domain webshooks.com
```

Esto solo registra el contenedor que Coolify ya gestiona en el registro de
devps — no cambia nada de cómo corre ni de cómo se rutea el tráfico. Sirve
para que `hzploy list` / `/dashboard/migrations` lo muestren, y para
confirmar que el agente puede inspeccionarlo. Este paso queda estampado
solo (`adopted_at`) — no hace falta anotarlo a mano en ningún lado.

### 2. Levantar el reemplazo en paralelo

Con `hzploy up` / el workflow reusable, apuntando al repo del sitio (si el
código está en git) — **sin** pasarle `--domain` todavía. Esto lo levanta
en un puerto nuevo del rango `40000-40999`, sin tocar el tráfico real que
sigue sirviendo la copia de Coolify.

### 3. Probar el reemplazo directo, sin pasar por DNS

```bash
curl -H "Host: webshooks.com" http://127.0.0.1:<puerto-nuevo>/
```

Repetir para cada ruta importante del sitio. El tráfico real de
`webshooks.com` sigue yendo a la copia vieja durante todo este paso.

Ese `hzploy up` sin `--domain`, sobre un proyecto que ya estaba adoptado,
queda estampado solo como `paralleled_at` en `/dashboard/migrations`.

### 4. Cutover — mover el vhost

Recién cuando el paso 3 esté confirmado sano:

```bash
hzploy up webshooks-static <repo> --domain webshooks.com --primary web ...
```

El agente reescribe el vhost de `webshooks.com` para apuntar al contenedor
nuevo y recarga nginx. Esto sí afecta tráfico real — hacerlo en una ventana
de bajo tráfico y verificar inmediatamente después
(`curl -I https://webshooks.com`). Este `hzploy up` con `--domain` queda
estampado solo como `cutover_at`.

### 5. Apagar la copia vieja y sacarla de Coolify

Solo después de confirmar el paso 4 en producción durante un rato (no
minutos — al menos un ciclo de tráfico normal del sitio). A diferencia de
los pasos anteriores, esto **no** se detecta solo — el agente no tiene
forma de saber que apagaste algo en Coolify. Marcarlo a mano:

```bash
curl -X POST http://127.0.0.1:9400/projects/webshooks-static/migration \
  -H "Authorization: Bearer $DEVPS_TOKEN" -H "Content-Type: application/json" \
  -d '{"step": "decommissioned", "notes": "Container legacy-webshooks-web removido de Coolify"}'
```

### 6. Repetir con el siguiente sitio

Un sitio a la vez. Recién cuando la lista de sitios en Coolify llegue a
cero, se desinstala Coolify.

## Registro de migraciones

Vive en `/dashboard/migrations` (o `GET /migrations` en JSON) — ya no hay
que mantener una tabla a mano acá. Cada fila muestra `adopted_at` /
`paralleled_at` / `cutover_at` / `decommissioned_at` reales, estampados
por el agente a medida que corren los pasos de arriba.
