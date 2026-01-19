#!/usr/bin/env python3
"""
Diagnose streaming issue - Check why web server shows "Connecting..."
Run this on the server where security system is running
"""

import os
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import cv2
    import numpy as np
    from src.core.frame_manager_v2 import frame_manager_v2
    from src.core.config import config
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please run this from the project directory with venv activated")
    sys.exit(1)


def check_shared_memory():
    """Check shared memory status"""
    print("\n" + "="*60)
    print("1. CHECKING SHARED MEMORY")
    print("="*60)
    
    shm_dir = Path("/dev/shm")
    shm_files = list(shm_dir.glob("camera_*"))
    
    print(f"Found {len(shm_files)} camera ring buffers in /dev/shm:")
    for f in shm_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  - {f.name}: {size_mb:.2f} MB")
    
    if not shm_files:
        print("  ❌ NO RING BUFFERS FOUND!")
        print("  This means the security system is NOT running properly")
        return False
    
    return True


def check_camera_buffers():
    """Check if ring buffers are accessible and contain frames"""
    print("\n" + "="*60)
    print("2. CHECKING RING BUFFER ACCESS")
    print("="*60)
    
    # Try to read from all possible buffer names
    buffer_names = [
        "camera_full_overlay",  # What web server reads (split camera)
        "camera_full_raw",      # Raw full frame (split camera)
        "camera_top_raw",       # Top camera raw
        "camera_bottom_raw",    # Bottom camera raw
        "camera_overlay",       # What web server reads (regular camera)
        "camera_raw"            # Raw frame (regular camera)
    ]
    
    for buffer_name in buffer_names:
        print(f"\nChecking '{buffer_name}':")
        
        try:
            # Force read - should work immediately
            frame = frame_manager_v2.force_read_frame(buffer_name)
            
            if frame is not None:
                print(f"  ✅ SUCCESS - Frame shape: {frame.shape}")
                print(f"     Frame dtype: {frame.dtype}")
                print(f"     Frame mean value: {frame.mean():.2f}")
                
                # Try to detect if it's a black frame
                if frame.mean() < 5:
                    print(f"  ⚠️  WARNING - Frame is mostly black!")
                
                return True, buffer_name, frame.shape
            else:
                print(f"  ❌ FAILED - No frame available")
                
        except Exception as e:
            print(f"  ❌ ERROR - {type(e).__name__}: {e}")
    
    return False, None, None


