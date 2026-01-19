#!/bin/bash

echo "======================================"
echo "Restore FFmpeg to Working State"
echo "======================================"
echo ""

# Find backup file
BACKUP_FILE=$(ls -t src/camera/capture.py.backup.* 2>/dev/null | head -1)

if [ -z "$BACKUP_FILE" ]; then
    echo "❌ No backup file found!"
    echo ""
    echo "Will create manual fix instead..."
    echo ""
else
    echo "Found backup: $BACKUP_FILE"
    echo ""
    
    read -p "Restore from backup? (y/n): " choice
    if [ "$choice" = "y" ] || [ "$choice" = "Y" ]; then
        cp "$BACKUP_FILE" src/camera/capture.py
        echo "✅ Restored from backup"
        echo ""
    else
        echo "Skipping restore, will fix manually..."
        echo ""
    fi
fi

echo "======================================"
echo "Manual Fix: Revert fpsmax → fps"
echo "======================================"
echo ""

# Check current FFmpeg command
echo "Current FFmpeg command:"
grep -n "fpsmax=" src/camera/capture.py | head -3
echo ""

if grep -q "fpsmax=" src/camera/capture.py; then
    echo "Found fpsmax parameter, reverting to fps..."
    echo ""
    
    # Backup current state
    cp src/camera/capture.py src/camera/capture.py.before_fix.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backup created: src/camera/capture.py.before_fix.$(date +%Y%m%d_%H%M%S)"
    echo ""
    
    # Revert fpsmax → fps
    sed -i 's/fpsmax=/fps=/g' src/camera/capture.py
    
    # Fix the duplicate fps issue in V380SplitCameraCapture
    # Change: fpsmax=15, fps=5 → fps=5
    sed -i "s/fpsmax=[0-9]*, fps=/fps=/g" src/camera/capture.py
    
    echo "✅ Reverted fpsmax → fps"
    echo ""
    
    echo "Updated FFmpeg command:"
    grep -n "fps=" src/camera/capture.py | head -3
    echo ""
fi

echo "======================================"
echo "Check FFmpeg Version"
echo "======================================"
echo ""

FFMPEG_VERSION=$(ffmpeg -version | head -1)
echo "FFmpeg Version: $FFMPEG_VERSION"
echo ""

# Check if fpsmax is supported
if ffmpeg -h 2>/dev/null | grep -q "fpsmax"; then
    echo "✅ fpsmax parameter is supported"
else
    echo "⚠️  fpsmax parameter NOT supported"
    echo "   This version of FFmpeg doesn't support fpsmax"
    echo "   Using regular fps parameter instead"
fi
echo ""

echo "======================================"
echo "Restarting Service"
echo "======================================"
echo ""

# Stop service
sudo systemctl stop riftech-security-v2
sleep 2

# Start service
sudo systemctl start riftech-security-v2

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
    sudo journalctl -u riftech-security-v2 -n 50 --no-pager
    exit 1
fi

echo ""
echo "======================================"
echo "Verification"
echo "======================================"
echo ""

# Wait for stats
sleep 10

# Get latest stats
echo "Current FPS:"
sudo journalctl -u riftech-security-v2 -n 1 --no-pager | grep "FPS:"
echo ""

# Check FFmpeg process
echo "FFmpeg Process:"
ps aux | grep ffmpeg | grep -v grep
echo ""

echo "✅ FFmpeg restored to working state!"
echo ""
echo "System should now work with fps parameter."
echo "FPS should return to 4.8-5.0 (before fpsmax attempt)"
echo ""
echo "Monitor with: sudo journalctl -u riftech-security-v2 -f"
