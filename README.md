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
   cp .env.example .env
   # Edit .env and add your Oura API token
   ```

3. Get your Oura API token:
   - Go to [Oura Cloud](https://cloud.ouraring.com/personal-access-tokens)
   - Create a new personal access token
   - Copy the token to your `.env` file

## Development

Run the MCP server locally:

```bash
python src/oura_tool.py
```

The server will start on `http://localhost:8080/mcp`

## Testing

Test your tool locally using the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector http://localhost:8080/mcp
```

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