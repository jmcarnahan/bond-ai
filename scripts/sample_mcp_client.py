import asyncio
from fastmcp import Client

async def example():
    async with Client("http://127.0.0.1:5555/mcp") as client:

        tool_list = await client.list_tools()
        print(f"Available tools: {tool_list}")
        response = await client.call_tool("greet", {"name": "World"})
        print(f"Response from greet: {response}")

        print()
        resource_list = await client.list_resources()
        print(f"Available resources: {resource_list}")
        resource_response = await client.read_resource("example://resource")
        print(f"Response from resource: {resource_response}")



if __name__ == "__main__":
    asyncio.run(example())


