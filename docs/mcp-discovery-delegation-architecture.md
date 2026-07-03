# MCP Discovery & OAuth Delegation — Architecture & Review Guide

**Purpose:** a self-contained overview of the cross-repo effort that moves bond-ai
from hard-configuring MCP servers (and driving their OAuth itself) to **discovering**
them from bond-mcps and **delegating** the OAuth/Connect flow to bond-mcps. Written
to support a complete senior review in a fresh session — it covers the goal, the
authentication/discovery architecture, every file changed in both repos, how to run
and test it locally, how it maps to the deployed (EKS) environment, and the
non-obvious factors a reviewer should scrutinize.

**Status at time of writing (updated 2026-07-02; originally 2026-06-22):**

| Repo | Branch / state | PR | Scope |
|------|----------------|----|-------|
| **bond-ai** | PR #201 **merged to `main`** (`a9ad9df`); follow-up branch `fix-mcp-callback-connections-path` (5 commits, e2e-verified, pending PR) | #201 (merged) | discovery client, config overlay, connect client, delegated connections router, runtime JWT forwarding, nginx, tests. Follow-up: canonical-callback nginx routing, managed status in /mcp/tools, server-side JWT mint, discovery fast-retry, verify script |
| **bond-mcps** | `feat-mcp-delegation-companion` (**open, not merged**) | #9 (open) | HS256 delegation mode, `return_url` callback, status/disconnect routes, deployment-aware discovery file + AS route, scopes consolidation, tests. Follow-up commits: live integration test through FastMCP auth middleware; **callback moved to canonical `/connections/<name>/callback`** (66f7bdc) |

> **2026-07-02 update — canonical callback path.** After this doc was first
> written, commit `66f7bdc` (bond-mcps) moved the provider OAuth callback from
> `/connect/<name>/callback` to the **already-registered**
> `/connections/<name>/callback`, so delegation needs **no new provider-console
> registrations**. The ticket/start/status/disconnect routes stay under
> `/connect/<name>`. Sections below have been updated; if you find a stray
> `/connect/<name>/callback` reference, it's stale — trust this note.

> **Important rollout property:** the bond-ai side is **inert until configured**. With
> `BOND_MCPS_DISCOVERY_URL` unset, discovery is a no-op and behavior is identical to
> before. So merging bond-ai ahead of bond-mcps is safe; nothing activates until both
> the env var and the bond-mcps side are in place.

---

