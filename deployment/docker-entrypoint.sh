#!/usr/bin/env bash
# =============================================================================
# docker-entrypoint.sh — render the nginx front-door config, then start the app.
#
# Substitutes the ${BOND_MCPS_*_UPSTREAM} and ${NGINX_RESOLVER} placeholders in
# nginx-combined.conf.template with env vars (upstreams defaulted below to the
# public *.mcps.* ALB hostnames) and writes the result to the nginx config
# path. Uses an explicit envsubst variable WHITELIST so nginx's own $variables
# survive. Finally execs the container CMD (supervisord).
#
# Every value that lands in the config is VALIDATED first, and a bad one stops
# the container with a named reason rather than starting nginx on a config
# that would misroute silently: an upstream with a path would make the
# variable proxy_pass rewrite every request URI, and a value with anything
# but scheme://host[:port] characters could close the directive and inject
# configuration.
# =============================================================================
set -euo pipefail

die() { echo "docker-entrypoint: $*" >&2; exit 1; }

# Upstream origins (scheme + host, no trailing path). Override in EKS consume
# mode with in-cluster service DNS, e.g.
#   BOND_MCPS_AUTH_UPSTREAM=http://auth-server.bond-mcps.svc.cluster.local:8001
# In-cluster names must be FULLY qualified: nginx's resolver does not apply
# resolv.conf's search list.
: "${BOND_MCPS_AUTH_UPSTREAM:=https://auth.mcps.ai.southbayequity.cloud}"
: "${BOND_MCPS_MICROSOFT_UPSTREAM:=https://ms-graph.mcps.ai.southbayequity.cloud}"
: "${BOND_MCPS_ATLASSIAN_UPSTREAM:=https://atlassian.mcps.ai.southbayequity.cloud}"
: "${BOND_MCPS_GITHUB_UPSTREAM:=https://github.mcps.ai.southbayequity.cloud}"
: "${BOND_MCPS_DATABRICKS_UPSTREAM:=https://databricks.mcps.ai.southbayequity.cloud}"

# scheme://host[:port] — a DNS name, an IPv4 literal, or a bracketed IPv6
# literal — and nothing after it. Trailing slashes are forgiven (stripped),
# because "https://host/" is the same origin; a real path is refused.
UPSTREAM_RE='^https?://([A-Za-z0-9._-]+|\[[0-9A-Fa-f:.]+\])(:[0-9]{1,5})?$'
for name in BOND_MCPS_AUTH_UPSTREAM BOND_MCPS_MICROSOFT_UPSTREAM \
            BOND_MCPS_ATLASSIAN_UPSTREAM BOND_MCPS_GITHUB_UPSTREAM \
            BOND_MCPS_DATABRICKS_UPSTREAM; do
    value="${!name}"
    while [[ "$value" == */ ]]; do value="${value%/}"; done
    [[ "$value" =~ $UPSTREAM_RE ]] \
        || die "$name must be scheme://host[:port] with no path, got: '${!name}'"
    printf -v "$name" '%s' "$value"
    export "$name"
done

# The nameservers nginx re-resolves those upstreams through (the template's
# `resolver` directive). nginx does not read /etc/resolv.conf itself, so every
# nameserver in it is lifted here, space-separated — CoreDNS in EKS, 127.0.0.11
# under plain Docker. Set NGINX_RESOLVER to point it elsewhere. A container
# with no nameserver could not have reached the upstreams by name anyway, so
# that is a hard failure rather than a silent fallback. IPv6 addresses are
# bracketed, which is how nginx spells them.
if [ -z "${NGINX_RESOLVER:-}" ]; then
    [ -r /etc/resolv.conf ] || die "/etc/resolv.conf is missing and NGINX_RESOLVER is unset"
    NGINX_RESOLVER="$(awk '/^nameserver[[:space:]]/ { printf "%s ", $2 }' /etc/resolv.conf)"
fi
IPV4_RE='^[0-9]{1,3}(\.[0-9]{1,3}){3}$'
IPV6_RE='^[0-9A-Fa-f:.]+$'
resolvers=""
for token in $NGINX_RESOLVER; do
    token="${token#[}"; token="${token%]}"
    if [[ "$token" =~ $IPV4_RE ]]; then
        resolvers+="$token "
    elif [[ "$token" == *:* && "$token" =~ $IPV6_RE ]]; then
        resolvers+="[$token] "
    else
        die "NGINX_RESOLVER entry is not an IP address: '$token'"
    fi
done
NGINX_RESOLVER="${resolvers% }"
[ -n "$NGINX_RESOLVER" ] || die "no nameserver in /etc/resolv.conf and NGINX_RESOLVER is unset"
export NGINX_RESOLVER

TEMPLATE="/etc/nginx/templates/nginx-combined.conf.template"
TARGET="/etc/nginx/conf.d/default.conf"

# Whitelist only our placeholders so nginx runtime vars ($http_host, $mcps_*,
# etc.) are left untouched by envsubst.
envsubst '${BOND_MCPS_AUTH_UPSTREAM} ${BOND_MCPS_MICROSOFT_UPSTREAM} ${BOND_MCPS_ATLASSIAN_UPSTREAM} ${BOND_MCPS_GITHUB_UPSTREAM} ${BOND_MCPS_DATABRICKS_UPSTREAM} ${NGINX_RESOLVER}' \
    < "$TEMPLATE" > "$TARGET"

exec "$@"
