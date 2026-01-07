# MCP Configuration Migration Guide

## Context for Claude

This document guides the migration from the **dynamically-constructed Atlassian MCP config** (downstream fork) to the **generic JSON variable approach** (upstream). Use this when merging upstream changes into the downstream fork.

## The Change

### OLD (Downstream - Dynamic Construction)

The downstream fork constructs the MCP config dynamically in `backend.tf`:

```hcl
BOND_MCP_CONFIG = var.mcp_atlassian_service_url != "" && var.mcp_atlassian_oauth_secret_name != "" ? jsonencode({
  mcpServers = {
    atlassian = {
      url          = "${var.mcp_atlassian_service_url}/mcp/"
      transport    = "streamable-http"
      auth_type    = "oauth2"
      display_name = "Atlassian"
      description  = "Connect to Atlassian Jira and Confluence"
      oauth_config = {
        provider      = "atlassian"
        client_id     = var.mcp_atlassian_oauth_client_id
        client_secret = jsondecode(data.aws_secretsmanager_secret_version.mcp_atlassian_oauth[0].secret_string)["client_secret"]
        authorize_url = "https://auth.atlassian.com/authorize"
        token_url     = "https://auth.atlassian.com/oauth/token"
        scopes        = var.mcp_atlassian_oauth_scopes
        redirect_uri  = "${var.backend_service_url}/connections/atlassian/callback"
      }
      site_url = "https://api.atlassian.com"
      cloud_id = var.mcp_atlassian_oauth_cloud_id
    }
  }
}) : "{}"
```

This required these variables:
- `mcp_atlassian_service_url`
- `mcp_atlassian_oauth_secret_name`
- `mcp_atlassian_oauth_client_id`
- `mcp_atlassian_oauth_scopes`
- `mcp_atlassian_oauth_cloud_id`
- `backend_service_url`

And this data source:
```hcl
data "aws_secretsmanager_secret_version" "mcp_atlassian_oauth" {
  count     = var.mcp_atlassian_oauth_secret_name != "" ? 1 : 0
  secret_id = var.mcp_atlassian_oauth_secret_name
}
```

### NEW (Upstream - Generic JSON)

The upstream uses a single JSON variable in `backend.tf`:

```hcl
BOND_MCP_CONFIG = var.bond_mcp_config
```

With this variable definition:
```hcl
variable "bond_mcp_config" {
  description = "JSON configuration for MCP servers"
  type        = string
  default     = ""
}
```

## Migration Steps

### Step 1: Update backend.tf

Replace the dynamic MCP config block with:
```hcl
# MCP configuration (only set when provided)
BOND_MCP_CONFIG = var.bond_mcp_config
```

### Step 2: Remove Atlassian-specific variables from variables.tf

Remove these variable blocks (if present):
- `variable "mcp_atlassian_service_url"`
- `variable "mcp_atlassian_oauth_secret_name"`
- `variable "mcp_atlassian_oauth_client_id"`
- `variable "mcp_atlassian_oauth_scopes"`
- `variable "mcp_atlassian_oauth_cloud_id"`

