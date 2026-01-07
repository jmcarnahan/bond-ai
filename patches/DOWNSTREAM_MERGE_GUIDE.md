# Downstream Fork Merge Guide

## Context for Claude

This document helps resolve merge conflicts when syncing the downstream fork with upstream `jmcarnahan/bond-ai`. The upstream has been updated to align with downstream patterns, removing features that caused divergence.

## Summary of Upstream Changes

The upstream branch `downstream-patches-20250105` includes these changes to align with downstream:

| Change | Purpose |
|--------|---------|
| Removed `custom-domain.tf` | Eliminates Route53/custom domain complexity |
| Simplified `backend.tf` | Removed `local.frontend_fqdn` dependencies |
| Simplified `outputs.tf` | Removed custom domain outputs |
| Updated `variables.tf` | Removed custom domain vars, added downstream vars |
| Kept generic MCP config | Uses `var.bond_mcp_config` JSON approach |

## File-by-File Merge Guide

### 1. custom-domain.tf

**Upstream status:** DELETED

**Expected downstream status:** Should not exist (or should be deleted)

**Action:** If downstream has this file, delete it. If there's a conflict showing the file was deleted upstream, accept the deletion.

```bash
# If file exists in downstream, remove it
git rm deployment/terraform-existing-vpc/custom-domain.tf
```

### 2. backend.tf

**Key changes in upstream:**

```hcl
# JWT redirect - uses variable only, no local.frontend_fqdn fallback
JWT_REDIRECT_URI = var.jwt_redirect_uri != "" ? var.jwt_redirect_uri : "*"

# CORS - uses variable only, no appended custom domain
CORS_ALLOWED_ORIGINS = var.cors_allowed_origins

# MCP config - generic JSON approach
BOND_MCP_CONFIG = var.bond_mcp_config
```

**Potential conflicts:**

1. **JWT_REDIRECT_URI** - Downstream may have similar. Accept upstream version.

2. **CORS_ALLOWED_ORIGINS** - Downstream may have similar. Accept upstream version.

3. **BOND_MCP_CONFIG** - This is the main difference.
   - Upstream: `BOND_MCP_CONFIG = var.bond_mcp_config`
   - Downstream: Dynamic `jsonencode()` block for Atlassian
   - **Resolution:** See `MCP_CONFIG_MIGRATION.md` for migration steps. Accept upstream version and migrate tfvars to JSON format.

**Merge resolution:**
```hcl
# Accept this for JWT
JWT_REDIRECT_URI = var.jwt_redirect_uri != "" ? var.jwt_redirect_uri : "*"

# Accept this for CORS
CORS_ALLOWED_ORIGINS = var.cors_allowed_origins

# Accept this for MCP (then migrate your config to JSON in tfvars)
BOND_MCP_CONFIG = var.bond_mcp_config
```

### 3. outputs.tf

**Key changes in upstream:**

- **REMOVED** `output "frontend_url"` - Was using `local.use_custom_domain`
- **SIMPLIFIED** `output "deployment_instructions"` - No custom domain references

**Upstream version:**
```hcl
output "frontend_app_runner_service_url" {
  value = "https://${aws_apprunner_service.frontend.service_url}"
  description = "Frontend App Runner service URL (auto-generated)"
}

# NOTE: frontend_url output was REMOVED

output "deployment_instructions" {
  value = <<-EOT

    Deployment Complete!

    Backend URL: https://${aws_apprunner_service.backend.service_url}
    Frontend URL: https://${aws_apprunner_service.frontend.service_url}

    Next Steps:
    1. Update Okta application with callback URL:
       https://${aws_apprunner_service.backend.service_url}/auth/okta/callback

    2. Test the deployment:
       curl https://${aws_apprunner_service.backend.service_url}/health

    3. Access the application:
       https://${aws_apprunner_service.frontend.service_url}
  EOT
  description = "Post-deployment instructions"
}
```

**Action:** Accept upstream version. If downstream has custom outputs (e.g., from custom-domain.tf), remove them.

### 4. variables.tf

**Variables ADDED in upstream (from downstream patches):**

```hcl
variable "app_runner_subnet_ids" {
  description = "List of subnet IDs for App Runner VPC connector (use internal-green subnets)"
  type        = list(string)
  default     = []
}

variable "mcp_atlassian_service_url" {
  description = "MCP Atlassian service URL (set after first deployment to avoid circular dependency)"
  type        = string
  default     = ""
}

variable "backend_service_url" {
  description = "Backend service URL (set after first deployment for OAuth redirect)"
  type        = string
  default     = ""
}

# WAF Configuration
variable "waf_enabled" {
  description = "Enable WAF protection for App Runner services"
  type        = bool
  default     = true
}

variable "waf_cloudwatch_enabled" {
  description = "Enable CloudWatch metrics for WAF"
  type        = bool
  default     = true
}

variable "waf_sampled_requests_enabled" {
  description = "Enable sampled requests for WAF (useful for debugging blocked requests)"
  type        = bool
  default     = true
}
```

