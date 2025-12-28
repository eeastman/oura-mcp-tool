"""
OAuth 2.0 Server Implementation with Persistent Storage
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, Response
from datetime import datetime, timedelta
import uuid
import urllib.parse
import hashlib
import base64
import os
import asyncio
from .storage_wrapper import get_storage_manager, OAuthStorageManager

# Get storage manager instance
storage: OAuthStorageManager = get_storage_manager()

def get_base_url():
    """Get the base URL for OAuth endpoints"""
    RAILWAY_PUBLIC_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN')
    PORT = int(os.environ.get("PORT", 8080))
    
    if RAILWAY_PUBLIC_DOMAIN:
        return f"https://{RAILWAY_PUBLIC_DOMAIN}"
    else:
        return f"http://localhost:{PORT}"

def setup_oauth_routes(app: FastAPI):
    """Setup OAuth endpoints on the FastAPI app"""
    
    BASE_URL = get_base_url()
    
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
            
            client_data = {
                "client_id": client_id,
                "redirect_uris": data.get("redirect_uris", []),
                "client_name": data.get("client_name", "Unknown"),
                "created_at": datetime.now().isoformat()
            }
            
            await storage.clients.set(client_id, client_data)
            
            return {
                "client_id": client_id,
                "client_name": client_data["client_name"],
                "redirect_uris": client_data["redirect_uris"]
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
        client = await storage.clients.get(client_id)
        if not client:
            # Return error per RFC 6749 4.1.2.1
            error_params = urllib.parse.urlencode({
                "error": "invalid_request",
                "error_description": "The client identifier is invalid",
                "state": state
            })
            return RedirectResponse(url=f"{redirect_uri}?{error_params}")
        
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
        
        await storage.auth_codes.set(session_id, auth_request)
        
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
                auth_data = await storage.auth_codes.get(code)
                if not auth_data:
                    return JSONResponse(
                        content={"error": "invalid_grant", "error_description": "Authorization code is invalid"},
                        status_code=400
                    )
                
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
                access_token_data = {
                    "client_id": client_id,
                    "user_id": auth_data.get("user_id", "anonymous"),
                    "scope": auth_data.get("scope", ""),
                    "resource": resource or BASE_URL,  # RFC 8707
                    "created_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                    "refresh_token": refresh_token
                }
                await storage.create_access_token(access_token, access_token_data)
                
                # Store refresh token (longer expiry)
                refresh_token_data = {
                    "client_id": client_id,
                    "user_id": auth_data.get("user_id", "anonymous"),
                    "scope": auth_data.get("scope", ""),
                    "resource": resource or BASE_URL,  # RFC 8707
                    "created_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
                    "is_refresh_token": True
                }
                await storage.create_refresh_token(refresh_token, refresh_token_data)
                
                # Clean up authorization code
                await storage.auth_codes.delete(code)
                
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
                
                token_data = await storage.access_tokens.get(refresh_token)
                if not token_data:
                    return JSONResponse(
                        content={"error": "invalid_grant", "error_description": "Refresh token is invalid"},
                        status_code=400
                    )
                
                # Verify it's a refresh token
                if not token_data.get("is_refresh_token"):
                    return JSONResponse(
                        content={"error": "invalid_grant", "error_description": "Token is not a refresh token"},
                        status_code=400
                    )
                
                # Check expiration
                expires_at = datetime.fromisoformat(token_data["expires_at"])
                if datetime.now() > expires_at:
                    await storage.access_tokens.delete(refresh_token)
                    return JSONResponse(
                        content={"error": "invalid_grant", "error_description": "Refresh token has expired"},
                        status_code=400
                    )
                
                # Generate new access token
                new_access_token = str(uuid.uuid4())
                
                # Store new access token
                new_token_data = {
                    "client_id": client_id or token_data["client_id"],
                    "user_id": token_data["user_id"],
                    "scope": token_data["scope"],
                    "resource": resource or token_data.get("resource", BASE_URL),  # RFC 8707
                    "created_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                    "refresh_token": refresh_token
                }
                await storage.create_access_token(new_access_token, new_token_data)
                
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
        auth_data = await storage.auth_codes.get(session)
        if not auth_data:
            raise HTTPException(status_code=400, detail="Invalid session")
        
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
        
        auth_data = await storage.auth_codes.get(session_id)
        if not auth_data:
            raise HTTPException(status_code=400, detail="Invalid session")
        
        # Store user's Oura token
        user_id = str(uuid.uuid4())
        await storage.user_tokens.set(user_id, {
            "oura_token": oura_token,
            "created_at": datetime.now().isoformat()
        })
        
        # Update auth data
        auth_data["user_id"] = user_id
        auth_data["status"] = "authorized"
        
        # Generate final authorization code
        final_code = str(uuid.uuid4())
        await storage.auth_codes.set(final_code, auth_data)
        await storage.auth_codes.delete(session_id)
        
        # Redirect back to Dreamer
        redirect_url = f"{auth_data['redirect_uri']}?code={final_code}"
        if auth_data.get("state"):
            redirect_url += f"&state={auth_data['state']}"
        
        print(f"=== AUTHORIZATION COMPLETE ===")
        print(f"Generated auth code: {final_code}")
        print(f"Redirecting to: {redirect_url}")
        
        # Use 302 redirect for better compatibility
        return RedirectResponse(url=redirect_url, status_code=302)

    # OAuth revoke endpoint
    @app.post("/oauth/revoke")
    async def revoke_token(request: Request):
        """Token revocation endpoint"""
        form_data = await request.form()
        token = form_data.get("token")
        print(f"Token revocation requested for: {token}")
        
        # Remove token if it exists
        if token:
            await storage.access_tokens.delete(token)
        
        # Always return 200 OK per RFC 7009
        return {"revoked": True}

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

    # Development-only test token endpoint
    if os.getenv("ENABLE_TEST_ENDPOINTS") == "true":
        @app.post("/oauth/test-token")
        async def create_test_token(request: Request):
            """Create a test token for development - DO NOT USE IN PRODUCTION"""
            try:
                data = await request.json()
                oura_token = data.get("oura_token")

                if not oura_token:
                    raise HTTPException(status_code=400, detail="oura_token required")

                # Create test user
                user_id = str(uuid.uuid4())
                await storage.user_tokens.set(user_id, {
                    "oura_token": oura_token,
                    "created_at": datetime.now().isoformat()
                })

                # Create access token
                access_token = str(uuid.uuid4())
                token_data = {
                    "client_id": "test-client",
                    "user_id": user_id,
                    "scope": "oura:read",
                    "resource": BASE_URL,
                    "created_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
                }
                await storage.create_access_token(access_token, token_data, 86400)

                return {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": 86400,
                    "instructions": f"Use this header: Authorization: Bearer {access_token}"
                }

            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    # Start background task for cleanup
    @app.on_event("startup")
    async def startup_event():
        """Start background cleanup task"""
        async def cleanup_task():
            while True:
                try:
                    count = await storage.cleanup_expired()
                    if count > 0:
                        print(f"Cleaned up {count} expired tokens")
                except Exception as e:
                    print(f"Cleanup error: {e}")
                await asyncio.sleep(3600)  # Run every hour
        
        asyncio.create_task(cleanup_task())

# Token validation function
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
    
    token_data = await storage.validate_token(token)
    if not token_data:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return token_data

# Export for use in main app - now we need to export the storage manager too
__all__ = ['setup_oauth_routes', 'validate_token', 'storage']