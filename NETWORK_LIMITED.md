# Quick Start: Limited Network Environment

If you have restricted internet access, follow this guide.

## TL;DR (30 seconds)

```bash
# If you have network access ONCE:
pip install -r requirements.txt

# Then all of this works OFFLINE:
pytest -v                          # Run all tests
python main.py                     # Run the manager
python -m ui.web.run               # Start web dashboard at http://localhost:8080
```

## Step-by-Step (Limited Network)

### Step 1: Install Dependencies (Requires Network ONCE)

```bash
pip install -r requirements.txt
```

After this, everything runs **offline forever**.

### Step 2: Test Everything Works (NO NETWORK NEEDED)

```bash
# Run full test suite
pytest -v

# Expected: 78 tests pass
```

### Step 3: Run Locally (NO NETWORK NEEDED)

**Option A: Run the manager (background job)**
```bash
python main.py
```

**Option B: Run the web dashboard**
```bash
python -m ui.web.run
# Then open: http://localhost:8080
```

**Option C: Run both in separate terminals**
```bash
# Terminal 1:
python main.py

# Terminal 2:
python -m ui.web.run
```

## What Works Without Network?

✅ **All job execution** (completely local)
- Fund balance tracking
- Qualifying case detection
- DPI calculation
- Alert generation

✅ **All API endpoints**
- Dashboard (`/`)
- Status (`/api/status`)
- Alerts (`/api/alerts`)
- Analytics (`/api/alert-analytics`)
- Metrics (`/metrics`)
- Health check (`/health`)

✅ **All 78 tests** pass offline

❌ **External data fetching** (requires network)
- USVSST website scraping
- DOJ press releases
- OFAC sanctions list

❌ **LLM helpers** (requires network + API key)
- Memo summarization
- Alert classification
- Parser repair

## What Requires Network?

Only if you enable these features in `config.yaml`:

```yaml
jobs:
  usvsst_scraper:
    # ... requires network to fetch from website

  doj_monitor:
    # ... requires network to fetch from website

  ofac_monitor:
    # ... requires network to fetch from website

llm_helpers:
  memo_summary:
    enabled: false  # Set to true = requires API + network
```

## Working Completely Offline

**Disable external data sources:**

```yaml
# Edit config.yaml
jobs:
  usvsst_scraper:
    description: "Disabled for offline testing"
    # Comment out or remove all configuration

  doj_monitor:
    # Disabled

  ofac_monitor:
    # Disabled

llm_helpers:
  memo_summary:
    enabled: false
  classification:
    enabled: false
  parser_repair:
    enabled: false
```

Now run:
```bash
python main.py      # Completely offline
python -m ui.web.run  # Completely offline
pytest -v           # All tests pass offline
```

## Testing Core Features (Offline)

```bash
# Test database operations
pytest tests/test_models.py -v

# Test alert rules
pytest tests/test_alerting.py -v

# Test job scheduling
pytest tests/test_dag.py -v

# Test state machine
pytest tests/test_state_machine.py -v

# Test integration
pytest tests/test_integration.py -v

# All work offline
```

## Deployment for Limited Network

### Option 1: Docker (Needs Network Once)

```bash
# Build image locally (no registry access needed)
docker build -t agent-manager .

# Run container
docker run -p 8080:8080 agent-manager

# Then access: http://localhost:8080
```

### Option 2: Raw Python

```bash
python -m ui.web.run
# Then access: http://localhost:8080
```

### Option 3: Save/Transfer via USB/File

```bash
# On connected machine:
docker build -t agent-manager .
docker save agent-manager > agent-manager.tar  # ~400 MB

# Transfer agent-manager.tar to limited-network machine

# On limited-network machine:
docker load < agent-manager.tar
docker run -p 8080:8080 agent-manager
```

## Bandwidth Usage (If You Have Some)

| Feature | Size | Frequency | Total/Day |
|---------|------|-----------|-----------|
| USVSST scraper | 100 KB | Hourly | ~2.4 MB |
| DOJ monitor | 50 KB | Every 6h | ~200 KB |
| OFAC monitor | 50 KB | Daily | ~50 KB |
| Health checks | 1 KB | Every 15 min | ~1.4 MB |
| **Total** | | | **~4 MB/day** |

Very lightweight! You can disable jobs in config to use even less.

## Troubleshooting

### "No module named 'fastapi'"

```bash
# Need to install dependencies (requires network once)
pip install -r requirements.txt
```

### "pytest not found"

```bash
# Install dev dependencies
pip install pytest
```

### "Can't reach external websites"

Expected! Disable these in `config.yaml`:
- `usvsst_scraper`
- `doj_monitor`
- `ofac_monitor`

Core features still work.

### "Need to deploy to cloud"

If network limited, use local Docker:
```bash
docker build -t agent-manager .
docker run -p 8080:8080 agent-manager
```

For cloud: Use Railway web UI (no CLI needed), or save Docker image and transfer.

## Summary

**Minimum Network Use:**
- 1 × `pip install` (one-time, can cache)
- 0 × Monthly operations

**Completely Offline:**
- Job execution
- Alert generation
- Web dashboard
- Testing
- Local monitoring

**Your system is optimized for limited bandwidth!** 🎯