**Keep these variables** (they're useful for other purposes):
- `backend_service_url` - Still useful for OAuth redirects
- `mcp_atlassian_service_url` - Can keep if used elsewhere

### Step 3: Remove the data source

Remove this data source block (if present):
```hcl
data "aws_secretsmanager_secret_version" "mcp_atlassian_oauth" {
  count     = var.mcp_atlassian_oauth_secret_name != "" ? 1 : 0
  secret_id = var.mcp_atlassian_oauth_secret_name
}
```

### Step 4: Update tfvars file

Convert from individual variables to JSON.

**Before (individual variables):**
```hcl
mcp_atlassian_service_url      = "https://mcp-atlassian.example.com"
mcp_atlassian_oauth_secret_name = "atlassian-oauth-secret"
mcp_atlassian_oauth_client_id  = "your-client-id"
mcp_atlassian_oauth_scopes     = "read:jira-work,read:confluence-content.all"
mcp_atlassian_oauth_cloud_id   = "your-cloud-id"
backend_service_url            = "https://backend.example.com"
```

**After (JSON variable):**
```hcl
bond_mcp_config = <<-EOT
{
  "mcpServers": {
    "atlassian": {
      "url": "https://mcp-atlassian.example.com/mcp/",
      "transport": "streamable-http",
      "auth_type": "oauth2",
      "display_name": "Atlassian",
      "description": "Connect to Atlassian Jira and Confluence",
      "oauth_config": {
        "provider": "atlassian",
        "client_id": "your-client-id",
        "client_secret_from_secrets_manager": "atlassian-oauth-secret",
        "authorize_url": "https://auth.atlassian.com/authorize",
        "token_url": "https://auth.atlassian.com/oauth/token",
        "scopes": "read:jira-work,read:confluence-content.all",
        "redirect_uri": "https://backend.example.com/connections/atlassian/callback"
      },
      "site_url": "https://api.atlassian.com",
      "cloud_id": "your-cloud-id"
    }
  }
}
EOT
```

### Step 5: Handle the client_secret

The dynamic approach fetched `client_secret` from Secrets Manager at Terraform apply time. With the JSON approach, you have options:

**Option A: Include secret in JSON (less secure)**
```json
"client_secret": "actual-secret-value"
```

**Option B: Reference Secrets Manager in backend code (recommended)**
Use a placeholder in the JSON that the backend resolves:
```json
"client_secret_from_secrets_manager": "atlassian-oauth-secret"
```
The backend application should look up secrets when it sees `*_from_secrets_manager` keys.

**Option C: Use Terraform templatefile with secrets**
```hcl
bond_mcp_config = templatefile("${path.module}/mcp-config.json.tpl", {
  atlassian_client_secret = jsondecode(data.aws_secretsmanager_secret_version.mcp_atlassian_oauth.secret_string)["client_secret"]
})
```

## Benefits of Generic JSON Approach

1. **Flexibility** - Can configure any MCP server, not just Atlassian
2. **Simplicity** - One variable instead of many
3. **No circular dependencies** - JSON is self-contained
4. **Easier to extend** - Add new MCP servers without Terraform changes

## Merge Conflict Resolution

When merging upstream, if you see conflicts in `backend.tf` around the `BOND_MCP_CONFIG` line:

1. Accept the upstream version: `BOND_MCP_CONFIG = var.bond_mcp_config`
2. Remove the downstream's dynamic jsonencode block
3. Update your tfvars to use the JSON format shown above
4. Remove the `mcp_atlassian_oauth` data source if it exists

## Concrete Example: Atlassian MCP Migration

The upstream repo has an example file at `deployment/terraform-existing-vpc/environments/mcp-atlassian.example.tfvars` that shows the OLD individual variable approach:

```hcl
# OLD approach (individual variables)
mcp_atlassian_enabled = true
mcp_atlassian_oauth_cloud_id = "ec8ace41-7cde-4e66-aaf1-6fca83a00c53"
mcp_atlassian_oauth_client_id = "KHXrX7yQOU0dahJswA63C8drUeK9EtWJ"
mcp_atlassian_oauth_secret_name = "bond-ai-dev-mcp-atlassian-oauth"
mcp_atlassian_oauth_scopes = "read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access"
```

**Convert to NEW JSON approach:**

```hcl
# NEW approach (JSON in bond_mcp_config)
# Note: backend_service_url must be set for the redirect_uri
backend_service_url = "https://your-backend.us-west-2.awsapprunner.com"

bond_mcp_config = <<-EOT
{
  "mcpServers": {
    "atlassian": {
      "url": "https://your-mcp-atlassian-server.us-west-2.awsapprunner.com/mcp/",
      "transport": "streamable-http",
      "auth_type": "oauth2",
      "display_name": "Atlassian",
      "description": "Connect to Atlassian Jira and Confluence",
      "oauth_config": {
        "provider": "atlassian",
        "client_id": "KHXrX7yQOU0dahJswA63C8drUeK9EtWJ",
        "client_secret_arn": "arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:bond-ai-dev-mcp-atlassian-oauth-XXXXX",
        "authorize_url": "https://auth.atlassian.com/authorize",
        "token_url": "https://auth.atlassian.com/oauth/token",
        "scopes": "read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access",
        "redirect_uri": "https://your-backend.us-west-2.awsapprunner.com/connections/atlassian/callback"
      },
      "site_url": "https://api.atlassian.com",
      "cloud_id": "ec8ace41-7cde-4e66-aaf1-6fca83a00c53"
    }
  }
}
EOT
```

### Multiple MCP Servers

You can define multiple MCP servers in a single config. Example from upstream's us-west-2 deployment:

```hcl
bond_mcp_config = <<-EOT
{
  "mcpServers": {
    "sbel": {
      "url": "https://pumfqsj3is.us-west-2.awsapprunner.com/mcp",
      "transport": "streamable-http",
      "display_name": "SBEL Lending Data",
      "description": "Query loan products across Acra, ARC, Champions, and PRMG lenders"
    },
    "atlassian": {
      "url": "https://mcp-atlassian.us-west-2.awsapprunner.com/mcp/",
      "transport": "streamable-http",
      "auth_type": "oauth2",
      "display_name": "Atlassian",
      "description": "Connect to Atlassian Jira and Confluence",
      "oauth_config": {
        "provider": "atlassian",
        "client_id": "YOUR_CLIENT_ID",
        "client_secret_arn": "arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:NAME",
        "authorize_url": "https://auth.atlassian.com/authorize",
        "token_url": "https://auth.atlassian.com/oauth/token",
        "scopes": "read:jira-user read:jira-work write:jira-work offline_access",
        "redirect_uri": "https://your-backend/connections/atlassian/callback"
      },
      "site_url": "https://api.atlassian.com",
      "cloud_id": "YOUR_CLOUD_ID"
    }
  }
}
EOT
```

### Inline JSON (Alternative)

If you prefer a single line (useful for CI/CD):

```hcl
bond_mcp_config = "{\"mcpServers\":{\"sbel\":{\"url\":\"https://server.com/mcp\",\"transport\":\"streamable-http\",\"display_name\":\"My Server\",\"description\":\"Description here\"}}}"
```

## Testing After Migration

1. Run `terraform validate` to check syntax
2. Run `terraform plan` to verify no unexpected changes
3. Verify the MCP config is passed correctly to the backend
4. Test Atlassian MCP connectivity in the application
