"""
Oura Stress and Resilience MCP Tool - Access stress load and resilience data through Dreamer platform
"""

from fastmcp import FastMCP
from pydantic import Field
import httpx
import os
from datetime import datetime, date
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import jwt
import json

# Load environment variables
load_dotenv()

# Get configuration from environment
OURA_API_TOKEN = os.getenv('OURA_API_TOKEN')
OURA_API_BASE_URL = "https://api.ouraring.com/v2/usercollection"
AUTH_SERVER_URL = os.getenv('AUTH_SERVER_URL', 'https://auth-oura-stress.railway.app')
TOOL_SERVER_URL = os.getenv('TOOL_SERVER_URL', 'https://oura-stress-resilience.railway.app')
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this-in-production')

# Initialize FastMCP server
mcp = FastMCP("oura-stress-resilience", version="1.0.0")

# Initialize FastAPI app for OAuth endpoints
app = FastAPI(title="Oura Stress & Resilience OAuth Server")

# Configure CORS for Dreamer platform
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"]
)


class OuraAPIClient:
    """Client for interacting with Oura API"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}"
        }
    
    async def fetch_with_retry(self, endpoint: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 3) -> Dict[str, Any]:
        """Fetch data from Oura API with retry logic"""
        url = f"{OURA_API_BASE_URL}/{endpoint}"
        
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, headers=self.headers, params=params)
                    
                    if response.status_code == 401:
                        return {
                            "error": "Invalid API token. Please check your Oura API token.",
                            "isError": True
                        }
                    
                    if response.status_code == 429:
                        if attempt < max_retries:
                            # Rate limited, wait and retry
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return {
                            "error": "Rate limit exceeded. Please try again later.",
                            "isError": True
                        }
                    
                    response.raise_for_status()
                    return response.json()
                    
            except httpx.TimeoutException:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {
                    "error": "Request timeout. Please try again.",
                    "isError": True
                }
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {
                    "error": f"Error fetching data: {str(e)}",
                    "isError": True
                }


# Initialize the Oura client
oura_client = OuraAPIClient(OURA_API_TOKEN) if OURA_API_TOKEN else None

# Simple in-memory storage for OAuth clients (for demo - use database in production)
oauth_clients = {}
authorization_codes = {}
access_tokens = {}

# OAuth 2.0 Endpoints

@app.get("/.well-known/oauth-authorization-server")
async def oauth_server_metadata():
    """OAuth 2.0 Authorization Server Metadata (RFC 8414)"""
    return {
        "issuer": AUTH_SERVER_URL,
        "authorization_endpoint": f"{AUTH_SERVER_URL}/oauth/authorize",
        "token_endpoint": f"{AUTH_SERVER_URL}/oauth/token", 
        "registration_endpoint": f"{AUTH_SERVER_URL}/oauth/register",
        "code_challenge_methods_supported": ["S256"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "response_types_supported": ["code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["stress:read", "resilience:read"]
    }

@app.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata():
    """Protected Resource Metadata (RFC 9728)"""
    return {
        "resource": TOOL_SERVER_URL,
        "authorization_servers": [AUTH_SERVER_URL],
        "scopes_supported": ["stress:read", "resilience:read"], 
        "bearer_methods_supported": ["header"]
    }

@app.post("/oauth/register")
async def dynamic_client_registration(request: Request):
    """Dynamic Client Registration (RFC 7591)"""
    try:
        client_data = await request.json()
        
        # Generate client ID
        import uuid
        client_id = str(uuid.uuid4())
        
        # Store client info
        oauth_clients[client_id] = {
            "client_id": client_id,
            "redirect_uris": client_data.get("redirect_uris", []),
            "client_name": client_data.get("client_name", "Unknown Client"),
            "client_uri": client_data.get("client_uri", ""),
            "grant_types": client_data.get("grant_types", ["authorization_code"]),
            "response_types": client_data.get("response_types", ["code"]),
            "token_endpoint_auth_method": client_data.get("token_endpoint_auth_method", "none")
        }
        
        return {
            "client_id": client_id,
            "client_name": oauth_clients[client_id]["client_name"],
            "redirect_uris": oauth_clients[client_id]["redirect_uris"],
            "grant_types": oauth_clients[client_id]["grant_types"],
            "response_types": oauth_clients[client_id]["response_types"],
            "token_endpoint_auth_method": oauth_clients[client_id]["token_endpoint_auth_method"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid client registration: {str(e)}")

@app.get("/oauth/authorize")
async def authorize_endpoint(
    response_type: str,
    client_id: str, 
    redirect_uri: str,
    scope: str = "",
    state: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "S256"
):
    """OAuth 2.0 Authorization Endpoint"""
    
    # Validate client
    if client_id not in oauth_clients:
        raise HTTPException(status_code=400, detail="Invalid client_id")
    
    client = oauth_clients[client_id]
    if redirect_uri not in client["redirect_uris"]:
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")
    
    # For demo purposes, automatically approve (in production, show user consent page)
    import uuid
    auth_code = str(uuid.uuid4())
    
    # Store authorization code with PKCE challenge
    authorization_codes[auth_code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "user_id": "demo_user",  # In production, get from authenticated user
        "expires_at": datetime.now().timestamp() + 600  # 10 minutes
    }
    
    # Redirect back to client with authorization code
    from fastapi.responses import RedirectResponse
    callback_url = f"{redirect_uri}?code={auth_code}"
    if state:
        callback_url += f"&state={state}"
    
    return RedirectResponse(url=callback_url)

@app.post("/oauth/token") 
async def token_endpoint(request: Request):
    """OAuth 2.0 Token Endpoint"""
    try:
        form_data = await request.form()
        
        grant_type = form_data.get("grant_type")
        
        if grant_type == "authorization_code":
            # Authorization Code Grant
            code = form_data.get("code")
            redirect_uri = form_data.get("redirect_uri")
            client_id = form_data.get("client_id") 
            code_verifier = form_data.get("code_verifier")
            
            # Validate authorization code
            if code not in authorization_codes:
                raise HTTPException(status_code=400, detail="Invalid authorization code")
            
            code_data = authorization_codes[code]
            
            # Check expiration
            if datetime.now().timestamp() > code_data["expires_at"]:
                del authorization_codes[code]
                raise HTTPException(status_code=400, detail="Authorization code expired")
            
            # Validate PKCE challenge
            if code_data["code_challenge_method"] == "S256":
                import hashlib
                import base64
                
                challenge = base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier.encode()).digest()
                ).decode().rstrip('=')
                
                if challenge != code_data["code_challenge"]:
                    raise HTTPException(status_code=400, detail="Invalid code_verifier")
            
            # Generate tokens
            import uuid
            access_token = str(uuid.uuid4())
            refresh_token = str(uuid.uuid4())
            
            # Store access token
            access_tokens[access_token] = {
                "client_id": client_id,
                "user_id": code_data["user_id"],
                "scope": code_data["scope"],
                "expires_at": datetime.now().timestamp() + 3600  # 1 hour
            }
            
            # Clean up authorization code
            del authorization_codes[code]
            
            return {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": refresh_token,
                "scope": code_data["scope"]
            }
            
        elif grant_type == "refresh_token":
            # Refresh Token Grant (simplified implementation)
            refresh_token = form_data.get("refresh_token")
            
            # Generate new access token
            import uuid
            new_access_token = str(uuid.uuid4())
            
            access_tokens[new_access_token] = {
                "client_id": form_data.get("client_id"),
                "user_id": "demo_user",
                "scope": form_data.get("scope", ""),
                "expires_at": datetime.now().timestamp() + 3600
            }
            
            return {
                "access_token": new_access_token,
                "token_type": "Bearer", 
                "expires_in": 3600,
                "scope": form_data.get("scope", "")
            }
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported grant_type")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Bearer token validation
async def validate_bearer_token(request: Request):
    """Validate Bearer token from Authorization header"""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, 
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    if token not in access_tokens:
        raise HTTPException(
            status_code=401,
            detail="Invalid access token", 
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token_data = access_tokens[token]
    
    # Check expiration
    if datetime.now().timestamp() > token_data["expires_at"]:
        del access_tokens[token]
        raise HTTPException(
            status_code=401,
            detail="Access token expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return token_data


def calculate_stress_ratio(high_stress_seconds: int, recovery_seconds: int) -> float:
    """Calculate stress:recovery ratio, handling division by zero"""
    if recovery_seconds == 0:
        return float('inf') if high_stress_seconds > 0 else 0.0
    return high_stress_seconds / recovery_seconds


def get_day_summary_description(ratio: float) -> str:
    """Convert stress ratio to descriptive summary"""
    if ratio == 0:
        return "very_restorative"
    elif ratio <= 1:
        return "restorative" 
    elif ratio <= 2:
        return "balanced"
    elif ratio <= 4:
        return "stressful"
    else:
        return "very_stressful"


def get_resilience_level(contributors: Dict[str, int]) -> str:
    """Determine resilience level based on contributor scores"""
    avg_score = sum(contributors.values()) / len(contributors) if contributors else 0
    
    if avg_score >= 75:
        return "excellent"
    elif avg_score >= 60:
        return "good"
    elif avg_score >= 45:
        return "limited"
    else:
        return "low"


@mcp.tool()
async def get_stress_and_resilience(
    user_id: Optional[str] = Field(None, description="User ID (not required for personal tokens)"),
    date_param: Optional[str] = Field(None, description="Date in YYYY-MM-DD format (defaults to today)")
) -> dict:
    """
    Returns today's stress load (time in high stress vs. recovery) and resilience level.
    
    Provides actionable stress:recovery ratio and resilience context to understand
    capacity decline patterns beyond just readiness scores.
    """
    
    if not oura_client:
        return {
            "content": [{
                "type": "text",
                "text": "Oura API token not configured. Please set OURA_API_TOKEN environment variable."
            }],
            "isError": True
        }
    
    try:
        # Use provided date or default to today
        target_date = date_param if date_param else date.today().strftime("%Y-%m-%d")
        
        # Validate date format
        datetime.strptime(target_date, "%Y-%m-%d")
        
        # Fetch both stress and resilience data in parallel
        stress_params = {"start_date": target_date, "end_date": target_date}
        
        # Make both API calls
        stress_task = oura_client.fetch_with_retry("daily_stress", stress_params)
        resilience_task = oura_client.fetch_with_retry("daily_resilience", stress_params)
        
        stress_data, resilience_data = await asyncio.gather(stress_task, resilience_task)
        
        # Check for API errors
        if stress_data.get("isError"):
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Error fetching stress data: {stress_data.get('error')}"
                }],
                "isError": True
            }
            
        if resilience_data.get("isError"):
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error fetching resilience data: {resilience_data.get('error')}"
                }],
                "isError": True
            }
        
        # Extract data for the target date
        stress_records = stress_data.get("data", [])
        resilience_records = resilience_data.get("data", [])
        
        # Find records for the target date
        stress_record = next((r for r in stress_records if r.get("day") == target_date), None)
        resilience_record = next((r for r in resilience_records if r.get("day") == target_date), None)
        
        if not stress_record:
            return {
                "content": [{
                    "type": "text",
                    "text": f"No stress data found for {target_date}"
                }],
                "structuredContent": {
                    "date": target_date,
                    "stress": None,
                    "resilience": None
                }
            }
        
        # Process stress data
        high_stress_seconds = stress_record.get("stress_high", 0)
        recovery_seconds = stress_record.get("recovery_high", 0)
        ratio = calculate_stress_ratio(high_stress_seconds, recovery_seconds)
        day_summary = get_day_summary_description(ratio)
        
        stress_result = {
            "highStressSeconds": high_stress_seconds,
            "recoverySeconds": recovery_seconds, 
            "ratio": ratio if ratio != float('inf') else None,
            "daySummary": day_summary
        }
        
        # Process resilience data
        resilience_result = None
        if resilience_record:
            contributors = resilience_record.get("contributors", {})
            resilience_contributors = {
                "sleepRecovery": contributors.get("sleep_recovery", 0),
                "daytimeRecovery": contributors.get("daytime_recovery", 0), 
                "stress": contributors.get("stress", 0)
            }
            
            resilience_result = {
                "level": get_resilience_level(resilience_contributors),
                "contributors": resilience_contributors
            }
        
        # Create summary text
        stress_hours = high_stress_seconds // 3600
        stress_minutes = (high_stress_seconds % 3600) // 60
        recovery_hours = recovery_seconds // 3600
        recovery_minutes = (recovery_seconds % 3600) // 60
        
        summary_text = f"Stress & Resilience for {target_date}: "
        summary_text += f"{stress_hours}h{stress_minutes}m high stress, "
        summary_text += f"{recovery_hours}h{recovery_minutes}m recovery"
        
        if ratio != float('inf') and ratio is not None:
            summary_text += f" (ratio: {ratio:.1f}:1)"
        
        if resilience_result:
            summary_text += f", resilience: {resilience_result['level']}"
        
        return {
            "content": [{
                "type": "text",
                "text": summary_text
            }],
            "structuredContent": {
                "date": target_date,
                "stress": stress_result,
                "resilience": resilience_result
            }
        }
        
    except ValueError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Invalid date format: {str(e)}. Please use YYYY-MM-DD format."
            }],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching stress and resilience data: {str(e)}"
            }],
            "isError": True
        }


# Protected MCP endpoint
@app.post("/mcp")
async def protected_mcp_endpoint(request: Request):
    """MCP endpoint with OAuth protection"""
    # Validate Bearer token first
    token_data = await validate_bearer_token(request)
    
    # Get request body and headers
    body = await request.body()
    
    # Create a simple response handler for MCP
    try:
        # For now, let's create a simple JSON-RPC handler for our specific tool
        import json
        
        # Parse the MCP request
        mcp_request = json.loads(body.decode())
        
        # Check if this is a tools/list request
        if mcp_request.get("method") == "tools/list":
            return {
                "jsonrpc": "2.0", 
                "id": mcp_request.get("id"),
                "result": {
                    "tools": [{
                        "name": "get_stress_and_resilience",
                        "description": "Get stress load and resilience data for a specific date",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "user_id": {
                                    "type": "string",
                                    "description": "User ID (not required for personal tokens)"
                                },
                                "date_param": {
                                    "type": "string", 
                                    "description": "Date in YYYY-MM-DD format (defaults to today)"
                                }
                            }
                        }
                    }]
                }
            }
        
        # Check if this is a tools/call request  
        elif mcp_request.get("method") == "tools/call":
            params = mcp_request.get("params", {})
            if params.get("name") == "get_stress_and_resilience":
                # Call our tool function with the provided arguments
                args = params.get("arguments", {})
                result = await get_stress_and_resilience(
                    user_id=args.get("user_id"),
                    date_param=args.get("date_param")
                )
                
                return {
                    "jsonrpc": "2.0",
                    "id": mcp_request.get("id"), 
                    "result": result
                }
        
        # Handle initialize request
        elif mcp_request.get("method") == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": mcp_request.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "oura-stress-resilience",
                        "version": "1.0.0"
                    }
                }
            }
        
        # Default error response
        return {
            "jsonrpc": "2.0",
            "id": mcp_request.get("id"),
            "error": {
                "code": -32601,
                "message": f"Method not found: {mcp_request.get('method')}"
            }
        }
        
    except Exception as e:
        print(f"MCP request error: {str(e)}")
        return {
            "jsonrpc": "2.0", 
            "id": mcp_request.get("id") if 'mcp_request' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "oura-stress-resilience",
        "timestamp": datetime.now().isoformat(),
        "oauth_clients": len(oauth_clients),
        "active_tokens": len(access_tokens)
    }


def main():
    """Run the OAuth-protected MCP server"""
    import uvicorn
    
    # Railway sets PORT dynamically
    port = int(os.environ.get("PORT", 8080))
    
    # Debug: Print environment info
    print(f"Starting OAuth-protected server with PORT={port}")
    print(f"OURA_API_TOKEN present: {'Yes' if os.environ.get('OURA_API_TOKEN') else 'No'}")
    print(f"AUTH_SERVER_URL: {AUTH_SERVER_URL}")
    print(f"TOOL_SERVER_URL: {TOOL_SERVER_URL}")
    
    if not OURA_API_TOKEN:
        print("Warning: OURA_API_TOKEN not set. The server will start but API calls will fail.")
        print("Please set your Oura API token in the environment or .env file.")
    
    print(f"Starting Oura Stress & Resilience OAuth + MCP server on port {port}")
    print(f"Server will listen on 0.0.0.0:{port}")
    print("\nEndpoints:")
    print(f"  OAuth metadata: https://your-domain.com/.well-known/oauth-authorization-server")
    print(f"  Resource metadata: https://your-domain.com/.well-known/oauth-protected-resource")
    print(f"  MCP endpoint: https://your-domain.com/mcp (requires Bearer token)")
    print(f"  Health check: https://your-domain.com/health")
    
    # Run FastAPI with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()