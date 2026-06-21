# Combined Mode — Status & Remaining Work

**Branch:** `path-routing-local-combined` (bond-ai) + `combined-mode-public-url` (bond-mcps)
**Last updated:** 2026-06-21
**State:** Working but NOT fully verified. Do not merge yet — see "Still to do" below.

This is a living progress note. The architecture/reference doc is
[`local-dev-combined-mode.md`](local-dev-combined-mode.md); the full plan is
`.claude/plans/review-all-of-the-fluffy-bachman.md`. This file tracks what is
actually done vs. what still needs testing.

---

## What we built

Combined mode runs the whole local stack behind a single nginx front door on
**`http://localhost:8000`**, so the OAuth callback URLs already registered with
every provider (`http://localhost:8000/auth/<provider>/callback`) work locally
with **no provider-console changes**.

```
Browser / OAuth provider
        │
        ▼
   nginx :8000  (Docker container, listens :8080 inside, host maps 8000→8080)
        │
        ├── /                           → static Flutter build (flutterui/build/web)
        ├── /rest/<api>                 → bond-ai backend :8002 (strips /rest)
        ├── /health                     → bond-ai backend :8002
        ├── /auth/<provider>/callback   → bond-ai backend :8002
        ├── /login/<provider>           → bond-ai backend :8002
        └── /connections/<svc>/callback → bond-mcps auth proxy :18000
```

### Key design decisions made during execution

1. **Front door is `:8000`, not `:8080`.** The original plan used `:8080`, but
   the user already has every OAuth callback registered at `:8000`. nginx took
   `:8000`; bond-mcps's auth proxy moved off `:8000` → **`:18000`** in combined
   mode to free the port. (Inside the container nginx listens on `:8080`; the
   Makefile maps host `8000` → container `8080`.)

2. **Static Flutter build, not `flutter run -d web-server`.** Proxying a live
   Flutter dev server through nginx was fragile — DDS hangs, random debug
   WebSocket ports, a ~965-script load waterfall (~25s first paint), and
   occasional dev-server crashes. Combined mode now serves the pre-compiled
   bundle out of `flutterui/build/web/`. Trade-off: **no hot reload** in
   combined mode — use split mode (`make dev`) for active UI iteration.

3. **Flutter build is part of `make dev-combined`.** A file-based Make
   dependency (`FLUTTER_WEB_OUT` vs. `FLUTTER_SRC`) rebuilds only when Flutter
   sources change. First build ~30–60s; subsequent starts ~5s (build skipped via
   mtime). Build uses `--no-tree-shake-icons` (required by `material_symbols_icons`)
   and `--dart-define=API_BASE_URL=http://localhost:8000/rest`.

4. **bond-mcps startup detection hardened.** Replaced `sleep 3` (too short for
   FastMCP cold start, caused false `[down]` reports) with a port-bind poll, and
   added a `fastmcp`-missing warning.

### Files changed

**bond-ai (this branch):**
- `Makefile` — `dev-combined`, `build-web`, `nginx*` targets, `_check-providers-combined` startup probe; `NGINX_PORT=8000`, `MCP_AUTH_PORT_COMBINED=18000`, `FLUTTER_COMBINED_BASE=http://localhost:8000/rest`
- `deployment/nginx-local-combined.conf` — the front-door config (listens `:8080` inside container)
- `.env.combined.example` — all `*_REDIRECT_URI` at `:8000`, `COOKIE_SECURE=false`, CORS includes `:8000`
- `tests/test_local_nginx_config.py` — offline `nginx -t` + design-invariant assertions (CI gate)
- `docs/local-dev-combined-mode.md` — architecture/reference
- `archive/` — deleted (dead MCP code; canonical MCPs live in bond-mcps)

**bond-mcps (`combined-mode-public-url` branch):**
- `Makefile` — `dev-combined` binds auth proxy to `:18000`, exports `BOND_AUTH_PROXY_PUBLIC_URL=http://localhost:8000`; `check-mcp-deps` + `_wait-mcp-binds`
- `auth/auth/proxy_server.py` — startup log line for the effective public redirect base

