from fastmcp import FastMCP

mcp = FastMCP("My MCP Server")

@mcp.tool()
def greet(name: str) -> str:
    return f"Hello, {name}!"

@mcp.tool()
def current_time() -> str:
    from datetime import datetime
    return datetime.now().isoformat()

if __name__ == "__main__":
    mcp.run()
