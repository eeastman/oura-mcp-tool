# Oura Stress & Resilience MCP Tool

An MCP-compatible tool for accessing Oura Ring stress and resilience data through the Dreamer platform.

## What it does

Returns today's **stress load** (time spent in high stress vs. high recovery) and **resilience level** with its 3 contributors: sleep recovery, daytime recovery, and overall stress load.

## Why it matters

Readiness tells you what your capacity is today. Stress and Resilience tell you **why** it might be declining. If someone has low readiness, is it because they slept poorly? Or because they've been running at a 4:1 stress-to-recovery ratio all week and aren't getting any daytime rest?

## Tool Response Format

```json
{
  "stress": {
    "highStressSeconds": 14400,   // 4 hours
    "recoverySeconds": 3600,       // 1 hour  
    "ratio": 4.0,                   // stress:recovery
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

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up your environment variables:
   ```bash
   # Required
   OURA_API_TOKEN=your_oura_api_token_here
   
   # OAuth Configuration (optional - defaults provided)
   AUTH_SERVER_URL=https://your-auth-server.com
   TOOL_SERVER_URL=https://your-tool-server.com
   JWT_SECRET=your-super-secret-key-change-this-in-production
   ```

3. Get your Oura API token:
   - Go to [Oura Cloud](https://cloud.ouraring.com/personal-access-tokens)
   - Create a new personal access token
   - Add it to your environment variables

## Development

Run the OAuth-protected MCP server locally:

```bash
python src/oura_tool.py
```

The server will start on `http://localhost:8080` with these endpoints:

- **OAuth Discovery**: `/.well-known/oauth-authorization-server`
- **Protected Resource**: `/.well-known/oauth-protected-resource` 
- **MCP Endpoint**: `/mcp` (requires Bearer token)
- **Health Check**: `/health`

## OAuth 2.0 Protection

This tool is protected with OAuth 2.0 + PKCE for Dreamer platform integration:

- **Dynamic Client Registration** (RFC 7591)
- **Authorization Server Metadata** (RFC 8414) 
- **Protected Resource Metadata** (RFC 9728)
- **PKCE with S256** for secure authorization
- **Bearer token validation** for all MCP requests

## Testing

### Local Testing (OAuth Protected)

1. **Get an access token** via OAuth flow
2. **Test with Bearer token**:

```bash
curl -H "Authorization: Bearer your_token_here" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/list","id":1}' \
     http://localhost:8080/mcp
```

### Dreamer Platform Integration

When registering with Dreamer:
1. Deploy your server publicly
2. Dreamer automatically discovers OAuth metadata
3. Users authenticate via OAuth flow
4. All subsequent MCP calls include Bearer tokens

## Deployment

This tool can be deployed to any platform that supports Python web applications:
- Railway
- Render
- Fly.io
- AWS Lambda
- Google Cloud Functions

Make sure to set the `OURA_API_TOKEN` environment variable in your deployment platform.

## Available Tool

- `get_stress_and_resilience`: Get stress load and resilience data for a specific date (defaults to today)

### Key Features
- **Actionable ratio**: Computing stress:recovery ratio (4:1 is concerning) rather than raw seconds
- **Combined data**: Merges Oura's separate `/daily_stress` and `/daily_resilience` endpoints into one call
- **Smart defaults**: Uses today's date if none specified  
- **Resilience context**: Shows the 3 contributing factors that explain capacity changes

## License

MIT

<!-- Force deployment refresh -->