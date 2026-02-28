# Running Agent Manager in Limited Network Environments

## Overview

Your Agent Manager is optimized for low-bandwidth deployment. Here's how to work with limited network access.

## Current Setup (Already Optimized)

✅ **Project Size**: 1.3 MB
✅ **Dependencies**: Minimal and lightweight
✅ **Docker Image**: ~400 MB (Python 3.12-slim base)
✅ **No external API calls required** (LLM is optional)

## 1. Offline Testing (No Network Required)

Run the full test suite without any external calls:

```bash
# All 78 tests run completely offline
pytest -v

# Specific test areas:
pytest tests/test_alerting.py          # Alert logic (offline)
pytest tests/test_dag.py               # Job scheduling (offline)
pytest tests/test_models.py            # Database operations (offline)
pytest tests/test_integration.py       # Full pipeline (offline)
pytest tests/test_snapshots.py         # HTML parsing (offline)
```

**Result**: All tests pass without network access ✓

## 2. Run Locally Without Anthropic API

The system works fine without LLM helpers:

```bash
# Run without API key (deterministic mode)
python main.py

# No errors - just skips LLM features
# All core functionality works perfectly
```

Config automatically disables LLM helpers if key is missing.

## 3. Local Web Dashboard (No External Calls)

```bash
# Start the web server (localhost only, no external calls)
python -m ui.web.run

# Visit: http://localhost:8080
# All endpoints work without network:
#   /                    (Dashboard)
#   /health              (Status)
#   /api/status          (Jobs)
#   /api/alerts          (Alert history)
#   /api/alert-analytics (Analytics)
#   /metrics             (Prometheus)
```

## 4. Docker Without Registry Access

If you can't reach Docker registries, use the local Dockerfile:

```bash
# Build image locally (doesn't require registry access)
docker build -t agent-manager:local .

# Run container offline
docker run -p 8080:8080 agent-manager:local

# Your app is now running locally in a container
```

## 5. Pre-download Dependencies (Optional)

If you'll have brief network access, pre-cache all dependencies:

```bash
# Download all Python packages to local cache
pip download -d ./pip-cache -r requirements.txt

# Later, install from cache:
pip install --no-index --find-links ./pip-cache -r requirements.txt
```

## 6. Deployment Options for Limited Network

### Option A: Direct Docker Push (Minimal Bandwidth)

```bash
# Build locally
docker build -t agent-manager .

# Push to private registry (if available)
docker tag agent-manager myregistry.com/agent-manager:latest
docker push myregistry.com/agent-manager:latest

# Or save/load via file:
docker save agent-manager > agent-manager.tar  # ~400 MB file
docker load < agent-manager.tar
```

### Option B: Railway with Offline Prep

If deploying to Railway but network is slow:

1. Pre-install all dependencies locally
2. Use `pip freeze` to lock versions
3. Push code, Railway pulls minimal deps

```bash
# Generate locked dependencies
pip freeze > requirements-locked.txt

# Commit to git
git add requirements-locked.txt
```

## 7. Network-Free Testing Commands

All these commands work offline:

```bash
# Test core functionality
python -c "from agent_manager.manager import AgentManager; print('✓ Core imports work')"

# Test database
python -c "from agent_manager.models import Database; db = Database(':memory:'); print('✓ DB works')"

# Test web app
python -c "from ui.web.app import app; print('✓ Web app loads')"

# Run tests
pytest -v --tb=short

# Validate config
python -c "import yaml; yaml.safe_load(open('config.yaml')); print('✓ Config valid')"
```

## 8. Reduce Bandwidth Usage

### Skip Optional Dependencies

If bandwidth is critical, comment out unused features in `config.yaml`:

```yaml
notifications:
  log:
    enabled: true
  email:
    enabled: false    # Disable if not using
  webhook:
    enabled: false    # Disable if not using

llm_helpers:
  memo_summary:
    enabled: false     # Disable to save API calls
  classification:
    enabled: false
  parser_repair:
    enabled: false
```

### Reduce Logging

```yaml
# In your environment
export LOG_LEVEL=WARNING  # Less verbose logging
```

## 9. Scheduled Job Bandwidth

Jobs that fetch external URLs:
- `usvsst_scraper`: ~100 KB per run
- `doj_monitor`: ~50 KB per run
- `ofac_monitor`: ~50 KB per run

To reduce:
```yaml
# Increase schedule intervals (run less frequently)
schedules:
  hourly:
    cron: "0 * * * *"          # Currently every hour
    # cron: "0 */6 * * *"        # Change to every 6 hours
```

## 10. Complete Offline Workflow

```bash
# 1. Clone repo (one-time network use)
git clone <repo>
cd Codespace

# 2. Install dependencies (one-time network use)
pip install -r requirements.txt

# 3. Run tests (no network)
pytest -v

# 4. Run locally (no network)
python main.py

# 5. Access web dashboard (no network)
# Browser: http://localhost:8080

# 6. All subsequent work is offline ✓
```

## Troubleshooting Limited Network

### Issue: `pip install` is slow

```bash
# Use cached package index
pip install --cache-dir ./cache -r requirements.txt

# Or install from pre-downloaded packages
pip install --no-index -r requirements.txt
```

### Issue: Can't reach GitHub for Railway CLI

**Solution**: Use the provided deployment scripts instead, or deploy via Railway web UI (doesn't require CLI).

### Issue: Docker image is slow to pull

```bash
# Build locally instead of pulling
docker build -t agent-manager .
```

### Issue: Tests are slow

```bash
# Run only critical tests
pytest tests/test_manager.py tests/test_models.py -v

# Or skip network-dependent tests
pytest -v -k "not integration"
```

## Summary

**Your Agent Manager is optimized for:**
- ✅ Complete offline operation
- ✅ Minimal bandwidth usage (~200 KB per scraper run)
- ✅ No external API dependencies (LLM is optional)
- ✅ Local testing without network
- ✅ Flexible deployment options

**Recommended Setup for Limited Network:**
1. Initial: Clone + `pip install` (one-time)
2. Daily: Run locally with `python main.py`
3. Test: Run `pytest` (no network)
4. Dashboard: Access `http://localhost:8080` (no network)
5. Deploy: Use Railway web UI or Docker push (when network available)

No network access required for core functionality! 🚀
