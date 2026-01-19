#!/usr/bin/env python3
"""
Quick Fix for Overlay Writer Issue
Run this on the Ubuntu server (10.26.27.104)
"""

import os
import sys
import subprocess
import yaml

print("=" * 60)
print("OVERLAY WRITER FIX SCRIPT")
print("=" * 60)

# Check 1: FFmpeg Installation
print("\n[1] Checking FFmpeg installation...")
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ FFmpeg is installed")
        print(f"   Version: {result.stdout.split()[2]}")
    else:
        print("❌ FFmpeg not found!")
        print("   Install with: sudo apt install ffmpeg")
        sys.exit(1)
except FileNotFoundError:
    print("❌ FFmpeg not found!")
    print("   Install with: sudo apt install ffmpeg")
    sys.exit(1)

# Check 2: Python dependencies
print("\n[2] Checking Python dependencies...")
required_packages = [
    'opencv-python',
    'numpy',
    'pyyaml',
    'ultralytics',  # For YOLO
]

missing = []
for pkg in required_packages:
    try:
        result = subprocess.run(
            ['pip', 'show', pkg],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            missing.append(pkg)
    except:
        missing.append(pkg)

if missing:
    print(f"⚠️ Missing packages: {', '.join(missing)}")
    print("   Install with: pip install -r requirements.txt")
else:
    print("✅ All dependencies installed")

# Check 3: Shared memory limits
print("\n[3] Checking shared memory limits...")
try:
    result = subprocess.run(['free', '-h'], capture_output=True, text=True)
    print(result.stdout)
    
    result = subprocess.run(['df', '-h', '/dev/shm'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"/dev/shm (shared memory):")
        print(result.stdout)
except:
    print("⚠️ Could not check shared memory")

# Check 4: Camera connectivity test
print("\n[4] Testing camera connectivity...")

with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

rtsp_url = config["camera"]["rtsp_url"]
print(f"Testing RTSP connection to: {rtsp_url}")

# Extract IP from RTSP URL
import urllib.parse
parsed = urllib.parse.urlparse(rtsp_url)
host = parsed.hostname
port = 554

import socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((host, port))
    sock.close()
    
    if result == 0:
        print(f"✅ Camera reachable at {host}:{port}")
    else:
        print(f"❌ Cannot connect to camera at {host}:{port}")
        print(f"   Error code: {result}")
except Exception as e:
    print(f"❌ Network error: {e}")

# Check 5: Test FFmpeg RTSP capture
print("\n[5] Testing FFmpeg RTSP capture...")
print("   (This will take 5 seconds...)")

test_cmd = [
    'ffmpeg',
    '-rtsp_transport', 'tcp',
    '-stimeout', '5000000',
    '-i', rtsp_url,
    '-vf', 'fps=1',
    '-f', 'null',
    '-'
]

try:
    result = subprocess.run(
        test_cmd,
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if "Error" in result.stderr and "Connection refused" not in result.stderr:
        print("⚠️ FFmpeg encountered issues:")
        # Print only errors
        for line in result.stderr.split('\n'):
            if 'Error' in line or 'error' in line:
                print(f"   {line}")
    else:
        print("✅ FFmpeg can connect to camera")
        
except subprocess.TimeoutExpired:
    print("⚠️ FFmpeg command timed out")
except Exception as e:
    print(f"❌ FFmpeg test failed: {e}")

# Check 6: System logs
print("\n[6] Checking system logs for errors...")
print("   Looking for initialization errors...")

try:
    result = subprocess.run(
        ['journalctl', '-u', 'riftech-security-v2', '-n', '50', '--no-pager'],
        capture_output=True,
        text=True
    )
    
    logs = result.stdout
    errors_found = []
    
    for line in logs.split('\n'):
        if 'ERROR' in line or 'CRITICAL' in line:
            if 'overlay writer unable to read frame' not in line.lower():
                errors_found.append(line)
    
    if errors_found:
        print("⚠️ Found errors in logs:")
        for err in errors_found[:5]:  # Show first 5 errors
            print(f"   {err}")
    else:
        print("✅ No critical errors found in recent logs")
        
except Exception as e:
    print(f"⚠️ Could not read logs: {e}")

# Fix suggestions
print("\n" + "=" * 60)
print("FIX RECOMMENDATIONS")
print("=" * 60)

print("\nBased on the diagnostics, try these fixes in order:")

print("\n[OPTION 1] Restart the service cleanly:")
print("   sudo systemctl stop riftech-security-v2")
print("   sudo systemctl start riftech-security-v2")
print("   journalctl -u riftech-security-v2 -f")

print("\n[OPTION 2] Clear shared memory buffers:")
print("   sudo rm -f /dev/shm/riftech_*")
print("   sudo systemctl restart riftech-security-v2")

print("\n[OPTION 3] Increase shared memory size:")
print("   sudo mount -o remount,size=2G /dev/shm")
print("   sudo systemctl restart riftech-security-v2")

print("\n[OPTION 4] Test camera directly with FFmpeg:")
print("   ffmpeg -rtsp_transport tcp -i rtsp://admin:Kuncong203@10.26.27.196:554/live/ch00_0")
print("   -vf fps=5 -f null -")

print("\n[OPTION 5] Check if camera is streaming at correct resolution:")
print("   ffmpeg -rtsp_transport tcp -i rtsp://admin:Kuncong203@10.26.27.196:554/live/ch00_0")
print("   -v info -f null - 2>&1 | grep 'Stream'")

print("\n" + "=" * 60)
