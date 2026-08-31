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
        logs-backend logs-frontend check-ports check-mcps check-mcps-hard \
        clean help smoke \
        nginx nginx-stop nginx-reload nginx-logs nginx-status \
        dev-combined backend-combined build-web \
        _check-backend-port _check-frontend-port \
        _wait-backend _wait-frontend _check-providers-combined

LOG_DIR := tmp/logs

BACKEND_PORT  ?= 8002
FRONTEND_PORT ?= 3002
MCP_AUTH_PORT ?= 8000

# Combined-mode front-door (nginx in Docker; see docs/local-dev-combined-mode.md).
# Listens on :8000 so existing OAuth callback URLs already registered with
# Google / Okta / Cognito / Atlassian / GitHub / Microsoft (which all use
# :8000) keep working without any provider console changes.
NGINX_PORT      ?= 8000
NGINX_CONTAINER := bond-ai-nginx-local
NGINX_CONF      := $(CURDIR)/deployment/nginx-local-combined.conf

# bond-mcps auth proxy moves to this port in combined mode so nginx can take
# :8000. Must match COMBINED_AUTH_PORT in bond-mcps's Makefile.
MCP_AUTH_PORT_COMBINED ?= 18000

ENV_FILE_COMBINED      ?= .env.combined
# The Flutter app constructs API URLs as `${API_BASE_URL}/<endpoint>` where
# <endpoint> is bare (e.g. `/providers`, `/login/google`). In combined mode
# we need those to reach the backend through nginx's `/rest/` proxy, so the
# baseURL must include the `/rest` segment — otherwise calls hit the SPA
# fallthrough and the backend never sees them.
FLUTTER_COMBINED_BASE  ?= http://localhost:$(NGINX_PORT)/rest

# Static Flutter build for combined mode. nginx serves these files instead of
# proxying to `flutter run -d web-server` — that path was fragile (DDS hangs,
# 0.0.0.0 bind quirks, slow first paint). Build only re-runs when any source
# under flutterui/lib or flutterui/web changes or pubspec changes.
FLUTTER_WEB_OUT := flutterui/build/web/main.dart.js
FLUTTER_SRC     := $(shell find flutterui/lib flutterui/web flutterui/pubspec.yaml flutterui/pubspec.lock -type f 2>/dev/null)

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

# Hard-fail variant for combined mode — a half-broken combined stack (no MCPs
# reachable through the front door) is worse than telling the user to start
# bond-mcps first. Probes the COMBINED-mode port (:18000) because that's
# where `make dev-combined` in bond-mcps binds the auth proxy.
check-mcps-hard:
	@if ! curl -sf --max-time 2 -o /dev/null http://localhost:$(MCP_AUTH_PORT_COMBINED)/health 2>/dev/null; then \
	  echo "  bond-mcps auth proxy not reachable on :$(MCP_AUTH_PORT_COMBINED)" >&2; \
	  echo "  run 'make dev-combined' in ../bond-mcps/ first" >&2; \
	  exit 1; \
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

# ----- start (combined mode) ---------------------------------------------
#
# Combined mode runs everything behind an nginx front door on :$(NGINX_PORT).
# Requires bond-mcps's auth proxy reachable on :$(MCP_AUTH_PORT_COMBINED)
# (the combined-mode port; hard-fails otherwise) and .env.combined populated
# (copy from .env.combined.example).
#
# Differences from `dev`:
#   - nginx on :$(NGINX_PORT) routes /auth, /connections, /rest to the right
#     upstream; / serves a static Flutter build. All OAuth callbacks already
#     registered with providers at :$(NGINX_PORT) work unchanged.
#   - backend loads .env.combined (OAuth callbacks pointed at :$(NGINX_PORT),
#     JWT_REDIRECT_URI=:$(NGINX_PORT), COOKIE_SECURE=false for HTTP)
#   - No flutter run process — build-web compiles a static bundle once,
#     nginx serves it from /usr/share/nginx/html. No hot reload here (use
#     split mode for active UI iteration).

