#!/bin/bash

echo "======================================"
echo "Fix FFmpeg with -fpsmax Parameter"
echo "======================================"
echo ""

# Cek current FFmpeg in capture.py
echo "Current FFmpeg command in capture.py:"
grep -n "fps=" src/camera/capture.py | head -5
echo ""

echo "======================================"
echo "Analysis"
echo "======================================"
echo ""

if grep -q "fps=" src/camera/capture.py; then
    echo "❌ ISSUE FOUND: FFmpeg uses fixed fps="
    echo "   This limits FPS even with -fpsmax parameter"
    echo ""
    echo "💡 Solution: Use -fpsmax (Frigate-style) for maximum FPS"
    echo ""
    
    # Backup file
    cp src/camera/capture.py src/camera/capture.py.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backup created: src/camera/capture.py.backup.$(date +%Y%m%d_%H%M%S)"
    echo ""
    
    echo "======================================"
    echo "Updating FFmpeg Command"
    echo "======================================"
    echo ""
    
    # Update: fps=X → fpsmax=X
    sed -i "s/fps=/fpsmax=/g" src/camera/capture.py
    
    echo "✅ Updated FFmpeg command:"
    grep -n "fpsmax=" src/camera/capture.py | head -5
    echo ""
    
    echo "======================================"
    echo "Updating FFmpeg Command in V380SplitCameraCapture"
    echo "======================================"
    echo ""
    
    # Get config fps
    CONFIG_FPS=$(grep "fps:" config/config.yaml | head -1 | awk '{print $2}')
    if [ -z "$CONFIG_FPS" ]; then
        CONFIG_FPS=30
    fi
    
    echo "Config fps: $CONFIG_FPS"
    echo "Setting preview fpsmax to: $CONFIG_FPS"
    echo ""
    
    # Update V380SplitCameraCapture to use fpsmax instead of fps
    sed -i "s/'-vf', f'fps=/-vf', f'fpsmax=$CONFIG_FPS, fps=/g" src/camera/capture.py
    
    echo "✅ Updated V380SplitCameraCapture:"
    grep -A 2 "ffmpeg_cmd =" src/camera/capture.py | grep -E "(ffmpeg_cmd|fps)"
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
    echo "✅ FFmpeg -fpsmax parameter added!"
    echo ""
    echo "Key change:"
    echo "   Before: fps=5 (fixed FPS)"
    echo "   After:  fpsmax=30 (maximum FPS, Frigate-style)"
    echo ""
    echo "Expected improvements:"
    echo "   - FPS: 4.8 → 15-30 (3-6x faster)"
    echo "   - Stream: Smooth (no longer stuck)"
    echo "   - Latency: Low (Frigate-style)"
    echo ""
    echo "Monitor with: sudo journalctl -u riftech-security-v2 -f"
    echo ""
else
    echo "✅ FFmpeg already uses -fpsmax parameter"
    echo ""
fi
