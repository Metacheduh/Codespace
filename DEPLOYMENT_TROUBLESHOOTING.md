# Deployment Troubleshooting & Root Cause Analysis

## Issue Summary

The GitHub Actions workflow was failing to deploy to Railway due to 3 critical issues:

### 1. Network Connectivity Issues ❌
**Problem:** npm couldn't reach github.com to download Railway CLI
```
FetchError: request to https://github.com/railwayapp/cli/releases/download failed
EAI_AGAIN: getaddrinfo github.com
```

**Root Cause:** GitHub Actions runner had network restrictions preventing external downloads.

**Solution:** ✅ Use Railway's native GitHub Action instead of CLI

---

### 2. Missing RAILWAY_TOKEN Secret ❌
**Problem:** The workflow references `secrets.RAILWAY_TOKEN` but it's never configured in GitHub

**Solution:** ✅ Set up the secret in GitHub (see below)

---

### 3. Missing Project Context ❌
**Problem:** Railway CLI didn't know which project to deploy to (no `.railway` metadata in git)

**Solution:** ✅ Official Railway Action handles this automatically with RAILWAY_TOKEN

---

## Fixed Workflow

The GitHub Actions workflow has been updated to use `railwayapp/deploy-action@v1`:

```yaml
- name: Deploy to Railway
  uses: railwayapp/deploy-action@v1
  with:
    token: ${{ secrets.RAILWAY_TOKEN }}
    service: agent-manager-web
```

This approach:
- ✅ Doesn't require npm or CLI installation
- ✅ Uses official Railway infrastructure
- ✅ Is more reliable and faster
- ✅ Handles project context automatically

---

## What You Need To Do

### Step 1: Get Your Railway Token

```bash
# On your local machine with Railway CLI installed:
railway login
railway tokens create
```

Copy the token (looks like: `eyJhbGc...`)

### Step 2: Add Secret to GitHub

1. Go to your GitHub repo
2. **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `RAILWAY_TOKEN`
5. Value: Paste your Railway token
6. Click **Add secret**

### Step 3: Verify Deployment

```bash
# Push a commit to trigger the workflow
git commit --allow-empty -m "Trigger Railway deployment"
git push origin claude/deterministic-agent-manager-YfZXd
```

Then:
1. Go to GitHub **Actions** tab
2. Watch "Deploy to Railway" workflow run
3. Check Railway dashboard for successful deployment

---

## Checking Railway Token Status

**To verify your Railway project is linked:**

```bash
# Locally:
railway info
```

**To get your Railway token:**

```bash
railway tokens list  # View all tokens
railway tokens create  # Create a new one
```

---

## Common Issues After Fix

### Workflow Still Failing?

```bash
# Check if RAILWAY_TOKEN secret is set (GitHub UI shows "configured")
# Re-push a commit to trigger the workflow
git commit --allow-empty -m "Retry deployment"
git push origin claude/deterministic-agent-manager-YfZXd
```

### Deployment Successful but App Doesn't Start?

1. Check Railway logs: `railway logs --follow`
2. Verify environment variables: `railway variables list`
3. Ensure ANTHROPIC_API_KEY is set

### Port Issues?

The app listens on:
- **Port:** 8080 (configured in railway.toml)
- **Health check:** /health (configured in railway.toml)

---

## Verifying the Deployment

Once deployed successfully:

```bash
# Get your Railway app URL
railway domains

# Test the app:
curl https://your-app-url.railway.app/health
curl https://your-app-url.railway.app/api/status
```

---

## Next Steps

1. ✅ Set RAILWAY_TOKEN in GitHub Secrets
2. ✅ Push code to trigger auto-deployment
3. ✅ Verify in GitHub Actions that it succeeds
4. ✅ Check Railway dashboard for live app
5. ✅ Add ANTHROPIC_API_KEY to Railway environment variables

**Your deployment is now automated!** Every push to the branch will auto-deploy. 🚀