dev-combined: _check-backend-port check-mcps-hard build-web
	@if [ ! -f "$(ENV_FILE_COMBINED)" ]; then \
	  echo "  missing $(ENV_FILE_COMBINED) — copy .env.combined.example and edit" >&2; \
	  exit 1; \
	fi
	@$(MAKE) --no-print-directory backend-combined
	@$(MAKE) --no-print-directory nginx
	@$(MAKE) --no-print-directory _check-providers-combined
	@echo
	@echo "Combined dev stack ready at http://localhost:$(NGINX_PORT)/"
	@echo "Logs: tmp/logs/backend.log; nginx logs: make nginx-logs"
	@echo "Flutter code change? Re-run \`make dev-combined\` — build-web detects via mtime."

# Static Flutter build. File-based dependency: only re-runs if Flutter source
# is newer than the build output. First-time build is slow (~30-60s);
# incremental builds skip when nothing changed.
build-web: $(FLUTTER_WEB_OUT)

$(FLUTTER_WEB_OUT): $(FLUTTER_SRC)
	@echo "Building Flutter web bundle (API_BASE_URL=$(FLUTTER_COMBINED_BASE))..."
	@echo "  (first build can take ~30-60s; subsequent runs skip when source is unchanged)"
	@# --no-tree-shake-icons because material_symbols_icons uses non-const
	@# IconData which breaks the default tree-shaker.
	@cd flutterui && flutter build web \
	    --no-tree-shake-icons \
	    --dart-define=API_BASE_URL=$(FLUTTER_COMBINED_BASE)
	@touch $(FLUTTER_WEB_OUT)

# Probe /rest/providers through nginx and report. Three failure modes this
# catches that would otherwise show up as a confusing "no providers" screen
# in the Flutter UI:
#   1. nginx /rest/ proxy misconfigured → response is HTML (SPA fallthrough)
#   2. backend not responding → empty response
#   3. backend up + nginx OK but no OAuth client IDs in .env → empty list
_check-providers-combined:
	@out=$$(curl -s --max-time 3 http://localhost:$(NGINX_PORT)/rest/providers 2>/dev/null); \
	case "$$out" in \
	  '') echo "  [warn] /rest/providers returned no response — backend may still be starting" ;; \
	  '<'*) echo "  [warn] /rest/providers returned HTML — nginx /rest/ proxy isn't reaching the backend (see docs/local-dev-combined-mode.md)" ;; \
	  '{'*) \
	    n=$$(echo "$$out" | tr ',' '\n' | grep -c '"name"' || true); \
	    if [ "$$n" = "0" ]; then \
	      echo "  [warn] /rest/providers returned no OAuth providers — check .env for GOOGLE_CLIENT_ID / OKTA_* / COGNITO_*"; \
	    else \
	      echo "  providers OK ($$n configured)"; \
	    fi ;; \
	  *) echo "  [warn] /rest/providers returned unexpected response: $$(echo $$out | head -c 80)" ;; \
	esac

backend-combined: _check-backend-port
	@mkdir -p $(LOG_DIR)
	@echo "Starting bond-ai backend on :$(BACKEND_PORT) (env: $(ENV_FILE_COMBINED))..."
	@( set -a; . ./$(ENV_FILE_COMBINED); set +a; \
	   nohup poetry run uvicorn bondable.rest.main:app --reload \
	     --host 0.0.0.0 --port $(BACKEND_PORT) ) \
	     > $(CURDIR)/$(LOG_DIR)/backend.log 2>&1 &
	@$(MAKE) --no-print-directory _wait-backend

# Note: frontend-combined was removed when combined mode switched to serving
# a static Flutter build (build-web target). The nginx target mounts
# flutterui/build/web into the container — no live flutter run process in
# combined mode. Split mode (`make frontend`) is unchanged.

# ----- stop --------------------------------------------------------------

