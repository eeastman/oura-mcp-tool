#!/bin/bash

# Replace with your Railway URL
RAILWAY_URL="https://YOUR-APP-NAME.up.railway.app"

echo "Testing your Oura MCP tool..."
curl -X POST "$RAILWAY_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}' \
  | python -m json.tool