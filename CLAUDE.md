# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a focused MCP (Model Context Protocol) tool that provides **stress and resilience data** from Oura Ring devices. Built using Python 3.11 and FastMCP framework, designed for deployment to the Dreamer platform.

**Purpose**: Returns actionable stress:recovery ratios and resilience context to understand why readiness might be declining.

## Commands

### Development
- **Run server locally**: `python src/oura_tool.py`
- **Install dependencies**: `pip install -r requirements.txt`
- **Test with MCP Inspector**: `npx @modelcontextprotocol/inspector http://localhost:8080/mcp`

### Environment Setup
Required environment variable:
- `OURA_API_TOKEN` - Personal Access Token from Oura (get from https://cloud.ouraring.com/personal-access-tokens)

## Architecture

The entire application is contained in `/src/oura_tool.py` with a single-tool focus:

1. **OuraAPIClient** - Handles API interactions with retry logic and error handling
2. **One MCP Tool**: `get_stress_and_resilience`
   - Combines data from Oura's `/daily_stress` and `/daily_resilience` endpoints
   - Calculates actionable stress:recovery ratio (e.g., 4:1 is concerning)
   - Returns resilience level with 3 contributing factors
   - Defaults to today's date if none specified

3. **Helper Functions**:
   - `calculate_stress_ratio()` - Handles division by zero and computes ratio
   - `get_day_summary_description()` - Maps ratio to human-readable categories
   - `get_resilience_level()` - Categorizes resilience based on contributor scores

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