# Atlassian MCP Server for Bond AI

Custom MCP server providing Jira and Confluence tools for Bond AI. Built following the same patterns as the GitHub and Microsoft Graph MCP servers.

## Quick Start

```bash
# Install dependencies
cd mcps/atlassian
poetry install

# Run tests
poetry run pytest tests/ -v

# Start MCP server locally
fastmcp run atlassian_mcp.py --transport streamable-http --port 9001
```

## Tools (14 total)

### Jira (8 tools)

| Tool | Description |
|------|-------------|
| `list_projects` | List accessible Jira projects (name, key, type) |
| `search_issues` | Search with JQL — the workhorse tool |
| `count_issues` | Count issues matching JQL without fetching data |
| `get_issue` | Full issue details including comments |
| `create_issue` | Create issue with type, description, assignee, priority, labels |
| `update_issue` | Update summary, description, assignee, priority, labels |
| `add_issue_comment` | Add comment to an issue |
| `transition_issue` | Move issue through workflow (e.g., "In Progress", "Done") |

### Confluence (5 tools)

| Tool | Description |
|------|-------------|
| `list_spaces` | List accessible spaces |
| `search_content` | Search pages/blogs using CQL |
| `get_page` | Get page with body content |
| `create_page` | Create page in a space |
| `update_page` | Update page title/body |

### User (1 tool)

| Tool | Description |
|------|-------------|
| `get_myself` | Current user info (accountId, displayName, email) |

## Atlassian OAuth App Setup

### 1. Create OAuth 2.0 App

1. Go to [developer.atlassian.com/console/myapps](https://developer.atlassian.com/console/myapps)
2. Create a new OAuth 2.0 integration
3. Add scopes:
   - `read:jira-work` — Read Jira issues and projects
   - `write:jira-work` — Create/update Jira issues
   - `read:confluence-content.all` — Read Confluence pages
   - `write:confluence-content` — Create/update Confluence pages
   - `read:me` — Read user profile
4. Set callback URL to your Bond AI backend OAuth callback
5. Note your Client ID and Client Secret

### 2. Find Your Cloud ID

```bash
# Replace YOUR-DOMAIN with your Atlassian domain
curl -s https://YOUR-DOMAIN.atlassian.net/_edge/tenant_info | jq .cloudId
```

## CLI Usage

The CLI uses environment variables for authentication (no OAuth flow):

```bash
export ATLASSIAN_ACCESS_TOKEN=your_token
export ATLASSIAN_CLOUD_ID=your_cloud_id

# Jira
atlassian-cli jira projects
atlassian-cli jira search "project = PROJ AND status = Open"
atlassian-cli jira count "project = PROJ AND type = Bug"
atlassian-cli jira get PROJ-123
atlassian-cli jira create PROJ "Fix login bug" --type Bug --priority High
atlassian-cli jira comment PROJ-123 "Working on this"
atlassian-cli jira transition PROJ-123 "In Progress"

# Confluence
atlassian-cli confluence spaces
atlassian-cli confluence search 'type = page AND text ~ "release notes"'
atlassian-cli confluence get 12345

# User
atlassian-cli user me
```

## Bond AI Integration

Add to `BOND_MCP_CONFIG` in `.env`:

```json
{
  "mcpServers": {
    "atlassian_v2": {
      "url": "https://YOUR-MCP-URL.awsapprunner.com/mcp",
      "transport": "streamable-http",
      "auth_type": "oauth2",
      "oauth2_provider": "atlassian",
      "cloud_id": "YOUR-CLOUD-ID"
    }
  }
}
```

The Bond AI backend will:
1. Pass the user's OAuth token as `Authorization: Bearer {token}`
2. Pass the cloud ID as `X-Atlassian-Cloud-Id: {cloud_id}`

## Architecture

```
User Browser
    → Bond AI Frontend
    → Bond AI Backend (OAuth + Token Storage)
    → Atlassian MCP Server (this project)
    → Atlassian REST APIs (api.atlassian.com)
```

The MCP server is stateless — it receives the OAuth token and cloud ID via HTTP headers on every request.

## API Details

### Dual Base URLs

Unlike GitHub (1 base URL), Atlassian requires two:
- **Jira**: `https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3`
- **Confluence**: `https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/api/v2`

### Jira Search: New Endpoints

Uses the new (non-deprecated) endpoints:
- `GET /rest/api/3/search/jql` — token-based pagination
- `POST /rest/api/3/search/approximate-count` — efficient counting

### ADF (Atlassian Document Format)

Jira v3 requires descriptions and comments in ADF. Plain text is auto-wrapped:
```json
{"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "..."}]}]}
```

## Deployment (AWS)

```bash
cd mcps/atlassian/deployment
terraform init
terraform plan -var-file=../../deployment/terraform-existing-vpc/environments/dev.tfvars
terraform apply -var-file=../../deployment/terraform-existing-vpc/environments/dev.tfvars
```

Creates:
- ECR repository for Docker image
- App Runner service with VPC egress
- IAM roles for ECR access and CloudWatch logs
- Auto-scaling (min 1, max 2 instances)

## Troubleshooting

### "Authorization required" error
The MCP server isn't receiving the OAuth token. Check that Bond AI backend is passing the `Authorization: Bearer` header.

### "Cloud ID required" error
The `X-Atlassian-Cloud-Id` header is missing. Ensure `cloud_id` is configured in the MCP server config.

### "Rate limited by Atlassian"
Atlassian enforces rate limits. The error message includes the retry-after time. Wait and try again.

### Transition fails with "not available"
The error will list available transitions. Use one of those names (case-insensitive).

### JQL syntax errors
The error message from Jira will include the specific JQL parsing error. Check [Jira JQL documentation](https://support.atlassian.com/jira-service-management-cloud/docs/use-advanced-search-with-jira-query-language-jql/).
