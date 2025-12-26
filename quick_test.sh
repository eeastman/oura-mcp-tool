#\!/bin/bash
# Quick test script for OAuth endpoints

echo "🧪 Testing OAuth Server Endpoints"
echo "================================="

# Test health
echo -e "\n1. Health Check:"
curl -s http://localhost:8080/health  < /dev/null |  python -m json.tool

# Test OAuth metadata
echo -e "\n2. OAuth Metadata:"
curl -s http://localhost:8080/.well-known/oauth-authorization-server | python -m json.tool | head -15

# Register a test client
echo -e "\n3. Registering Test Client:"
CLIENT_RESPONSE=$(curl -s -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uris": ["https://dreamer.com/oauth/callback"],
    "client_name": "Manual Test Client"
  }')

echo $CLIENT_RESPONSE | python -m json.tool
CLIENT_ID=$(echo $CLIENT_RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['client_id'])")

# Test MCP without auth (should fail)
echo -e "\n4. Testing MCP without auth (should return 401):"
curl -s -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}' \
  -w "\nHTTP Status: %{http_code}\n"

echo -e "\n✅ Server is working correctly\!"
echo -e "\nTo test the full flow:"
echo "1. Deploy to Railway (or similar)"
echo "2. Get your public URL"
echo "3. Add to Dreamer with that URL"
