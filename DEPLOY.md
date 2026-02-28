# Deployment Guide

## Overview

The Agent Manager runs via launchd on macOS, executing `main.py` every 60 seconds.

## Installation Steps

### 1. Set up log directory

```bash
mkdir -p ~/.agent_manager
touch ~/.agent_manager/agent_manager.log
```

### 2. Clone / locate the repository

The code is at: `/home/user/Codespace`

### 3. Install dependencies

```bash
cd /home/user/Codespace
pip install -r requirements.txt
```

### 4. Create launchd plist

Replace `__INSTALL_PATH__` and `__HOME__` in `com.agent-manager.plist`:

```bash
INSTALL_PATH="/home/user/Codespace"
HOME_DIR="$HOME"

sed "s|__INSTALL_PATH__|${INSTALL_PATH}|g; s|__HOME__|${HOME_DIR}|g" com.agent-manager.plist > ~/Library/LaunchAgents/com.agent-manager.deterministic.plist
```

### 5. Load the launchd agent

```bash
launchctl load ~/Library/LaunchAgents/com.agent-manager.deterministic.plist
```

## Where to See It Running

### View logs:
```bash
# Main application log (all jobs, alerts, etc.)
tail -f ~/.agent_manager/agent_manager.log

# launchd stdout/stderr
tail -f ~/.agent_manager/launchd.out
tail -f ~/.agent_manager/launchd.err
```

### Check launchd status:
```bash
launchctl list | grep agent-manager
```

### Manually test the manager:
```bash
cd /home/user/Codespace
python3 main.py
```

### View the database:
```bash
sqlite3 data/agent_manager.db
sqlite> SELECT job_name, status, COUNT(*) FROM job_runs GROUP BY job_name, status;
sqlite> SELECT rule_name, severity, message FROM alerts ORDER BY created_at DESC LIMIT 10;
```

## Database Location

All data is stored at: `/home/user/Codespace/data/agent_manager.db`

The database tracks:
- Job runs (status, timestamps, errors)
- Snapshots (raw HTML from scraped sources)
- Fund balances & qualifying cases (USVSST)
- Confirmed deposits (ONLY from USVSST postings)
- Articles (DOJ / OFAC)
- DPI scores
- Alerts (with deterministic evidence trails)
- Memos (optional LLM-generated narratives)

## Troubleshooting

### Manager not running
```bash
# Check launchd status
launchctl list | grep agent-manager

# Load it manually if needed
launchctl load ~/Library/LaunchAgents/com.agent-manager.deterministic.plist

# Check for errors in logs
tail -f ~/.agent_manager/launchd.err
```

### Manual execution
```bash
cd /home/user/Codespace
python3 main.py
```

### Debugging
Edit `main.py` to add `logging.DEBUG` level, or inspect the SQLite database directly:
```bash
sqlite3 data/agent_manager.db ".schema"
```

## Unload / Stop

```bash
launchctl unload ~/Library/LaunchAgents/com.agent-manager.deterministic.plist
```
