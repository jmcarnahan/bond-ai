# MCP Atlassian Server Deployment

This document describes how to deploy the MCP Atlassian server to AWS App Runner using Terraform.

## Overview

The MCP Atlassian server provides Model Context Protocol (MCP) access to Jira and Confluence APIs. It is deployed as a **private App Runner service** accessible only from within your VPC, with the backend service proxying requests.

### Architecture

```
                    Internet
                        │
                        ▼
    ┌───────────────────────────────────────┐
    │  Backend App Runner (Public)          │
    │  - Handles OAuth callbacks            │
    │  - Proxies MCP requests               │
    │  - /connections/atlassian/callback    │
    └───────────────────────────────────────┘
                        │
                        ▼ (VPC internal)
    ┌───────────────────────────────────────┐
    │  MCP Atlassian App Runner (Private)   │
    │  - Port 8000                          │
    │  - /mcp endpoint                      │
    │  - VPC egress only                    │
    └───────────────────────────────────────┘
                        │
                        ▼
    ┌───────────────────────────────────────┐
    │  Shared VPC Connector                 │
    │  - Enables VPC networking             │
    │  - Reused from backend service        │
    └───────────────────────────────────────┘
```

## Prerequisites

### 1. Atlassian OAuth App

Create an OAuth 2.0 app in the [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/):

1. Go to **Create** → **OAuth 2.0 integration**
2. Name your app (e.g., "Bond AI MCP")
3. Configure permissions:
   - **Jira API**: `read:jira-user`, `read:jira-work`, `write:jira-work`
   - **Confluence API**: `read:confluence-space.summary`, `write:confluence-content`
4. Add `offline_access` scope for refresh tokens
5. Set the callback URL to your backend: `https://<backend-url>/connections/atlassian/callback`
6. Note the **Client ID** and **Client Secret**

### 2. Find Your Atlassian Cloud ID

Your Cloud ID can be found by:
- Visiting `https://<your-domain>.atlassian.net/_edge/tenant_info`
- Or from the Atlassian Admin console

Example: `ec8ace41-7cde-4e66-aaf1-6fca83a00c53`

### 3. Store OAuth Secret in AWS Secrets Manager

```bash
aws secretsmanager create-secret \
  --name bond-ai-dev-mcp-atlassian-oauth \
  --secret-string '{"client_secret":"YOUR_ATLASSIAN_OAUTH_CLIENT_SECRET"}' \
  --region us-east-1
```

### 4. Docker

Docker must be running on the machine executing Terraform, as the deployment mirrors the image from GitHub Container Registry to ECR.

## Configuration

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `mcp_atlassian_enabled` | Enable deployment | `true` |
| `mcp_atlassian_oauth_cloud_id` | Atlassian Cloud ID | `"ec8ace41-7cde-..."` |
| `mcp_atlassian_oauth_client_id` | OAuth app client ID | `"KHXrX7yQ..."` |
| `mcp_atlassian_oauth_secret_name` | Secrets Manager secret name | `"bond-ai-dev-mcp-atlassian-oauth"` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `mcp_atlassian_oauth_scopes` | `"read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access"` | OAuth scopes |
| `mcp_atlassian_logging_level` | `"INFO"` | Logging level |
| `mcp_atlassian_cpu` | `"0.25 vCPU"` | CPU allocation |
| `mcp_atlassian_memory` | `"0.5 GB"` | Memory allocation |

### Example tfvars

Create a file `environments/mcp-atlassian.tfvars`:

```hcl
mcp_atlassian_enabled           = true
mcp_atlassian_oauth_cloud_id    = "ec8ace41-7cde-4e66-aaf1-6fca83a00c53"
mcp_atlassian_oauth_client_id   = "KHXrX7yQOU0dahJswA63C8drUeK9EtWJ"
mcp_atlassian_oauth_secret_name = "bond-ai-dev-mcp-atlassian-oauth"
```

## Deployment

```bash
cd deployment/terraform-existing-vpc

# Validate configuration
terraform validate

# Plan deployment
terraform plan \
  -var-file=environments/example.tfvars \
  -var-file=environments/mcp-atlassian.tfvars

# Apply
terraform apply \
  -var-file=environments/example.tfvars \
  -var-file=environments/mcp-atlassian.tfvars
```

## Outputs

After deployment, Terraform provides these outputs:

| Output | Description |
|--------|-------------|
| `mcp_atlassian_service_url` | App Runner service URL (VPC-only) |
| `mcp_atlassian_mcp_endpoint` | Full MCP endpoint URL |
| `mcp_atlassian_service_arn` | Service ARN |
| `mcp_atlassian_ecr_repository` | ECR repository URL |

## How It Works

### Image Mirroring

Since AWS App Runner doesn't support pulling images from GitHub Container Registry (`ghcr.io`), the deployment:

1. Creates an ECR repository
2. Pulls `ghcr.io/sooperset/mcp-atlassian:latest`
3. Tags and pushes to ECR
4. App Runner pulls from ECR

### Environment Variables

The following environment variables are injected into the App Runner service:

