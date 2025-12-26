#!/usr/bin/env python3
"""
Test script for OAuth 2.0 flow with PKCE
Tests the complete flow as Dreamer would use it
"""

import httpx
import json
import uuid
import hashlib
import base64
import secrets
import urllib.parse
import asyncio
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8080"
TEST_REDIRECT_URI = "https://dreamer.com/oauth/callback"

def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge"""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip('=')
    return code_verifier, code_challenge

async def test_discovery():
    """Test OAuth discovery endpoints"""
    print("\n=== Testing Discovery Endpoints ===")
    
    async with httpx.AsyncClient() as client:
        # Test authorization server metadata
        print("\n1. Testing /.well-known/oauth-authorization-server")
        response = await client.get(f"{BASE_URL}/.well-known/oauth-authorization-server")
        print(f"Status: {response.status_code}")
        metadata = response.json()
        print(f"Metadata: {json.dumps(metadata, indent=2)}")
        
        # Verify required fields
        required_fields = ["issuer", "authorization_endpoint", "token_endpoint", 
                         "registration_endpoint", "code_challenge_methods_supported"]
        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"
        assert "S256" in metadata["code_challenge_methods_supported"], "S256 not supported"
        
        # Test protected resource metadata
        print("\n2. Testing /.well-known/oauth-protected-resource")
        response = await client.get(f"{BASE_URL}/.well-known/oauth-protected-resource")
        print(f"Status: {response.status_code}")
        resource_metadata = response.json()
        print(f"Resource Metadata: {json.dumps(resource_metadata, indent=2)}")
        
        return metadata

async def test_client_registration():
    """Test dynamic client registration"""
    print("\n=== Testing Client Registration ===")
    
    registration_data = {
        "redirect_uris": [TEST_REDIRECT_URI],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "client_name": "Test Client"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/oauth/register",
            json=registration_data
        )
        print(f"Status: {response.status_code}")
        client_info = response.json()
        print(f"Client Info: {json.dumps(client_info, indent=2)}")
        
        assert "client_id" in client_info, "No client_id returned"
        return client_info["client_id"]

async def test_authorization_flow(client_id: str):
    """Test the authorization flow"""
    print("\n=== Testing Authorization Flow ===")
    
    # Generate PKCE parameters
    code_verifier, code_challenge = generate_pkce_pair()
    state = str(uuid.uuid4())
    
    print(f"\nPKCE Parameters:")
    print(f"Code Verifier: {code_verifier}")
    print(f"Code Challenge: {code_challenge}")
    print(f"State: {state}")
    
    # Build authorization URL
    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": TEST_REDIRECT_URI,
        "scope": "oura:read",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    
    auth_url = f"{BASE_URL}/oauth/authorize?{urllib.parse.urlencode(auth_params)}"
    print(f"\nAuthorization URL: {auth_url}")
    
    # Note: In a real test, we'd need to handle the browser flow
    # For now, we'll simulate getting a code
    print("\nNOTE: Manual intervention required - visit the URL and get the authorization code")
    return code_verifier, state

async def test_token_exchange(client_id: str, code: str, code_verifier: str):
    """Test token exchange"""
    print("\n=== Testing Token Exchange ===")
    
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "code_verifier": code_verifier,
        "redirect_uri": TEST_REDIRECT_URI
    }
    
    async with httpx.AsyncClient() as client:
        # Test with form data (standard OAuth)
        print("\n1. Testing with form data")
        response = await client.post(
            f"{BASE_URL}/oauth/token",
            data=token_data
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            tokens = response.json()
            print(f"Tokens: {json.dumps(tokens, indent=2)}")
            return tokens
        else:
            print(f"Error: {response.text}")
            return None

async def test_refresh_token(refresh_token: str, client_id: str):
    """Test refresh token flow"""
    print("\n=== Testing Refresh Token ===")
    
    refresh_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/oauth/token",
            data=refresh_data
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            tokens = response.json()
            print(f"New Tokens: {json.dumps(tokens, indent=2)}")
            return tokens
        else:
            print(f"Error: {response.text}")
            return None

async def test_mcp_endpoint(access_token: str):
    """Test MCP endpoint with bearer token"""
    print("\n=== Testing MCP Endpoint ===")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    async with httpx.AsyncClient() as client:
        # Test initialize
        print("\n1. Testing initialize")
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }
        
        response = await client.post(
            f"{BASE_URL}/mcp",
            json=mcp_request,
            headers=headers
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Test tools/list
        print("\n2. Testing tools/list")
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        response = await client.post(
            f"{BASE_URL}/mcp",
            json=mcp_request,
            headers=headers
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

async def test_error_cases():
    """Test various error cases"""
    print("\n=== Testing Error Cases ===")
    
    async with httpx.AsyncClient() as client:
        # Test invalid client_id
        print("\n1. Testing invalid client_id")
        response = await client.get(
            f"{BASE_URL}/oauth/authorize?response_type=code&client_id=invalid&redirect_uri={TEST_REDIRECT_URI}"
        )
        print(f"Status: {response.status_code}")
        
        # Test missing authorization header
        print("\n2. Testing MCP without auth")
        response = await client.post(
            f"{BASE_URL}/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 401:
            print("Correctly returned 401 Unauthorized")
        
        # Test invalid grant type
        print("\n3. Testing invalid grant type")
        response = await client.post(
            f"{BASE_URL}/oauth/token",
            data={"grant_type": "invalid_grant"}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 400:
            error = response.json()
            print(f"Error response: {json.dumps(error, indent=2)}")

async def main():
    """Run all tests"""
    print("OAuth 2.0 + PKCE Flow Test Suite")
    print("=" * 50)
    
    try:
        # Test discovery
        metadata = await test_discovery()
        
        # Test client registration
        client_id = await test_client_registration()
        
        # Test authorization flow
        code_verifier, state = await test_authorization_flow(client_id)
        
        print("\n" + "="*50)
        print("MANUAL STEP REQUIRED:")
        print("1. Visit the authorization URL above")
        print("2. Enter your Oura token when prompted")
        print("3. Copy the 'code' parameter from the redirect URL")
        print("4. Run: python test_oauth_flow.py --code YOUR_CODE")
        print("="*50)
        
        # Test error cases
        await test_error_cases()
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 2 and sys.argv[1] == "--code":
        # Continue flow with provided code
        async def continue_flow():
            code = sys.argv[2]
            print(f"Continuing with code: {code}")
            
            # You'd need to store client_id and code_verifier from previous run
            # For demo purposes, re-register client
            client_id = await test_client_registration()
            
            # Generate new PKCE (in real test, load from storage)
            code_verifier, _ = generate_pkce_pair()
            
            # Exchange token
            tokens = await test_token_exchange(client_id, code, code_verifier)
            
            if tokens:
                # Test refresh
                new_tokens = await test_refresh_token(tokens["refresh_token"], client_id)
                
                # Test MCP
                await test_mcp_endpoint(tokens["access_token"])
        
        asyncio.run(continue_flow())
    else:
        asyncio.run(main())