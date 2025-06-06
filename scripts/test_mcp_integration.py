from bondable.bond.mcp_client import MCPClient

async def test_mcp_integration():
    # Test connection and list tools
    print("Testing connection and listing tools...")
    async with await MCPClient.get_client() as client:
        tools = await client.list_tools()
        print(f"   ✓ Connected successfully")
        print(f"   ✓ Found {len(tools)} tools:")
        for tool in tools:
            print(f"     - {tool}")

    print("\n" + "=" * 50)
    print("✅ MCP Integration test completed successfully!")
    
test_mcp_integration()
