# Oura MCP Tool

An MCP-compatible tool for accessing Oura Ring health data through the Dreamer platform.

## Features

This tool provides access to various Oura health metrics:
- Sleep data and analysis
- Daily activity metrics
- Heart rate and HRV data
- Readiness scores
- Temperature trends

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

## Available Tools

- `get_sleep_data`: Retrieve sleep data for a date range
- `get_activity_data`: Get daily activity metrics
- `get_readiness_data`: Access readiness scores
- `get_heart_rate_data`: Fetch heart rate and HRV data
- `get_personal_info`: Get user profile information

## License

MIT