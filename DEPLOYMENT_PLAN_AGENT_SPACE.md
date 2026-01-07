# Bond AI Deployment Plan - AWS agent-space Account

**AWS Account:** 019593708315 (agent-space)
**Region:** us-west-2
**Date Created:** December 1, 2025
**Last Updated:** December 1, 2025 (Session completed)

---

## ✅ DEPLOYMENT COMPLETED

**Status:** Successfully deployed to production
**Date Completed:** December 1, 2025

**Deployed Services:**
- ✅ Backend: `https://rqs8cicg8h.us-west-2.awsapprunner.com`
- ✅ Frontend: `https://jid5jmztei.us-west-2.awsapprunner.com`
- ✅ MCP Atlassian: `https://fa3vbibtmu.us-west-2.awsapprunner.com` (Private/VPC-only)

---

## Critical Lessons Learned (Session Notes)

### 1. Database Version Issue
**Problem:** Terraform tried to downgrade PostgreSQL from 15.12 to 15.7
**Fix:** Updated `rds.tf` to specify `engine_version = "15.12"`
**Lesson:** Always match Terraform config to actual deployed version

### 2. Auto-scaling Name Length Limit
**Problem:** App Runner auto-scaling config name too long (38 chars, max 32)
**Original:** `bond-ai-dev-mcp-atlassian-autoscaling`
**Fixed:** `bond-ai-dev-mcp-atl-as`
**Lesson:** AWS has strict naming limits for some resources

### 3. S3 VPC Endpoint Already Exists
**Problem:** VPC already had S3 endpoint, Terraform tried to recreate it
**Fix:** Commented out the `aws_vpc_endpoint.s3` resource in `vpc-endpoints.tf`
**Lesson:** Check existing VPC infrastructure before deploying

### 4. Docker Keychain Conflicts (macOS)
**Problem:** ECR login credentials caused keychain conflicts
**Error:** `The specified item already exists in the keychain. (-25299)`
**Fix:** `security delete-internet-password -s "019593708315.dkr.ecr.us-west-2.amazonaws.com"`
**Lesson:** macOS Docker credential storage can conflict, clear before ECR operations

### 5. ⚠️ CRITICAL: Multi-Architecture Docker Images
**Problem:** MCP Atlassian image pulled as arm64 on Mac, failed on AWS (needs amd64)
**Error:** `exec /app/.venv/bin/mcp-atlassian: exec format error`
**Root Cause:**
- Local Mac (Apple Silicon) defaults to arm64
- AWS App Runner requires linux/amd64
- `docker pull` without `--platform` flag uses host architecture

**Solution:**
```bash
# Pull specific amd64 version by digest
docker pull ghcr.io/sooperset/mcp-atlassian@sha256:56f4ec862a1b44037afe7e557c0d0c1d3cc72210e56241721f31789e6db84ba7

# Or use platform flag (doesn't always work with multi-platform manifests)
docker pull --platform linux/amd64 ghcr.io/sooperset/mcp-atlassian:latest

# Tag and push to ECR
docker tag ghcr.io/sooperset/mcp-atlassian@sha256:56f4ec... 019593708315.dkr.ecr.us-west-2.amazonaws.com/bond-ai-dev-mcp-atlassian:latest
docker push 019593708315.dkr.ecr.us-west-2.amazonaws.com/bond-ai-dev-mcp-atlassian:latest
```

**Updated Terraform** (`mcp-atlassian.tf` line 211):
```hcl
docker pull --platform linux/amd64 ghcr.io/sooperset/mcp-atlassian:latest
```

**Lesson:** ALWAYS specify `--platform linux/amd64` when mirroring images to AWS from Apple Silicon Macs

### 6. Missing Docker Start Command
**Problem:** Container exited immediately with code 0 (success)
**Root Cause:** MCP Atlassian image requires command arguments: `--transport streamable-http --port 8000`
**Fix:** Added `start_command` to Terraform (`mcp-atlassian.tf` line 331):
```hcl
image_configuration {
  port = "8000"
  start_command = "--transport streamable-http --port 8000"
  runtime_environment_variables = { ... }
}
```
**Lesson:** Container images that expect CMD args need `start_command` in App Runner config