**Variables REMOVED from upstream:**

```hcl
# REMOVED - Custom domain variables (delete if present in downstream)
variable "domain_name" { ... }
variable "frontend_subdomain" { ... }
variable "create_hosted_zone" { ... }
variable "existing_hosted_zone_id" { ... }
variable "use_private_zone" { ... }
variable "custom_frontend_fqdn" { ... }
```

**Variables downstream may have that upstream doesn't:**

If downstream has these Atlassian-specific variables, they should be REMOVED (replaced by JSON config):
```hcl
# REMOVE these - replaced by bond_mcp_config JSON
variable "mcp_atlassian_oauth_secret_name" { ... }
variable "mcp_atlassian_oauth_client_id" { ... }
variable "mcp_atlassian_oauth_scopes" { ... }
variable "mcp_atlassian_oauth_cloud_id" { ... }
```

**Action:**
1. Accept upstream's added variables
2. Remove custom domain variables
3. Remove Atlassian-specific MCP variables (if any)
4. Keep `bond_mcp_config` variable

### 5. rds.tf

**Upstream status:** `engine_version = "15.12"`

**Action:** Should match. No conflicts expected.

### 6. Data Sources (if any mcp_atlassian_oauth)

**If downstream has:**
```hcl
data "aws_secretsmanager_secret_version" "mcp_atlassian_oauth" {
  count     = var.mcp_atlassian_oauth_secret_name != "" ? 1 : 0
  secret_id = var.mcp_atlassian_oauth_secret_name
}
```

**Action:** REMOVE this data source. The MCP config will handle secrets differently (see `MCP_CONFIG_MIGRATION.md`).

## tfvars Migration

After merging, update your tfvars file:

### Remove these variables:
```hcl
# DELETE these lines
domain_name = "..."
frontend_subdomain = "..."
create_hosted_zone = ...
existing_hosted_zone_id = "..."
use_private_zone = ...
custom_frontend_fqdn = "..."

# DELETE these if present (replaced by bond_mcp_config)
mcp_atlassian_oauth_secret_name = "..."
mcp_atlassian_oauth_client_id = "..."
mcp_atlassian_oauth_scopes = "..."
mcp_atlassian_oauth_cloud_id = "..."
```

### Add/update these:
```hcl
# Ensure these are set (may already exist)
jwt_redirect_uri = "https://your-frontend-url"
cors_allowed_origins = "http://localhost,http://localhost:3000,https://your-frontend-url"
backend_service_url = "https://your-backend-url"

# MCP config as JSON (see MCP_CONFIG_MIGRATION.md for full example)
bond_mcp_config = <<-EOT
{
  "mcpServers": {
    "atlassian": {
      "url": "https://mcp-atlassian.example.com/mcp/",
      ...
    }
  }
}
EOT
```

## Post-Merge Checklist

1. [ ] `custom-domain.tf` is deleted
2. [ ] No references to `local.frontend_fqdn` or `local.use_custom_domain`
3. [ ] `backend.tf` uses `BOND_MCP_CONFIG = var.bond_mcp_config`
4. [ ] `outputs.tf` has no `frontend_url` output
5. [ ] `variables.tf` has no custom domain variables
6. [ ] `variables.tf` has no Atlassian-specific MCP variables
7. [ ] No `mcp_atlassian_oauth` data source exists
8. [ ] tfvars updated with `bond_mcp_config` JSON
9. [ ] `terraform validate` passes
10. [ ] `terraform plan` shows expected changes only

## Validation Commands

```bash
# Check for any remaining custom domain references
grep -r "frontend_fqdn\|use_custom_domain" deployment/terraform-existing-vpc/

# Check for Atlassian-specific MCP variables
grep -r "mcp_atlassian_oauth" deployment/terraform-existing-vpc/

# Validate Terraform
cd deployment/terraform-existing-vpc
terraform validate

# Plan to see what would change
terraform plan -var-file=your-environment.tfvars
```

## If Merge Goes Wrong

If the merge creates too many conflicts:

```bash
# Abort the merge
git merge --abort

# Try a different strategy - accept upstream for terraform files
git checkout upstream/main -- deployment/terraform-existing-vpc/
git checkout HEAD -- deployment/terraform-existing-vpc/*.tfvars  # Keep your tfvars

# Then manually migrate your tfvars using this guide
```

## Questions?

If Claude encounters issues not covered here:
1. Check if it's related to custom domain removal → delete the reference
2. Check if it's related to MCP config → use generic JSON approach
3. Check if it's a new variable → keep it if it has a default, ask user otherwise
