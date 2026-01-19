#!/bin/bash

echo "======================================"
echo "Increase Capture FPS to 15"
echo "======================================"
echo ""

# Check current config
echo "Current detect_fps in config:"
grep "detect_fps:" config/config.yaml
echo ""

echo "======================================"
echo "Quick Fix: Increase FPS to 15"
echo "======================================"
echo ""

echo "This will:"
echo "  - Increase detect_fps from 5 to 15 in config"
echo "  - Update FFmpeg to use fps=15"
echo "  - Restart service"
echo "  - Expected FPS: 10-15 (2-3x better than 4.8)"
echo ""

read -p "Continue? (y/n): " choice
if [ "$choice" != "y" ] && [ "$choice" != "Y" ]; then
    echo "Cancelled"
    exit 0
fi

echo ""

# Backup config
cp config/config.yaml config/config.yaml.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backup created: config/config.yaml.backup.$(date +%Y%m%d_%H%M%S)"
echo ""

# Update detect_fps in config
sed -i 's/detect_fps: 5/detect_fps: 15/g' config/config.yaml
echo "✅ Updated detect_fps: 5 → 15"
echo ""

echo "New detect_fps:"
grep "detect_fps:" config/config.yaml
echo ""

# Update FFmpeg in capture.py
sed -i "s/fps=5/fps=15/g" src/camera/capture.py
echo "✅ Updated FFmpeg: fps=5 → fps=15"
echo ""

echo "Updated FFmpeg commands:"
grep -n "fps=" src/camera/capture.py | head -3
echo ""

echo "======================================"
echo "Restarting Service"
echo "======================================"
echo ""

sudo systemctl stop riftech-security-v2
sleep 2
sudo systemctl start riftech-security-v2

echo "Waiting for service to start..."
sleep 5

if sudo systemctl is-active --quiet riftech-security-v2; then
    echo "✅ Service started successfully"
else
    echo "❌ Service failed to start"
    echo ""
    echo "Check logs:"
    sudo journalctl -u riftech-security-v2 -n 20 --no-pager
    exit 1
fi

echo ""
echo "======================================"
echo "Verification"
echo "======================================"
echo ""

# Wait for stats
sleep 10

echo "Expected FPS: 10-15"
echo ""
echo "Actual FPS:"
sudo journalctl -u riftech-security-v2 -n 1 --no-pager | grep "FPS:"
echo ""

echo "FFmpeg Process:"
ps aux | grep ffmpeg | grep -v grep
echo ""

echo "======================================"
echo "Summary"
echo "======================================"
echo ""
echo "✅ FPS increased from 5 to 15"
echo "✅ Stream should be 2-3x smoother"
echo "✅ Detection will run at 10-15 FPS"
echo ""
echo "Expected improvements:"
echo "   - Preview FPS: 4.8 → 10-15"
echo "   - Stream quality: Better"
echo "   - Detection responsiveness: Faster"
echo ""
echo "Trade-offs:"
echo "   - CPU usage: May increase to 25-35%"
echo "   - Memory usage: May increase to 900MB-1GB"
echo "   - Detection runs more frequently"
echo ""
echo "Monitor with: sudo journalctl -u riftech-security-v2 -f | grep 'FPS:'"
echo ""
echo "If FPS still 4.8-5.0:"
echo "  - Camera may not support 15 FPS"
echo "  - Network may be limiting"
echo "  - Check FFmpeg logs for errors"
echo ""