### 7. Circular Dependency: Backend ↔ MCP Atlassian
**Problem:** Backend needs MCP URL, MCP needs Backend URL for OAuth redirect
**Terraform Error:** `Error: Cycle: aws_apprunner_service.backend, aws_apprunner_service.mcp_atlassian`

**Solution:** Two-stage deployment with variables
```hcl
# variables.tf - Add after Stage 1
variable "mcp_atlassian_service_url" {
  description = "MCP Atlassian service URL (set after first deployment)"
  type        = string
  default     = ""
}

variable "backend_service_url" {
  description = "Backend service URL (set after first deployment)"
  type        = string
  default     = ""
}

# backend.tf - Use variables instead of resource references
BOND_MCP_CONFIG = var.mcp_atlassian_service_url != "" ? jsonencode({
  mcpServers = {
    atlassian = {
      url = "${var.mcp_atlassian_service_url}/mcp"
      oauth_config = {
        redirect_uri = "${var.backend_service_url}/connections/atlassian/callback"
      }
    }
  }
}) : "{}"

# agent-space.tfvars - Set after Stage 1 completes
mcp_atlassian_service_url = "https://fa3vbibtmu.us-west-2.awsapprunner.com"
backend_service_url = "https://rqs8cicg8h.us-west-2.awsapprunner.com"
```

**Lesson:** For interdependent services, use variables + multi-stage deployment instead of direct resource references

### 8. VPC Subnet Selection
**Problem:** Terraform was auto-selecting routing subnets instead of internal-green subnets
**Fix:** Added explicit subnet configuration:
```hcl
# variables.tf
variable "app_runner_subnet_ids" {
  description = "List of subnet IDs for App Runner VPC connector"
  type        = list(string)
  default     = []
}

# agent-space.tfvars
app_runner_subnet_ids = ["subnet-0912fc7ffa04c9f5e", "subnet-0a8d3f8ed7df1f24b"]
```
**Lesson:** Don't rely on auto-detection for subnets in complex VPCs with multiple subnet types

---

## Three-Stage Deployment Process (Actual)

### Stage 1: Infrastructure Deployment ✅ COMPLETED

**What Was Deployed:**
- Backend service (with new OAuth features, wildcards for CORS/JWT)
- Frontend service (with Connections UI)
- MCP Atlassian service (private, VPC-only, amd64 image)
- ECR repositories for all three services
- IAM roles and security groups

**Issues Resolved During Stage 1:**
1. Fixed database version (15.7 → 15.12)
2. Shortened auto-scaling config name
3. Commented out duplicate S3 VPC endpoint
4. Cleared Docker keychain conflicts
5. Pulled correct amd64 image for MCP Atlassian
6. Added missing start command for MCP container
7. Fixed VPC subnet selection

**Duration:** ~2 hours (including troubleshooting)

**Outputs Captured:**
```
backend_service_url = "https://rqs8cicg8h.us-west-2.awsapprunner.com"
frontend_service_url = "https://jid5jmztei.us-west-2.awsapprunner.com"
mcp_atlassian_service_url = "https://fa3vbibtmu.us-west-2.awsapprunner.com"
mcp_atlassian_mcp_endpoint = "https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp"
```

### Stage 2: Wire Up MCP Configuration ✅ IN PROGRESS

**Purpose:** Add `BOND_MCP_CONFIG` to backend so it knows about MCP Atlassian service

**Files Modified:**
- `variables.tf` - Added `mcp_atlassian_service_url` and `backend_service_url` variables
- `backend.tf` - Added `BOND_MCP_CONFIG` environment variable using the new variables
- `agent-space.tfvars` - Set the URLs from Stage 1 outputs

**What Gets Updated:**
- Backend service only (environment variables)
- Adds full MCP Atlassian configuration with OAuth settings

**Command:**
```bash
terraform plan -var-file=environments/agent-space.tfvars -out=tfplan
terraform apply tfplan
```

**Expected Duration:** 5-8 minutes (backend restart)

### Stage 3: Security Hardening (PENDING)

**Purpose:** Tighten CORS, JWT, and Okta redirect URIs from wildcards to actual URLs

