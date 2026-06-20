# Local dev orchestration for bond-ai.
#
# Backend (uvicorn) and frontend (Flutter web) start in the background,
# logs land in tmp/logs/, and lsof is used for port/pid discovery so we
# don't need PID files. Pattern mirrors ../bond-mcps/Makefile.
#
# Ports (override via env):
#   BACKEND_PORT   default 8002  — bond-ai FastAPI
#   FRONTEND_PORT  default 3002  — Flutter web
#   MCP_AUTH_PORT  default 8000  — bond-mcps auth proxy (external, MCP OAuth)
#
# bond-mcps's auth proxy (port 8000) must be started separately
# (`make dev` in ../bond-mcps/) — bond-ai itself doesn't need it, only the
# MCP OAuth flows do. `make backend` warns if it's not detected.
#
# Requires: poetry, flutter, lsof, ps.

.PHONY: install dev backend frontend stop restart status logs \
        logs-backend logs-frontend check-ports check-mcps clean help smoke \
        _check-backend-port _check-frontend-port \
        _wait-backend _wait-frontend

LOG_DIR := tmp/logs

BACKEND_PORT  ?= 8002
FRONTEND_PORT ?= 3002
MCP_AUTH_PORT ?= 8000

# ----- install -----------------------------------------------------------

install:
	poetry install
	cd flutterui && flutter pub get

# ----- preflight ---------------------------------------------------------

# Public preflight: checks both ports. Used by `make dev` and as a
# standalone user-facing check.
check-ports: _check-backend-port _check-frontend-port

