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
para que `hzploy list` / el dashboard (Fase 2) lo muestren, y para
confirmar que el agente puede inspeccionarlo.

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

### 4. Cutover — mover el vhost

Recién cuando el paso 3 esté confirmado sano:

```bash
hzploy up webshooks-static <repo> --domain webshooks.com --primary web ...
```

El agente reescribe el vhost de `webshooks.com` para apuntar al contenedor
nuevo y recarga nginx. Esto sí afecta tráfico real — hacerlo en una ventana
de bajo tráfico y verificar inmediatamente después
(`curl -I https://webshooks.com`).

### 5. Apagar la copia vieja y sacarla de Coolify

Solo después de confirmar el paso 4 en producción durante un rato (no
minutos — al menos un ciclo de tráfico normal del sitio). Documentar acá
mismo qué contenedor/proyecto de Coolify se dio de baja y cuándo.

### 6. Repetir con el siguiente sitio

Un sitio a la vez. Recién cuando la lista de sitios en Coolify llegue a
cero, se desinstala Coolify.

## Registro de migraciones

| Sitio | Adoptado | Cutover | Coolify dado de baja | Notas |
|---|---|---|---|---|
| _(vacío — se llena a medida que se migra cada uno)_ | | | | |
