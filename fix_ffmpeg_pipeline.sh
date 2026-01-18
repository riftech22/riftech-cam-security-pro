#!/bin/bash

echo "======================================"
echo "Fix FFmpeg Pipeline FPS"
echo "======================================"
echo ""

# Cek current main_v2.py
echo "Current FFmpeg Command in main_v2.py:"
grep -n "ffmpeg.*-vf" main_v2.py | head -3
echo ""

# Cek config fps
echo "Config FPS settings:"
grep -E "fps:" config/config.yaml
echo ""

echo "======================================"
echo "Analysis"
echo "======================================"
echo ""

# Check if FFmpeg uses hardcoded fps
if grep -q "fps=2" main_v2.py; then
    echo "❌ ISSUE FOUND: FFmpeg uses hardcoded fps=2"
    echo "   This is why FPS is still 1.9-2.0 even with lower resolution"
    echo ""
    echo "💡 Solution: Update FFmpeg to use config fps"
    echo ""
    
    # Backup main_v2.py
    cp main_v2.py main_v2.py.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backup created: main_v2.py.backup.$(date +%Y%m%d_%H%M%S)"
    echo ""
    
    # Get config fps
    CONFIG_FPS=$(grep "detect_fps:" config/config.yaml | awk '{print $2}')
    if [ -z "$CONFIG_FPS" ]; then
        CONFIG_FPS=5
    fi
    
    echo "Config detect_fps: $CONFIG_FPS"
    echo ""
    
    echo "======================================"
    echo "Updating FFmpeg Pipeline"
    echo "======================================"
    echo ""
    
    # Update FFmpeg command - replace fps=2 with fps=<config_fps>
    sed -i "s/fps=2/fps=$CONFIG_FPS/g" main_v2.py
    
    echo "✅ Updated FFmpeg command:"
    grep -n "ffmpeg.*-vf" main_v2.py | head -3
    echo ""
    
    echo "======================================"
    echo "Restarting Service"
    echo "======================================"
    echo ""
    
    # Restart service
    sudo systemctl restart riftech-security-v2
    
    # Wait for service to start
    echo "Waiting for service to start..."
    sleep 5
    
    # Check status
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
    
    # Wait a bit more for stats
    sleep 10
    
    # Get latest stats
    echo "New FPS (expected: $CONFIG_FPS+):"
    sudo journalctl -u riftech-security-v2 -n 1 --no-pager | grep "FPS:"
    
    echo ""
    echo "✅ FFmpeg pipeline fixed!"
    echo ""
    echo "Monitor improvement:"
    echo "  sudo journalctl -u riftech-security-v2 -f | grep 'FPS:'"
    echo ""
else
    echo "✅ FFmpeg already uses config fps"
    echo ""
    echo "Checking FPS bottleneck in other areas..."
    echo ""
fi
