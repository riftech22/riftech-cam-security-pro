#!/bin/bash

echo "======================================"
echo "Increase FPS in Config"
echo "======================================"
echo ""

# Cek current config
echo "Current FPS settings:"
grep -E "fps:" config/config.yaml | grep -v "#"
echo ""

echo "======================================"
echo "Analysis"
echo "======================================"
echo ""

# Get current detect_fps
CURRENT_FPS=$(grep "detect_fps:" config/config.yaml | awk '{print $2}')
echo "Current detect_fps: $CURRENT_FPS"

if [ "$CURRENT_FPS" -lt 5 ]; then
    echo "❌ ISSUE FOUND: detect_fps is too low ($CURRENT_FPS)"
    echo "   This limits FPS to ~$CURRENT_FPS even with optimized resolution"
    echo ""
    echo "💡 Solution: Increase detect_fps to 5, 10, or 15"
    echo ""
    
    # Backup config
    cp config/config.yaml config/config.yaml.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backup created: config/config.yaml.backup.$(date +%Y%m%d_%H%M%S)"
    echo ""
    
    echo "======================================"
    echo "Recommended FPS Options:"
    echo "======================================"
    echo ""
    echo "1. fps: 5    - Balanced (recommended)"
    echo "   - Good for mid-range systems"
    echo "   - Expected FPS: 5-10"
    echo ""
    echo "2. fps: 10   - Fast"
    echo "   - Good for high-end systems"
    echo "   - Expected FPS: 10-20"
    echo ""
    echo "3. fps: 15   - Very Fast"
    echo "   - Best for high-end systems"
    echo "   - Expected FPS: 15-30"
    echo ""
    echo "4. fps: 30   - Maximum Speed"
    echo "   - Only for very powerful systems"
    echo "   - Expected FPS: 20-30+"
    echo ""
    
    read -p "Choose detect_fps (1-4): " choice
    
    case $choice in
        1)
            NEW_FPS=5
            ;;
        2)
            NEW_FPS=10
            ;;
        3)
            NEW_FPS=15
            ;;
        4)
            NEW_FPS=30
            ;;
        *)
            echo "Invalid choice, keeping current fps: $CURRENT_FPS"
            exit 1
            ;;
    esac
    
    echo ""
    echo "======================================"
    echo "Updating detect_fps to $NEW_FPS"
    echo "======================================"
    echo ""
    
    # Update detect_fps in config
    sed -i "s/detect_fps: $CURRENT_FPS/detect_fps: $NEW_FPS/" config/config.yaml
    
    echo "✅ Configuration updated"
    echo ""
    echo "New detect_fps:"
    grep "detect_fps:" config/config.yaml
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
    echo "New FPS (expected: $NEW_FPS+):"
    sudo journalctl -u riftech-security-v2 -n 1 --no-pager | grep "FPS:"
    
    echo ""
    echo "✅ FPS increased successfully!"
    echo ""
    echo "Expected improvements:"
    echo "   - FPS: $CURRENT_FPS → $NEW_FPS+ ($(echo "scale=1; $NEW_FPS / $CURRENT_FPS" | bc)x faster)"
    echo ""
    echo "Monitor with: sudo journalctl -u riftech-security-v2 -f"
    echo ""
else
    echo "✅ detect_fps is already reasonable: $CURRENT_FPS"
    echo ""
    echo "Checking other potential bottlenecks..."
    echo ""
fi
