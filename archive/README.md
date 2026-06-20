# archive/

Code under this directory was previously part of bond-ai but has been extracted
to a separate repository: https://github.com/<owner>/bond-mcps (locally at
`/Users/jcarnahan/projects/bond-mcps/`).

## What's here

- `archive/mcps/` — the local atlassian / github / microsoft MCP servers and
  the `shared_auth/` OAuth proxy. The canonical versions now live in
  `bond-mcps/mcps/` and `bond-mcps/auth/`.
- `archive/tests/` — integration tests that exercised those local MCP servers
  (test_atlassian_mcp.py, test_mcp_atlassian_e2e.py, test_mcp_atlassian_tools.py,
  test_mcp_running_server.py, test_mcp_ssl_fix.py, test_mcp_tools_fetching.py).
  Their coverage belongs in bond-mcps; archived here pending deletion.

## Why archive instead of delete

Nothing in `bondable/` imports any of this code — bond-ai talks to MCP servers
over HTTP via `BOND_MCP_CONFIG` only. The archive step is a soak period: if we
discover something still references this code, we restore from here rather than
from git history. A follow-up PR will delete `archive/` once we're confident.

Archived: 2026-06-19.