**Files to Update:**
- `backend.tf` - Update lines 60, 67, 74:
```hcl
OKTA_REDIRECT_URI = "https://rqs8cicg8h.us-west-2.awsapprunner.com/auth/okta/callback"
JWT_REDIRECT_URI = "https://jid5jmztei.us-west-2.awsapprunner.com"
CORS_ALLOWED_ORIGINS = "https://jid5jmztei.us-west-2.awsapprunner.com,http://localhost:5000"
```

**External Updates Required:**
1. Update McAfee Okta app callback URL to match `OKTA_REDIRECT_URI`
2. Update Atlassian OAuth app callback URL (already set in MCP config)

**Command:**
```bash
terraform apply -var-file=environments/agent-space.tfvars
```

**Expected Duration:** 3-5 minutes

---

## Critical Configuration Files

### 1. agent-space.tfvars (After Stage 1)
```hcl
aws_region   = "us-west-2"
environment  = "dev"
project_name = "bond-ai"

existing_vpc_id = "vpc-0f15dee1f11b1bf06"
app_runner_subnet_ids = ["subnet-0912fc7ffa04c9f5e", "subnet-0a8d3f8ed7df1f24b"]

okta_domain      = "https://mcafee.okta.com"
okta_client_id   = "0oaqobsogrUx7ywt55d7"
okta_secret_name = "bond-ai-dev-okta-secret"

mcp_atlassian_enabled = true
mcp_atlassian_oauth_cloud_id = "55de5903-f98d-499f-967a-32673b683dc8"
mcp_atlassian_oauth_client_id = "CSio9UBBGirs72QdZOZKY71Dw057DfT7"
mcp_atlassian_oauth_secret_name = "bond-ai-dev-atlassian-mcp-secret"

# Set after Stage 1 deployment
mcp_atlassian_service_url = "https://fa3vbibtmu.us-west-2.awsapprunner.com"
backend_service_url = "https://rqs8cicg8h.us-west-2.awsapprunner.com"
```

### 2. Key Terraform Changes Made

**rds.tf:**
- Line 19: `engine_version = "15.12"` (was 15.7)

**mcp-atlassian.tf:**
- Line 211: `docker pull --platform linux/amd64 ghcr.io/sooperset/mcp-atlassian:latest`
- Line 302: `auto_scaling_configuration_name = "bond-ai-dev-mcp-atl-as"`
- Line 331: `start_command = "--transport streamable-http --port 8000"`

**vpc-endpoints.tf:**
- Lines 4-14: S3 VPC endpoint commented out (already exists)

**variables.tf:**
- Lines 23-39: Added `app_runner_subnet_ids`, `mcp_atlassian_service_url`, `backend_service_url`

**backend.tf:**
- Lines 76-98: Added `BOND_MCP_CONFIG` with MCP Atlassian configuration

---

## Verification Commands

### Check Service Status
```bash
# Backend
curl https://rqs8cicg8h.us-west-2.awsapprunner.com/health

# MCP Atlassian (private - only accessible from within VPC)
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn arn:aws:apprunner:us-west-2:019593708315:service/bond-ai-dev-mcp-atlassian/485d144f1a2445a590b106ccfb511c5f \
  --region us-west-2 --query 'Service.Status'
```

### Check Logs
```bash
# Backend logs
AWS_PROFILE=agent-space aws logs tail /aws/apprunner/bond-ai-dev-backend/service \
  --region us-west-2 --follow

# MCP Atlassian logs
AWS_PROFILE=agent-space aws logs tail /aws/apprunner/bond-ai-dev-mcp-atlassian/485d144f1a2445a590b106ccfb511c5f/service \
  --region us-west-2 --follow
```

### Test MCP Connection (After Stage 2)
```bash
# Login to frontend
open https://jid5jmztei.us-west-2.awsapprunner.com

# Navigate to Connections screen
# Should see Atlassian card with "Connect" button

# Test API endpoint
TOKEN="<your_jwt_token>"
curl -H "Authorization: Bearer $TOKEN" \
  https://rqs8cicg8h.us-west-2.awsapprunner.com/connections

# Should return:
# {
#   "connections": [{
#     "name": "atlassian",
#     "display_name": "Atlassian",
#     "connected": false,
#     "requires_authorization": true
#   }]
# }
```

