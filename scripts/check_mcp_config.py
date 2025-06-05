#!/usr/bin/env python3
"""
Quick script to check MCP configuration
"""

import os
import json
from bondable.bond.config import Config

def main():
    print("Checking MCP Configuration...")
    print("=" * 50)
    
    # Check environment variable
    bond_mcp_config = os.getenv('BOND_MCP_CONFIG')
    print(f"BOND_MCP_CONFIG env var: {bond_mcp_config}")
    
    # Check config class
    try:
        config = Config.config()
        mcp_config = config.get_mcp_config()
        print(f"\nParsed MCP config:")
        print(json.dumps(mcp_config, indent=2))
        
        servers = mcp_config.get("mcpServers", {})
        print(f"\nFound {len(servers)} servers:")
        for name, server_config in servers.items():
            print(f"  - {name}: {server_config}")
    except Exception as e:
        print(f"Error loading config: {e}")

if __name__ == "__main__":
    main()