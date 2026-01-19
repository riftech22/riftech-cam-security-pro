#!/bin/bash

echo "======================================"
echo "Check FFmpeg Status"
echo "======================================"
echo ""

echo "1. Check FFmpeg Process:"
echo "======================================"
ps aux | grep -E "(ffmpeg|main_v2)" | grep -v grep
echo ""

echo "2. Check FFmpeg Command in capture.py:"
echo "======================================"
grep -A 5 "ffmpeg_cmd =" src/camera/capture.py | grep -E "(ffmpeg_cmd|fps|fpsmax)"
echo ""

echo "3. Check Service Status:"
echo "======================================"
sudo systemctl status riftech-security-v2 --no-pager -l | head -20
echo ""

echo "4. Check Recent Errors:"
echo "======================================"
sudo journalctl -u riftech-security-v2 -n 30 --no-pager | grep -E "(error|Error|ERROR|failed|Failed|FAILED)"
echo ""

echo "5. Check Full Recent Logs:"
echo "======================================"
sudo journalctl -u riftech-security-v2 -n 10 --no-pager
echo ""

echo "======================================"
echo "Diagnosis"
echo "======================================"

if ps aux | grep -q "[f]fmpeg"; then
    echo "✅ FFmpeg process is running"
else
    echo "❌ FFmpeg process NOT running - This is why FPS is 0.0"
    echo ""
    echo "Possible causes:"
    echo "  - FFmpeg command syntax error after sed replacement"
    echo "  - fpsmax parameter not supported in this FFmpeg version"
    echo "  - Camera connection issue"
fi

if grep -q "fpsmax=" src/camera/capture.py; then
    echo "✅ FFmpeg command uses fpsmax parameter"
else
    echo "❌ FFmpeg command still uses fps parameter"
fi

if sudo systemctl is-active --quiet riftech-security-v2; then
    echo "✅ Service is active"
else
    echo "❌ Service is not active"
fi

echo ""
echo "======================================"
echo "Recommendation"
echo "======================================"
echo ""
echo "If FPS is 0.0 and FFmpeg is not running:"
echo "1. Restore backup file:"
echo "   cp src/camera/capture.py.backup.YYYYMMDD_HHMMSS src/camera/capture.py"
echo ""
echo "2. Or revert fpsmax to fps manually:"
echo "   nano src/camera/capture.py"
echo "   Change: fpsmax= → fps="
echo ""
echo "3. Restart service:"
echo "   sudo systemctl restart riftech-security-v2"
echo ""
