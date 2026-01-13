# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a focused MCP (Model Context Protocol) tool that provides **stress, resilience, and readiness data** from Oura Ring devices. Built using Python 3.11 with FastAPI + FastMCP, **OAuth 2.0 protected** for deployment to the Dreamer platform.

**Purpose**: Returns actionable health metrics including stress:recovery ratios, resilience context, readiness scores with contributor breakdown, and detailed sleep quality data to understand what's affecting your wellness.

**Security**: Full OAuth 2.0 + PKCE implementation with Dynamic Client Registration per Dreamer requirements.

## Commands

### Development
- **Run server locally**: `python main.py` or `python src/oura_tool.py` (starts FastAPI server on port 8080)
- **Install dependencies**: `pip install -r requirements.txt` (includes FastAPI, uvicorn, PyJWT, httpx, aiosqlite)
- **Test OAuth endpoints**: `curl http://localhost:8080/.well-known/oauth-authorization-server`
- **Test with Bearer token**: `curl -H "Authorization: Bearer token" http://localhost:8080/mcp`
- **Test with MCP Inspector**: `npx @modelcontextprotocol/inspector http://localhost:8080/mcp`
- **Test persistence**: `python test_persistence.py` (tests token persistence across restarts)

### Environment Setup
Required:
- `OURA_API_TOKEN` - Personal Access Token from Oura (get from https://cloud.ouraring.com/personal-access-tokens)

Optional (with defaults):
- `AUTH_SERVER_URL` - OAuth authorization server URL  
- `TOOL_SERVER_URL` - Tool server URL for resource metadata
- `JWT_SECRET` - Secret for token signing (change in production)
- `STORAGE_TYPE` - Storage backend: "sqlite" (default) or "memory" (for testing)
- `SQLITE_DB_PATH` - Path to SQLite database (default: "data/tokens.db")

## Architecture

The application follows a modular structure for better maintainability and reusability:

```
oura_tool/
├── main.py                      # Entry point for deployment
├── src/
│   ├── oura_tool.py            # Main FastAPI app and MCP endpoints
│   ├── auth/
│   │   ├── oauth_server.py     # OAuth 2.0 implementation with persistent storage
│   │   ├── storage.py          # Storage interface and implementations
│   │   └── storage_wrapper.py  # Dictionary-like wrapper for storage
│   └── tools/
│       ├── oura_client.py      # Oura API client (reusable)
│       ├── stress_resilience.py # Stress & resilience tool logic
│       ├── readiness.py        # Readiness score tool logic
│       ├── sleep_quality.py    # Sleep quality tool logic
│       └── trends.py           # Multi-day trends tool logic
├── data/                        # SQLite database directory (gitignored)
```

### Key Components:

1. **OAuth Module** (`src/auth/oauth_server.py`)
   - OAuth Discovery endpoints (RFC 8414, RFC 9728) 
   - Dynamic Client Registration (RFC 7591)
   - Authorization + Token endpoints with PKCE
   - Token validation logic
   - Persistent storage using SQLite (via storage abstraction)
   - Automatic cleanup of expired tokens (runs hourly)

2. **Oura API Client** (`src/tools/oura_client.py`)
   - Handles all Oura API interactions
   - Retry logic and error handling
   - Supports multiple endpoints (stress, resilience, sleep, activity, readiness)
   - Reusable for other Oura-based tools

3. **MCP Tools**
   - **Stress & Resilience** (`src/tools/stress_resilience.py`)
     - `get_stress_and_resilience` function
     - Combines data from `/daily_stress` and `/daily_resilience` endpoints
     - Calculates actionable stress:recovery ratio
     - Returns resilience level with contributing factors
   - **Readiness** (`src/tools/readiness.py`)
     - `get_readiness` function
     - Fetches data from `/daily_readiness` endpoint
     - Returns overall readiness score (0-100)
     - Provides 8 individual contributor scores
     - Identifies limiting factors (contributors < 70)
   - **Sleep Quality** (`src/tools/sleep_quality.py`)
     - `get_sleep_quality` function
     - Combines data from `/daily_sleep` and `/sleep` endpoints
     - Returns overall sleep score (0-100)
     - Provides 7 contributor scores (deepSleep, remSleep, efficiency, latency, restfulness, timing, totalSleep)
     - Includes sleep stage durations (total, deep, rem, light, awake) in seconds
     - Includes bedtime timestamps (start and end)
     - Identifies limiting factors (contributors < 70)
   - **Trends** (`src/tools/trends.py`)
     - `get_trends` function
     - Fetches multi-day data from `/daily_readiness`, `/daily_sleep`, and `/sleep` endpoints
     - Returns 7-day trends (configurable 3-30 days) for:
       - Readiness scores with direction and baseline comparison
       - HRV averages with direction and baseline comparison
       - Body temperature deviation with special pattern detection
       - Sleep scores with direction and baseline comparison
     - Pre-computes direction: "rising", "declining", "stable", "elevatedThenRecovering"
     - Compares current period to 30-day baseline (changeVsBaseline %)

4. **Main App** (`src/oura_tool.py`)
   - FastAPI app setup
   - MCP endpoint handlers
   - Minimal glue code (~340 lines, down from 921)

## Key Implementation Details

- Modular architecture allows easy addition of new tools
- OAuth module is completely reusable for other MCP tools
- Oura API client can be used for any Oura-based tools (sleep, activity, etc.)
- Returns both human-readable summary and structured data
- Handles edge cases (no recovery time, missing data, API errors)
- Time formatting shows hours and minutes (e.g., "4h 23m high stress")
- Uses Oura's resilience level directly (e.g., "solid", "limited") instead of calculating

### Persistent Storage
- Tokens and OAuth data stored in SQLite database (data/tokens.db)
- Survives server restarts - no loss of authentication state
- Automatic cleanup of expired tokens runs hourly
- Storage abstraction allows future migration to Redis if needed
- In-memory storage option available for testing

## Response Format
Returns MCP-formatted response with both human-readable and structured data:
```json
{
  "content": [
    {
      "type": "text",
      "text": "Stress: 4h, Recovery: 1h (ratio: 4.0:1)"
    }
  ],
  "structuredContent": {
    "date": "2025-12-27",
    "stress": {
      "highStressSeconds": 14400,
      "recoverySeconds": 3600, 
      "ratio": 4.0
    },
    "resilience": {
      "level": "solid",
      "contributors": {
        "sleepRecovery": 65.8,
        "daytimeRecovery": 42.1,
        "stress": 38.5
      }
    }
  },
  "isError": false
}
```

## Testing

### Local Development
1. Set `OURA_API_TOKEN` environment variable with your Oura token
2. Run `python main.py` to start the server
3. Test with MCP Inspector: `npx @modelcontextprotocol/inspector http://localhost:8080/mcp`
   - Auth is bypassed for MCP Inspector in development
   - Test various dates and error cases
   - Verify response format matches schema

### Adding New Tools
1. Create a new file in `src/tools/` (e.g., `sleep_tracker.py`)
2. Import and use the `OuraAPIClient` from `oura_client.py`
3. Add new MCP endpoint handler in `src/oura_tool.py`
4. OAuth protection is automatic via the existing setup

## Deployment

- **Entry point**: `python main.py` (configured in `railway.json`)
- Uses Railway deployment (port from `PORT` env var, binds to `0.0.0.0`)
- OAuth is required in production (remove test mode bypass)
- See `DEPLOYMENT.md` for other platform options