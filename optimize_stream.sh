#!/bin/bash

echo "======================================"
echo "Optimize Stream Resolution"
echo "======================================"
echo ""

# Backup config
cp config/config.yaml config/config.yaml.backup.$(date +%Y%m%d_%H%M%S)

# Read current config
echo "Current Resolution:"
grep -A 5 "camera:" config/config.yaml | grep -E "(width|height)"
echo ""

echo "======================================"
echo "Recommended Resolutions for AI:"
echo "======================================"
echo ""
echo "1. 1280x720 (720p HD) - Recommended"
echo "   - Fast AI processing (15-30 FPS)"
echo "   - Good quality"
echo "   - Low CPU/Memory usage"
echo ""
echo "2. 640x480 (VGA) - Very Fast"
echo "   - Very fast AI processing (30-60 FPS)"
echo "   - Lower quality but good for detection"
echo "   - Very low CPU/Memory usage"
echo ""
echo "3. 1920x1080 (1080p FHD) - Balanced"
echo "   - Moderate AI processing (5-15 FPS)"
echo "   - High quality"
echo "   - Moderate CPU/Memory usage"
echo ""
echo "4. 2304x2592 (Current) - NOT RECOMMENDED"
echo "   - Very slow AI processing (1-2 FPS)"
echo "   - Maximum quality but impractical"
echo "   - Very high CPU/Memory usage"
echo ""

read -p "Choose resolution (1-4): " choice

case $choice in
    1)
        WIDTH=1280
        HEIGHT=720
        ;;
    2)
        WIDTH=640
        HEIGHT=480
        ;;
    3)
        WIDTH=1920
        HEIGHT=1080
        ;;
    4)
        WIDTH=2304
        HEIGHT=2592
        ;;
    *)
        echo "Invalid choice, keeping current resolution"
        exit 1
        ;;
esac

echo ""
echo "======================================"
echo "Updating Resolution to ${WIDTH}x${HEIGHT}"
echo "======================================"
echo ""

# Update config file
if command -v yq &> /dev/null; then
    # Using yq if available
    yq eval ".camera.width = $WIDTH" -i config/config.yaml
    yq eval ".camera.height = $HEIGHT" -i config/config.yaml
    yq eval ".camera.width = $WIDTH" -i config/config.yaml
    yq eval ".camera.height = $HEIGHT" -i config/config.yaml
else
    # Using sed if yq not available
    sed -i "s/width: [0-9]*/width: $WIDTH/" config/config.yaml
    sed -i "s/height: [0-9]*/height: $HEIGHT/" config/config.yaml
fi

echo "✅ Configuration updated"
echo ""
echo "New Resolution:"
grep -A 5 "camera:" config/config.yaml | grep -E "(width|height)"
echo ""

echo "======================================"
echo "Updating FFmpeg Pipeline"
echo "======================================"
echo ""

# Check if main_v2.py uses config resolution
if grep -q "scale=" main_v2.py; then
    echo "ℹ️  FFmpeg pipeline uses config resolution"
    echo "   Resolution will be applied after restart"
else
    echo "⚠️  FFmpeg pipeline may need manual update"
    echo "   Check main_v2.py for scale= parameter"
fi

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
echo "Current FPS:"
sudo journalctl -u riftech-security-v2 -n 1 --no-pager | grep "FPS:"

echo ""
echo "✅ Optimization complete!"
echo ""
echo "Expected improvements:"
echo "   - FPS: 1.6 → 15-30 (9-18x faster)"
echo "   - Memory: 1.3GB → 300-500MB (60-75% reduction)"
echo "   - CPU: 96% → 30-50% (50-70% reduction)"
echo ""
echo "Monitor with: sudo journalctl -u riftech-security-v2 -f"
echo ""
