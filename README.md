# devps

Self-operated deploy control plane for the shared Hetzner VPS. One agent,
one shared credential, per-project onboarding without a new SSH key, a new
hand-picked port, or a new nginx vhost every time.

## Status

**Phase 0 — done:** read-only audit of the VPS.
[`docs/AUDIT.md`](docs/AUDIT.md) has the findings (what Coolify manages,
what's hand-managed, ports already in use, the ones `devps` claims for
itself).

**Phase 1 — this repo, pending bootstrap on the VPS:** the control-plane
agent (FastAPI, runs as a systemd service directly on the host — see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for why it's not
containerized), a SQLite registry, port allocation, nginx vhost + certbot
automation, a `hzploy` CLI, and a reusable GitHub Actions workflow other
repos call to deploy. See [`docs/ONBOARDING.md`](docs/ONBOARDING.md) to
bring a project in, and [`docs/MIGRATION.md`](docs/MIGRATION.md) for the
site-by-site plan to move things currently on Coolify over, with zero
downtime and no big-bang cutover.

**Phase 2 (next):** a dashboard over the same registry the agent already
maintains.

## Why this exists

This VPS runs multiple unrelated projects behind one IP (no project gets a
dedicated server). Onboarding each one by hand meant: a new SSH keypair, a
manually chosen port (checked by hand against `ss -tlnp` to avoid
collisions), a hand-written `docker-compose.coexist.yml`, and a hand-written
nginx vhost + certbot run. `devps` replaces all of that with one long-lived
agent that owns port allocation, container lifecycle, and reverse-proxy
routing for every project on the box.
