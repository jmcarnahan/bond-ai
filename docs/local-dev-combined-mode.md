# Local Dev — Combined Mode (path-based routing)

Combined mode runs the bond-ai backend, Flutter web app, and bond-mcps OAuth proxy behind a single nginx front door on **`http://localhost:8080`**. It mirrors the production ALB shape, so each OAuth provider only needs **one** localhost callback URL per environment (instead of one per service).

Split mode (`make dev`) is unchanged and remains the recommended workflow for active iteration. Combined mode (`make dev-combined`) is for OAuth-flow testing and integration work.

---

## Architecture

```
Browser / OAuth provider
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│  nginx :8080 (bond-ai owns the config)                        │
│                                                               │
│   /auth/<provider>/callback   ──►  bond-ai     :8002          │
│   /rest/<api>                 ──►  bond-ai     :8002 (strip)  │
│   /health                     ──►  bond-ai     :8002          │
│   /connections/<svc>/callback ──►  bond-mcps   :8000          │
│   /connect/<svc>/callback     ──►  bond-mcps AS :8001 (future)│
│   /oauth/*                    ──►  bond-mcps AS :8001 (future)│
│   /.well-known/*              ──►  bond-mcps AS :8001 (future)│
│   /                           ──►  Flutter dev :3002          │
└───────────────────────────────────────────────────────────────┘
```

nginx runs as a Docker container (`nginx:1.27-alpine`) managed by bond-ai's Makefile. The container reaches host-running services via `host.docker.internal`.

---

## Why this design

| Decision | Rationale |
|---|---|
| Front-door port **`:8080`** | Matches the existing `nginx-combined.conf`; not taken by anything in our local landscape. |
| nginx as **Docker container** | macOS doesn't ship nginx; Alpine image is ~10 MB and starts in <1s. Mirrors prod's containerized routing. |
| **Separate `nginx-local-combined.conf`** | Prod and local target different upstreams (in-container vs host). One file would be wrong for both. |
| **Independent two-command startup** | `make dev-combined` in each repo. Hard-fail (not warn) in bond-ai if bond-mcps isn't reachable on `:8000`. Fewer surprises than auto-invoking across repos. |
| **`BOND_FRONT_DOOR_URL` runtime rewrite** | `config.py` rewrites `:8000/connections/` → front-door URL inside `BOND_MCP_CONFIG` at parse time. Single source of truth — no duplicate `.env` files to maintain. |
| **`COOKIE_SECURE=false` in `.env.combined`** | `auth.py` defaults to `Secure` cookies. Browsers silently drop `Secure` cookies sent over HTTP, which would look like "logged-out for no reason" with no error. Production stays secure by default. |
| **Split mode untouched** | `make dev` works exactly as today. Combined mode is purely additive — falls back cleanly if anything goes wrong. |

---

## Prerequisites

- Docker Desktop running (`docker info` returns OK).
- `bond-mcps` checked out as a sibling (`../bond-mcps`) with working `make dev`.
- `.env.combined` populated from `.env.combined.example` (see "Setup" below).

---

## Setup (first time)

1. **Copy and edit the env template:**
   ```bash
   cp .env.combined.example .env.combined
   # Edit to fill in OAuth client IDs/secrets and your BOND_MCP_CONFIG JSON.
   # Note: BOND_MCP_CONFIG can be your normal split-mode JSON unchanged —
   # config.py rewrites :8000/connections/ → :8080/connections/ at parse time
   # because BOND_FRONT_DOOR_URL is set in .env.combined.
   ```

2. **Register the combined-mode callback URLs in each OAuth provider console** (additive — keep the existing `:8002` and `:8000` entries):
   - User-login providers (Google / Okta / Cognito): add `http://localhost:8080/auth/<provider>/callback`.
   - MCP providers (Atlassian / GitHub / Microsoft): add `http://localhost:8080/connections/<provider>/callback`.

---

## Daily use

Two commands in two terminals:

```bash
# Terminal 1
cd /Users/jcarnahan/projects/bond-mcps
make dev-combined            # auth proxy on :8000 with PUBLIC_URL=http://localhost:8080

# Terminal 2
cd /Users/jcarnahan/projects/bond-ai
make dev-combined            # backend :8002, Flutter :3002, nginx :8080
```

Then open `http://localhost:8080/` in a browser.

`make stop` in each repo shuts everything down (including the nginx container in bond-ai).

---

## When to use which mode

| Mode | Use for |
|---|---|
| `make dev` (split) | Active iteration on backend or frontend code. Faster startup, fewer moving parts, predictable hot reload. |
| `make dev-combined` | OAuth provider flow testing, end-to-end integration checks, validating the path-routing shape before deployment. |

If Flutter hot reload through the nginx WebSocket proxy is unreliable, fall back to split mode for active UI work.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `make dev-combined` aborts with "bond-mcps auth proxy not reachable on :8000" | bond-mcps not running | Run `make dev-combined` in bond-mcps first. |
| OAuth login succeeds but session immediately ends; UI thinks you're logged out | `COOKIE_SECURE=true` and HTTP — browser dropped the cookie | Confirm `.env.combined` has `COOKIE_SECURE=false`. Check DevTools → Application → Cookies for `http://localhost:8080`. |
| nginx 503 with `bond-mcps auth proxy not reachable on :8000` JSON | bond-mcps went down mid-session | Restart bond-mcps; `make nginx-reload` is not required (502 → 503 is upstream-only). |
| `/connections/<svc>/callback` returns from bond-ai's :8002 instead of bond-mcps :8000 | Stale split-mode browser cache or wrong env var | Hard refresh; verify `BOND_FRONT_DOOR_URL` set in `.env.combined`; check backend log for "Rewrote MCP redirect URIs..." line. |
| Flutter hot reload doesn't trigger through nginx | WebSocket proxying through nginx is finicky | Use `make dev` (split mode) for active Flutter iteration. |

---

## Out of scope

- **Production nginx-combined.conf** has the same `/connections/` upstream as this local config, and is silently broken in App Runner deployments since the MCP code moved to bond-mcps. Tracked separately; will be addressed in the production routing chapter or when the App Runner combined-docker path is deprecated in favor of EKS path-based routing.
- **bond-mcps Authorization Server (`:8001`)** routes (`/connect/`, `/oauth/`, `/.well-known/`) are forward-allocated as commented-out blocks in `nginx-local-combined.conf`. Uncomment when JWT mode is in regular local use.
- **Mobile (`bondai://auth-callback`)** flows are unaffected by this change.
