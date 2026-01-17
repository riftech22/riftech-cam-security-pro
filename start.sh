#!/bin/bash
# Quick start script for Riftech Security System (Security System Only)

set -e

echo "============================================================"
echo "  Riftech Security System - Security System Only"
echo "============================================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run install.sh first."
    exit 1
fi

# Activate virtual environment
echo "✓ Activating virtual environment..."
source venv/bin/activate

# Check if config exists
if [ ! -f "config/config.yaml" ]; then
    echo ""
    echo "❌ Configuration file not found!"
    echo "Creating from example..."
    cp config/config.yaml.example config/config.yaml
    echo ""
    echo "⚠️  Please edit config/config.yaml with your settings."
    echo "Then run start.sh again."
    exit 1
fi

# Check if main entry point exists
if [ -f "main.py" ]; then
    MAIN_FILE="main.py"
elif [ -f "src/security_system.py" ]; then
    MAIN_FILE="src/security_system.py"
else
    echo "❌ Could not find security system entry point!"
    echo "Looking for main.py or src/security_system.py"
    exit 1
fi

# Start security system
echo ""
echo "✓ Starting Riftech Security System..."
echo "  - Mode: Security System Only (AI Detection)"
echo "  - For Web Interface: ./start-web.sh"
echo ""
echo "⚠️  Press Ctrl+C to stop"
echo ""

python3 $MAIN_FILE