# Snapshot-then-kill: gather PIDs first (so we can report all services even
# after the first pgid-sweep kills the rest), then loop kills by pgid + pid.
# Don't refactor into per-port find+kill — that pattern only reports the
# first service stopped, since subsequent iterations find nothing.
# Also stops the nginx container (no-op if it's not running) so `make stop`
# covers both split and combined modes uniformly.
# Robust stop: uvicorn --reload runs TWO processes on :$(BACKEND_PORT) (the
# reloader + its worker), so killing a single `lsof | head -1` PID left the
# port bound and made `make dev-combined` fail its port check. Instead, for
# each port: kill ALL listeners (TERM the whole process group + the pid), then
# poll up to ~5s and escalate to KILL until the socket is actually free. This
# makes `make stop && make dev-combined` reliable.
stop:
	@$(MAKE) --no-print-directory nginx-stop
	@any=0; \
	for port in $(BACKEND_PORT) $(FRONTEND_PORT); do \
	  pids=$$(lsof -nP -iTCP:$$port -sTCP:LISTEN -t 2>/dev/null | sort -u); \
	  [ -z "$$pids" ] && continue; \
	  any=1; echo "Stopping :$$port ($$(echo $$pids | tr '\n' ' '))"; \
	  for pid in $$pids; do \
	    pgid=$$(ps -o pgid= -p $$pid 2>/dev/null | tr -d ' '); \
	    [ -n "$$pgid" ] && kill -TERM -- -$$pgid 2>/dev/null || true; \
	    kill -TERM $$pid 2>/dev/null || true; \
	  done; \
	  for i in 1 2 3 4 5 6 7 8 9 10; do \
	    rem=$$(lsof -nP -iTCP:$$port -sTCP:LISTEN -t 2>/dev/null); \
	    [ -z "$$rem" ] && break; \
	    sleep 0.5; \
	    for pid in $$rem; do kill -KILL $$pid 2>/dev/null || true; done; \
	  done; \
	  rem=$$(lsof -nP -iTCP:$$port -sTCP:LISTEN -t 2>/dev/null); \
	  [ -n "$$rem" ] && echo "  WARN: :$$port still in use ($$rem)" >&2 || echo "  :$$port free"; \
	done; \
	[ $$any -eq 0 ] && echo "  nothing to stop (no process on :$(BACKEND_PORT) or :$(FRONTEND_PORT))" || true

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

# ----- nginx front door (combined mode) ----------------------------------
#
# Runs nginx:1.27-alpine in Docker against deployment/nginx-local-combined.conf.
# Upstreams are reached via host.docker.internal: backend :8002, bond-mcps
# auth proxy :8000, Flutter web :3002. See docs/local-dev-combined-mode.md.

nginx:
	@if docker ps --format '{{.Names}}' | grep -q "^$(NGINX_CONTAINER)$$"; then \
	  echo "  nginx container already running"; exit 0; \
	fi
	@if [ ! -f "$(NGINX_CONF)" ]; then \
	  echo "  missing $(NGINX_CONF)" >&2; exit 1; \
	fi
	@if [ ! -d "$(CURDIR)/flutterui/build/web" ]; then \
	  echo "  missing flutterui/build/web — run \`make build-web\` first" >&2; exit 1; \
	fi
	@echo "Starting nginx front-door on :$(NGINX_PORT)..."
	@docker run -d --rm \
	  --name $(NGINX_CONTAINER) \
	  -p $(NGINX_PORT):8080 \
	  -v "$(NGINX_CONF):/etc/nginx/conf.d/default.conf:ro" \
	  -v "$(CURDIR)/flutterui/build/web:/usr/share/nginx/html:ro" \
	  --add-host=host.docker.internal:host-gateway \
	  nginx:1.27-alpine >/dev/null
	@sleep 1
	@$(MAKE) --no-print-directory nginx-status

nginx-stop:
	@if docker ps --format '{{.Names}}' | grep -q "^$(NGINX_CONTAINER)$$"; then \
	  echo "Stopping nginx container..."; \
	  docker stop $(NGINX_CONTAINER) >/dev/null; \
	else \
	  echo "  nginx container not running"; \
	fi

# `nginx -s reload` inside the container — picks up edits to
# nginx-local-combined.conf without dropping connections. Faster than
# nginx-stop + nginx.
nginx-reload:
	@if ! docker ps --format '{{.Names}}' | grep -q "^$(NGINX_CONTAINER)$$"; then \
	  echo "  nginx container not running — use 'make nginx' to start it" >&2; exit 1; \
	fi
	@echo "Reloading nginx config..."
	@docker exec $(NGINX_CONTAINER) nginx -t && \
	  docker exec $(NGINX_CONTAINER) nginx -s reload && \
	  echo "  reloaded"

