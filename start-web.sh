#!/bin/bash
# Start Riftech Security System Web Server

set -e

echo "============================================================"
echo "  Riftech Security System - Web Server"
echo "============================================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found!"
    echo "Please run install.sh first."
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if config exists
if [ ! -f "config/config.yaml" ]; then
    echo ""
    echo "Configuration file not found!"
    echo "Creating from example..."
    cp config/config.yaml.example config/config.yaml
    echo ""
    echo "Please edit config/config.yaml with your settings."
    echo "Then run start-web.sh again."
    exit 1
fi

# Install/update web server dependencies
echo ""
echo "Checking web server dependencies..."
pip install -q fastapi uvicorn[standard] websockets python-jose[cryptography] passlib[bcrypt] pydantic python-multipart

# Start web server
echo ""
echo "Starting Riftech Security System Web Server..."
echo "Web Interface: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo ""

# Start web server with uvicorn
python3 -m uvicorn src.api.web_server:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    --access-log