def check_web_server():
    """Check if web server is running"""
    print("\n" + "="*60)
    print("3. CHECKING WEB SERVER")
    print("="*60)
    
    try:
        import subprocess
        result = subprocess.run(
            ["systemctl", "status", "riftech-web-server"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if "active (running)" in result.stdout:
            print("  ✅ Web server is RUNNING")
            return True
        else:
            print("  ❌ Web server is NOT running")
            print(f"  Status: {result.stdout}")
            return False
            
    except Exception as e:
        print(f"  ❌ ERROR checking web server: {e}")
        return False


def check_security_system():
    """Check if security system is running"""
    print("\n" + "="*60)
    print("4. CHECKING SECURITY SYSTEM")
    print("="*60)
    
    try:
        import subprocess
        result = subprocess.run(
            ["systemctl", "status", "riftech-security-v2"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if "active (running)" in result.stdout:
            print("  ✅ Security system is RUNNING")
            return True
        else:
            print("  ❌ Security system is NOT running")
            print(f"  Status: {result.stdout}")
            return False
            
    except Exception as e:
        print(f"  ❌ ERROR checking security system: {e}")
        return False


def check_recent_logs():
    """Check recent logs for errors"""
    print("\n" + "="*60)
    print("5. CHECKING RECENT LOGS (last 20 lines)")
    print("="*60)
    
    try:
        import subprocess
        result = subprocess.run(
            ["journalctl", "-u", "riftech-security-v2", "-n", "20", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        lines = result.stdout.split('\n')
        
        # Find and print relevant lines
        relevant_lines = [
            line for line in lines 
            if any(keyword in line.lower() for keyword in [
                'overlay writer', 'ring buffer', 'capture worker', 
                'error', 'warning', 'failed', 'camera', 'frame'
            ])
        ]
        
        if relevant_lines:
            for line in relevant_lines[-10:]:  # Last 10 relevant lines
                print(f"  {line}")
        else:
            print("  No relevant log lines found")
            
    except Exception as e:
        print(f"  ❌ ERROR reading logs: {e}")


def test_stream_endpoint():
    """Test if /api/stream returns frames"""
    print("\n" + "="*60)
    print("6. TESTING /api/stream ENDPOINT")
    print("="*60)
    
    try:
        import requests
        
        # Try to get first frame from stream
        response = requests.get(
            "http://localhost:8000/api/stream",
            stream=True,
            timeout=5
        )
        
        if response.status_code == 200:
            print("  ✅ Stream endpoint RESPONDS (200 OK)")
            
            # Try to read first frame
            chunk_count = 0
            for chunk in response.iter_content(chunk_size=1024):
                chunk_count += 1
                if chunk_count > 100:  # Read enough for first frame
                    break
            
            if chunk_count > 10:
                print(f"  ✅ Stream is SENDING data ({chunk_count} chunks received)")
                return True
            else:
                print(f"  ❌ Stream NOT sending enough data (only {chunk_count} chunks)")
                return False
        else:
            print(f"  ❌ Stream endpoint FAILED (status: {response.status_code})")
            return False
            
    except requests.exceptions.ConnectionError:
        print("  ❌ Web server NOT accessible (Connection refused)")
        return False
    except Exception as e:
        print(f"  ❌ ERROR testing stream: {type(e).__name__}: {e}")
        return False


def main():
    """Main diagnostic function"""
    print("\n" + "="*60)
    print("RIFTECH SECURITY SYSTEM - STREAMING DIAGNOSTIC")
    print("="*60)
    
    # Run checks
    has_shared_memory = check_shared_memory()
    security_running = check_security_system()
    web_running = check_web_server()
    
    if has_shared_memory and security_running:
        buffer_ok, buffer_name, buffer_shape = check_camera_buffers()
    else:
        buffer_ok, buffer_name, buffer_shape = False, None, None
    
    check_recent_logs()
    
    if web_running:
        stream_ok = test_stream_endpoint()
    else:
        stream_ok = False
    
    # Summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    
    issues = []
    
    if not has_shared_memory:
        issues.append("❌ No ring buffers in shared memory")
        issues.append("   → Security system not started or crashed")
        issues.append("   → Run: sudo systemctl restart riftech-security-v2")
    
    if not security_running:
        issues.append("❌ Security system is not running")
        issues.append("   → Run: sudo systemctl start riftech-security-v2")
    
    if not buffer_ok:
        issues.append("❌ Ring buffers exist but no frames available")
        issues.append("   → Capture worker may have crashed")
        issues.append("   → Camera may not be connected")
        issues.append("   → Check camera configuration in config/config.yaml")
        issues.append("   → Check journalctl -u riftech-security-v2 -f")
    
    if not web_running:
        issues.append("❌ Web server is not running")
        issues.append("   → Run: sudo systemctl start riftech-web-server")
    
    if not stream_ok and web_running:
        issues.append("❌ Web server running but stream endpoint failing")
        issues.append("   → Buffer name mismatch between security system and web server")
        issues.append("   → Check web_server.py line ~297 (force_read_frame)")
        issues.append("   → Should be reading from: " + (buffer_name if buffer_name else "camera_full_overlay or camera_overlay"))
    
    if issues:
        print("\nISSUES FOUND:")
        for issue in issues:
            print(f"{issue}")
        
        print("\n" + "="*60)
        print("RECOMMENDED FIXES:")
        print("="*60)
        
        if not has_shared_memory or not security_running:
            print("\n1. Restart security system:")
            print("   sudo systemctl restart riftech-security-v2")
            print("   sudo systemctl status riftech-security-v2")
        
        if not web_running:
            print("\n2. Start web server:")
            print("   sudo systemctl start riftech-web-server")
            print("   sudo systemctl status riftech-web-server")
        
        if not stream_ok and web_running:
            print("\n3. Check buffer name mismatch in web_server.py")
            print(f"   Security system is writing to: {buffer_name}")
            print("   Web server should read from same buffer")
            print("   Check src/api/web_server.py around line 297")
        
        print("\n4. Monitor logs in real-time:")
        print("   journalctl -u riftech-security-v2 -f")
        print("   journalctl -u riftech-web-server -f")
        
        return 1
    else:
        print("\n✅ ALL CHECKS PASSED!")
        print("Streaming should be working correctly")
        return 0


if __name__ == "__main__":
    sys.exit(main())