nginx-logs:
	@docker logs -f $(NGINX_CONTAINER)

nginx-status:
	@if docker ps --format '{{.Names}}' | grep -q "^$(NGINX_CONTAINER)$$"; then \
	  echo "  [up]   nginx :$(NGINX_PORT) (container $(NGINX_CONTAINER))"; \
	else \
	  echo "  [down] nginx :$(NGINX_PORT)"; \
	fi

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
	@echo "Combined mode (nginx front-door on :$(NGINX_PORT); see docs/local-dev-combined-mode.md):"
	@echo "  make build-web      Build the static Flutter bundle for combined mode (auto-runs from dev-combined)"
	@echo "  make dev-combined   Build Flutter (if needed) + backend + nginx (requires bond-mcps + .env.combined)"
	@echo "  make nginx          Start nginx container (proxies /rest/auth/connections; serves static Flutter)"
	@echo "  make nginx-stop     Stop nginx container"
	@echo "  make nginx-reload   Reload nginx config without dropping connections"
	@echo "  make nginx-logs     tail -F nginx container logs"
	@echo "  make nginx-status   Show nginx container status"
	@echo ""
	@echo "Deploy to EKS dev (see deployment/README.md):"
	@echo "  make deploy-plan    Guards + terraform plan saved to tmp/ — read it"
	@echo "  make deploy         Apply exactly that saved plan"
	@echo "  make deploy-status  Terraform's image tag vs what the cluster runs"
	@echo "  make deploy-smoke   Post-deploy contract check (EKS)"
	@echo ""
	@echo "Override ports: BACKEND_PORT=8010 make dev"
	@echo "External (split mode): bond-mcps auth proxy on :$(MCP_AUTH_PORT) (run 'make dev' in ../bond-mcps/)"
	@echo "External (combined): bond-mcps auth proxy on :$(MCP_AUTH_PORT_COMBINED) (run 'make dev-combined' in ../bond-mcps/)"

# ── Deploy to EKS ───────────────────────────────────────────────────────────
# `terraform apply` IS the deploy. build-stages.tf computes a 12-char content
# hash over what Dockerfile.combined ships (bondable/**/*.py, flutterui/lib,
# packages/bond_chat_ui/lib, requirements.txt, pubspec.lock, the nginx/
# supervisord/entrypoint templates), builds + pushes that tag if ECR doesn't
# already have it, and rolls kubernetes_deployment.backend onto it.
#
# THE WORKING TREE IS THE INPUT. build-stages.tf hashes files on disk, not a
# git ref, and it runs `flutter build web` from the tree — so a dirty tree or
# a feature branch ships to dev silently. deploy-check guards exactly that,
# and is the whole reason this wrapper exists. Note the guard's boundary: the
# live tfvars file is gitignored, so variable changes are invisible to git —
# the saved plan (which embeds the resolved values) is what you review.
#
# Two steps, on purpose:
#   make deploy-plan   → guard, then plan, saved to $(TF_PLAN). READ IT.
#   make deploy        → apply exactly that saved plan; it never re-plans.
#
# The saved plan embeds resolved variable values — including everything in
# $(TF_VARFILE) — so it lives under tmp/ (gitignored) and is deleted after a
# successful apply.

TF_DIR     := deployment/terraform-existing-vpc
TF_ENV     ?= dev
TF_REGION  ?= us-west-2
# NOT environments/$(TF_ENV).tfvars — the live var file is named for the
# region + VPC topology. Override TF_VARFILE to target a different stack.
TF_VARFILE ?= environments/us-west-2-existing-vpc.tfvars
TF_PLAN    := $(CURDIR)/tmp/terraform-$(TF_ENV).tfplan
K8S_NS     := bond-ai

