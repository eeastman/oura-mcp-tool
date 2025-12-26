#!/bin/bash
# Monitor server logs in real-time

echo "🔍 Monitoring OAuth server logs..."
echo "Try connecting from Dreamer now!"
echo "================================="
echo ""

# Find the python process and show its output
PID=$(ps aux | grep "python.*oura_tool.py" | grep -v grep | awk '{print $2}' | head -1)

if [ -z "$PID" ]; then
    echo "❌ Server not running!"
    echo "Start it with: python src/oura_tool.py"
else
    echo "✅ Server running with PID: $PID"
    echo "Watching for incoming requests..."
    echo ""
    
    # For Railway deployments, check logs with:
    # railway logs
fi

echo "Tips:"
echo "- Look for GET requests to /.well-known/* endpoints"
echo "- Check for any 404 or 500 errors"
echo "- Watch for 'UNHANDLED REQUEST' messages"
echo "- Note any 'Token validation failed' errors"