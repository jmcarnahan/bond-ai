# Verifying the Combined Stack (bond-ai + bond-mcps)

A repeatable recipe to confirm bond-ai and bond-mcps are both running on this
machine and actually talking to each other in **local combined mode** (nginx
front door on `http://localhost:8000`). Companion to
[local-dev-combined-mode.md](local-dev-combined-mode.md) (how to start the
stack) and
[mcp-discovery-delegation-architecture.md](mcp-discovery-delegation-architecture.md)
(why it's shaped this way).

## TL;DR

```bash
./scripts/verify-combined-stack.sh
```

Exit 0 with all `PASS` lines → the stack is up and the two repos are talking.
Any `FAIL` prints a targeted hint; the restart recipe is at the bottom of the
output.

## What the script proves, layer by layer

| # | Check | What a pass means |
|---|-------|-------------------|
| 1 | Docker + `bond-ai-nginx-local` container | the front door exists |
| 2 | Ports 8000 / 8002 / 18000–18004 listening | nginx, bond-ai backend, bond-mcps AS + 4 MCPs are all up |
| 3 | `GET :8000/health` → 200 | nginx reaches the bond-ai backend |
| 4 | `GET :8000/rest/providers` → JSON | the `/rest` strip-proxy works (HTML here = SPA fallthrough bug) |
| 5 | `GET :8000/connections/discovery` → `{"mcps":[…]}` | **bond-ai ↔ bond-mcps discovery plane is live** |
| 6 | `GET :8000/connections` → 200 | the OAuth return-trip SPA route works (no broken 301 to the in-container port) |
| 7a | status endpoint without a token → 401 | bond-mcps is in **JWT mode** (auth actually enforced) |
| 7b | status endpoint with a freshly minted Bond JWT → 200/404 | **the HS256 trust seam is live**: shared secret, `iss=bond-ai`, `aud=mcp-server`, `sub=email` all align across repos |

Check 7 is the one no automated test in either repo covers (each side only
emulates the other) — it exercises the real cross-repo contract at runtime by
minting a token exactly the way bond-ai does and calling bond-mcps with it.

## Starting the stack (if verification fails)

```bash
# Terminal 1 — bond-mcps in HS256 delegation mode
cd ../bond-mcps
make dev-combined-jwt        # AS :18000, MCPs :18001–18004
                             # requires BOND_MCPS_JWT_SECRET = bond-ai's JWT_SECRET_KEY

# Terminal 2 — bond-ai combined stack
cd ../bond-ai
make stop && make dev-combined   # nginx :8000 + backend :8002 + static Flutter build

./scripts/verify-combined-stack.sh
```

## The manual step the script can't do

The script proves the plumbing; the full OAuth round trip needs a browser and
your consent (this is the "real proof" — see the architecture doc §9):

1. Open `http://localhost:8000/` and log in.
2. Go to **Connections** → click **Connect** on a tile (e.g. Atlassian).
3. Complete the provider consent screen.
4. You should land back on the Connections screen with the tile showing
   **Connected** (this exercises `/connections/<provider>/callback` routing
   and the SPA return route).
5. In chat, run a tool from that MCP — it should succeed using the token
   stored in bond-mcps' `tokens.db`.
6. **Disconnect** on the tile should clear it.

## Known gotcha: managed tiles missing right after a restart

`make dev-combined` starts the backend **before** nginx, and
`BOND_MCPS_DISCOVERY_URL` points through nginx (`:8000/connections/discovery`),
so the backend's first discovery fetch gets connection-refused and fails soft
to an empty list — the Connections screen then shows only static tiles (no
Atlassian/GitHub/Microsoft/Databricks). Symptom in `tmp/logs/backend.log`:

```
WARNING - bondable.bond.mcp_discovery - MCP discovery fetch failed (ConnectError: ...); failing soft
```

The discovery poller now fast-retries every 10s until its first successful
fetch (`STARTUP_RETRY_SECONDS` in `mcp_discovery.py`), so the tiles appear
within seconds of nginx coming up — just refresh the page. (Before that fix
the retry waited a full TTL: up to 5 minutes of missing tiles.)

## Notes

- The JWT seam check reads `JWT_SECRET_KEY` from `.env` by default; override
  with `BOND_AI_ENV_FILE=.env.combined ./scripts/verify-combined-stack.sh`.
- The seam check's identity is a throwaway email
  (`verify-stack@example.com`) and the status call is read-only — it creates
  no state in bond-mcps.
- A long-running stack (days) can drift — stale Flutter build, expired login
  sessions. When in doubt, restart with the recipe above; `make stop` kills
  all listeners on both ports reliably.
