#!/bin/bash

# Replace with your actual Railway URL
TOOL_URL="https://your-app-name.up.railway.app/mcp"

echo "Testing MCP endpoint: $TOOL_URL"
echo "---"

# Test initialize method
echo "Testing initialize method..."
curl -X POST "$TOOL_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "1.0.0",
      "capabilities": {}
    },
    "id": 1
  }' | python -m json.tool

echo -e "\n---"

# Test list tools
echo "Testing tools/list method..."
curl -X POST "$TOOL_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 2
  }' | python -m json.tool