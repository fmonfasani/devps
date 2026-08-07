# devps

Self-operated deploy control plane for the shared Hetzner VPS. One agent,
one shared credential, per-project onboarding without a new SSH key, a new
hand-picked port, or a new nginx vhost every time.

## Status

**Phase 0 — done:** read-only audit of the VPS.
[`docs/AUDIT.md`](docs/AUDIT.md) has the findings (what Coolify manages,
what's hand-managed, ports already in use, the ones `devps` claims for
itself).

**Phase 1 — live, bootstrapped on the VPS:** the control-plane agent
(FastAPI, runs as a systemd service directly on the host — see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for why it's not
containerized), a SQLite registry, port allocation, nginx vhost + certbot
automation, a `hzploy` CLI, and a reusable GitHub Actions workflow other
repos call to deploy. See [`docs/ONBOARDING.md`](docs/ONBOARDING.md) to
bring a project in, and [`docs/MIGRATION.md`](docs/MIGRATION.md) for the
site-by-site plan to move things currently on Coolify over, with zero
downtime and no big-bang cutover.

**Phase 2 — this repo, pending redeploy:** a server-rendered dashboard
(same FastAPI process, no separate service or build step — see
`/dashboard`) over an extended registry that now keeps history, not just
current state:

- an append-only `events` log — every `deploy`/`adopt`/`restart` records
  what happened and when, including failed attempts, so a status snapshot
  can't hide that something broke and got retried;
- a `migrations` table — the live version of `docs/MIGRATION.md`'s table,
  stamped automatically by `adopt` (→ *adopted*) and `deploy` on a
  previously-adopted project (→ *paralleled* without a domain, *cutover*
  with one); `decommissioned` is stamped by hand
  (`POST /projects/{name}/migration`), since the agent has no way to know
  when the old copy actually got turned off.

Login is the same `DEVPS_TOKEN`, entered once into a form instead of typed
into a header every time.

## Why this exists

This VPS runs multiple unrelated projects behind one IP (no project gets a
dedicated server). Onboarding each one by hand meant: a new SSH keypair, a
manually chosen port (checked by hand against `ss -tlnp` to avoid
collisions), a hand-written `docker-compose.coexist.yml`, and a hand-written
nginx vhost + certbot run. `devps` replaces all of that with one long-lived
agent that owns port allocation, container lifecycle, and reverse-proxy
routing for every project on the box.
