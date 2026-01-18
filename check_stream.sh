#!/bin/bash

echo "======================================"
echo "Check Riftech Security V2 Service"
echo "======================================"
echo ""

# Check service status
echo "1. Service Status:"
sudo systemctl status riftech-security-v2 --no-pager -l
echo ""

# Check stream endpoint
echo "2. Stream Endpoint Check:"
curl -I http://localhost:8000/api/stream 2>&1 | head -5
echo ""

# Check if port 8000 is listening
echo "3. Port 8000 Status:"
sudo netstat -tlnp | grep :8000 || echo "Port 8000 not listening"
echo ""

# Check recent logs
echo "4. Recent Logs (last 20 lines):"
sudo journalctl -u riftech-security-v2 -n 20 --no-pager
echo ""

# Check if process is running
echo "5. Running Processes:"
ps aux | grep -E "(python|security|web_server)" | grep -v grep
echo ""
