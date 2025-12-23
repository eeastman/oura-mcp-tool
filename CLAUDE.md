# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a focused MCP (Model Context Protocol) tool that provides **stress and resilience data** from Oura Ring devices. Built using Python 3.11 with FastAPI + FastMCP, **OAuth 2.0 protected** for deployment to the Dreamer platform.

**Purpose**: Returns actionable stress:recovery ratios and resilience context to understand why readiness might be declining.

**Security**: Full OAuth 2.0 + PKCE implementation with Dynamic Client Registration per Dreamer requirements.

## Commands

### Development
- **Run server locally**: `python src/oura_tool.py` (starts FastAPI server on port 8080)
- **Install dependencies**: `pip install -r requirements.txt` (includes FastAPI, uvicorn, PyJWT)
- **Test OAuth endpoints**: `curl http://localhost:8080/.well-known/oauth-authorization-server`
- **Test with Bearer token**: `curl -H "Authorization: Bearer token" http://localhost:8080/mcp`

### Environment Setup
Required:
- `OURA_API_TOKEN` - Personal Access Token from Oura (get from https://cloud.ouraring.com/personal-access-tokens)

Optional (with defaults):
- `AUTH_SERVER_URL` - OAuth authorization server URL  
- `TOOL_SERVER_URL` - Tool server URL for resource metadata
- `JWT_SECRET` - Secret for token signing (change in production)

## Architecture

The entire application is contained in `/src/oura_tool.py` combining OAuth server + MCP tool:

1. **FastAPI App** - Hosts both OAuth and MCP endpoints
   - OAuth Discovery endpoints (RFC 8414, RFC 9728) 
   - Dynamic Client Registration (RFC 7591)
   - Authorization + Token endpoints with PKCE
   - Protected MCP endpoint with Bearer token validation

2. **OuraAPIClient** - Handles API interactions with retry logic and error handling

3. **One MCP Tool**: `get_stress_and_resilience`
   - OAuth-protected via Bearer token validation
   - Combines data from Oura's `/daily_stress` and `/daily_resilience` endpoints
   - Calculates actionable stress:recovery ratio (e.g., 4:1 is concerning)
   - Returns resilience level with 3 contributing factors

4. **OAuth Components**:
   - In-memory storage for demo (use database in production)
   - PKCE S256 challenge validation
   - Access token lifecycle management
   - JSON-RPC MCP protocol handler

## Key Implementation Details

- Makes parallel API calls to both stress and resilience endpoints using `asyncio.gather()`
- Returns both human-readable summary and structured data
- Handles edge cases (no recovery time, missing data, API errors)
- Time formatting shows hours and minutes (e.g., "4h23m high stress")

## Response Format
Returns structured data matching this pattern:
```json
{
  "stress": {
    "highStressSeconds": 14400,
    "recoverySeconds": 3600, 
    "ratio": 4.0,
    "daySummary": "stressful"
  },
  "resilience": {
    "level": "limited",
    "contributors": {
      "sleepRecovery": 65,
      "daytimeRecovery": 42,
      "stress": 38
    }
  }
}
```

## Deployment

Uses Railway deployment (port from `PORT` env var, binds to `0.0.0.0`). See `DEPLOYMENT.md` for other platform options.