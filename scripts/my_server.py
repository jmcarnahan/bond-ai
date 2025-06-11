from fastmcp import FastMCP

mcp = FastMCP("My MCP Server")

@mcp.tool()
def greet(name: str) -> str:
    print(f"Called: Greet tool with name '{name}'")
    return f"Hello, {name}!"

@mcp.tool()
def current_time() -> str:
    from datetime import datetime
    curr_time = datetime.now().isoformat()
    print(f"Called: Current time is {curr_time}")
    return curr_time

@mcp.resource(uri="example://resource", name="ExampleResource")
def example_resource() -> str:
    print("Called: Accessing example resource")
    return "This is an example resource content."


if __name__ == "__main__":
    mcp.run()
