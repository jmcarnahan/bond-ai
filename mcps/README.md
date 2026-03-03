# Bond AI MCP Servers

This directory contains MCP (Model Context Protocol) servers that extend Bond AI agents with external service integrations. Each MCP server runs as a standalone service and communicates with the Bond AI backend via streamable HTTP transport.

## Available MCPs

| MCP | Directory | Port | Description |
|-----|-----------|------|-------------|
| **Atlassian** | [`atlassian/`](atlassian/) | 9001 | Jira and Confluence via Atlassian REST API |
| **GitHub** | [`github/`](github/) | 5558 | Repositories, issues, PRs, and code via GitHub REST API |
| **Microsoft** | [`microsoft/`](microsoft/) | 5557 | Email, Teams, OneDrive, and SharePoint via Microsoft Graph API |

## Architecture

```
Bond AI Frontend (Flutter)
    |
    v
Bond AI Backend (FastAPI)
    |-- Manages OAuth flows and token storage per user
    |-- Routes tool calls to the correct MCP server
    |-- Passes user's service token as Authorization: Bearer header
    |
    +---> Atlassian MCP (port 9001)  ---> Atlassian REST API
    +---> GitHub MCP (port 5558)     ---> GitHub REST API
    +---> Microsoft MCP (port 5557)  ---> Microsoft Graph API
```

Each MCP server:
- Receives pre-authenticated Bearer tokens from the Bond AI backend
- Does **not** manage OAuth or store tokens
- Exposes tools via the MCP protocol (FastMCP)
- Runs as a standalone process (locally or as an App Runner service in AWS)

## Configuration

MCPs are configured in the `BOND_MCP_CONFIG` environment variable in the Bond AI backend's `.env` file. Each entry specifies the MCP URL, transport, auth type, and OAuth config:

```json
{
    "mcpServers": {
        "microsoft": {
            "url": "http://localhost:5557/mcp",
            "auth_type": "oauth2",
            "transport": "streamable-http",
            "display_name": "Microsoft",
            "description": "Connect to Microsoft email, Teams, OneDrive, and SharePoint",
            "oauth_config": {
                "provider": "microsoft",
                "client_id": "<CLIENT_ID>",
                "client_secret": "<CLIENT_SECRET>",
                "authorize_url": "https://login.microsoftonline.com/<AUTHORITY>/oauth2/v2.0/authorize",
                "token_url": "https://login.microsoftonline.com/<AUTHORITY>/oauth2/v2.0/token",
                "scopes": "Mail.Read Mail.ReadWrite Mail.Send User.Read offline_access Files.Read.All Sites.Read.All",
                "redirect_uri": "http://localhost:8000/connections/microsoft/callback"
            }
        }
    }
}
```

## Local Development

Each MCP is an independent Poetry project. To run one locally:

```bash
cd mcps/<mcp_name>
poetry install
poetry run pytest tests/ -v                   # Run tests
poetry run fastmcp run <server>.py --transport streamable-http --port <port>
```

## Production Deployment

Each MCP has its own `deployment/` directory with a standalone Terraform module that deploys it as an AWS App Runner service. Services can be deployed as **public** (default) or **private** (VPC-only, requires the main deployment's `apprunner.requests` VPC endpoint).

```bash
cd mcps/<mcp_name>/deployment
terraform init

# Public deployment (default)
terraform apply -var-file=<mcp_name>.tfvars

# Private deployment (VPC-only access)
# Set mcp_<name>_is_private = true in your tfvars
terraform apply -var-file=<mcp_name>.tfvars
```

**Important**: The Dockerfile CMD must include `--host 0.0.0.0` to bind to all interfaces. Without this, App Runner health checks will fail because FastMCP defaults to binding on `127.0.0.1` (localhost only).

## Adding a New MCP

1. Create a new directory under `mcps/` (e.g., `mcps/salesforce/`)
2. Initialize a Poetry project with `fastmcp` and `httpx` dependencies
3. Create the MCP server module (follow `microsoft/ms_graph_mcp.py` as a template)
4. Add tests using `respx` for HTTP mocking
5. Add a `deployment/` directory with Terraform (copy from `microsoft/deployment/`)
6. Add the MCP entry to `BOND_MCP_CONFIG` in the backend `.env`
7. Update this README with the new MCP entry