GREEN  := \033[32m
RED    := \033[31m
YELLOW := \033[33m
BLUE   := \033[34m
RESET  := \033[0m

.PHONY: deploy-check deploy-plan deploy deploy-status deploy-smoke

# Refuses to ship anything that is not exactly the merged commit.
# DEPLOY_UNSAFE=1 skips ONLY the three git checks — never the tooling ones,
# which are hard prerequisites rather than policy.
deploy-check:
	@command -v terraform >/dev/null || { printf "$(RED)x$(RESET) terraform not installed\n"; exit 1; }
	@command -v aws       >/dev/null || { printf "$(RED)x$(RESET) aws CLI not installed\n"; exit 1; }
	@command -v jq        >/dev/null || { printf "$(RED)x$(RESET) jq not installed (maintenance-mode build reads the theme config with it)\n"; exit 1; }
	@command -v kubectl   >/dev/null || { printf "$(RED)x$(RESET) kubectl not installed\n"; exit 1; }
	@command -v flutter   >/dev/null || { printf "$(RED)x$(RESET) flutter not installed — build-stages.tf runs 'flutter build web' on the HOST, not in Docker\n"; exit 1; }
	@command -v docker    >/dev/null || { printf "$(RED)x$(RESET) docker not installed\n"; exit 1; }
	@docker info >/dev/null 2>&1 || { printf "$(RED)x$(RESET) docker daemon is not running — apply builds the image\n"; exit 1; }
	@docker buildx version >/dev/null 2>&1 || { printf "$(RED)x$(RESET) docker buildx missing — needed for --platform linux/amd64\n"; exit 1; }
	@test -f $(TF_DIR)/$(TF_VARFILE) || { printf "$(RED)x$(RESET) missing $(TF_DIR)/$(TF_VARFILE) (gitignored; copy environments/example.tfvars)\n"; exit 1; }
	@aws sts get-caller-identity >/dev/null 2>&1 || { printf "$(RED)x$(RESET) no usable AWS credentials\n"; exit 1; }
	@if [ -n "$(DEPLOY_UNSAFE)" ]; then \
	   printf "  $(YELLOW)!$(RESET) DEPLOY_UNSAFE=1 — shipping this working tree with no git checks\n"; \
	 else \
	   test -z "$$(git status --porcelain)" || { \
	     printf "$(RED)x$(RESET) working tree is not clean — the image is built from it, so uncommitted\n"; \
	     printf "    (and untracked) files would ship. Commit or stash first.\n"; \
	     printf "    Deliberate? make deploy-plan DEPLOY_UNSAFE=1\n"; exit 1; }; \
	   b=$$(git rev-parse --abbrev-ref HEAD); \
	   [ "$$b" = "main" ] || { \
	     printf "$(RED)x$(RESET) on branch '$$b', not main — dev serves merged code\n"; \
	     printf "    Deliberate? make deploy-plan DEPLOY_UNSAFE=1\n"; exit 1; }; \
	   git fetch -q origin main; \
	   [ "$$(git rev-parse HEAD)" = "$$(git rev-parse origin/main)" ] || { \
	     printf "$(RED)x$(RESET) local main is not identical to origin/main — pull or push first\n"; exit 1; }; \
	 fi
	@printf "  $(GREEN)v$(RESET) $(TF_ENV) <- $$(git rev-parse --short HEAD) ($$(git rev-parse --abbrev-ref HEAD)) as account $$(aws sts get-caller-identity --query Account --output text)\n"

deploy-plan: deploy-check
	@mkdir -p tmp
	@terraform -chdir=$(TF_DIR) init -input=false >/dev/null
	@terraform -chdir=$(TF_DIR) plan -input=false -var-file=$(TF_VARFILE) -out=$(TF_PLAN)
	@git rev-parse HEAD > $(TF_PLAN).sha
	@printf "\n  $(BLUE)->$(RESET) read the plan above. Expected for a code release:\n"
	@printf "     null_resource.build_combined_image  must be replaced (triggers.image_tag)\n"
	@printf "     kubernetes_deployment.backend[0]    updated in place with the new tag\n"
	@printf "     Nothing else. Aurora, EKS, KMS, Secrets Manager, ACM or WAF\n"
	@printf "     appearing is NOT expected — stop and investigate. (WAF rules ride\n"
	@printf "     the shared bond-platform ALB: changes hit bond-mcps traffic too.)\n"
	@printf "  $(BLUE)->$(RESET) then: make deploy\n"

# Re-runs the guard rather than trusting the one deploy-plan ran. The saved
# plan pins the image TAG, but `flutter build web` + `docker buildx` read the
# tree at APPLY time — a commit landing in between would ship different
# content under the reviewed tag. Comparing HEAD to the plan-time sha closes that.
deploy: deploy-check
	@test -f $(TF_PLAN) || { printf "$(RED)x$(RESET) no saved plan — run: make deploy-plan\n"; exit 1; }
	@planned=$$(cat $(TF_PLAN).sha 2>/dev/null); \
	 [ "$$planned" = "$$(git rev-parse HEAD)" ] || { \
	   printf "$(RED)x$(RESET) HEAD moved since the plan was made — re-run: make deploy-plan\n"; \
	   printf "    planned $$planned\n    now     $$(git rev-parse HEAD)\n"; exit 1; }
	@terraform -chdir=$(TF_DIR) apply $(TF_PLAN)
	@rm -f $(TF_PLAN) $(TF_PLAN).sha
	@printf "  $(GREEN)v$(RESET) applied. Next: make deploy-smoke\n"

# What terraform thinks is deployed vs what the cluster is actually running.
deploy-status:
	@printf "  $(BLUE)terraform$(RESET)\n"
	@printf "    image tag  %s\n" "$$(terraform -chdir=$(TF_DIR) output -raw deployed_image_tag 2>/dev/null || echo '?')"
	@printf "    image uri  %s\n" "$$(terraform -chdir=$(TF_DIR) output -raw deployed_image_uri 2>/dev/null || echo '?')"
	@printf "    url        %s\n" "$$(terraform -chdir=$(TF_DIR) output -raw eks_custom_domain_url 2>/dev/null || echo '?')"
	@printf "  $(BLUE)cluster$(RESET) (%s)\n" "$$(terraform -chdir=$(TF_DIR) output -raw eks_cluster_name 2>/dev/null || echo '?')"
	@kubectl get deploy -n $(K8S_NS) \
	  -o custom-columns=NAME:.metadata.name,READY:.status.readyReplicas,IMAGE:'.spec.template.spec.containers[0].image' \
	  2>/dev/null || printf "    $(YELLOW)!$(RESET) kubectl not configured — %s\n" "$$(terraform -chdir=$(TF_DIR) output -raw eks_kubectl_config)"

# Post-deploy contract check. boto3 lives in the project's poetry env.
# The cluster name, ALB hostname and ALB ARN MUST be passed: the script's
# name-convention defaults ("bond-ai-dev-eks", "bond-ai-dev-eks-alb") don't
# exist — this stack consumes the shared bond-platform-dev cluster and the
# bond-mcps-owned ALB, whose name is k8s-generated.
# --expect-public-alb: the shared ALB is internet-facing by design; the smoke
# check verifies a WAF Web ACL is attached rather than requiring private IPs.
# --guardrails-mode comes from terraform so the exploit test asserts the
# deployed mode (permissive → guardrail must NOT block).
deploy-smoke:
	@cluster=$$(terraform -chdir=$(TF_DIR) output -raw eks_cluster_name); \
	 host=$$(terraform -chdir=$(TF_DIR) output -raw eks_custom_domain_url | sed -e 's|^https\{0,1\}://||'); \
	 alb_arn=$$(terraform -chdir=$(TF_DIR) output -raw eks_alb_arn 2>/dev/null || echo ""); \
	 gmode=$$(terraform -chdir=$(TF_DIR) output -raw guardrail_mode 2>/dev/null || echo "enforce"); \
	 printf "  $(BLUE)->$(RESET) smoke: cluster=$$cluster host=$$host guardrails=$$gmode\n"; \
	 poetry run python $(TF_DIR)/scripts/smoke_test_deployment.py \
	   --env $(TF_ENV) --region $(TF_REGION) \
	   --test-eks --skip-apprunner \
	   --eks-cluster-name "$$cluster" \
	   --eks-alb-hostname "$$host" \
	   --eks-alb-arn "$$alb_arn" \
	   --guardrails-mode "$$gmode" \
	   --expect-public-alb
