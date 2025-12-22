# Deployment Guide for Oura MCP Tool

This guide covers multiple deployment options for your Oura MCP tool.

## Prerequisites

Before deploying, you'll need:
1. Your Oura API token from https://cloud.ouraring.com/personal-access-tokens
2. The deployment files already added to your repository

## Option 1: Railway (Recommended - Easiest)

Railway offers the simplest deployment with automatic HTTPS and minimal configuration.

### Steps:

1. **Sign up at Railway**: Go to https://railway.app and sign in with GitHub

2. **Create new project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose `oura-mcp-tool`

3. **Add environment variable**:
   - Go to your project settings
   - Click on "Variables"
   - Add: `OURA_API_TOKEN` = `your_oura_api_token_here`
   - Railway will automatically set `PORT`

4. **Deploy**:
   - Railway will automatically deploy your app
   - You'll get a URL like `https://oura-mcp-tool-production.up.railway.app`

5. **Get your MCP endpoint**:
   - Your MCP endpoint will be: `https://your-app-name.up.railway.app/mcp`

## Option 2: Render

Render is another easy platform with free tier options.

### Steps:

1. **Sign up at Render**: Go to https://render.com

2. **Create a new Web Service**:
   - Click "New +"
   - Select "Web Service"
   - Connect your GitHub account
   - Select the `oura-mcp-tool` repository

3. **Configure the service**:
   - Name: `oura-mcp-tool`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python src/oura_tool.py`

4. **Add environment variable**:
   - Add `OURA_API_TOKEN` with your token value

5. **Deploy**: Click "Create Web Service"

## Option 3: Fly.io

Fly.io offers global deployment with good free tier.

### Steps:

1. **Install Fly CLI**:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Sign up and login**:
   ```bash
   fly auth signup
   # or if you have an account
   fly auth login
   ```

3. **Create fly.toml** (already in your repo):
   ```toml
   app = "oura-mcp-tool-yourusername"
   primary_region = "ord"

   [build]
     dockerfile = "Dockerfile"

   [env]
     PORT = "8080"

   [[services]]
     protocol = "tcp"
     internal_port = 8080
     
     [[services.ports]]
       port = 80
       handlers = ["http"]
       
     [[services.ports]]
       port = 443
       handlers = ["tls", "http"]
   ```

4. **Deploy**:
   ```bash
   fly launch
   # Follow the prompts, say yes to create app
   
   # Set your secret
   fly secrets set OURA_API_TOKEN=your_token_here
   
   # Deploy
   fly deploy
   ```

## Option 4: Google Cloud Run

For a more scalable solution with pay-per-use pricing.

### Steps:

1. **Install Google Cloud CLI**: https://cloud.google.com/sdk/docs/install

2. **Authenticate and set project**:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

3. **Enable Cloud Run**:
   ```bash
   gcloud services enable run.googleapis.com
   ```

4. **Build and deploy**:
   ```bash
   # Build the container
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/oura-mcp-tool

   # Deploy to Cloud Run
   gcloud run deploy oura-mcp-tool \
     --image gcr.io/YOUR_PROJECT_ID/oura-mcp-tool \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars OURA_API_TOKEN=your_token_here
   ```

## Option 5: Heroku

If you have a Heroku account (no longer has free tier).

### Steps:

1. **Install Heroku CLI**: https://devcenter.heroku.com/articles/heroku-cli

2. **Create Heroku app**:
   ```bash
   heroku create oura-mcp-tool-yourusername
   ```

3. **Set environment variable**:
   ```bash
   heroku config:set OURA_API_TOKEN=your_token_here
   ```

4. **Deploy**:
   ```bash
   git push heroku master
   ```

## Post-Deployment Steps

After deploying to any platform:

1. **Test your endpoint**:
   ```bash
   curl -X POST https://your-deployed-url/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "method": "initialize", "id": 1}'
   ```

2. **Register with Dreamer**:
   - Go to Dreamer's Tools section
   - Add Custom Tool
   - Enter your deployed URL: `https://your-deployed-url/mcp`
   - Complete the verification process

## Security Considerations

1. **Never commit your API token** - Always use environment variables
2. **Use HTTPS** - All platforms above provide HTTPS by default
3. **Consider adding rate limiting** if you plan to share the tool
4. **Monitor usage** to avoid unexpected costs

## Troubleshooting

### Tool not responding
- Check logs in your deployment platform
- Verify OURA_API_TOKEN is set correctly
- Ensure PORT environment variable is being read

### CORS errors
- The tool already includes CORS headers for all origins
- If issues persist, check if your platform adds additional restrictions

### Memory issues
- The tool is lightweight, but if you see memory errors:
  - Increase memory limits in your platform settings
  - Consider implementing response pagination for large data sets

## Cost Estimates

- **Railway**: Free tier includes 500 hours/month (~$5/month after)
- **Render**: Free tier with spin-down after 15 min inactivity
- **Fly.io**: Free tier includes 3 shared VMs
- **Google Cloud Run**: Free tier includes 2 million requests/month
- **Heroku**: Starts at $7/month for hobby dyno

Choose based on your needs for uptime, performance, and budget!