# Per-service port checks so `backend` and `frontend` can be invoked
# independently — `make dev` calls them in sequence and we don't want the
# second target to fail because the first one just claimed its port.
_check-backend-port:
	@if lsof -nP -iTCP:$(BACKEND_PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
	  owner=$$(lsof -nP -iTCP:$(BACKEND_PORT) -sTCP:LISTEN -t | head -1 | xargs -I{} ps -p {} -o comm= 2>/dev/null | tail -1); \
	  echo "  port $(BACKEND_PORT) in use by $$owner" >&2; \
	  echo "Free it or override via BACKEND_PORT." >&2; \
	  exit 1; \
	fi

_check-frontend-port:
	@if lsof -nP -iTCP:$(FRONTEND_PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
	  owner=$$(lsof -nP -iTCP:$(FRONTEND_PORT) -sTCP:LISTEN -t | head -1 | xargs -I{} ps -p {} -o comm= 2>/dev/null | tail -1); \
	  echo "  port $(FRONTEND_PORT) in use by $$owner" >&2; \
	  echo "Free it or override via FRONTEND_PORT." >&2; \
	  exit 1; \
	fi

# Warn (don't fail) if bond-mcps auth proxy isn't running. MCP OAuth flows
# need it; bond-ai itself does not.
check-mcps:
	@if ! lsof -nP -iTCP:$(MCP_AUTH_PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
	  echo "  [warn] bond-mcps auth proxy not detected on :$(MCP_AUTH_PORT)."; \
	  echo "         MCP OAuth flows will fail until you run 'make dev' in ../bond-mcps/."; \
	fi

# ----- start -------------------------------------------------------------

backend: _check-backend-port check-mcps
	@mkdir -p $(LOG_DIR)
	@echo "Starting bond-ai backend on :$(BACKEND_PORT)..."
	@( nohup poetry run uvicorn bondable.rest.main:app --reload \
	     --host 0.0.0.0 --port $(BACKEND_PORT) ) \
	     > $(CURDIR)/$(LOG_DIR)/backend.log 2>&1 &
	@$(MAKE) --no-print-directory _wait-backend
	@$(MAKE) --no-print-directory status

frontend: _check-frontend-port
	@mkdir -p $(LOG_DIR)
	@echo "Starting Flutter web on :$(FRONTEND_PORT)..."
	@( cd flutterui && nohup flutter run -d web-server \
	     --web-port=$(FRONTEND_PORT) --web-hostname=localhost \
	     --target lib/main.dart ) \
	     > $(CURDIR)/$(LOG_DIR)/frontend.log 2>&1 &
	@$(MAKE) --no-print-directory _wait-frontend
	@$(MAKE) --no-print-directory status

# Poll /health on the backend port up to BACKEND_READY_TIMEOUT seconds
# (default 20). Doesn't fail the make invocation if the probe times out —
# the process may still be initializing or hung; user can investigate via
# `make logs-backend`. lsof-based `make status` will still show [up] if
# the socket is bound regardless.
BACKEND_READY_TIMEOUT ?= 20
_wait-backend:
	@i=0; while [ $$i -lt $(BACKEND_READY_TIMEOUT) ]; do \
	  if curl -sf --max-time 2 -o /dev/null http://localhost:$(BACKEND_PORT)/health 2>/dev/null; then \
	    echo "  backend responding to /health after $${i}s"; exit 0; \
	  fi; \
	  i=$$((i+1)); sleep 1; \
	done; \
	echo "  [warn] backend not responding to /health after $(BACKEND_READY_TIMEOUT)s — check tmp/logs/backend.log" >&2

# Poll the frontend root up to FRONTEND_READY_TIMEOUT seconds (default 45;
# cold Flutter web compile can be slow).
FRONTEND_READY_TIMEOUT ?= 45
_wait-frontend:
	@i=0; while [ $$i -lt $(FRONTEND_READY_TIMEOUT) ]; do \
	  if curl -sf --max-time 2 -o /dev/null http://localhost:$(FRONTEND_PORT)/ 2>/dev/null; then \
	    echo "  frontend responding on / after $${i}s"; exit 0; \
	  fi; \
	  i=$$((i+1)); sleep 1; \
	done; \
	echo "  [warn] frontend not responding on / after $(FRONTEND_READY_TIMEOUT)s — check tmp/logs/frontend.log" >&2

# On-demand health probe (no waiting). Use after the services have been
# running for a while, or to debug why something isn't working.
smoke:
	@bok=fail; fok=fail; \
	if curl -sf --max-time 2 -o /dev/null http://localhost:$(BACKEND_PORT)/health 2>/dev/null; then bok=ok; fi; \
	if curl -sf --max-time 2 -o /dev/null http://localhost:$(FRONTEND_PORT)/ 2>/dev/null; then fok=ok; fi; \
	echo "  backend  :$(BACKEND_PORT)/health  $$bok"; \
	echo "  frontend :$(FRONTEND_PORT)/        $$fok"; \
	if [ "$$bok" = "fail" ] || [ "$$fok" = "fail" ]; then exit 1; fi

dev: check-ports
	@$(MAKE) --no-print-directory backend
	@$(MAKE) --no-print-directory frontend

# ----- stop --------------------------------------------------------------

# Snapshot-then-kill: gather PIDs first (so we can report all services even
# after the first pgid-sweep kills the rest), then loop kills by pgid + pid.
# Don't refactor into per-port find+kill — that pattern only reports the
# first service stopped, since subsequent iterations find nothing.
stop:
	@pids_to_kill=""; \
	for entry in "backend:$(BACKEND_PORT)" "frontend:$(FRONTEND_PORT)"; do \
	  name=$${entry%%:*}; port=$${entry##*:}; \
	  pid=$$(lsof -nP -iTCP:$$port -sTCP:LISTEN -t 2>/dev/null | head -1); \
	  if [ -n "$$pid" ]; then \
	    echo "Stopping $$name :$$port (pid $$pid)"; \
	    pids_to_kill="$$pids_to_kill $$pid"; \
	  fi; \
	done; \
	if [ -z "$$pids_to_kill" ]; then \
	  echo "  nothing to stop (no process on :$(BACKEND_PORT) or :$(FRONTEND_PORT))"; \
	  exit 0; \
	fi; \
	for pid in $$pids_to_kill; do \
	  pgid=$$(ps -o pgid= -p $$pid 2>/dev/null | tr -d ' '); \
	  if [ -n "$$pgid" ]; then kill -- -$$pgid 2>/dev/null; fi; \
	  kill $$pid 2>/dev/null || true; \
	done

restart: stop
	@sleep 1
	@$(MAKE) --no-print-directory dev

# ----- status / logs -----------------------------------------------------

status:
	@for entry in "backend:$(BACKEND_PORT)" "frontend:$(FRONTEND_PORT)" "bond-mcps-auth:$(MCP_AUTH_PORT)"; do \
	  name=$${entry%%:*}; port=$${entry##*:}; \
	  pid=$$(lsof -nP -iTCP:$$port -sTCP:LISTEN -t 2>/dev/null | head -1); \
	  if [ -n "$$pid" ]; then echo "  [up]   $$name :$$port (pid $$pid)"; \
	  else echo "  [down] $$name :$$port"; fi; \
	done

logs:
	tail -F $(LOG_DIR)/*.log

logs-backend:
	tail -F $(LOG_DIR)/backend.log

logs-frontend:
	tail -F $(LOG_DIR)/frontend.log

clean:
	rm -rf $(LOG_DIR)

help:
	@echo "Bond AI local dev (ports: backend=$(BACKEND_PORT), frontend=$(FRONTEND_PORT)):"
	@echo "  make install        Install Python + Flutter deps"
	@echo "  make dev            Start backend + frontend"
	@echo "  make backend        Start backend only"
	@echo "  make frontend       Start frontend only"
	@echo "  make stop           Stop both"
	@echo "  make restart        stop + dev"
	@echo "  make status         Show port/PID status (lsof — bind check only)"
	@echo "  make smoke          HTTP probe: backend /health and frontend / (real readiness)"
	@echo "  make logs           tail -F all logs"
	@echo "  make logs-backend   tail backend log only"
	@echo "  make logs-frontend  tail frontend log only"
	@echo "  make check-ports    Verify $(BACKEND_PORT)/$(FRONTEND_PORT) are free"
	@echo "  make clean          Remove tmp/logs"
	@echo ""
	@echo "Override ports: BACKEND_PORT=8010 make dev"
	@echo "External: bond-mcps auth proxy on :$(MCP_AUTH_PORT) (run 'make dev' in ../bond-mcps/)"
