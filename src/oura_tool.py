"""
Oura Stress and Resilience MCP Tool
"""

import os
import sys
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import json

# Import our modules
try:
    # Try absolute import first (for when running as python main.py)
    from src.auth.oauth_server import setup_oauth_routes, validate_token, storage
    from src.tools.stress_resilience import get_stress_and_resilience_data as get_stress_resilience
except ImportError:
    # Fall back to relative import (for when running as python src/oura_tool.py)
    from auth.oauth_server import setup_oauth_routes, validate_token, storage
    from tools.stress_resilience import get_stress_and_resilience_data as get_stress_resilience

# Load environment variables
load_dotenv()

# Configuration

# Server configuration
PORT = int(os.environ.get("PORT", 8080))

# Initialize FastAPI app
app = FastAPI(title="Oura Stress & Resilience Tool")

# CORS setup per Dreamer requirements
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)

# Setup OAuth routes from our auth module
setup_oauth_routes(app)

# MCP Tool Implementation

async def get_stress_and_resilience_data(user_id: str, date_param: Optional[str] = None) -> dict:
    """Get stress and resilience data for user"""
    
    # Get user's Oura token from storage
    user_data = await storage.user_tokens.get(user_id)
    if not user_data:
        return {
            "content": [{"type": "text", "text": "User not found"}],
            "isError": True
        }
    
    oura_token = user_data["oura_token"]
    
    # Call the imported function
    return await get_stress_resilience(oura_token, date_param)

# MCP endpoint info
@app.get("/mcp")
async def mcp_info():
    """MCP endpoint - return tools list for GET requests"""
    # Some MCP clients do GET first to check available tools
    return {
        "tools": [{
            "name": "get_stress_and_resilience",
            "description": "Get stress and resilience data for a specific date",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "date_param": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (defaults to today)"
                    }
                }
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["text"]},
                                "text": {"type": "string"}
                            },
                            "required": ["type", "text"]
                        }
                    },
                    "structuredContent": {"type": "object"},
                    "isError": {"type": "boolean"}
                },
                "required": ["content"]
            }
        }]
    }

# MCP OPTIONS for CORS
@app.options("/mcp")
async def mcp_options():
    """Handle OPTIONS requests for CORS"""
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Mcp-Session-Id",
            "Access-Control-Expose-Headers": "Mcp-Session-Id",
            "Access-Control-Max-Age": "86400"
        }
    )

# Protected MCP endpoint
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP endpoint with OAuth protection"""
    print("=== MCP ENDPOINT CALLED ===")
    print(f"Headers: {dict(request.headers)}")
    
    # Validate OAuth token
    try:
        token_data = await validate_token(request)
        print(f"Token validated for user: {token_data.get('user_id')}")
    except HTTPException as e:
        print(f"Token validation failed: {e.detail}")
        raise
    
    try:
        # Parse MCP request
        body = await request.body()
        body_str = body.decode()
        print(f"MCP request body: {body_str}")
        
        # Handle empty body case
        if not body_str:
            print("Empty body received, returning error")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error: Empty request body"}
                },
                headers={"Content-Type": "application/json"},
                status_code=400
            )
        
        try:
            mcp_request = json.loads(body_str)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                },
                headers={"Content-Type": "application/json"},
                status_code=400
            )
        
        method = mcp_request.get("method")
        print(f"MCP method: {method}")
        
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": mcp_request.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "oura-stress-resilience", "version": "1.0.0"}
                }
            }
            return JSONResponse(content=response, headers={"Content-Type": "application/json"})
        
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": mcp_request.get("id"),
                "result": {
                    "tools": [{
                        "name": "get_stress_and_resilience",
                        "description": "Get stress and resilience data for a specific date",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "date_param": {
                                    "type": "string",
                                    "description": "Date in YYYY-MM-DD format (defaults to today)"
                                }
                            }
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "type": {"type": "string", "enum": ["text"]},
                                            "text": {"type": "string"}
                                        },
                                        "required": ["type", "text"]
                                    }
                                },
                                "structuredContent": {"type": "object"},
                                "isError": {"type": "boolean"}
                            },
                            "required": ["content", "structuredContent", "isError"]
                        }
                    }]
                }
            }
            return JSONResponse(content=response, headers={"Content-Type": "application/json"})
        
        elif method == "tools/call":
            params = mcp_request.get("params", {})
            if params.get("name") == "get_stress_and_resilience":
                args = params.get("arguments", {})
                result = await get_stress_and_resilience_data(
                    user_id=token_data["user_id"],
                    date_param=args.get("date_param")
                )
                
                
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": mcp_request.get("id"),
                        "result": result
                    },
                    headers={"Content-Type": "application/json"}
                )
        
        # Unknown method
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": mcp_request.get("id"),
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            },
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        print(f"MCP error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": mcp_request.get("id") if 'mcp_request' in locals() else None,
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
            },
            headers={"Content-Type": "application/json"}
        )

# MCP at root path for Dreamer compatibility
@app.post("/")
async def root_mcp_endpoint(request: Request):
    """Handle MCP requests at root path (Dreamer uses this)"""
    return await mcp_endpoint(request)

# Health check
@app.get("/health")
async def health():
    """Health check"""
    # Since storage is async, we can't easily count items
    # Just return basic health status
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "storage": "persistent",
        "storage_type": os.getenv('STORAGE_TYPE', 'sqlite')
    }


# Test endpoints for development
@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "service": "Oura Stress & Resilience Tool",
        "version": "1.0.0",
        "endpoints": {
            "oauth_metadata": "/.well-known/oauth-authorization-server",
            "resource_metadata": "/.well-known/oauth-protected-resource",
            "mcp": "/mcp",
            "health": "/health"
        }
    }

# Catch-all route for debugging
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(request: Request, path: str):
    """Log all unhandled requests for debugging"""
    print(f"=== UNHANDLED REQUEST ===")
    print(f"Path: /{path}")
    print(f"Method: {request.method}")
    print(f"Headers: {dict(request.headers)}")
    if request.method in ["POST", "PUT"]:
        try:
            body = await request.body()
            print(f"Body: {body.decode()}")
        except:
            pass
    raise HTTPException(status_code=404, detail=f"Path not found: /{path}")


def main():
    """Run the server"""
    import uvicorn
    
    print(f"Starting Oura Stress & Resilience Tool on port {PORT}")
    print(f"Base URL: http://localhost:{PORT}")
    print("\nOAuth Endpoints:")
    print(f"  Metadata: http://localhost:{PORT}/.well-known/oauth-authorization-server")
    print(f"  Authorization: http://localhost:{PORT}/oauth/authorize")
    print(f"  Token: http://localhost:{PORT}/oauth/token")
    print(f"  Registration: http://localhost:{PORT}/oauth/register")
    print(f"\nMCP Endpoint: http://localhost:{PORT}/mcp")
    print(f"Health Check: http://localhost:{PORT}/health")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()