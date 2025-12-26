#!/usr/bin/env python3
"""
Full integration test for OAuth + MCP flow
Simulates the complete Dreamer client flow
"""

import httpx
import json
import uuid
import hashlib
import base64
import secrets
import urllib.parse
import asyncio
import os
from typing import Dict, Any, Optional
from datetime import datetime

# Configuration
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8080")
TEST_OURA_TOKEN = os.getenv("TEST_OURA_TOKEN", "")  # Set this for automated testing
DREAMER_REDIRECT_URI = "https://dreamer.com/oauth/callback"

class OAuthMCPTestClient:
    """Test client simulating Dreamer's OAuth + MCP flow"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.client_id: Optional[str] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        
    async def close(self):
        await self.client.aclose()
        
    def generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge per RFC 7636"""
        # Code verifier: 43-128 characters of [A-Z,a-z,0-9,-,.,_,~]
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('=')
        
        # Code challenge: base64url(sha256(code_verifier))
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('ascii')).digest()
        ).decode().rstrip('=')
        
        return code_verifier, code_challenge
    
    async def discover_oauth_metadata(self) -> Dict[str, Any]:
        """Discover OAuth authorization server metadata"""
        print("\n📋 Discovering OAuth metadata...")
        
        # Try OAuth 2.0 endpoint first
        response = await self.client.get(f"{self.base_url}/.well-known/oauth-authorization-server")
        if response.status_code == 200:
            metadata = response.json()
            print(f"✅ Found OAuth 2.0 metadata at {response.url}")
            return metadata
            
        # Fallback to OIDC endpoint
        response = await self.client.get(f"{self.base_url}/.well-known/openid-configuration")
        if response.status_code == 200:
            metadata = response.json()
            print(f"✅ Found OIDC metadata at {response.url}")
            return metadata
            
        raise Exception("Failed to discover OAuth metadata")
    
    async def discover_resource_metadata(self) -> Dict[str, Any]:
        """Discover protected resource metadata"""
        print("\n📋 Discovering protected resource metadata...")
        
        response = await self.client.get(f"{self.base_url}/.well-known/oauth-protected-resource")
        if response.status_code != 200:
            print(f"⚠️  No protected resource metadata found (optional)")
            return {}
            
        metadata = response.json()
        print(f"✅ Found protected resource metadata")
        return metadata
    
    async def register_client(self, metadata: Dict[str, Any]) -> str:
        """Perform dynamic client registration"""
        print("\n🔐 Registering as OAuth client...")
        
        registration_endpoint = metadata.get("registration_endpoint")
        if not registration_endpoint:
            raise Exception("No registration endpoint found")
            
        registration_data = {
            "redirect_uris": [DREAMER_REDIRECT_URI],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "client_name": "Dreamer Test Client",
            "client_uri": "https://dreamer.com"
        }
        
        response = await self.client.post(registration_endpoint, json=registration_data)
        if response.status_code != 200:
            raise Exception(f"Registration failed: {response.text}")
            
        client_info = response.json()
        self.client_id = client_info["client_id"]
        print(f"✅ Registered with client_id: {self.client_id}")
        return self.client_id
    
    async def get_authorization_code(self, metadata: Dict[str, Any], oura_token: str) -> tuple[str, str, str]:
        """Simulate authorization flow and get code"""
        print("\n🔑 Starting authorization flow...")
        
        # Generate PKCE parameters
        code_verifier, code_challenge = self.generate_pkce_pair()
        state = str(uuid.uuid4())
        
        print(f"  PKCE challenge: {code_challenge[:20]}...")
        print(f"  State: {state}")
        
        # Build authorization URL
        auth_params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": DREAMER_REDIRECT_URI,
            "scope": "oura:read",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        
        auth_endpoint = metadata["authorization_endpoint"]
        auth_url = f"{auth_endpoint}?{urllib.parse.urlencode(auth_params)}"
        
        # Follow redirect to get session
        response = await self.client.get(auth_url, follow_redirects=False)
        if response.status_code != 307:
            raise Exception(f"Expected redirect, got {response.status_code}")
            
        # Extract session from redirect URL
        redirect_url = response.headers.get("location")
        parsed = urllib.parse.urlparse(redirect_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        session_id = query_params.get("session", [None])[0]
        
        if not session_id:
            raise Exception("No session ID in redirect")
            
        print(f"  Session ID: {session_id}")
        
        # Submit Oura token to complete authorization
        print("  Submitting Oura token...")
        response = await self.client.post(
            f"{self.base_url}/oauth/connect",
            data={
                "session_id": session_id,
                "oura_token": oura_token
            },
            follow_redirects=False
        )
        
        if response.status_code not in [302, 307]:
            raise Exception(f"Expected redirect after token submission, got {response.status_code}")
            
        # Extract authorization code from redirect
        redirect_url = response.headers.get("location")
        parsed = urllib.parse.urlparse(redirect_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        code = query_params.get("code", [None])[0]
        returned_state = query_params.get("state", [None])[0]
        
        if not code:
            raise Exception("No authorization code in redirect")
            
        if returned_state != state:
            raise Exception("State mismatch - possible CSRF")
            
        print(f"✅ Got authorization code: {code[:10]}...")
        return code, code_verifier, state
    
    async def exchange_code_for_tokens(self, metadata: Dict[str, Any], code: str, code_verifier: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens"""
        print("\n🔄 Exchanging code for tokens...")
        
        token_endpoint = metadata["token_endpoint"]
        
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "redirect_uri": DREAMER_REDIRECT_URI,
            "code_verifier": code_verifier
        }
        
        response = await self.client.post(
            token_endpoint,
            data=token_data,  # Use form encoding
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            error_data = response.json()
            raise Exception(f"Token exchange failed: {error_data}")
            
        tokens = response.json()
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token")
        
        print(f"✅ Got access token: {self.access_token[:10]}...")
        if self.refresh_token:
            print(f"✅ Got refresh token: {self.refresh_token[:10]}...")
        
        return tokens
    
    async def refresh_access_token(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Use refresh token to get new access token"""
        print("\n♻️  Refreshing access token...")
        
        if not self.refresh_token:
            raise Exception("No refresh token available")
            
        token_endpoint = metadata["token_endpoint"]
        
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id
        }
        
        response = await self.client.post(
            token_endpoint,
            data=refresh_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            error_data = response.json()
            raise Exception(f"Refresh failed: {error_data}")
            
        tokens = response.json()
        self.access_token = tokens["access_token"]
        
        print(f"✅ Got new access token: {self.access_token[:10]}...")
        return tokens
    
    async def call_mcp_method(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Call an MCP method with authentication"""
        if not self.access_token:
            raise Exception("No access token available")
            
        mcp_request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {}
        }
        
        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=mcp_request,
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        
        if response.status_code == 401:
            raise Exception("Unauthorized - token may be expired")
        elif response.status_code != 200:
            raise Exception(f"MCP call failed with status {response.status_code}")
            
        return response.json()
    
    async def test_mcp_tools(self):
        """Test MCP tool functionality"""
        print("\n🛠️  Testing MCP tools...")
        
        # Initialize
        print("  Initializing MCP...")
        result = await self.call_mcp_method("initialize", {"protocolVersion": "2024-11-05"})
        if "error" in result:
            raise Exception(f"Initialize failed: {result['error']}")
        print("  ✅ MCP initialized")
        
        # List tools
        print("  Listing available tools...")
        result = await self.call_mcp_method("tools/list")
        if "error" in result:
            raise Exception(f"List tools failed: {result['error']}")
            
        tools = result["result"]["tools"]
        print(f"  ✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"    - {tool['name']}: {tool['description']}")
        
        # Call stress and resilience tool
        print("\n  Calling get_stress_and_resilience...")
        result = await self.call_mcp_method("tools/call", {
            "name": "get_stress_and_resilience",
            "arguments": {"date_param": datetime.now().strftime("%Y-%m-%d")}
        })
        
        if "error" in result:
            raise Exception(f"Tool call failed: {result['error']}")
            
        tool_result = result["result"]
        print(f"  ✅ Tool result: {tool_result['content'][0]['text']}")
        
        if "structuredContent" in tool_result:
            structured = tool_result["structuredContent"]
            if "stress" in structured:
                stress = structured["stress"]
                print(f"    High stress: {stress.get('highStressSeconds', 0) / 3600:.1f} hours")
                print(f"    Recovery: {stress.get('recoverySeconds', 0) / 3600:.1f} hours")
                if stress.get('ratio'):
                    print(f"    Ratio: {stress['ratio']:.1f}:1")

async def run_full_test():
    """Run the complete OAuth + MCP integration test"""
    print("🚀 Starting Full OAuth + MCP Integration Test")
    print("=" * 60)
    
    if not TEST_OURA_TOKEN:
        print("\n⚠️  WARNING: No TEST_OURA_TOKEN environment variable set!")
        print("The test will pause for manual token entry during authorization.")
        print("To run fully automated, set: export TEST_OURA_TOKEN='your-token'")
    
    client = OAuthMCPTestClient()
    
    try:
        # 1. Discovery
        oauth_metadata = await client.discover_oauth_metadata()
        resource_metadata = await client.discover_resource_metadata()
        
        # Validate metadata
        required_fields = ["authorization_endpoint", "token_endpoint", "registration_endpoint"]
        for field in required_fields:
            if field not in oauth_metadata:
                raise Exception(f"Missing required metadata field: {field}")
        
        # 2. Dynamic Client Registration
        await client.register_client(oauth_metadata)
        
        # 3. Authorization Flow
        if TEST_OURA_TOKEN:
            code, code_verifier, state = await client.get_authorization_code(oauth_metadata, TEST_OURA_TOKEN)
        else:
            print("\n⏸️  MANUAL STEP REQUIRED:")
            print(f"Visit the authorization URL and complete the flow manually.")
            print("Then re-run with the authorization code.")
            return
        
        # 4. Token Exchange
        tokens = await client.exchange_code_for_tokens(oauth_metadata, code, code_verifier)
        
        # 5. Test MCP Tools
        await client.test_mcp_tools()
        
        # 6. Test Token Refresh
        if client.refresh_token:
            print("\n⏰ Waiting a moment before testing refresh...")
            await asyncio.sleep(2)
            await client.refresh_access_token(oauth_metadata)
            
            # Test MCP with refreshed token
            print("  Testing MCP with refreshed token...")
            result = await client.call_mcp_method("tools/list")
            print("  ✅ MCP works with refreshed token")
        
        print("\n✅ ALL TESTS PASSED! 🎉")
        print("\nThe OAuth + MCP flow is working correctly.")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await client.close()

async def test_error_scenarios():
    """Test various error scenarios"""
    print("\n🔥 Testing Error Scenarios")
    print("=" * 60)
    
    client = OAuthMCPTestClient()
    
    try:
        # Test unauthorized MCP access
        print("\n1️⃣ Testing MCP without authentication...")
        try:
            # Make direct request without auth header
            response = await client.client.post(
                f"{client.base_url}/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}
            )
            if response.status_code == 401:
                print("  ✅ Correctly rejected unauthorized request")
            else:
                print(f"  ❌ Should have returned 401, got {response.status_code}")
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
        
        # Test with invalid token
        print("\n2️⃣ Testing MCP with invalid token...")
        client.access_token = "invalid-token-12345"
        try:
            result = await client.call_mcp_method("initialize")
            print("  ❌ Should have failed!")
        except Exception as e:
            if "Unauthorized" in str(e) or "401" in str(e):
                print("  ✅ Correctly rejected invalid token")
            else:
                raise
        
        print("\n✅ Error handling tests passed!")
        
    finally:
        await client.close()

if __name__ == "__main__":
    import sys
    
    async def main():
        # Run error tests first
        await test_error_scenarios()
        
        # Then run full integration test
        await run_full_test()
    
    asyncio.run(main())