---

## Common Issues & Solutions

### Issue: Docker Image Architecture Mismatch
**Symptoms:** Container starts but exits with "exec format error"
**Solution:** Always pull amd64 images for AWS:
```bash
docker pull --platform linux/amd64 <image>
# Or by digest
docker pull <image>@sha256:<amd64-digest>
```

### Issue: Circular Dependency in Terraform
**Symptoms:** `Error: Cycle` when resources reference each other
**Solution:** Use variables instead of direct resource references, deploy in stages

### Issue: Docker Keychain Conflicts
**Symptoms:** `The specified item already exists in the keychain`
**Solution:**
```bash
security delete-internet-password -s "<ecr-registry-url>"
```

### Issue: App Runner Service CREATE_FAILED
**Solution Steps:**
1. Check logs: `aws logs tail /aws/apprunner/<service-name>/service`
2. Delete failed service: `aws apprunner delete-service --service-arn <arn>`
3. Fix issue in Terraform
4. Reapply

---

## Local Development Notes

### Running MCP Atlassian Locally (macOS)
```bash
# Use arm64 version on Apple Silicon Mac
docker run --rm --name mcp-atlassian -p 9001:8000 \
    -v /Users/jcarnahan/certs/combined.pem:/etc/ssl/certs/ca-bundle.crt:ro \
    -e SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt \
    -e REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-bundle.crt \
    --env-file /Users/jcarnahan/projects/bond-ai/mcp-atlassian.env \
    ghcr.io/sooperset/mcp-atlassian:latest \
    --transport streamable-http --port 8000
```

**Note:** Local Mac uses arm64, AWS uses amd64. Docker automatically selects correct architecture for the platform.

---

## Cost Estimate

**Monthly Infrastructure Costs (agent-space):**
- RDS PostgreSQL (db.t3.micro): ~$15-16/month
- Backend App Runner (0.5 vCPU): ~$15-20/month
- Frontend App Runner (0.25 vCPU): ~$15-20/month
- **MCP Atlassian App Runner (0.25 vCPU): ~$15-20/month** ✅ NEW
- NAT Gateway: ~$45/month (shared)
- Storage (S3, ECR): <$3/month
- Secrets Manager: ~$2/month
- Bedrock API (variable): ~$20-50/month

**Total: ~$140-160/month** (increased ~$15-20 with MCP Atlassian)

---

## Next Steps (After Full Deployment)

1. ✅ Stage 1 complete - All services deployed
2. 🔄 Stage 2 in progress - Adding MCP config to backend
3. ⏳ Stage 3 pending - Security hardening (CORS, JWT, Okta)
4. ⏳ Test end-to-end OAuth flows
5. ⏳ Update documentation with final URLs
6. ⏳ Monitor CloudWatch for any errors

---

---

## Session 2: Database Schema & OAuth Integration Issues (December 1, 2025)

### 9. Frontend Auto-Deploy Disabled
**Problem:** Frontend changes not appearing after backend deployment
**Root Cause:** App Runner service had `AutoDeployEnabled: false`
**Fix:** Manually triggered deployment with:
```bash
AWS_PROFILE=agent-space aws apprunner start-deployment \
  --service-arn arn:aws:apprunner:us-west-2:019593708315:service/bond-ai-dev-frontend/...
```
**Lesson:** Check auto-deploy settings when new code doesn't appear after image push

### 10. ⚠️ CRITICAL: ConnectionConfig Table Sync Issues
**Problem:** Foreign key violation - `connection_name='atlassian'` not in `connection_configs` table
**Error:**
```
(psycopg2.errors.ForeignKeyViolation) insert or update on table "connection_oauth_states"
violates foreign key constraint "connection_oauth_states_connection_name_fkey"
DETAIL: Key (connection_name)=(atlassian) is not present in table "connection_configs".
```

**Root Cause Chain:**
1. `BedrockMetadata.create_all()` overrode parent method without calling `super()`
2. This bypassed `Metadata.sync_connection_configs()` which populates the table from `BOND_MCP_CONFIG`
3. Foreign key constraint blocked OAuth state creation

