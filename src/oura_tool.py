"""
Oura Stress and Resilience MCP Tool - Simple OAuth implementation for Dreamer platform
"""

from fastmcp import FastMCP
from pydantic import Field
import httpx
import os
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import json
import uuid
import urllib.parse
import hashlib
import base64

# Load environment variables
load_dotenv()

# Configuration
OURA_API_BASE_URL = "https://api.ouraring.com/v2/usercollection"

# Server configuration - simplified for better reliability
PORT = int(os.environ.get("PORT", 8080))
RAILWAY_PUBLIC_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN')

if RAILWAY_PUBLIC_DOMAIN:
    BASE_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}"
else:
    BASE_URL = f"http://localhost:{PORT}"

JWT_SECRET = os.getenv('JWT_SECRET', 'change-this-secret-in-production')

# Oura OAuth Configuration (optional)
OURA_CLIENT_ID = os.getenv('OURA_CLIENT_ID')
OURA_CLIENT_SECRET = os.getenv('OURA_CLIENT_SECRET')

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

# Simple in-memory storage
clients = {}
auth_codes = {}
access_tokens = {}
user_tokens = {}

class OuraAPIClient:
    """Client for Oura API"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {"Authorization": f"Bearer {api_token}"}
    
    async def fetch_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Fetch data from Oura API"""
        url = f"{OURA_API_BASE_URL}/{endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:  # 30 second timeout per Dreamer docs
                response = await client.get(url, headers=self.headers, params=params or {})
                
                if response.status_code == 401:
                    return {"error": "Invalid Oura token", "isError": True}
                
                if response.status_code == 429:
                    return {"error": "Rate limited", "isError": True}
                
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            return {"error": f"API error: {str(e)}", "isError": True}

