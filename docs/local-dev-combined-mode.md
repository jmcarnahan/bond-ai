# Local Dev — Combined Mode

Combined mode puts the bond-ai backend, Flutter web app, and bond-mcps auth
proxy behind a single nginx front door on **`http://localhost:8000`**. It's
the local-dev analogue of the production single-ALB routing model.

Front-door port `:8000` is chosen because the OAuth callback URLs already
registered with every provider (Google / Okta / Cognito for user-login;
Atlassian / GitHub / Microsoft for MCP) use `:8000`. Combined mode aligns the
local stack with those existing URLs — **no provider console changes needed**.

Split mode (`make dev`) is unchanged and remains the fastest workflow for
active backend or UI iteration.

---

## Architecture

```
Browser / OAuth provider
        │
        ▼
┌────────────────────────────────────────────────────────────────────┐
│  nginx :8000  (bond-ai owns the config)                            │
│                                                                    │
│   /                           ──►  static Flutter build            │
│                                   (flutterui/build/web mounted as  │
│                                    /usr/share/nginx/html)          │
│   /rest/<api>                 ──►  bond-ai     :8002 (strip)       │
│   /health                     ──►  bond-ai     :8002               │
│   /auth/<provider>/callback   ──►  bond-ai     :8002               │
│   /login/<provider>           ──►  bond-ai     :8002               │
│   /connections/<svc>/callback ──►  bond-mcps   :18000              │
└────────────────────────────────────────────────────────────────────┘
```

The Flutter app is served as a **static build** — nginx serves the
pre-compiled bundle out of `flutterui/build/web/`. There is no
`flutter run` process in combined mode. This intentionally trades hot
reload for stability: `flutter run -d web-server` behind nginx was
fragile (DDS hangs, port-bind quirks, slow 965-script first paint).

**bond-mcps's auth proxy MOVES off `:8000` in combined mode** — it binds
to `:18000` instead so nginx can take `:8000` as the front door. The
individual MCP services (Microsoft, GitHub, Atlassian, Databricks) keep
their `:18001`–`:18004` ports.

nginx runs as a `nginx:1.27-alpine` Docker container managed by bond-ai's
Makefile. API upstreams are reached via `host.docker.internal`. Backend
(`:8002`) and bond-mcps (`:18000` in combined mode) are still host
processes — nginx is only fronting them and serving the static Flutter
bundle.

---

## Prerequisites

- Docker Desktop running (`docker info` returns OK).
- `bond-mcps` checked out as a sibling (`../bond-mcps`) with `make install` done.
- `.env.combined` populated from `.env.combined.example` (see below).
- Existing OAuth callback URLs registered with providers at `:8000`. If
  you have URLs at any other port (e.g., `:8002` from the recent port
  migration), this design will fail with `redirect_mismatch` until you
  align them.

---

## Setup (first time)

```bash
cp .env.combined.example .env.combined
# Edit if you want — the defaults work as-is. Overrides:
#   GOOGLE_AUTH_REDIRECT_URI=http://localhost:8000/auth/google/callback
#   OKTA_REDIRECT_URI=http://localhost:8000/auth/okta/callback
#   COGNITO_REDIRECT_URI=http://localhost:8000/auth/cognito/callback
#   JWT_REDIRECT_URI=http://localhost:8000
#   COOKIE_SECURE=false       (HTTP local dev)
#   CORS_ALLOWED_ORIGINS includes http://localhost:8000
```

Real OAuth client IDs and secrets, `BOND_MCP_CONFIG`, JWT signing keys,
etc. stay in `.env`. `load_dotenv()` fills them in without overwriting
what `.env.combined` exported.

---

## Daily use

```bash
# Terminal 1
cd ../bond-mcps && make dev-combined        # auth proxy on :18000, MCPs on :18001-:18004

# Terminal 2
cd ../bond-ai && make dev-combined          # build-web (if needed) + backend + nginx
```

Open **`http://localhost:8000/`**.

The first `make dev-combined` triggers `flutter build web` (~30–60s);
subsequent runs skip the build via mtime-based Make dependency. After
editing any Flutter source file (`flutterui/lib/**`, `flutterui/web/**`,
`pubspec.yaml`, `pubspec.lock`), re-run `make dev-combined` — build-web
detects the change and rebuilds.

`make stop` in each repo shuts everything down (including the nginx
container on the bond-ai side).

---

## When to use which mode

| Mode | Use for |
|---|---|
| `make dev` (split) | Active iteration on backend or frontend code. Faster startup, fewer moving parts, hot reload. Flutter dev server with live recompilation. |
| `make dev-combined` | OAuth flow testing, MCP integration, validating production-shaped routing. Static Flutter bundle (no hot reload — re-run `make dev-combined` to rebuild). |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `make dev-combined` aborts with "bond-mcps auth proxy not reachable on :18000" | bond-mcps not in combined mode | Run `make dev-combined` (not `make dev`) in bond-mcps first. |
| OAuth provider returns `redirect_mismatch` | Provider has a different URL registered than what bond-ai is sending | Confirm the provider's allowed callback list includes `http://localhost:8000/auth/<provider>/callback`. If you have a different port registered, either add `:8000` or change the corresponding `*_REDIRECT_URI` in `.env.combined`. |
| Login redirect succeeds but the app immediately thinks you're logged out | Browser dropped the `Secure` cookie sent over HTTP | Confirm `.env.combined` has `COOKIE_SECURE=false`. DevTools → Application → Cookies → `localhost` should show `bond_session` and `bond_csrf` after login. |
| `make dev-combined` startup probe says `[warn] /rest/providers returned HTML` | nginx routing wrong, or backend didn't load `.env.combined` | Check `tmp/logs/backend.log` for the loaded env vars; check `make nginx-logs`. |
| Combined-mode UI doesn't reflect a recent Flutter code change | Static bundle is stale | Re-run `make dev-combined` — build-web detects via mtime and rebuilds. |
| `make build-web` fails with `Avoid non-constant invocations of IconData` | A new icon-pack import broke tree-shaking | The Makefile passes `--no-tree-shake-icons` already; check that you didn't drop that flag in a local edit. |
| Regular browser shows blank page but incognito works | Cached service worker or stale assets from a previous Flutter dev-server session | DevTools → Application → Storage → Clear site data, then hard refresh. |

---

## Why combined mode exists

1. **Single host:port for OAuth callbacks.** All six providers (3
   user-login + 3 MCP) point at `:8000`. Production (Chapter 2) will use
   `https://app.{env}.example.com` with the same path-based routing —
   combined mode is the local rehearsal of that shape.
2. **Single URL to remember.** `http://localhost:8000/` is the only URL
   you visit during a combined-mode session.
3. **Same-origin app + API.** The browser sees `:8000` as the origin for
   both page loads and `fetch()` calls — no CORS preflight on every API
   call.

For active code iteration, split mode is simpler and faster. Combined
mode is the production-shape rehearsal.

---

## Out of scope

- **Production `nginx-combined.conf`** (App Runner combined-docker target)
  has its own `/connections/` upstream concerns. Tracked separately;
  Chapter 2 (EKS path-based routing) supersedes that deployment model.
- **bond-mcps Authorization Server (`:8001`)** routes (`/connect/`,
  `/oauth/`, `/.well-known/`) are forward-allocated as commented-out
  blocks in the nginx config. Uncomment when JWT mode is in regular use.
- **Mobile (`bondai://auth-callback`)** flows are unaffected by this work.