## Table of contents
1. [What we're building and why](#1-what-were-building-and-why)
2. [The three planes: Discovery, Authentication, Connect](#2-the-three-planes)
3. [The cross-repo contract (locked)](#3-the-cross-repo-contract-locked)
4. [End-to-end flows](#4-end-to-end-flows)
5. [Path & port topology (local combined mode)](#5-path--port-topology-local-combined-mode)
6. [Files changed/added — bond-ai](#6-files-changedadded--bond-ai)
7. [Files changed/added — bond-mcps](#7-files-changedadded--bond-mcps)
8. [How to run locally](#8-how-to-run-locally)
9. [How to test](#9-how-to-test)
10. [Deployed (EKS) architecture](#10-deployed-eks-architecture)
11. [Hidden factors & risks a reviewer should scrutinize](#11-hidden-factors--risks-a-reviewer-should-scrutinize)
12. [Open questions / decisions](#12-open-questions--decisions)
13. [Appendix: commit & branch index](#13-appendix-commit--branch-index)

---

## 1. What we're building and why

### The problem
A prior cross-repo refactor moved the MCP servers and their OAuth configuration into
**bond-mcps**, which is meant to be the single owner of "everything about an MCP" (its
URL, tools, OAuth scopes/client, per-user tokens). bond-ai, however, still:

1. **Hard-configured the full MCP list** (URLs, scopes, client IDs) in `BOND_MCP_CONFIG`
   (env / Secrets Manager). This config *drifted* — bond-ai's Atlassian tile sent stale
   **classic** OAuth scopes the registered app no longer supported, so Atlassian rejected
   the authorize request. There were three independent owners of the same OAuth config.
2. **Ran its own OAuth "Connect" flow** and stored tokens in its own `mcp_token_cache`,
   a parallel world to bond-mcps' `tokens.db`.

### The decision: full delegation (handoff-doc "Option A")
bond-mcps shipped a discovery endpoint that lists MCPs as `{name, display_name, url}`
only — **no OAuth metadata by design**. That made the original "overlay scopes from
discovery" idea (Option C) impossible, so we went with **full delegation**:

- bond-ai **discovers** the MCP set from bond-mcps (one env var, polled).
- bond-ai **authenticates** MCP tool calls with its own **Bond JWT**, validated by
  bond-mcps via a **shared secret**. bond-mcps resolves the per-user provider token
  itself.
- bond-ai **delegates** the OAuth Connect flow to bond-mcps' `/connect/<name>` routes;
  the provider redirect lands on bond-mcps (which stores the token), then the user is
  returned to bond-ai with the connection established.

**Net effect:** bond-mcps becomes the single source of truth for MCP config and managed
provider tokens; the stale-scope class of bug is structurally eliminated; the two token
stores unify *for managed providers* (user-defined BYO-OAuth servers stay bond-ai-owned).

---

## 2. The three planes

The integration is best understood as three orthogonal planes that share one identity
(the Bond JWT) but otherwise solve independent problems.

### 2a. Discovery plane — "which MCPs exist and where"
- bond-ai calls `GET {BOND_MCPS_DISCOVERY_URL}` → `{"mcps":[{name, display_name, url}]}`.
- Cached in-process with a TTL and refreshed by a background poller (so MCPs can be
  added/removed without restarting bond-ai — *with caveats in deployment, see §11*).
- The discovered set is overlaid onto bond-ai's effective MCP config as `bond_jwt`
  servers; everything beyond the URL (tools) is learned via the MCP protocol itself.

### 2b. Authentication plane — Bond JWT + shared secret
- bond-ai mints **HS256** JWTs signed with `JWT_SECRET_KEY`; claims: `sub`=**email**,
  `iss="bond-ai"`, `aud=["bond-ai-api","mcp-server"]`, `exp`, `jti`.
- Every bond-mcps-bound call (discovery is unauthenticated; tool calls + connect calls
  are authenticated) carries `Authorization: Bearer <BondJWT>`.
- bond-mcps validates with the **same secret** (`BOND_MCPS_JWT_PUBLIC_KEY` = bond-ai's
  `JWT_SECRET_KEY`, `BOND_MCPS_JWT_ALGORITHM=HS256`, `BOND_MCPS_JWT_ISSUER=bond-ai`,
  `BOND_MCPS_JWT_AUDIENCE=mcp-server`) and derives **`user_key = sub = email`**.
- This is the same identity at connect-time (ticket mint) and tool-call-time, so the
  token stored during Connect is the one resolved during a later tool call.

### 2c. Connect plane — delegated OAuth with a return trip
- bond-ai never drives provider OAuth for managed MCPs. It mints a **ticket** at
  bond-mcps, hands the browser bond-mcps' `connect_url`, and supplies a **`return_url`**.
- bond-mcps runs the provider OAuth, stores the token in `tokens.db` keyed by `user_key`,
  then **302s the browser back** to bond-ai's `return_url` with a success/error marker.
- bond-ai's connections screen reads the marker, reloads, and queries
  `GET /connect/<name>/status` per managed MCP to render Connect/Disconnect.

### Identity & token ownership summary
| | Managed MCPs (discovered) | User-defined MCPs (BYO OAuth) |
|--|---------------------------|-------------------------------|
| Config owner | bond-mcps | bond-ai (DB) |
| OAuth driven by | bond-mcps `/connect/<name>` | bond-ai `connections.py` (unchanged) |
| Tokens stored in | bond-mcps `tokens.db` (key = JWT `sub`=email) | bond-ai `mcp_token_cache` |
| Tool-call auth | Bond JWT (bond-mcps resolves the provider token) | bond-ai attaches the provider access token |

---

## 3. The cross-repo contract (locked)

bond-ai's client is `bondable/bond/mcp_connect_client.py`. For each managed MCP it
derives `base = scheme://host[:port]` from the discovered URL (with the `/mcp` path
stripped), then calls (all with `Authorization: Bearer <BondJWT>`):

| Op | Method + path | Request | Success response | 404 means |
|----|---------------|---------|------------------|-----------|
| discovery | `GET {discovery_url}` *(unauthenticated)* | — | `{"mcps":[{name,display_name,url}]}` | — |
| mint ticket | `POST {base}/connect/{name}/ticket` | JSON `{return_url}` | `{ticket, connect_url}` (`connect_url` required) | — |
| status | `GET {base}/connect/{name}/status` | — | `{connected, valid, scopes}` | "no connect surface" → bond-ai omits the tile |
| disconnect | `DELETE {base}/connect/{name}` | — | `{disconnected: bool}` | nothing to delete → `false` |

Browser-facing (not called by bond-ai, hit by the user's browser / the provider):

| Op | Method + path | Behavior |
|----|---------------|----------|
| start | `GET {connect_base}/connect/{name}?ticket=…&return_url=…` | validate ticket, PKCE, 302 → provider authorize URL |
| callback | `GET {connect_base}/connections/{name}/callback?code&state` | exchange code, store token, **302 → `{return_url}{?\|&}connection_success={name}`** (or `connection_error={name}&error=…`); legacy "close this tab" HTML if no `return_url`. **Note the `/connections/` (plural) path** — the canonical, already-registered provider redirect (shared with the CLI flow), so delegation needs no new console registration (66f7bdc) |

**Bond JWT shape** (bond-ai `rest/utils/auth.py`, `routers/auth.py`): HS256, secret =
`JWT_SECRET_KEY`; `sub`=email, `iss="bond-ai"`, `aud=["bond-ai-api","mcp-server"]`,
`exp`, `jti`.

**Status semantics** (bond-mcps `connect_routes.py`): `connected` = a token row exists
for `(user_key, provider)`; `valid` = (not expired) **or** a refresh token is present
(refresh-only state still reads as connected → shows *Disconnect*); `scopes` = stored
granted scopes.

**Return-URL safety:** validated on **both** sides — bond-ai via `is_safe_redirect_url`
(`ALLOWED_REDIRECT_DOMAINS`); bond-mcps via `_validate_return_url` against
`BOND_MCPS_ALLOWED_RETURN_HOSTS` (CSV allowlist), re-checked at redirect time.

---

## 4. End-to-end flows

### Discovery (background, every TTL)
```
bond-ai mcp_discovery ──GET {BOND_MCPS_DISCOVERY_URL}──▶ bond-mcps (AS or auth proxy)
        ◀── {"mcps":[{name,display_name,url}]} ──
   → overlaid into get_mcp_config() as bond_jwt / streamable-http servers
```

### Tool call (runtime)
```
bond-ai execute_mcp_tool ──Bearer <BondJWT>──▶ bond-mcps MCP  /mcp
                          bond-mcps verifies JWT (shared secret) → user_key = sub = email
                          → tokens.db lookup → calls the upstream provider
   (no token → MissingProviderConnection → tool error carries a /connect URL →
    bond-ai returns a structured authorization_required result)
```

### Connect (the user journey)
```
1. User clicks "Connect" on a tile
   bond-ai  GET /rest/connections/<name>/authorize
   bond-ai  ──POST {base}/connect/<name>/ticket  (Bond JWT, {return_url})──▶ bond-mcps MCP
            ◀── { connect_url } ──
   Browser ◀── authorization_url = connect_url ──
2. Browser ──▶ bond-mcps  GET /connect/<name>?ticket&return_url ──▶ provider authorize
3. provider ──▶ bond-mcps GET /connections/<name>/callback (exchange, store in tokens.db)
   Browser ◀── 302 {return_url}?connection_success=<name> ──
4. bond-ai connections screen reads connection_success, reloads, calls
   GET {base}/connect/<name>/status per managed MCP → renders Disconnect
```

---

## 5. Path & port topology (local combined mode)

```
Browser / OAuth provider
        │
        ▼
   nginx :8000  (bond-ai front door; container listens :8080, host maps 8000→8080)
        ├── /                          → static Flutter build (flutterui/build/web)
        ├── /rest/<api>                → bond-ai backend :8002  (strips /rest)
        │     incl. /rest/connections/* (bond-ai's OWN connections REST API)
        ├── /auth/* , /login/*         → bond-ai backend :8002  (user login)
        ├── /connections/discovery     → bond-mcps :18000       (discovery)
        ├── /connections/<p>/callback  → bond-mcps per-MCP ports (provider OAuth
        │                                 redirect; exact-matched per provider:
        │                                 microsoft :18001, github :18002,
        │                                 atlassian :18003)
        ├── /connections (exact)       → SPA index.html          (OAuth return trip)
        └── /connect/<provider>/*      → bond-mcps per-MCP ports (ticket/start/
                                          status/disconnect)
                                          microsoft :18001, github :18002,
                                          atlassian :18003, databricks :18004
```

### Path ownership table (the conflict the design had to resolve)
| External path | Owner |
|---------------|-------|
| `/rest/connections/*` | **bond-ai** backend (the UI's connections API; nginx strips `/rest`) |
| `/connections/discovery` | **bond-mcps** AS/proxy (:18000) |
| `/connections/<p>/callback` | **bond-mcps** per-MCP FastMCP ports (:18001–18003) — the canonical, already-registered provider redirect |
| `/connections` (exact, no slash) | **bond-ai** SPA (the connect flow's `return_url`) |
| `/connect/<provider>/*` | **bond-mcps** per-MCP FastMCP ports (:18001–18004) |
| `/auth/*`, `/login/*` | **bond-ai** user login |

The key non-collision: bond-ai's connections **API** is under `/rest/connections/*`,
while bond-mcps owns bare `/connections/*` and `/connect/*`. The provider redirect
IS the bare `/connections/<name>/callback` — deliberately, since that URI is already
registered in every provider console — and nginx exact-matches each one to the MCP
port that serves it (66f7bdc). The bare `/connections` SPA route (the `return_url`
target) is exact-matched to index.html so it never falls into the proxy prefix.
Caveat: in plain combined mode (JWT off, `make dev-combined` in bond-mcps) the MCP
ports don't serve the callback route, so the CLI relay flow through the front door
404s — use split mode or `dev-combined-jwt` for CLI logins (see §8).

---

## 6. Files changed/added — bond-ai

Merged in **PR #201** (`170ced0` feat + `daef8f7` SSRF fix → merge `a9ad9df`).
16 files, +1649/−21.

| File | Change |
|------|--------|
| `bondable/bond/mcp_discovery.py` | **new** — `get_discovered_mcps()`; TTL cache + background poller (`start/stop_background_poller`); SSRF-guards both the discovery URL **and each discovered MCP URL**; fail-soft to last-good/empty. Env: `BOND_MCPS_DISCOVERY_URL` / `_TTL_SECONDS` / `_TIMEOUT_SECONDS`. **Poller is the sole fetcher** — when it's alive, request threads only read cache (no blocking HTTP on the event loop). |
| `bondable/bond/mcp_connect_client.py` | **new** — **async** (`httpx.AsyncClient`) client for `mint_connect_ticket` / `get_connect_status` / `delete_connection`. `connect_base_url()` strips the discovered path to an origin. `_safe_name()` strips URL-control chars from the name (SSRF defense + CodeQL taint break). |
| `bondable/bond/config.py` | `get_mcp_config()` now overlays discovered MCPs onto the static config as `bond_jwt` / `streamable-http`, dropping any stale inline `oauth_config`, preserving annotations, leaving `command`/user-defined servers untouched. No-op when discovery is disabled. |
| `bondable/rest/routers/connections.py` | Managed (delegated) track added alongside the preserved user-defined OAuth2 path. `authorize`→mint ticket; `list`/`status`→bond-mcps status (concurrent via `asyncio.gather`, **per-MCP fail-soft**); `disconnect`→bond-mcps delete. Passes the **discovery-sourced `managed["name"]`** (not the request path param) into the client → no SSRF taint. |
| `bondable/bond/providers/bedrock/BedrockMCP.py` | `bond_jwt` branch forwards the user's JWT to discovered servers (mechanism already existed). New `_extract_connect_url()` turns a `MissingProviderConnection` tool error into a structured `{authorization_required, connect_url}` result. |
| `bondable/rest/main.py` | Starts/stops the discovery poller in the app `lifespan` (no-op when discovery unset). |
| `deployment/nginx-local-combined.conf` | Routes `/connect/<provider>/*` AND the canonical `/connections/<provider>/callback` (exact matches) to the per-MCP ports (18001–18004); bare `/connections` (the `return_url` target) serves the SPA. |
| `.env.example`, `.env.combined.example` | Document `BOND_MCPS_DISCOVERY_URL` + the shared-secret mapping. |
| `docs/combined-mode-status.md` | Updated §3 to describe delegation + the bond-mcps prerequisites. |
| `tests/test_mcp_discovery.py` | parse/cache/TTL/SSRF/fail-soft + poller-sole-fetcher + overlay. |
| `tests/test_mcp_connect_client.py` | async client; URL construction; `_safe_name`; malicious-name-can't-escape-path. |
| `tests/test_jwt_mcps_trust.py` | HS256 accept/reject contract (wrong secret/aud/iss/expired). |
| `tests/test_mcp_managed_runtime.py` | JWT forwarding + connect_url surfacing. |
| `tests/test_connections_delegation.py` | full Connect choreography vs a stubbed bond-mcps. |
| `tests/test_local_nginx_config.py` | `/connect/*` routing invariants. |

---

## 7. Files changed/added — bond-mcps

On **PR #9** (`feat-mcp-delegation-companion`, **open**): commits `ca71586` (discovery
file + AS route), `e8c3615` (connect: return_url/status/disconnect), `9cfe650`
(`dev-combined-jwt`). 16 files, +1072/−122. Plan: `lets-make-a-plan-dynamic-pretzel.md`.

| File | Change |
|------|--------|
| `auth/auth/connect_routes.py` | `register_connect_routes` now registers **5** routes: `POST /connect/<name>/ticket`, `GET /connect/<name>`, `GET /connections/<name>/callback` (canonical registered redirect path, per 66f7bdc), **`GET /connect/<name>/status`**, **`DELETE /connect/<name>`**. `return_url` flows mint→stash (`oauth_pending_auth.client_state`)→callback **302**. `_validate_return_url` (env `BOND_MCPS_ALLOWED_RETURN_HOSTS`). `_public_base` honors `BOND_MCPS_CONNECT_PUBLIC_URL` (front door) for `connect_url` + provider `redirect_uri`. user_key via `get_sub_claim`. **Scope storage fix**: persist provider `scope` under the `scopes` key. |
| `auth/auth/jwt_identity.py` | **No code change** — HS256 was already supported via `BOND_MCPS_JWT_PUBLIC_KEY` + `BOND_MCPS_JWT_ALGORITHM=HS256`. `_resolve_audience()` auto-accepts `<PUBLIC_URL>/mcp` and merges the configured `BOND_MCPS_JWT_AUDIENCE`. Setting `PUBLIC_KEY` also un-dormants the connect routes (gate = JWKS-or-PUBLIC_KEY). |
| `auth/auth/discovery.py` | Source precedence: **`BOND_MCPS_DISCOVERY_FILE`** (deploy-time JSON) → local `mcps/*/mcp.json` scan → `[]`. Entry accepts absolute **`url`** (deployment) or **`port`+`path`** (→ `localhost`, local). Accepts `{"mcps":[…]}` or a bare list; malformed entries skipped (fail-soft). |
| `auth/auth/auth_server/endpoints.py` | Registers **`GET /connections/discovery`** (unauthenticated) on the **Authorization Server** — the always-on component in JWT-mode deployments (the auth proxy is typically off there). Same `discover_mcps()`. |
| `Makefile` | `dev-combined-jwt` + `_start-mcp-deleg`: injects `BOND_MCPS_JWT_PUBLIC_KEY=$(BOND_MCPS_JWT_SECRET)`, `…_ALGORITHM=HS256`, `…_ISSUER=bond-ai`, `…_AUDIENCE=mcp-server`, `…_AS_BASE_URL`/`…_CONNECT_PUBLIC_URL`=front door, `…_PUBLIC_URL=http://localhost:<port>`, `…_ALLOWED_RETURN_HOSTS=localhost`. Requires `BOND_MCPS_JWT_SECRET` (= bond-ai `JWT_SECRET_KEY`). AS :18000, MCPs :18001–18004. |
| `deployment/terraform-existing-vpc/locals.tf`, `services.tf`, `modules/service/*` | Renders `discovery_json` from enabled MCP services + `base_domain` (`url: https://<prefix>.<base_domain>/mcp`); passes it to **only** the AS service. |
| `deployment/helm/mcp-service/templates/discovery-configmap.yaml` (+ `deployment.yaml`, `values.yaml`, `configmap.yaml`) | Renders a ConfigMap from `discovery.json`, mounts it read-only at `/etc/bond-mcps`, sets `BOND_MCPS_DISCOVERY_FILE` on the AS pod. |
| `mcps/atlassian/atlassian_mcp.py` | **Scopes consolidation** — `ATLASSIAN_CONNECT_CONFIG.scopes = " ".join(atlassian.local_auth.SCOPES)`, a single canonical source. |
| `auth/tests/test_connect_routes.py` (new), `test_jwt_hs256.py` (new), `test_discovery.py` (extended) | return_url round-trip + allowlist; status/disconnect states; HS256 accept/reject + audience merge; discovery file precedence + shapes + AS route. |

---

## 8. How to run locally

Combined mode runs the whole stack behind nginx on `http://localhost:8000`, so the
OAuth callbacks registered with providers at `:8000` keep working. To exercise
**delegation** you must run bond-mcps in **JWT mode** (which un-dormants `/connect/*`).

```bash
# --- NO new provider-console registrations needed (66f7bdc) ---
# The delegated callback is the canonical /connections/<provider>/callback,
# already registered for every provider at http://localhost:8000/... —
# nginx exact-routes each one to the MCP port that serves it.

# Terminal 1 — bond-mcps in HS256 delegation mode.
# BOND_MCPS_JWT_SECRET MUST equal bond-ai's JWT_SECRET_KEY.
cd ../bond-mcps
export BOND_MCPS_JWT_SECRET="$(grep -E '^JWT_SECRET_KEY=' ../bond-ai/.env | cut -d= -f2- | tr -d '"')"
#   plus provider creds in each mcps/<svc> env: ATLASSIAN_CLIENT_ID/SECRET, GITHUB_CLIENT_ID/SECRET, …
make dev-combined-jwt          # AS :18000, MCPs :18001–18004

# Terminal 2 — bond-ai combined stack (front door :8000 + backend :8002).
cd ../bond-ai
#   set in .env.combined (or .env): BOND_MCPS_DISCOVERY_URL=http://localhost:8000/connections/discovery
make dev-combined

# Open http://localhost:8000/  → Connections → Connect on a tile.
```

Sanity checks:
```bash
curl -s http://localhost:8000/connections/discovery | jq        # MCP list (via nginx → :18000)
# Connect on the Atlassian tile → consent → returns to bond-ai → tile shows Connected
# Run an Atlassian tool in chat → succeeds using the token in bond-mcps tokens.db
```

---

## 9. How to test

### Automated — bond-ai (all green on `main`)
```bash
cd bond-ai
poetry run python -m pytest tests/test_mcp_discovery.py tests/test_mcp_connect_client.py \
  tests/test_jwt_mcps_trust.py tests/test_mcp_managed_runtime.py \
  tests/test_connections_delegation.py -q
# Full suite at last run: 1429 passed, 434 skipped, 0 failed.
```
Notable: `test_connections_delegation.py` drives the **entire Connect choreography**
(authorize → ticket → status shows connected → disconnect) against a stubbed bond-mcps;
`test_jwt_mcps_trust.py` pins the HS256 token shape to bond-mcps' verifier config.

### Automated — bond-mcps
```bash
cd bond-mcps/auth && poetry run pytest -q
# Covers: HS256 accept/reject + audience merge (test_jwt_hs256.py); return_url
# round-trip + allowlist + status/disconnect states (test_connect_routes.py);
# discovery file precedence + shapes + AS route (test_discovery.py).
```

### Manual end-to-end (the real proof)
Run the local recipe in §8, then verify the round trip: discovery lists MCPs → Connect
on a tile → provider consent → **302 back to bond-ai showing Connected** → an MCP tool
call works → Disconnect clears it. This is the path that no single-repo test can cover
(the two contract test suites emulate each other; only the live run spans both).

---

## 10. Deployed (EKS) architecture

The deployed topology differs from local in three load-bearing ways. A reviewer should
trace each carefully.

1. **Discovery source is a deploy-time file, served by the Authorization Server.**
   In deployment the auth proxy is typically off, so discovery moved to the **always-on
   AS**. Terraform renders `discovery.json` (`{name, display_name, url: https://<prefix>.<base_domain>/mcp}`)
   from the enabled MCP services, mounts it as a ConfigMap at `/etc/bond-mcps`, and sets
   `BOND_MCPS_DISCOVERY_FILE` on the AS pod. bond-ai points
   `BOND_MCPS_DISCOVERY_URL` → `https://auth.<base_domain>/connections/discovery`.
   *This file is static per deploy — see §11.2.*

2. **JWT validation.** Each MCP runs with the JWT env (HS256 + shared secret, or RS256
   via `BOND_MCPS_JWT_JWKS_URI` — both supported by `build_verifier()`), `iss=bond-ai`,
   `aud=mcp-server`. The MCPs validate the Bond JWT and resolve `user_key=sub=email`.

3. **Connect routing.** `connect_url` + the provider `redirect_uri` use
   `BOND_MCPS_CONNECT_PUBLIC_URL` (the front-door origin). The deployed front door must
   route `/connect/<provider>/*` to the correct per-MCP pod — the same per-provider
   routing nginx does locally. *Whether this is the front-door host or each MCP's own
   ingress host is an open question — see §12.*

In-cluster addressing for bond-ai → bond-mcps uses the shared ALB ingress hosts
(`auth.<domain>`, `github.<domain>`, …) or in-cluster service DNS
(`<svc>.<ns>.svc.cluster.local:8000`).

---

## 11. Hidden factors & risks a reviewer should scrutinize

These are the non-obvious things most reviews miss. Each is real and worth a careful look.

1. **The shared HS256 secret is a single symmetric key across two services.** Anyone who
   holds `JWT_SECRET_KEY` can mint a token bond-mcps accepts **as any user** (it's the
   verification key *and* the signing key). Rotation must be coordinated atomically
   (rotate bond-ai `JWT_SECRET_KEY` **and** `BOND_MCPS_JWT_PUBLIC_KEY` on every MCP at
   once, or accept a window of 401s). `jwt_identity.py` already supports **RS256/JWKS**;
   for production, asymmetric keys (bond-ai publishes a JWKS, MCPs verify with the public
   key) avoid sharing a signing secret entirely. The HS256 choice is for simplicity —
   the prod posture deserves an explicit decision.

2. **"Add an MCP without restart" is only true locally.** Locally, discovery scans the
   filesystem, so dropping in `mcps/foo/mcp.json` makes `foo` appear on the next poll. In
   **deployment**, discovery reads a static ConfigMap file rendered at `terraform apply`
   time; adding/removing an MCP requires re-rendering `discovery.json` and the AS pod
   picking up the new ConfigMap. bond-ai polls, but the *source* is static per-deploy.
   This asymmetry is the single easiest thing to misread in the whole design.

3. **Two token stores remain — by design, but with sharp edges.** Managed providers live
   only in bond-mcps `tokens.db` (key = email); user-defined BYO-OAuth lives only in
   bond-ai `mcp_token_cache`. They never unify. A managed Disconnect clears only
   bond-mcps. bond-ai has *no* visibility into whether a managed token exists except via
   the live `/connect/<name>/status` call.

4. **Identity is the email in `sub`.** If a user's email changes (SSO rename), their
   stored tokens orphan (keyed by the old email). Also, **CLI/laptop single-tenant
   tokens** (from `make login-*`) are keyed by local username — a *separate identity
   domain* invisible in JWT mode. A developer who connected Atlassian via the CLI won't
   see it via the UI delegation path. Expected, but surprising.

5. **Per-MCP connect routes couple the front door to the MCP port/host map.** `/connect`
   lives on each MCP's FastMCP server (so bond-ai can derive the origin by stripping
   `/mcp` from the discovered URL). Locally that means nginx hardcodes
   `/connect/atlassian → :18003`, etc.; adding an MCP needs an nginx block. In deployment
   the same per-provider routing must exist at the front door (see §12).

6. **No new provider-console registrations are required** *(resolved by 66f7bdc — this
   was originally a risk)*. The delegated callback reuses the canonical, already-
   registered `/connections/<provider>/callback` at the front-door origin; nginx
   exact-routes each provider's callback to its MCP port. It remains distinct from
   `/auth/<provider>/callback` (bond-ai user login) — still easy to conflate. The
   flip side: in plain combined mode (JWT off) the MCP ports don't serve the
   callback, so CLI-relay logins through the front door 404 — use split mode or
   `dev-combined-jwt` for CLI logins.

7. **`return_url` is an open-redirect surface, guarded on both sides.** bond-ai validates
   via `is_safe_redirect_url` (`ALLOWED_REDIRECT_DOMAINS`); bond-mcps via
   `BOND_MCPS_ALLOWED_RETURN_HOSTS`. **Both** allowlists must include the prod host. Too
   loose → open redirect; too strict → the callback falls back to "close this tab" HTML
   and the user never returns to bond-ai.

8. **Audience / issuer / sub must align exactly across repos, and nothing tests the live
   seam.** bond-ai's `aud` includes `mcp-server`; bond-mcps `AUDIENCE=mcp-server` (and
   also auto-accepts `<PUBLIC_URL>/mcp`); `iss=bond-ai`; `sub=email` — both sides. A drift
   (e.g., someone flips `JWT_ISSUER` in bond-ai) yields a **silent 401 on every tool
   call**. The contract tests on each side *emulate* the other; no automated test spans
   both at runtime. The manual e2e in §9 is the only thing that exercises the real seam.

9. **SSRF was a real finding and is mitigated, not eliminated.** bond-ai dials discovered
   URLs server-side *with the user's JWT attached*. Mitigations: discovered URLs are
   SSRF-validated at the discovery boundary (metadata/link-local blocked; localhost +
   private cluster IPs intentionally allowed); the path-segment `name` is sanitized and
   sourced from discovery (not the request). **Not** mitigated: a hostname that resolves
   to a private IP (DNS rebinding) — consistent with the existing
   `user_mcp_servers._validate_url_ssrf` posture and required so in-cluster private IPs
   work. CodeQL flagged the three connect calls (`py/partial-ssrf`); fixed in `daef8f7`.

10. **Event-loop blocking was the headline bug, fixed in two passes.** The connect client
    is fully async (`httpx.AsyncClient`); the discovery *fetch* is synchronous but the
    background **poller is the sole fetcher**, so request threads never block on a
    discovery HTTP call. Note: the poller is per-process — multiple uvicorn workers means
    N pollers and N× discovery traffic (each worker needs its own cache; acceptable).

11. **Two Connect entry points, only one fully wired to UI.** (a) The connections-screen
    tile uses the proactive `authorize → ticket` flow and is fully wired. (b) The
    chat/tool-time path surfaces `MissingProviderConnection`'s `connect_url` as a
    structured result, but **no Flutter affordance consumes it yet** — it reaches the
    user only as LLM-relayed text. Building a tool-time "Connect" button is a documented
    follow-up.

12. **A subtle token-storage bug was fixed in passing.** Providers return granted scopes
    under the key `scope`; bond-mcps now persists them under `scopes` (the key
    `TokenRepository` reads and `/status` returns). Without this fix, `/status` would
    report `scopes: null` even when connected.

13. **The AS-vs-proxy split is a deployment assumption worth confirming.** Discovery was
    duplicated onto the AS because the auth proxy is "usually off" in JWT-mode deploys.
    Confirm the AS is genuinely the always-on component in the target topology, and that
    nothing else relied on the proxy serving discovery in deployment.

---

## 12. Open questions / decisions

1. **Deployed `/connect` routing.** `BOND_MCPS_CONNECT_PUBLIC_URL` is the front door, but
   `/connect/<provider>` lives on per-MCP pods. Does the deployed front-door ingress
   route `/connect/<provider>/*` to the right pod (mirroring local nginx), or should the
   connect flow use each MCP's own ingress host (and register per-host callbacks)? This
   is the highest-risk deployment detail.
2. **HS256 vs RS256 in production** (§11.1) — decide whether to keep the shared symmetric
   secret or move to bond-ai-published JWKS.
3. **`user_key` = email vs internal `user_id`** — email is the current `sub`; an internal
   stable ID would survive email changes but requires aligning `sub` (and
   `BOND_MCPS_JWT_SUB_CLAIM`) on both sides.
4. **Tool-time Connect affordance** (§11.11) — build the Flutter UI that consumes the
   surfaced `connect_url`, or leave it as text.
5. **Discovery refresh in deployment** (§11.2) — accept static-per-deploy, or add a
   live/dynamic deployment source later.

---

## 13. Appendix: commit & branch index

**bond-ai** — merged to `main` via PR #201:
- `170ced0` feat(mcp): discover MCPs from bond-mcps and delegate OAuth connect
- `daef8f7` fix(mcp): resolve CodeQL partial-SSRF in connect client
- `a9ad9df` Merge pull request #201

**bond-ai** — follow-up branch `fix-mcp-callback-connections-path` (pending PR):
- `9735f75` fix(nginx): route MCP OAuth callbacks via /connections/<provider>/callback
- `6fed1cd` feat(dev): add combined-stack verification recipe (script + doc)
- `5e72c77` fix(mcp): fast-retry discovery until first successful fetch
- `c111988` fix(mcp): delegate managed-MCP status in tools list, mint Bond JWT server-side
- `b4ffce9` fix(dev): robust make stop; serve bare /connections from the SPA

**bond-mcps** — open PR #9, branch `feat-mcp-delegation-companion` (off `main`):
- `ca71586` feat(discovery): deployment-aware source (JSON file) + serve on Auth Server
- `e8c3615` feat(connect): delegate MCP OAuth to bond-mcps (return_url, status, disconnect)
- `9cfe650` feat(make): dev-combined-jwt — run MCPs in HS256 delegation mode
- `90ca9be` test(connect): live integration through FastMCP auth middleware (proof point)
- `66f7bdc` fix(connect): use canonical /connections/<provider>/callback (no re-registration)
- (prior, merged) `91a8503` feat(discovery): dynamic `/connections/discovery` on auth proxy;
  `ab943c1` dev-combined binds auth proxy to :18000 (frees :8000 for nginx)

**Plans & related docs:**
- bond-mcps plan: `~/.claude/plans/lets-make-a-plan-dynamic-pretzel.md` (titled "bond-mcps
  companion work for full MCP-OAuth delegation" — filename is an auto-generated artifact,
  not descriptive).
- bond-ai diagnosis/handoff: `docs/oauth-config-discovery-handoff.md` (superseded — see its
  "Update" banner).
- bond-ai combined-mode status: `docs/combined-mode-status.md` §3.
- bond-mcps discovery endpoint: `bond-mcps/docs/discovery.md`.