---

## What's verified

- ✅ `make dev-combined` starts the stack in ~5s (after first build).
- ✅ Static Flutter bundle loads at `http://localhost:8000/` in ~1–2s, zero
  console errors (verified via Playwright). Title renders correctly.
- ✅ Incremental build: editing Flutter source triggers rebuild; no-change start
  skips it.
- ✅ **Cognito login works end-to-end in an incognito browser** through the
  combined front door.
- ✅ `tests/test_local_nginx_config.py` passes (`nginx -t` clean; invariants hold).
- ✅ bond-mcps services report `[up]` correctly (no more false `[down]`).

---

## Still to do / to test

**This branch is NOT ready to merge.** Outstanding items:

1. **Regular (non-incognito) browser blank screen.** Earlier we saw a blank page
   in a normal browser caused by a cached service worker / stale assets from a
   previous Flutter dev-server session. Workaround documented (DevTools →
   Clear site data). Need to confirm whether the static-build switch fully
   resolves this or whether a cache-busting strategy is needed for the bundle.

2. **Google + Okta login.** Only Cognito has been verified end-to-end. Verify
   the other two user-login providers complete the full redirect → callback →
   session-cookie loop at `:8000`.

3. **MCP OAuth connections — now DELEGATED to bond-mcps** (branch
   `mcp-discovery-delegation`). bond-ai no longer hard-configures MCPs or drives
   their OAuth: it discovers the MCP set from `BOND_MCPS_DISCOVERY_URL`
   (`http://localhost:8000/connections/discovery`, polled) and delegates Connect
   to bond-mcps' `/connect/<name>` flow, forwarding the Bond JWT. bond-ai's side
   is implemented + unit/integration-tested; **not yet exercised live** in
   combined mode. To test, bond-mcps must run with JWT mode ON (shared secret =
   bond-ai `JWT_SECRET_KEY`, `HS256`, `iss=bond-ai`, `aud=mcp-server`) and provide
   the bond-mcps-side additions below. nginx now routes `/connect/<provider>/*` to
   the per-MCP ports (18001-18004). Confirm: discovery lists MCPs → Connect on a
   tile → bond-mcps consent → return to bond-ai Connected → an MCP tool call works.

   **bond-mcps prerequisites (companion work, not in this repo):**
   - JWT-mode config (shared secret, `HS256`, issuer/audience) — un-dormants
     `/connect/*`.
   - `return_url` support in `/connect/<name>/callback` (302 back to bond-ai with
     `?connection_success=`/`connection_error=`, allowlisted) — today it renders a
     terminal "close this tab" page.
   - `GET /connect/<name>/status` + `DELETE /connect/<name>` (JWT-authed) backing
     the Connections list/disconnect.
   - Deployment-aware discovery URLs (it currently emits `localhost` and `[]` off
     a dev checkout) — until then deployed bond-ai falls back to static config.

4. **Session-cookie persistence.** Confirm `bond_session` / `bond_csrf` are set
   on `localhost:8000` and survive a page reload (`COOKIE_SECURE=false` over HTTP).

5. **Split-mode coexistence / no regression.** Confirm `make dev` (split) still
   works unchanged after these branches land.

6. **bond-mcps branch.** `combined-mode-public-url` in bond-mcps must be pushed /
   PR'd alongside this branch — combined mode is broken without the `:18000`
   relocation.

7. **Soak.** Per the plan, run combined mode in real daily work for a cycle
   before declaring done. Watch for token-refresh failures across mode switches.

8. **Other known fixes pending.** (User flagged "more fixing to this project" —
   capture specifics here as they come up.)

---

## How to run (quick reference)

```bash
# Terminal 1 — bond-mcps (auth proxy :18000, MCPs :18001-:18004)
cd ../bond-mcps && make dev-combined

# Terminal 2 — bond-ai (build-web if needed + backend :8002 + nginx :8000)
cd ../bond-ai && make dev-combined
```

Open `http://localhost:8000/`. `make stop` in each repo tears everything down
(including the nginx container).
