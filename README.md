# devps

Self-operated deploy control plane for the shared Hetzner VPS. One agent,
one shared credential, per-project onboarding without a new SSH key, a new
hand-picked port, or a new nginx vhost every time.

## Status

**Phase 0 (current):** read-only audit of the VPS — see
[`.github/workflows/audit.yml`](.github/workflows/audit.yml) and
[`docs/AUDIT.md`](docs/AUDIT.md) once it's run.

**Phase 1 (next):** the actual control-plane agent (FastAPI) + a shared
reverse proxy (Traefik) so any project can be onboarded by calling one API,
instead of hand-writing a `docker-compose.coexist.yml` + deploy script +
GitHub Actions workflow per repo (see `fmonfasani/wapsell-saas` and
`fmonfasani/ailearning` for what that looked like before this existed).

## Why this exists

This VPS runs multiple unrelated projects behind one IP (no project gets a
dedicated server). Onboarding each one by hand meant: a new SSH keypair, a
manually chosen port (checked by hand against `ss -tlnp` to avoid
collisions), a hand-written `docker-compose.coexist.yml`, and a hand-written
nginx vhost + certbot run. `devps` replaces all of that with one long-lived
agent that owns port allocation, container lifecycle, and reverse-proxy
routing for every project on the box.
