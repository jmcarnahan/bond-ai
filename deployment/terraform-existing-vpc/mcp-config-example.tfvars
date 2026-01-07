# MCP Configuration Migration Example
#
# This file demonstrates the NEW JSON-based approach for MCP server configuration
# after the upstream merge. Use this as a template for migrating your existing
# Atlassian MCP configuration.
#
# See patches/MCP_CONFIG_MIGRATION.md for detailed migration instructions.

# ============================================================================
# MCP Configuration (NEW Approach - Generic JSON)
# ============================================================================

# The bond_mcp_config variable accepts a JSON string that defines all MCP servers.
# This replaces the previous approach of using individual variables like:
#   - mcp_atlassian_service_url
#   - mcp_atlassian_oauth_secret_name
#   - mcp_atlassian_oauth_client_id
#   - mcp_atlassian_oauth_scopes
#   - mcp_atlassian_oauth_cloud_id

bond_mcp_config = <<-EOT
{
  "mcpServers": {
    "atlassian": {
      "url": "https://YOUR-MCP-ATLASSIAN-SERVICE.us-west-2.awsapprunner.com/mcp/",
      "transport": "streamable-http",
      "auth_type": "oauth2",
      "display_name": "Atlassian",
      "description": "Connect to Atlassian Jira and Confluence",
      "oauth_config": {
        "provider": "atlassian",
        "client_id": "YOUR_ATLASSIAN_OAUTH_CLIENT_ID",
        "client_secret_arn": "arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:your-atlassian-oauth-secret-XXXXX",
        "authorize_url": "https://auth.atlassian.com/authorize",
        "token_url": "https://auth.atlassian.com/oauth/token",
        "scopes": "read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access",
        "redirect_uri": "https://YOUR-BACKEND-SERVICE.us-west-2.awsapprunner.com/connections/atlassian/callback"
      },
      "site_url": "https://api.atlassian.com",
      "cloud_id": "YOUR_ATLASSIAN_CLOUD_ID"
    }
  }
}
EOT

# IMPORTANT: Set backend_service_url for OAuth redirects
backend_service_url = "https://YOUR-BACKEND-SERVICE.us-west-2.awsapprunner.com"

# Optional: Keep mcp_atlassian_service_url if used elsewhere (e.g., for health checks)
mcp_atlassian_service_url = "https://YOUR-MCP-ATLASSIAN-SERVICE.us-west-2.awsapprunner.com"

# ============================================================================
# How to Migrate Your Existing Configuration
# ============================================================================
#
# OLD APPROACH (Remove these from your tfvars):
# -------------------------------------------
# mcp_atlassian_service_url      = "https://mcp-atlassian.example.com"
# mcp_atlassian_oauth_secret_name = "atlassian-oauth-secret"
# mcp_atlassian_oauth_client_id  = "your-client-id"
# mcp_atlassian_oauth_scopes     = "read:jira-work,read:confluence-content.all"
# mcp_atlassian_oauth_cloud_id   = "your-cloud-id"
# backend_service_url            = "https://backend.example.com"
#
# NEW APPROACH (Replace with):
# ----------------------------
# 1. Create bond_mcp_config JSON (see above)
# 2. Keep backend_service_url variable
# 3. Optionally keep mcp_atlassian_service_url if needed
# 4. Remove all mcp_atlassian_oauth_* variables
#
# The client_secret is now referenced by ARN instead of being fetched at
# terraform apply time. The backend application will resolve the secret.

# ============================================================================
# Multiple MCP Servers Example
# ============================================================================
#
# You can configure multiple MCP servers in a single bond_mcp_config:
#
# bond_mcp_config = <<-EOT
# {
#   "mcpServers": {
#     "atlassian": {
#       "url": "https://mcp-atlassian.example.com/mcp/",
#       "transport": "streamable-http",
#       "auth_type": "oauth2",
#       "display_name": "Atlassian",
#       "oauth_config": { ... }
#     },
#     "github": {
#       "url": "https://mcp-github.example.com/mcp/",
#       "transport": "streamable-http",
#       "auth_type": "oauth2",
#       "display_name": "GitHub",
#       "oauth_config": { ... }
#     },
#     "sbel": {
#       "url": "https://mcp-sbel.example.com/mcp",
#       "transport": "streamable-http",
#       "display_name": "SBEL Lending Data",
#       "description": "Query loan products"
#     }
#   }
# }
# EOT

# ============================================================================
# Inline JSON Alternative (for CI/CD)
# ============================================================================
#
# If you prefer a single-line format (useful for CI/CD pipelines):
#
# bond_mcp_config = "{\"mcpServers\":{\"atlassian\":{\"url\":\"https://server.com/mcp/\",\"transport\":\"streamable-http\",\"auth_type\":\"oauth2\",\"display_name\":\"Atlassian\",\"oauth_config\":{\"provider\":\"atlassian\",\"client_id\":\"ID\",\"client_secret_arn\":\"arn:aws:...\",\"scopes\":\"read:jira-work\"}}}}"