| Variable | Source |
|----------|--------|
| `JIRA_URL` | Computed: `https://api.atlassian.com/ex/jira/{cloud_id}` |
| `CONFLUENCE_URL` | Computed: `https://api.atlassian.com/ex/confluence/{cloud_id}` |
| `ATLASSIAN_OAUTH_CLIENT_ID` | From tfvars |
| `ATLASSIAN_OAUTH_CLIENT_SECRET` | From Secrets Manager |
| `ATLASSIAN_OAUTH_REDIRECT_URI` | Computed: `https://{backend_url}/connections/atlassian/callback` |
| `ATLASSIAN_OAUTH_SCOPE` | From tfvars (with default) |
| `ATLASSIAN_OAUTH_CLOUD_ID` | From tfvars |
| `MCP_LOGGING_LEVEL` | From tfvars (default: INFO) |

### Network Configuration

- **Ingress**: Private (`is_publicly_accessible = false`)
- **Egress**: Through VPC connector (shared with backend)
- **Health Check**: TCP on port 8000

## Resources Created

When `mcp_atlassian_enabled = true`, Terraform creates:

| Resource | Name Pattern |
|----------|--------------|
| ECR Repository | `{project}-{env}-mcp-atlassian` |
| ECR Lifecycle Policy | Keeps last 5 images |
| IAM Role | `{project}-{env}-mcp-atlassian-role` |
| IAM Policy | Secrets Manager + CloudWatch access |
| Auto Scaling Config | Min: 1, Max: 2 |
| App Runner Service | `{project}-{env}-mcp-atlassian` |

### Reused Resources

These existing resources are reused (no modifications):

- VPC Connector (`aws_apprunner_vpc_connector.backend`)
- ECR Access Role (`aws_iam_role.app_runner_ecr_access`)
- Security Group (`aws_security_group.app_runner`)

## Troubleshooting

### Image Mirror Failed

If the image mirroring fails:

```bash
# Verify Docker is running
docker info

# Manually test the pull
docker pull ghcr.io/sooperset/mcp-atlassian:latest
```

### Service Not Starting

Check App Runner logs:

```bash
aws apprunner list-services --region us-east-1

# Get service logs
aws logs tail /aws/apprunner/<service-name>/service --region us-east-1 --follow
```

### OAuth Errors

1. Verify the secret exists and contains valid JSON:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id bond-ai-dev-mcp-atlassian-oauth \
     --region us-east-1
   ```

2. Check the OAuth redirect URI matches your Atlassian app configuration

### VPC Connectivity Issues

The service uses the same VPC connector as the backend. If connectivity issues occur:

1. Check security group rules
2. Verify NAT Gateway is configured for outbound internet access
3. Check VPC endpoint configurations

### SSL Certificate Verification Errors (Local Development)

If you encounter SSL certificate verification errors when running the MCP Atlassian container locally:

```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
```

This typically occurs on corporate networks with SSL-intercepting proxies. There are two solutions:

#### Solution 1: Quick Fix (Development Only - Less Secure)

Update your `mcp-atlassian.env` file:

```bash
JIRA_SSL_VERIFY=false
CONFLUENCE_SSL_VERIFY=false
```

Then run the container:
```bash
docker run --rm --name mcp-atlassian -p 9001:8000 \
  --env-file mcp-atlassian.env \
  ghcr.io/sooperset/mcp-atlassian:latest \
  --transport streamable-http --port 8000
```

**Warning**: Only use this for local development. Never disable SSL verification in production.

#### Solution 2: Secure Fix (Recommended - Mount Certificates)

Mount your system's CA certificates into the container:

```bash
docker run --rm --name mcp-atlassian -p 9001:8000 \
  -v /path/to/your/ca-bundle.crt:/etc/ssl/certs/ca-bundle.crt:ro \
  -e SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt \
  -e REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-bundle.crt \
  --env-file mcp-atlassian.env \
  ghcr.io/sooperset/mcp-atlassian:latest \
  --transport streamable-http --port 8000
```

Common certificate paths:
- **macOS**: `/etc/ssl/cert.pem` or `/usr/local/etc/openssl/cert.pem`
- **Linux**: `/etc/ssl/certs/ca-certificates.crt`
- **Corporate**: Check with your IT department for corporate CA bundle location

With this approach, SSL verification remains enabled (more secure) and the container can properly verify certificates using your corporate CA bundle.

#### Production (AWS App Runner)

SSL certificate verification should work automatically in AWS App Runner without any configuration, as AWS provides trusted CA certificates in the container environment. The Terraform configuration explicitly sets:

```hcl
JIRA_SSL_VERIFY       = "true"
CONFLUENCE_SSL_VERIFY = "true"
```

If you encounter SSL errors in AWS, check:
1. VPC endpoint configurations
2. NAT Gateway has internet access
3. Security group rules allow outbound HTTPS (port 443)

## Disabling/Removing

### Disable (keep resources for later)

Set `mcp_atlassian_enabled = false` in your tfvars:

```hcl
mcp_atlassian_enabled = false
```

Then apply:

```bash
terraform apply -var-file=environments/example.tfvars \
                -var-file=environments/mcp-atlassian.tfvars
```

### Remove Completely

Delete the tfvars file and apply, or remove the `.tf` file:

```bash
rm environments/mcp-atlassian.tfvars
terraform apply -var-file=environments/example.tfvars
```

## Security Considerations

- OAuth client secret stored in AWS Secrets Manager (never in tfvars)
- Service is private (not accessible from internet)
- IAM role follows least privilege (only Secrets Manager and CloudWatch access)
- ECR image scanning enabled
- All traffic within VPC uses security groups

## Related Files

- `mcp-atlassian.tf` - Main Terraform configuration
- `environments/mcp-atlassian.example.tfvars` - Example configuration
- `backend.tf` - Backend service (handles OAuth callbacks)