# OAuth Discovery Endpoints
@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    """OAuth 2.0 Authorization Server Metadata"""
    metadata = {
        "issuer": BASE_URL,
        "authorization_endpoint": f"{BASE_URL}/oauth/authorize",
        "token_endpoint": f"{BASE_URL}/oauth/token",
        "registration_endpoint": f"{BASE_URL}/oauth/register",
        "code_challenge_methods_supported": ["S256"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "response_types_supported": ["code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["oura:read"],
        "response_modes_supported": ["query"],
        "subject_types_supported": ["public"],
        "revocation_endpoint": f"{BASE_URL}/oauth/revoke",
        "revocation_endpoint_auth_methods_supported": ["none"],
        "resource_indicators_supported": True  # RFC 8707
    }
    print(f"OAuth metadata requested, returning: {metadata}")
    return metadata

@app.get("/.well-known/oauth-protected-resource")
async def resource_metadata():
    """Protected Resource Metadata"""
    return {
        "resource": BASE_URL,
        "authorization_servers": [BASE_URL],
        "scopes_supported": ["oura:read"],
        "bearer_methods_supported": ["header"]
    }

# Handle trailing slash variant
@app.get("/.well-known/oauth-protected-resource/")
async def resource_metadata_slash():
    """Protected Resource Metadata (with trailing slash)"""
    return await resource_metadata()

# OAuth Endpoints
@app.post("/oauth/register")
async def register_client(request: Request):
    """Dynamic Client Registration"""
    try:
        data = await request.json()
        client_id = str(uuid.uuid4())
        
        clients[client_id] = {
            "client_id": client_id,
            "redirect_uris": data.get("redirect_uris", []),
            "client_name": data.get("client_name", "Unknown"),
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "client_id": client_id,
            "client_name": clients[client_id]["client_name"],
            "redirect_uris": clients[client_id]["redirect_uris"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration failed: {str(e)}")

@app.get("/oauth/authorize")
async def authorize(
    response_type: str,
    client_id: str,
    redirect_uri: str,
    scope: str = "",
    state: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "S256"
):
    """OAuth Authorization Endpoint"""
    print(f"Authorization request: client_id={client_id}, redirect_uri={redirect_uri}")
    
    # Validate client
    if client_id not in clients:
        # Return error per RFC 6749 4.1.2.1
        error_params = urllib.parse.urlencode({
            "error": "invalid_request",
            "error_description": "The client identifier is invalid",
            "state": state
        })
        return RedirectResponse(url=f"{redirect_uri}?{error_params}")
    
    client = clients[client_id]
    if redirect_uri not in client["redirect_uris"]:
        # Don't redirect for redirect_uri mismatch per RFC 6749 4.1.2.4
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")
    
    # Generate session for user auth flow
    session_id = str(uuid.uuid4())
    
    # Store authorization request
    auth_request = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "session_id": session_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(minutes=10)).isoformat()
    }
    
    auth_codes[session_id] = auth_request
    
    # Redirect to Oura connection page
    return RedirectResponse(url=f"{BASE_URL}/connect?session={session_id}")

@app.get("/oauth/token")
async def token_info():
    """OAuth token endpoint info for GET requests"""
    return {"error": "Method not allowed", "message": "Use POST to exchange tokens"}

@app.post("/oauth/token")
async def exchange_token(request: Request):
    """OAuth Token Exchange"""
    print("=== TOKEN EXCHANGE CALLED ===")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Available auth codes: {list(auth_codes.keys())}")
    
    try:
        # Handle both form data and JSON requests
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            form_data = await request.json()
            print(f"Token request JSON: {form_data}")
        else:
            form_data = dict(await request.form())
            print(f"Token request form data: {form_data}")
        
        grant_type = form_data.get("grant_type")
        
        if grant_type == "authorization_code":
            code = form_data.get("code")
            client_id = form_data.get("client_id")
            code_verifier = form_data.get("code_verifier")
            resource = form_data.get("resource")  # RFC 8707
            
            print(f"Exchanging code: {code} for client: {client_id}")
            
            # Find authorization session
            if code not in auth_codes:
                print(f"Code not found. Available codes: {list(auth_codes.keys())}")
                return JSONResponse(
                    content={"error": "invalid_grant", "error_description": "Authorization code is invalid"},
                    status_code=400
                )
            
            auth_data = auth_codes[code]
            
            # Validate PKCE if present
            if auth_data.get("code_challenge") and code_verifier:
                expected_challenge = base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier.encode()).digest()
                ).decode().rstrip('=')
                
                if expected_challenge != auth_data["code_challenge"]:
                    return JSONResponse(
                        content={"error": "invalid_grant", "error_description": "PKCE verification failed"},
                        status_code=400
                    )
            
            # Generate tokens
            access_token = str(uuid.uuid4())
            refresh_token = str(uuid.uuid4())
            
            # Store access token
            access_tokens[access_token] = {
                "client_id": client_id,
                "user_id": auth_data.get("user_id", "anonymous"),
                "scope": auth_data.get("scope", ""),
                "resource": resource or BASE_URL,  # RFC 8707
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                "refresh_token": refresh_token
            }
            
            # Store refresh token (longer expiry)
            access_tokens[refresh_token] = {
                "client_id": client_id,
                "user_id": auth_data.get("user_id", "anonymous"),
                "scope": auth_data.get("scope", ""),
                "resource": resource or BASE_URL,  # RFC 8707
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
                "is_refresh_token": True
            }
            
            # Clean up authorization code
            del auth_codes[code]
            
            print(f"Generated access token: {access_token}")
            print(f"Generated refresh token: {refresh_token}")
            
            response = {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": refresh_token,
                "scope": auth_data.get("scope", "")
            }
            # Include resource if specified (RFC 8707)
            if resource:
                response["resource"] = resource
            print(f"Token response: {response}")
            return response
        
        elif grant_type == "refresh_token":
            # Handle refresh token grant
            refresh_token = form_data.get("refresh_token")
            client_id = form_data.get("client_id")
            resource = form_data.get("resource")  # RFC 8707
            
            print(f"Refresh token request: token={refresh_token}, client={client_id}")
            
            if not refresh_token or refresh_token not in access_tokens:
                return JSONResponse(
                    content={"error": "invalid_grant", "error_description": "Refresh token is invalid"},
                    status_code=400
                )
            
            token_data = access_tokens[refresh_token]
            
            # Verify it's a refresh token
            if not token_data.get("is_refresh_token"):
                return JSONResponse(
                    content={"error": "invalid_grant", "error_description": "Token is not a refresh token"},
                    status_code=400
                )
            
            # Check expiration
            expires_at = datetime.fromisoformat(token_data["expires_at"])
            if datetime.now() > expires_at:
                del access_tokens[refresh_token]
                return JSONResponse(
                    content={"error": "invalid_grant", "error_description": "Refresh token has expired"},
                    status_code=400
                )
            
            # Generate new access token
            new_access_token = str(uuid.uuid4())
            
            # Store new access token
            access_tokens[new_access_token] = {
                "client_id": client_id or token_data["client_id"],
                "user_id": token_data["user_id"],
                "scope": token_data["scope"],
                "resource": resource or token_data.get("resource", BASE_URL),  # RFC 8707
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                "refresh_token": refresh_token
            }
            
            response = {
                "access_token": new_access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": refresh_token,
                "scope": token_data["scope"]
            }
            # Include resource if specified (RFC 8707)
            if resource or token_data.get("resource"):
                response["resource"] = resource or token_data["resource"]
            
            print(f"Refresh token response: {response}")
            return response
        
        else:
            return JSONResponse(
                content={"error": "unsupported_grant_type", "error_description": f"Grant type '{grant_type}' is not supported"},
                status_code=400
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Token exchange error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {str(e)}")

# User connection flow
@app.get("/connect")
async def connect_oura(session: str):
    """Show Oura connection page"""
    if session not in auth_codes:
        raise HTTPException(status_code=400, detail="Invalid session")
    
    auth_data = auth_codes[session]
    if auth_data["status"] != "pending":
        raise HTTPException(status_code=400, detail="Session already used")
    
    # Simple HTML form for Oura token
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Connect Oura Account</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; }}
            .form-group {{ margin: 20px 0; }}
            input[type="text"] {{ width: 100%; padding: 10px; margin: 5px 0; }}
            button {{ background: #007bff; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; }}
            .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>Connect Your Oura Account</h1>
        <div class="info">
            <p>To use this tool, you need to provide your Oura Personal Access Token.</p>
            <p><strong>Steps:</strong></p>
            <ol>
                <li>Go to <a href="https://cloud.ouraring.com/personal-access-tokens" target="_blank">Oura Cloud</a></li>
                <li>Create a new Personal Access Token</li>
                <li>Copy and paste it below</li>
            </ol>
        </div>
        
        <form action="/oauth/connect" method="post">
            <input type="hidden" name="session_id" value="{session}">
            <div class="form-group">
                <label>Oura Personal Access Token:</label>
                <input type="text" name="oura_token" placeholder="Enter your token here" required>
            </div>
            <button type="submit">Connect Account</button>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.post("/oauth/connect")
async def save_oura_token(request: Request):
    """Save Oura token and complete OAuth flow"""
    form_data = await request.form()
    session_id = form_data.get("session_id")
    oura_token = form_data.get("oura_token")
    
    if session_id not in auth_codes:
        raise HTTPException(status_code=400, detail="Invalid session")
    
    auth_data = auth_codes[session_id]
    
    # Store user's Oura token
    user_id = str(uuid.uuid4())
    user_tokens[user_id] = {
        "oura_token": oura_token,
        "created_at": datetime.now().isoformat()
    }
    
    # Update auth data
    auth_data["user_id"] = user_id
    auth_data["status"] = "authorized"
    
    # Generate final authorization code
    final_code = str(uuid.uuid4())
    auth_codes[final_code] = auth_data
    del auth_codes[session_id]
    
    # Redirect back to Dreamer
    redirect_url = f"{auth_data['redirect_uri']}?code={final_code}"
    if auth_data.get("state"):
        redirect_url += f"&state={auth_data['state']}"
    
    print(f"=== AUTHORIZATION COMPLETE ===")
    print(f"Generated auth code: {final_code}")
    print(f"Redirecting to: {redirect_url}")
    print(f"Auth codes in storage: {list(auth_codes.keys())}")
    
    # Use 302 redirect for better compatibility
    return RedirectResponse(url=redirect_url, status_code=302)

# Token validation
async def validate_token(request: Request):
    """Validate Bearer token"""
    auth_header = request.headers.get("Authorization", "")
    print(f"Authorization header: {auth_header[:50]}..." if auth_header else "No auth header")
    
    if not auth_header:
        raise HTTPException(
            status_code=401, 
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth_header[7:].strip()
    print(f"Token to validate: {token}")
    print(f"Available tokens: {list(access_tokens.keys())}")
    
    if token not in access_tokens:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token_data = access_tokens[token]
    
    # Check expiration
    expires_at = datetime.fromisoformat(token_data["expires_at"])
    if datetime.now() > expires_at:
        del access_tokens[token]
        raise HTTPException(
            status_code=401,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return token_data

# MCP Tool Implementation
async def get_stress_and_resilience_data(user_id: str, date_param: Optional[str] = None) -> dict:
    """Get stress and resilience data for user"""
    
    # Get user's Oura token
    if user_id not in user_tokens:
        return {
            "content": [{"type": "text", "text": "User not found"}],
            "isError": True
        }
    
    oura_token = user_tokens[user_id]["oura_token"]
    client = OuraAPIClient(oura_token)
    
    # Use provided date or today
    target_date = date_param or date.today().strftime("%Y-%m-%d")
    
    try:
        # Validate date
        datetime.strptime(target_date, "%Y-%m-%d")
        
        # Fetch data
        params = {"start_date": target_date, "end_date": target_date}
        stress_data = await client.fetch_data("daily_stress", params)
        resilience_data = await client.fetch_data("daily_resilience", params)
        
        # Check for errors
        if stress_data.get("isError"):
            return {
                "content": [{"type": "text", "text": f"Error: {stress_data['error']}"}],
                "isError": True
            }
        
        if resilience_data.get("isError"):
            return {
                "content": [{"type": "text", "text": f"Error: {resilience_data['error']}"}],
                "isError": True
            }
        
        # Process data
        stress_records = stress_data.get("data", [])
        resilience_records = resilience_data.get("data", [])
        
        stress_record = next((r for r in stress_records if r.get("day") == target_date), None)
        resilience_record = next((r for r in resilience_records if r.get("day") == target_date), None)
        
        if not stress_record:
            return {
                "content": [{"type": "text", "text": f"No data found for {target_date}"}],
                "isError": True
            }
        
        # Calculate stress metrics
        high_stress = stress_record.get("stress_high", 0)
        recovery = stress_record.get("recovery_high", 0)
        ratio = high_stress / recovery if recovery > 0 else float('inf')
        
        # Process resilience
        resilience_result = None
        if resilience_record:
            contributors = resilience_record.get("contributors", {})
            resilience_result = {
                "level": "good" if sum(contributors.values()) > 200 else "limited",
                "contributors": {
                    "sleepRecovery": contributors.get("sleep_recovery", 0),
                    "daytimeRecovery": contributors.get("daytime_recovery", 0),
                    "stress": contributors.get("stress", 0)
                }
            }
        
        # Format response
        stress_hours = high_stress // 3600
        recovery_hours = recovery // 3600
        summary = f"Stress: {stress_hours}h, Recovery: {recovery_hours}h"
        if ratio != float('inf'):
            summary += f" (ratio: {ratio:.1f}:1)"
        
        return {
            "content": [{"type": "text", "text": summary}],
            "structuredContent": {
                "date": target_date,
                "stress": {
                    "highStressSeconds": high_stress,
                    "recoverySeconds": recovery,
                    "ratio": ratio if ratio != float('inf') else None
                },
                "resilience": resilience_result
            },
            "isError": False
        }
        
    except ValueError:
        return {
            "content": [{"type": "text", "text": "Invalid date format. Use YYYY-MM-DD"}],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "isError": True
        }

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
    
    try:
        # Validate token
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
                            "required": ["content"]
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
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "clients": len(clients),
        "tokens": len(access_tokens)
    }

# OAuth callback endpoint (some clients might GET this)
@app.get("/oauth/callback")
async def oauth_callback(code: str = None, state: str = None, error: str = None):
    """Handle OAuth callbacks - just for debugging"""
    print(f"OAuth callback received: code={code}, state={state}, error={error}")
    return {
        "message": "This is the OAuth server callback endpoint",
        "code": code,
        "state": state,
        "error": error
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

# OAuth revoke endpoint (stub)
@app.post("/oauth/revoke")
async def revoke_token(request: Request):
    """Token revocation endpoint"""
    form_data = await request.form()
    token = form_data.get("token")
    print(f"Token revocation requested for: {token}")
    
    # Remove token if it exists
    if token and token in access_tokens:
        del access_tokens[token]
    
    # Always return 200 OK per RFC 7009
    return {"revoked": True}

def main():
    """Run the server"""
    import uvicorn
    
    print(f"Starting Oura Stress & Resilience Tool on port {PORT}")
    print(f"Base URL: {BASE_URL}")
    print("\nOAuth Endpoints:")
    print(f"  Metadata: {BASE_URL}/.well-known/oauth-authorization-server")
    print(f"  Authorization: {BASE_URL}/oauth/authorize")
    print(f"  Token: {BASE_URL}/oauth/token")
    print(f"  Registration: {BASE_URL}/oauth/register")
    print(f"\nMCP Endpoint: {BASE_URL}/mcp")
    print(f"Health Check: {BASE_URL}/health")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()