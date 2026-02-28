#!/bin/bash
# Local deployment script for limited network environments
# Runs Agent Manager locally without requiring cloud services or network

set -e

echo "🚀 Agent Manager - Local Deployment"
echo "===================================="
echo ""
echo "This script sets up Agent Manager for local development"
echo "No internet connection required after initial setup"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION found"

# Check dependencies are installed
echo ""
echo "Checking dependencies..."
python3 -c "
import sys
required = ['yaml', 'fastapi', 'uvicorn', 'bs4', 'prometheus_client', 'pythonjsonlogger']
missing = []
for pkg in required:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)

if missing:
    print(f'❌ Missing packages: {missing}')
    print('Run: pip install -r requirements.txt')
    sys.exit(1)
else:
    print('✓ All dependencies installed')
"

# Create data directory
echo ""
echo "Setting up local database..."
mkdir -p data
echo "✓ Data directory created"

# Run tests
echo ""
echo "Running test suite (no network required)..."
python3 -m pytest -v --tb=short -q
if [ $? -eq 0 ]; then
    echo "✓ All tests passed"
else
    echo "❌ Tests failed"
    exit 1
fi

# Start the application
echo ""
echo "🎉 Starting Agent Manager..."
echo ""
echo "Web Dashboard: http://localhost:8080"
echo "Health Check:  http://localhost:8080/health"
echo "API Status:    http://localhost:8080/api/status"
echo "Metrics:       http://localhost:8080/metrics"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the web server
python3 -m ui.web.run
