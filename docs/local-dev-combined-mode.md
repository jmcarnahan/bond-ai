# Local Dev — Combined Mode

Combined mode puts the bond-ai backend and Flutter web app behind a single
nginx front door on **`http://localhost:8080`**. It is the recommended URL
for OAuth flow testing and integration work.

Split mode (`make dev`) is unchanged and remains the fastest workflow for
active backend or UI iteration.

---

## Key design choice — no new OAuth callback URLs

Combined mode does **not** require any changes to your OAuth provider
console configuration. Existing callback URLs keep working:

- User-login (Google / Okta / Cognito): `http://localhost:8002/auth/<provider>/callback`
- MCP (Atlassian / GitHub / Microsoft): `http://localhost:8000/connections/<svc>/callback`

The OAuth provider redirects the browser straight to those ports (bypassing
nginx). The session cookie set on `:8002` is then visible on `:8080` when
the user arrives at the app, because **browser cookies on `localhost` are
not port-scoped** — a host-only cookie (no `Domain` attribute) set on
`localhost:8002` is sent on every request to any port on `localhost`.
`SameSite=Strict` allows it because `localhost` is a single site
(verified empirically — see commit history for a Playwright reproduction).

This design diverges from production (Chapter 2), where everything will
live behind one ALB hostname and OAuth callbacks DO route through the
shared host. Local combined mode trades that production-mirror property
for "no provider-console churn during local dev." Chapter 2 will register
the production callbacks at the right time.

---

## Architecture

```
Browser
   │
   ├──► http://localhost:8080  ── nginx (Docker)
   │                              │
   │                              ├── /            → Flutter dev :3002
   │                              ├── /rest/*      → bond-ai     :8002 (strip /rest)
   │                              └── /health      → bond-ai     :8002
   │
   ├──► http://localhost:8002/auth/<p>/callback  (browser → bond-ai directly)
   │
   └──► http://localhost:8000/connections/<s>/callback  (browser → bond-mcps directly)
```

nginx runs as a `nginx:1.27-alpine` container managed by bond-ai's
Makefile. Upstreams are reached via `host.docker.internal`. Backend
(`:8002`) and Flutter (`:3002`) are still host processes — nginx is
only fronting them.

---

## Prerequisites

- Docker Desktop running (`docker info` returns OK).
- `bond-mcps` checked out as a sibling (`../bond-mcps`) with working `make dev`.
- `.env.combined` populated from `.env.combined.example` (see below).

---

## Setup (first time)

```bash
cp .env.combined.example .env.combined
# Edit if you want, but the example is functional as-is. The only meaningful
# overrides are JWT_REDIRECT_URI (post-login lands on :8080), COOKIE_SECURE=false
# (browsers drop Secure cookies over HTTP), and CORS_ALLOWED_ORIGINS.
```

Real OAuth secrets, `BOND_MCP_CONFIG`, JWT signing keys, etc. stay in
`.env` — `load_dotenv()` fills them in without overwriting whatever the
Makefile exported from `.env.combined`.

No OAuth provider console changes are needed.

---

## Daily use

```bash
# Terminal 1
cd ../bond-mcps && make dev-combined        # alias for `make dev`

# Terminal 2
cd ../bond-ai && make dev-combined          # backend + Flutter + nginx
```

Open `http://localhost:8080/`.

`make stop` in each repo shuts everything down (including the nginx
container in bond-ai).

---

## When to use which mode

| Mode | Use for |
|---|---|
| `make dev` (split) | Active iteration on backend or frontend code. Faster startup, fewer moving parts, predictable Flutter hot reload. |
| `make dev-combined` | OAuth flow testing, MCP integration checks, validating the path-routing shape before deployment. |

If Flutter hot reload through the nginx WebSocket proxy is unreliable,
fall back to split mode for active UI work — the app is identical, just
served at `:3002` directly.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `make dev-combined` aborts with "bond-mcps auth proxy not reachable on :8000" | bond-mcps not running | Run `make dev-combined` in bond-mcps first. |
| OAuth login redirect succeeds but the app immediately thinks you're logged out | Browser dropped the cookie because `COOKIE_SECURE=true` over HTTP | Confirm `.env.combined` has `COOKIE_SECURE=false`. Check DevTools → Application → Cookies for `localhost` (no port) — both `bond_session` and `bond_csrf` should be present after login. |
| Flutter hot reload doesn't trigger through nginx | WebSocket proxying through nginx is finicky for dev-server protocols | Use `make dev` (split mode) for active Flutter iteration. |
| `curl :8080/` returns 502 | Flutter not bound to `0.0.0.0` (only `localhost`) — nginx in Docker can't reach `127.0.0.1` on the host | `frontend-combined` binds Flutter to `0.0.0.0`. If you started Flutter manually with `--web-hostname=localhost`, nginx can't reach it. |

---

## Why combined mode exists at all

Given the cross-port cookie trick makes the OAuth flow work even in split
mode, what's combined mode actually for?

1. **Single URL to remember.** `http://localhost:8080/` is the only URL a
   developer needs to know — same shape as production.
2. **Rehearses the production routing model.** The nginx config is a local
   stand-in for the eventual ALB Ingress, so routing bugs show up locally
   before they show up in deployment.
3. **Same-origin app + API.** No CORS preflight on every `fetch()` from
   the SPA because the app and API share an origin.

These are conveniences, not necessities. Split mode is still a valid
daily-driver — combined mode is the option for when you want
production-shaped local testing.

---

## Out of scope

- **Production `nginx-combined.conf`** (App Runner combined-docker target)
  has its own `/connections/` upstream concerns. Tracked separately; will
  be addressed in Chapter 2 or when the App Runner combined-docker path
  is deprecated in favor of EKS path-based routing.
- **bond-mcps Authorization Server (`:8001`)** routes (`/connect/`,
  `/oauth/`, `/.well-known/`) are not in scope here. When JWT mode
  becomes the default workflow they'll need their own routing decision —
  whether that's through nginx (forward-allocated in the config, since
  they're real HTTP endpoints with browser involvement) or bypassed like
  the current MCP callbacks depends on how the AS cookie/token flow
  shakes out.
- **Mobile (`bondai://auth-callback`)** flows are unaffected by this change.
