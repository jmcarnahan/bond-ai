#!/usr/bin/env bash
# =============================================================================
# docker-entrypoint.sh — render the nginx front-door config, then start the app.
#
# Substitutes the ${BOND_MCPS_*_UPSTREAM} placeholders in
# nginx-combined.conf.template with env vars (defaulted below to the public
# *.mcps.* ALB hostnames) and writes the result to the nginx config path. Uses
# an explicit envsubst variable WHITELIST so nginx's own $variables survive.
# Finally execs the container CMD (supervisord).
# =============================================================================
set -euo pipefail

# Upstream origins (scheme + host, no trailing path). Override in EKS consume
# mode with in-cluster service DNS, e.g.
#   BOND_MCPS_AUTH_UPSTREAM=http://auth-server.bond-mcps.svc.cluster.local:8001
: "${BOND_MCPS_AUTH_UPSTREAM:=https://auth.mcps.ai.southbayequity.cloud}"
: "${BOND_MCPS_MICROSOFT_UPSTREAM:=https://ms-graph.mcps.ai.southbayequity.cloud}"
: "${BOND_MCPS_ATLASSIAN_UPSTREAM:=https://atlassian.mcps.ai.southbayequity.cloud}"
: "${BOND_MCPS_GITHUB_UPSTREAM:=https://github.mcps.ai.southbayequity.cloud}"
: "${BOND_MCPS_DATABRICKS_UPSTREAM:=https://databricks.mcps.ai.southbayequity.cloud}"
export BOND_MCPS_AUTH_UPSTREAM BOND_MCPS_MICROSOFT_UPSTREAM \
    BOND_MCPS_ATLASSIAN_UPSTREAM BOND_MCPS_GITHUB_UPSTREAM \
    BOND_MCPS_DATABRICKS_UPSTREAM

TEMPLATE="/etc/nginx/templates/nginx-combined.conf.template"
TARGET="/etc/nginx/conf.d/default.conf"

# Whitelist only our placeholders so nginx runtime vars ($http_host, etc.) are
# left untouched by envsubst.
envsubst '${BOND_MCPS_AUTH_UPSTREAM} ${BOND_MCPS_MICROSOFT_UPSTREAM} ${BOND_MCPS_ATLASSIAN_UPSTREAM} ${BOND_MCPS_GITHUB_UPSTREAM} ${BOND_MCPS_DATABRICKS_UPSTREAM}' \
    < "$TEMPLATE" > "$TARGET"

exec "$@"
