# Apply Terraform Patches to Upstream Fork

This directory contains patches to sync local changes from the mcafee-eng fork to the upstream jmcarnahan/bond-ai repository.

## Overview

These patches add the following enhancements to the upstream fork:

1. **MCP Atlassian Integration** - Complete OAuth2 configuration for Atlassian MCP server
2. **WAF Variables** - Configuration options for Web Application Firewall
3. **Deployment Improvements** - Simplified variable-based configuration to avoid circular dependencies
4. **PostgreSQL Update** - Upgrade from 15.7 to 15.12

## Files to Patch

- `deployment/terraform-existing-vpc/backend.tf` - MCP config, OAuth variables
- `deployment/terraform-existing-vpc/outputs.tf` - Simplified outputs
- `deployment/terraform-existing-vpc/rds.tf` - PostgreSQL version bump
- `deployment/terraform-existing-vpc/variables.tf` - New MCP and WAF variables

## Prerequisites

- Git access to push to `jmcarnahan/bond-ai`
- Clean working directory in upstream fork
- These patch files copied to a machine with push access

## Application Instructions

### Step 1: Prepare the Upstream Repository

```bash
# Clone or navigate to the upstream fork
cd /path/to/jmcarnahan/bond-ai

# Ensure you're on the main branch and it's up to date
git checkout main
git pull origin main

# Verify clean working directory
git status
# Should show: "nothing to commit, working tree clean"
```

### Step 2: Apply the Patches

Apply patches in this order:

```bash
# Apply each patch file
git apply backend.tf.patch
git apply outputs.tf.patch
git apply rds.tf.patch
git apply variables.tf.patch
```

**Note**: If any patch fails with conflicts, you may need to apply them manually. Each patch file shows the exact changes needed.

### Step 3: Verify the Changes

```bash
# Review what was changed
git status
git diff

# Check specifically that these changes are present:
# 1. backend.tf has MCP_CONFIG section with Atlassian configuration
# 2. variables.tf has app_runner_subnet_ids, mcp_atlassian_service_url, backend_service_url, and WAF variables
# 3. rds.tf shows engine_version = "15.12"
# 4. outputs.tf has simplified deployment instructions
```

### Step 4: Commit and Push

```bash
# Stage the changes
git add deployment/terraform-existing-vpc/backend.tf
git add deployment/terraform-existing-vpc/outputs.tf
git add deployment/terraform-existing-vpc/rds.tf
git add deployment/terraform-existing-vpc/variables.tf

# Create a commit
git commit -m "Add MCP Atlassian support, WAF variables, and deployment improvements

- Add MCP Atlassian OAuth2 configuration with streamable-http transport
- Add WAF configuration variables for App Runner protection
- Add app_runner_subnet_ids, mcp_atlassian_service_url, backend_service_url variables
- Simplify OAuth redirect URIs to use variables and avoid circular dependencies
- Update PostgreSQL from 15.7 to 15.12
- Simplify deployment outputs to use direct App Runner URLs"

# Push to upstream
git push origin main
```

### Step 5: Verify on GitHub

1. Visit https://github.com/jmcarnahan/bond-ai
2. Verify the commit appears in the main branch
3. Check the 4 modified files to ensure changes are present

## Troubleshooting

### Patch Fails to Apply

If `git apply` fails, you can manually apply the changes:

1. Open the `.patch` file in a text editor
2. Lines starting with `-` should be removed
3. Lines starting with `+` should be added
4. Context lines (no prefix) help you find the right location

### Conflicts with Upstream Changes

If the upstream fork has been modified since these patches were created:

```bash
# Check what changed in upstream
git log --oneline --since="2025-01-01" -- deployment/terraform-existing-vpc/

# You may need to manually merge the changes
```

### Alternative: Manual Application

If patches don't apply cleanly, manually edit each file:

1. **backend.tf** (lines 42-91): Add MCP_CONFIG section and update OKTA/JWT/CORS variables
2. **outputs.tf** (lines 56-84): Remove frontend_url output, simplify deployment_instructions
3. **rds.tf** (line 19): Change `engine_version = "15.7"` to `"15.12"`
4. **variables.tf**: Add blocks at lines 23-41 (subnet/MCP vars) and 147-166 (WAF vars)

## Patch Details

### backend.tf Changes
- Updated OKTA_REDIRECT_URI to use variable pattern
- Updated JWT_REDIRECT_URI to use variable pattern
- Simplified CORS_ALLOWED_ORIGINS to use variable only
- Added complete BOND_MCP_CONFIG section with Atlassian OAuth2 setup

### outputs.tf Changes
- Removed frontend_url output (custom domain references)
- Simplified deployment_instructions to use App Runner URLs

### rds.tf Changes
- Bumped PostgreSQL version from 15.7 to 15.12

### variables.tf Changes
- Added app_runner_subnet_ids variable
- Added mcp_atlassian_service_url variable
- Added backend_service_url variable
- Added waf_enabled, waf_cloudwatch_enabled, waf_sampled_requests_enabled variables

## Post-Application

After successfully applying and pushing these patches:

1. The upstream fork will be in sync with the mcafee-eng fork for these 4 files
2. You can safely merge from upstream back to mcafee-eng without conflicts on these files
3. Future changes to these files should be made in upstream first, then pulled to mcafee-eng

## Questions?

If you encounter issues applying these patches, check:
- Git version: `git --version` (should be 2.x or higher)
- Patch format: Ensure files weren't corrupted during transfer
- Upstream state: Verify no one else has modified these files since patch creation
