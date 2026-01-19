#!/usr/bin/env python3
"""
Camera Diagnostic Script
Test V380 split camera connection and frame capture
"""

import sys
import subprocess
import time
import cv2
import numpy as np
from pathlib import Path

# Load config
import yaml
with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

print("=" * 60)
print("V380 SPLIT CAMERA DIAGNOSTIC")
print("=" * 60)

rtsp_url = config["camera"]["rtsp_url"]
width = config["camera"]["width"]
height = config["camera"]["height"]
detect_fps = config["camera"]["detect_fps"]

print(f"\nConfiguration:")
print(f"  RTSP URL: {rtsp_url}")
print(f"  Resolution: {width}x{height}")
print(f"  Detect FPS: {detect_fps}")
print(f"  Type: v380_split")

# Test 1: Network connectivity
print("\n" + "=" * 60)
print("TEST 1: Network Connectivity")
print("=" * 60)

import socket
from urllib.parse import urlparse

parsed = urlparse(rtsp_url)
host = parsed.hostname
port = 554  # Default RTSP port

print(f"Testing connection to {host}:{port}...")

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((host, port))
    sock.close()
    
    if result == 0:
        print("✅ Network connection successful!")
    else:
        print(f"❌ Network connection failed! Error code: {result}")
        print("   Check if camera is online and accessible")
        sys.exit(1)
except Exception as e:
    print(f"❌ Network test error: {e}")
    sys.exit(1)

# Test 2: FFmpeg RTSP Stream Test
print("\n" + "=" * 60)
print("TEST 2: FFmpeg RTSP Stream Test")
print("=" * 60)

print(f"Testing FFmpeg connection to {rtsp_url}...")
print("This will take 5 seconds...")

ffmpeg_cmd = [
    'ffmpeg',
    '-rtsp_transport', 'tcp',
    '-stimeout', '5000000',  # 5 second timeout
    '-i', rtsp_url,
    '-vf', f'fps=1,scale={width}:{height}',
    '-f', 'image2pipe',
    '-vcodec', 'mjpeg',
    '-q:v', '2',
    '-frames:v', '1',  # Capture just 1 frame
    '-'
]

print(f"Command: {' '.join(ffmpeg_cmd)}")

try:
    process = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**8
    )
    
    # Wait for frame
    frame_bytes = b''
    start_time = time.time()
    
    while time.time() - start_time < 5:
        data = process.stdout.read(1024)
        if not data:
            break
        frame_bytes += data
        
        if b'\xff\xd9' in frame_bytes:
            # Complete JPEG frame received
            end_marker = frame_bytes.find(b'\xff\xd9') + 2
            jpeg_data = frame_bytes[:end_marker]
            frame_bytes = frame_bytes[end_marker:]
            
            # Decode JPEG
            frame = cv2.imdecode(
                np.frombuffer(jpeg_data, dtype=np.uint8),
                cv2.IMREAD_COLOR
            )
            
            if frame is not None:
                print(f"✅ FFmpeg successfully captured frame!")
                print(f"   Frame shape: {frame.shape}")
                print(f"   Expected shape: ({height}, {width}, 3)")
                
                # Check if frame needs to be split
                if frame.shape[0] >= height:
                    split_point = frame.shape[0] // 2
                    top_frame = frame[:split_point, :, :]
                    bottom_frame = frame[split_point:, :, :]
                    
                    print(f"   Top frame shape: {top_frame.shape}")
                    print(f"   Bottom frame shape: {bottom_frame.shape}")
                    
                    # Save sample frames
                    Path("data/fixed_images").mkdir(parents=True, exist_ok=True)
                    cv2.imwrite("data/fixed_images/diagnostic_full.jpg", frame)
                    cv2.imwrite("data/fixed_images/diagnostic_top.jpg", top_frame)
                    cv2.imwrite("data/fixed_images/diagnostic_bottom.jpg", bottom_frame)
                    print("\n   Sample frames saved to data/fixed_images/")
                    print("   - diagnostic_full.jpg (complete frame)")
                    print("   - diagnostic_top.jpg (top camera)")
                    print("   - diagnostic_bottom.jpg (bottom camera)")
                else:
                    print("   ⚠️ Frame too small for splitting!")
                
                process.terminate()
                break
    else:
        print("❌ No frame received from FFmpeg within 5 seconds")
        process.terminate()
        sys.exit(1)
        
