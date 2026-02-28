#!/bin/bash
# Railway Deployment Script for Agent Manager
# Run this on your local machine with Railway CLI installed

set -e

echo "🚀 Agent Manager - Railway Deployment Script"
echo "============================================="

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found."
    echo "Install it with: npm install -g @railway/cli"
    exit 1
fi

echo "✓ Railway CLI found: $(railway --version)"

# Login to Railway
echo ""
echo "Step 1: Logging in to Railway..."
railway login

# Navigate to project directory
echo ""
echo "Step 2: Linking to Railway project..."
echo "Choose your project or create a new one"
railway link

# Deploy the application
echo ""
echo "Step 3: Deploying application..."
railway up

# Configure environment variables
echo ""
echo "Step 4: Setting environment variables..."
echo "Enter your Anthropic API key (sk-ant-...): "
read -s API_KEY
railway variables set ANTHROPIC_API_KEY="$API_KEY"

echo ""
echo "✓ Variables set:"
railway variables list

# Get the public URL
echo ""
echo "Step 5: Your app is live!"
APP_URL=$(railway domains)
echo "✓ App URL: $APP_URL"

echo ""
echo "Test endpoints:"
echo "  Dashboard:    $APP_URL"
echo "  Health:       $APP_URL/health"
echo "  API Status:   $APP_URL/api/status"
echo "  Metrics:      $APP_URL/metrics"
echo "  Logs:         railway logs --follow"

echo ""
echo "✅ Deployment complete!"