**Initial Fix Attempts:**
1. ✅ Modified `BedrockMetadata.create_all()` to call `super().create_all()`
2. ❌ Failed with: `'BedrockMetadata' object has no attribute 'session'`
3. ✅ Fixed initialization order in `Metadata.__init__` - moved `self.session` creation BEFORE `self.create_all()` call

**Files Changed:**
- `bondable/bond/providers/bedrock/BedrockMetadata.py` - Lines 90-93
- `bondable/bond/providers/metadata.py` - Lines 185-189 (initialization order)

**Lesson:**
- Subclasses must call `super()` to execute parent initialization logic
- Initialization order matters - dependencies must exist before methods that use them
- Foreign key constraints fail fast but provide poor UX when sync fails

### 11. OAuth Redirect URI Mismatch
**Problem:** Atlassian OAuth failed with incorrect redirect URI
**Expected:** `https://rqs8cicg8h.us-west-2.awsapprunner.com/connections/atlassian/callback` (backend)
**Actual:** `https://jid5jmztei.us-west-2.awsapprunner.com/connections/atlassian/callback` (frontend)

**Root Cause:** `ConnectionConfig` model missing `oauth_redirect_uri` column, code fell back to generating from `JWT_REDIRECT_URI` (frontend URL)

**Attempted Fix:**
1. Added `oauth_redirect_uri` column to `ConnectionConfig` model
2. Updated `sync_connection_configs()` to:
   - Populate `oauth_redirect_uri` for new records
   - UPDATE existing records with new OAuth fields
   - Added error handling for schema mismatches

**Files Changed:**
- `bondable/bond/providers/metadata.py`:
  - Line 119: Added `oauth_redirect_uri = Column(String, nullable=True)`
  - Lines 237-256: Added UPDATE logic with try/except for existing records
  - Line 279: Added `oauth_redirect_uri` to new record creation

**Lesson:** OAuth redirect URIs MUST point to backend for token exchange, never frontend

### 12. ⚠️ CRITICAL: SQLAlchemy Schema Migration Gap
**Problem:** Added `oauth_redirect_uri` column to model but column doesn't exist in deployed database
**Error:**
```
(psycopg2.errors.UndefinedColumn) column connection_configs.oauth_redirect_uri does not exist
```

**Impact:**
- Transaction abort on startup
- ALL subsequent database operations fail with `InFailedSqlTransaction`
- **Backend is currently BROKEN in production**

**Why This Happened:**
- SQLAlchemy `Base.metadata.create_all()` creates NEW tables but doesn't ALTER existing tables
- Adding columns to existing models requires explicit migration (ALTER TABLE or Alembic)
- The sync tries to UPDATE existing records with new column, causing error

**Attempted Solutions:**
1. ❌ `run_migrations()` method with ALTER TABLE - User rejected this approach
2. ✅ Added try/except around UPDATE logic with `session.rollback()` - Not yet deployed

**Current State:**
- Changes committed to git but NOT deployed
- Production backend still broken
- Need to either:
  - Deploy with error handling to gracefully skip column updates
  - Manually add column to database
  - Delete and recreate connection_configs table on next deploy

**Lesson:** SQLAlchemy ORM models != automatic database migrations. Need migration strategy for schema changes.

### 13. Architecture Question: Do We Need ConnectionConfig Table?
**Problem:** We're duplicating configuration data and fighting sync issues
**Current Design:**
- `BOND_MCP_CONFIG` environment variable (source of truth)
- `ConnectionConfig` database table (synced copy)
- Foreign key constraint enforces referential integrity
- Sync can fail due to schema mismatches

**Issues:**
- Sync complexity and failure modes
- Schema migration problems (this session)
- Duplication of configuration data
- Foreign key blocks operations when sync fails

**Proposed Alternative:** Remove table, use config only
**Pros:**
- No sync issues - config is always source of truth
- No schema migration problems
- Simpler code
- Configuration changes take effect on restart

**Cons:**
- Lose database referential integrity
- Need runtime validation instead
- Parse JSON on every connection lookup