except Exception as e:
    print(f"❌ FFmpeg test failed: {e}")
    if process:
        process.terminate()
    sys.exit(1)

# Test 3: Check FFmpeg stderr for warnings
print("\n" + "=" * 60)
print("TEST 3: FFmpeg Logs Analysis")
print("=" * 60)

print("Testing FFmpeg with verbose logging...")

ffmpeg_verbose_cmd = [
    'ffmpeg',
    '-v', 'verbose',
    '-rtsp_transport', 'tcp',
    '-stimeout', '5000000',
    '-i', rtsp_url,
    '-vf', f'fps=1,scale={width}:{height}',
    '-f', 'null',
    '-'
]

try:
    result = subprocess.run(
        ffmpeg_verbose_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10
    )
    
    stderr_text = result.stderr.decode('utf-8', errors='ignore')
    
    # Check for common issues
    issues = []
    
    if "Connection refused" in stderr_text:
        issues.append("Connection refused - Check camera credentials and IP")
    if "Timeout" in stderr_text or "timed out" in stderr_text.lower():
        issues.append("Connection timeout - Network or camera issue")
    if "401" in stderr_text or "Unauthorized" in stderr_text:
        issues.append("Authentication failed - Check username/password")
    if "No route to host" in stderr_text:
        issues.append("Network unreachable - Check IP address and network")
    if "Input/output error" in stderr_text:
        issues.append("I/O error - Camera stream issue")
    
    if issues:
        print("⚠️ Issues detected in FFmpeg logs:")
        for issue in issues:
            print(f"   - {issue}")
        
        # Save full log
        with open("data/logs/ffmpeg_diagnostic.log", "w") as f:
            f.write(stderr_text)
        print("\n   Full FFmpeg log saved to data/logs/ffmpeg_diagnostic.log")
    else:
        print("✅ No major issues detected in FFmpeg logs")
        
except subprocess.TimeoutExpired:
    print("⚠️ FFmpeg command timed out (10 seconds)")
except Exception as e:
    print(f"⚠️ FFmpeg log analysis error: {e}")

# Test 4: Resolution check
print("\n" + "=" * 60)
print("TEST 4: Resolution Verification")
print("=" * 60)

print(f"Configured resolution: {width}x{height}")
print(f"Split height (per camera): {height // 2}")

if width != 1280 or height != 720:
    print("⚠️ Non-standard resolution detected!")
    print("   V380 split cameras typically use 1280x720 (full)")
    print("   Each camera gets 640x720 after split")
else:
    print("✅ Resolution is correctly configured")

# Test 5: Continuous capture test
print("\n" + "=" * 60)
print("TEST 5: Continuous Capture Test (5 seconds)")
print("=" * 60)

print("Testing continuous frame capture for 5 seconds...")

try:
    process = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**8
    )
    
    frame_count = 0
    start_time = time.time()
    
    while time.time() - start_time < 5:
        data = process.stdout.read(1024)
        if not data:
            break
        
        frame_bytes += data
        
        if b'\xff\xd9' in frame_bytes:
            end_marker = frame_bytes.find(b'\xff\xd9') + 2
            frame_bytes = frame_bytes[end_marker:]
            frame_count += 1
    
    process.terminate()
    
    elapsed = time.time() - start_time
    actual_fps = frame_count / elapsed if elapsed > 0 else 0
    
    print(f"✅ Captured {frame_count} frames in {elapsed:.1f} seconds")
    print(f"   Actual FPS: {actual_fps:.1f}")
    print(f"   Expected FPS: {detect_fps}")
    
    if actual_fps < detect_fps * 0.5:
        print("   ⚠️ FPS is significantly lower than expected!")
        print("      This may cause frame drops and overlay writer issues")
    else:
        print("   ✅ FPS is acceptable")
        
except Exception as e:
    print(f"❌ Continuous capture test failed: {e}")
    if process:
        process.terminate()

# Summary
print("\n" + "=" * 60)
print("DIAGNOSTIC SUMMARY")
print("=" * 60)

print("\nIf all tests passed ✅, the issue may be:")
print("  1. Shared memory buffer not properly initialized")
print("  2. Capture worker not starting correctly")
print("  3. System resource constraints")
print("\nNext steps:")
print("  1. Check full system logs: journalctl -u riftech-security-v2 -n 100")
print("  2. Verify FFmpeg is installed: ffmpeg -version")
print("  3. Restart the service: sudo systemctl restart riftech-security-v2")

print("\n" + "=" * 60)
