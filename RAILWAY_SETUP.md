# Railway Cloud Deployment Guide

## Prerequisites

- Railway account (https://railway.app)
- Node.js 16+ installed locally
- Railway CLI installed: `npm install -g @railway/cli`

## Quick Setup (5 minutes)

### Step 1: Install Railway CLI (Local Machine)

```bash
npm install -g @railway/cli
```

### Step 2: Authenticate with Railway

```bash
railway login
```

This opens a browser for authentication. Complete the login flow.

### Step 3: Link Your Project

Navigate to your Codespace directory and run:

```bash
cd /path/to/Codespace
railway link
```

Choose "Create a new project" or select an existing one.

### Step 4: Deploy Your App

```bash
railway up
```

Railway will:
- Detect the Dockerfile
- Build your image
- Deploy to Railway's infrastructure
- Give you a public URL

### Step 5: Set Environment Variables

```bash
# Set the Anthropic API key (replace with your actual key)
railway variables set ANTHROPIC_API_KEY="sk-ant-YOUR-ACTUAL-API-KEY-HERE"

# Verify it was set
railway variables list
```

### Step 6: View Your Live App

```bash
# Open in browser
railway open

# Or get just the URL
railway domains
```

Your app is now live! Example URL:
```
https://agent-manager-production.up.railway.app
```

## Testing Your Deployment

Once live, test these endpoints:

```bash
# Replace with your actual Railway URL
RAILWAY_URL="https://agent-manager-production.up.railway.app"

# Health check
curl $RAILWAY_URL/health

# API Status
curl $RAILWAY_URL/api/status

# Metrics
curl $RAILWAY_URL/metrics

# View logs
railway logs --follow
```

## Useful Railway CLI Commands

```bash
# View all environment variables
railway variables list

# Update a variable
railway variables set VAR_NAME="new_value"

# View logs in real-time
railway logs --follow

# Check deployment status
railway status

# Redeploy after changes
railway up

# View project info
railway info

# Delete deployment
railway delete
```

## Database Persistence

Your SQLite database is stored in `/app/data/agent_manager.db` within the container.

**Important:** Railway containers are ephemeral by default. To persist data permanently:

1. Go to Railway dashboard
2. Click your project → "Volumes"
3. Create a volume for `/app/data`
4. Mount it to the service

Or use Railway's Postgres service (optional):

```bash
# Add Postgres
railway add postgres

# Update config.yaml to use DATABASE_URL environment variable
```

## IMPORTANT: Rotate Your API Key

Since you've shared your API key above, **rotate it immediately** for security:

1. Go to https://console.anthropic.com/account/keys
2. Click the three dots on your key → **Revoke**
3. Create a **new API key**
4. Update Railway:
   ```bash
   railway variables set ANTHROPIC_API_KEY="your-new-key-here"
   ```

## Troubleshooting

### Deployment fails

```bash
# Check logs for errors
railway logs --follow

# Rebuild and redeploy
railway up --force
```

### Environment variables not being used

```bash
# Verify variables are set
railway variables list

# Restart the service
railway status
# Then redeploy
railway up
```

### Port issues

The app listens on the PORT environment variable (set by Railway) or defaults to 8080. This is configured in `ui/web/run.py`.

### Database not persisting

Create a volume in Railway dashboard and mount to `/app/data`.

## Next Steps

1. Run `./deploy-railway.sh` or follow steps above
2. Test all endpoints from your Railway URL
3. Monitor logs and metrics
4. Rotate your Anthropic API key

## Support

- Railway Docs: https://docs.railway.app
- Railway Status: https://status.railway.app
- Your Project: `railway open`

---

**Your Agent Manager is now production-ready on Railway!** 🚀