**Recommended Hybrid Approach:**
1. Remove foreign key constraint (eliminates sync dependency)
2. Keep table for performance/audit (optional optimization)
3. Make sync non-blocking (warn but don't fail startup)
4. Validate connection_name at runtime against BOND_MCP_CONFIG

**Status:** Discussion only, no changes made

---

## Changes Made This Session (To Be Backed Out)

**NOTE:** These changes are being backed out to prepare for upstream merge. They will be reapplied after merging upstream changes.

### bondable/bond/providers/metadata.py
1. **Lines 9-11:** Added imports
   ```python
   import os
   import json
   import uuid
   ```

2. **Line 119:** Added column to ConnectionConfig
   ```python
   oauth_redirect_uri = Column(String, nullable=True)  # OAuth callback URL
   ```

3. **Lines 185-189:** Fixed initialization order
   ```python
   def __init__(self, metadata_db_url):
       self.metadata_db_url = metadata_db_url
       self.engine = create_engine(self.metadata_db_url, echo=False)
       self.session = scoped_session(sessionmaker(bind=self.engine))  # MOVED BEFORE create_all()
       self.create_all()
   ```

4. **Lines 194-198:** Updated create_all() to call sync
   ```python
   def create_all(self):
       Base.metadata.create_all(self.engine)
       # Sync connection configs from environment to database
       self.sync_connection_configs()
   ```

5. **Lines 200-300:** Added sync_connection_configs() method
   - Parses BOND_MCP_CONFIG environment variable
   - Creates ConnectionConfig records for OAuth2 connections
   - Updates existing records with new fields
   - Error handling for schema mismatches

### bondable/bond/providers/bedrock/BedrockMetadata.py
1. **Lines 90-93:** Fixed create_all() override
   ```python
   def create_all(self):
       """Create all tables including Bedrock-specific ones"""
       super().create_all()  # CHANGED: Now calls parent which includes sync
       LOGGER.info("Created all Bedrock metadata tables")
   ```

---

## Current Status & Next Steps

### Immediate Issues (BLOCKING)
1. 🔴 **Backend broken in production** - Transaction abort on startup
2. 🔴 **Schema mismatch** - `oauth_redirect_uri` column doesn't exist in database

### Upcoming Work
1. Back out metadata.py and BedrockMetadata.py changes (prepare for upstream merge)
2. Merge upstream changes from fork
3. Carefully reapply changes with proper migration strategy
4. Consider removing foreign key constraint for more resilient design
5. Test complete Atlassian OAuth flow end-to-end
6. Update McAfee Okta app with backend callback URL

### Files with Uncommitted Changes
- `bondable/bond/providers/metadata.py` - Has sync logic and error handling
- `bondable/bond/providers/bedrock/BedrockMetadata.py` - Has super() call fix

### Deployment State
- Backend: `https://rqs8cicg8h.us-west-2.awsapprunner.com` (BROKEN - transaction abort)
- Frontend: `https://jid5jmztei.us-west-2.awsapprunner.com` (Working)
- MCP Atlassian: `https://fa3vbibtmu.us-west-2.awsapprunner.com` (Working, VPC-only)

---

## Archive Notes

---

## Session 3: Upstream Merge & ConnectionConfig Table Removal (December 1, 2025)

### 14. Successful Upstream Merge - ConnectionConfig Table Elimination
**Problem:** Need to merge upstream changes that removed ConnectionConfig table redundancy
**Upstream Changes (commit 5e584ef):**
- Removed `ConnectionConfig` database table entirely
- Removed foreign key constraints from `UserConnectionToken.connection_name` and `ConnectionOAuthState.connection_name`
- Changed to use only `BOND_MCP_CONFIG` environment variable as source of truth
- Added runtime validation instead of database constraints
- Improved orphaned token handling in MCPTokenCache

**Merge Process:**
1. Stashed local deployment customizations (`deployment/` and `tests/`)
2. Created merge branch: `merge-upstream-5e584ef`
3. Merged upstream/main (clean merge, no conflicts)
4. Restored stashed deployment configs (including critical `BOND_MCP_CONFIG` in backend.tf)
5. Verified all deployment customizations preserved

**Key Issue During Merge:**
- Initial merge lost `BOND_MCP_CONFIG` section from `backend.tf`
- Discovered when reviewing backend.tf - missing lines 69-89 with MCP Atlassian config
- Fixed by restoring stash with `git stash pop`
- **Lesson:** Always verify critical config sections after merge, especially when stashing/unstashing

**Files Changed by Upstream:**
- `bondable/bond/auth/mcp_token_cache.py` - Added orphaned token logging
- `bondable/bond/providers/metadata.py` - Removed ConnectionConfig model, removed FK constraints
- `bondable/rest/routers/connections.py` - Simplified to use BOND_MCP_CONFIG directly

**Lesson:** This is the architectural improvement we discussed in Session 2! Upstream made the right choice to eliminate database sync complexity.

### 15. Database Migration Challenge - Foreign Key Constraints
**Problem:** Deployed database still has legacy FK constraints that need removal
**Root Cause:**
- SQLAlchemy only updates models, not deployed database schema
- Existing database has:
  - `user_connection_tokens.connection_name` → `connection_configs.name` (FK)
  - `connection_oauth_states.connection_name` → `connection_configs.name` (FK)
  - `connection_configs` table still exists

**Solution Implemented:** Admin API endpoint for table recreation
Created `POST /admin/recreate-table/{table_name}` endpoint:
- Admin-only (restricted to `john_carnahan@mcafee.com`)
- Drops specified table with CASCADE (removes dependent FK constraints)
- Calls `metadata.create_all()` to recreate with new schema
- Idempotent and safe

**Supporting Script:** `scripts/recreate_table.py`
```bash
# Get JWT token from frontend first (DevTools > Application > Local Storage)
python scripts/recreate_table.py connection_configs \
  --url https://rqs8cicg8h.us-west-2.awsapprunner.com \
  --token YOUR_JWT_TOKEN
```

**Migration Steps:**
1. Login to frontend: https://jid5jmztei.us-west-2.awsapprunner.com
2. Get JWT token from browser DevTools
3. Run script to drop `connection_configs` table (CASCADE removes FK constraints)
4. Backend automatically works with new schema

**File:** `bondable/rest/routers/auth.py:277-366`

**Lesson:** Admin endpoints following existing `delete_user_by_email` pattern provide safe database operations without needing direct DB access.

### 16. JWT Token Authentication for Deployed Environment
**Problem:** Script couldn't authenticate with deployed backend
**Error:** `401 Unauthorized - Could not validate credentials`
**Root Cause:** Script was generating JWT with local secret key, but deployed backend has different secret

**Solution:** Modified script to accept JWT token as parameter
- For local dev: Auto-generates token from local config
- For deployed: Requires real JWT token from authenticated session
- Added clear instructions for getting token from browser DevTools

**Lesson:** Deployed backends have different JWT secrets - always use real authenticated tokens for deployed environments.

### 17. Atlassian OAuth App Access Restriction
**Problem:** After successful deployment, Atlassian OAuth returns access denied
**Error Message:** "You don't have access to this app. This application is in development - only the owner of this application may grant it access to their account."

**Authorization URL Parameters Observed:**
```
https://api.atlassian.com/oauth2/authorize/server/consent?
  client_id=CSio9UBBGirs72QdZOZKY71Dw057DfT7
  redirect_uri=https://rqs8cicg8h.us-west-2.awsapprunner.com/connections/atlassian/callback
  state=bkp-Ldn-zKCyvKJ40x2I01Z_f3Og1NAhpHGgcj3W_Uo
  code_challenge=C7q27EuFZoTuT2BrJntE3caybmClP6eO3iN6LlxqdGw
  code_challenge_method=S256
  scope=offline_access+read:confluence-space.summary+read:jira-user+read:jira-work+write:confluence-content+write:jira-work
```

**Backend Logs:** ✅ All successful, no errors
- Authorization URL generated correctly
- PKCE challenge created properly
- Callback URL configured correctly
- Connection endpoint working

**Root Cause:** Atlassian OAuth app still in "Development" mode
**Solutions:**
1. **Make app public** (Recommended): Change app from Development to Production in Atlassian Developer Console
2. **Add test user**: Add `john_carnahan@mcafee.com` as authorized test user
3. **Use owner account**: Login with the account that created the OAuth app

**Status:** Pending Atlassian app configuration change

**Lesson:** OAuth apps in development mode restrict access to owner only. For production use, apps must be published or distributed.

---

## Current State After Session 3

### Successfully Completed
✅ Merged upstream changes (5e584ef) that removed ConnectionConfig table redundancy
✅ Preserved all deployment customizations (backend.tf, mcp-atlassian.tf, etc.)
✅ Created admin endpoint for database table recreation
✅ Created script to call admin endpoint with authentication
✅ Deployed updated backend with new changes
✅ OAuth authorization flow working correctly

### Pending Items
⏳ **Drop connection_configs table** - Use recreate_table.py script with JWT token
⏳ **Configure Atlassian OAuth app** - Change from Development to Production mode
⏳ **Test complete OAuth flow** - After Atlassian app configuration
⏳ **Commit and merge to main** - Finalize the upstream merge locally

### Deployment Status
- **Backend:** `https://rqs8cicg8h.us-west-2.awsapprunner.com` (Running with upstream changes)
- **Frontend:** `https://jid5jmztei.us-west-2.awsapprunner.com` (Working)
- **MCP Atlassian:** `https://fa3vbibtmu.us-west-2.awsapprunner.com` (Working, VPC-only)

### Git State
- **Branch:** `merge-upstream-5e584ef` (merge completed, not yet committed)
- **Uncommitted Changes:**
  - Deployment configs restored (10 modified files in `deployment/`)
  - Test files restored (2 modified files in `tests/`)
  - New admin endpoint added (`bondable/rest/routers/auth.py`)
  - New script added (`scripts/recreate_table.py`)
  - Upstream code changes merged (3 files from upstream)

---

## Key Files Modified This Session

### New Files
- `scripts/recreate_table.py` - Admin script for table recreation with JWT auth

### Modified Files
- `bondable/rest/routers/auth.py` - Added `POST /admin/recreate-table/{table_name}` endpoint
- `bondable/bond/auth/mcp_token_cache.py` - Upstream: Better orphaned token handling
- `bondable/bond/providers/metadata.py` - Upstream: Removed ConnectionConfig table
- `bondable/rest/routers/connections.py` - Upstream: Use BOND_MCP_CONFIG directly
- `deployment/terraform-existing-vpc/backend.tf` - Preserved BOND_MCP_CONFIG
- `deployment/terraform-existing-vpc/mcp-atlassian.tf` - Preserved customizations
- Other deployment files (data-sources.tf, outputs.tf, rds.tf, variables.tf, vpc-endpoints.tf)

---

## Commands Reference

### Run Table Recreation Script
```bash
# Get JWT token first from browser DevTools after login
python scripts/recreate_table.py connection_configs \
  --url https://rqs8cicg8h.us-west-2.awsapprunner.com \
  --token YOUR_JWT_TOKEN
```

### Check Backend Logs
```bash
AWS_PROFILE=agent-space aws logs tail /aws/apprunner/bond-ai-dev-backend/service \
  --region us-west-2 --follow
```

### Deploy Backend (if needed)
```bash
cd deployment/terraform-existing-vpc
terraform plan -var-file=environments/agent-space.tfvars
terraform apply -var-file=environments/agent-space.tfvars
```

---

## Archive Notes

This deployment plan was created during active deployment sessions on December 1, 2025. It captures real issues encountered and solutions applied across three sessions.

**Session 1 Key Takeaway:** Multi-stage deployment with proper architecture handling (arm64 vs amd64) is critical when deploying containerized services from Apple Silicon Macs to AWS.

**Session 2 Key Takeaway:** SQLAlchemy ORM models don't automatically migrate database schemas. Adding columns to existing models requires explicit migration strategy (ALTER TABLE, Alembic, or recreation). Foreign key constraints can make systems brittle - consider removing them for more resilient design.

**Session 3 Key Takeaway:** Upstream made the architectural improvement we discussed - removing ConnectionConfig table entirely and using environment config as single source of truth. Admin API endpoints provide safe database operations without direct DB access. OAuth apps in development mode restrict access and must be published for production use.
