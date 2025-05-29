import asyncio
from fastmcp import Client

async def example():
    async with Client("http://127.0.0.1:5555/mcp") as client:
        tool_list = await client.list_tools()
        print(f"Available tools: {tool_list}")
        response = await client.call_tool("greet", {"name": "World"})
        print(f"Response from greet: {response}")

if __name__ == "__main__":
    asyncio.run(example())
