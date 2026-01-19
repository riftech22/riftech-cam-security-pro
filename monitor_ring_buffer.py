#!/usr/bin/env python3
"""
Monitor ring buffer activity - Check if overlay writer is writing frames
Run this on server to diagnose why stream freezes
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
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please run this from the project directory with venv activated")
    sys.exit(1)


def monitor_buffer(buffer_name: str, duration: int = 30):
    """
    Monitor ring buffer activity
    
    Args:
        buffer_name: Name of buffer to monitor
        duration: Monitor duration in seconds
    """
    print(f"\n{'='*60}")
    print(f"MONITORING: {buffer_name}")
    print(f"{'='*60}\n")
    
    last_frame = None
    frame_change_count = 0
    frame_null_count = 0
    frame_same_count = 0
    start_time = time.time()
    
    for i in range(duration):
        current_time = time.time()
        elapsed = current_time - start_time
        
        # Try to read frame
        frame = frame_manager_v2.force_read_frame(buffer_name)
        
        if frame is None:
            frame_null_count += 1
            status = "❌ NULL"
        elif last_frame is None:
            # First frame received
            last_frame = frame.copy()
            frame_change_count += 1
            status = f"✅ FIRST - Shape: {frame.shape}, Mean: {frame.mean():.2f}"
        else:
            # Check if frame changed
            diff = np.abs(frame.astype(float) - last_frame.astype(float)).mean()
            
            if diff > 5.0:  # Frame changed significantly
                last_frame = frame.copy()
                frame_change_count += 1
                status = f"✅ CHANGED - Diff: {diff:.2f}, Mean: {frame.mean():.2f}"
            else:
                frame_same_count += 1
                status = f"⚠️  SAME - Diff: {diff:.2f}, Mean: {frame.mean():.2f}"
        
        # Calculate frame rate
        fps = frame_change_count / elapsed if elapsed > 0 else 0
        
        print(f"[{elapsed:6.1f}s] {status} | Changes: {frame_change_count:3d} | Null: {frame_null_count:3d} | Same: {frame_same_count:3d} | FPS: {fps:5.1f}")
        
        time.sleep(1.0)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY for {buffer_name}")
    print(f"{'='*60}")
    print(f"Total time:          {elapsed:.1f}s")
    print(f"Frame changes:       {frame_change_count}")
    print(f"Null frames:         {frame_null_count}")
    print(f"Same frames:         {frame_same_count}")
    print(f"Average FPS:         {fps:.1f}")
    
    if frame_null_count > 5:
        print(f"\n❌ ISSUE: {frame_null_count} null frames detected!")
        print("   → Overlay writer may have stopped writing")
        print("   → Check journalctl -u riftech-security-v2 -f | grep overlay")
    
    if frame_same_count > 20:
        print(f"\n⚠️  ISSUE: {frame_same_count} identical frames detected!")
        print("   → Frames not being updated frequently enough")
        print("   → Check capture worker status")
    
    if fps < 5.0 and elapsed > 5.0:
        print(f"\n⚠️  ISSUE: Low FPS ({fps:.1f})")
        print("   → Overlay writer may be too slow")
        print("   → Check CPU usage")
    
    return frame_null_count > 5 or frame_same_count > 20


def main():
    """Main monitoring function"""
    print("\n" + "="*60)
    print("RIFTECH SECURITY SYSTEM - RING BUFFER MONITOR")
    print("="*60)
    
    # Try to determine which buffer to monitor
    buffers_to_check = [
        "camera_full_overlay",  # V380 split camera
        "camera_overlay",       # Regular camera
    ]
    
    active_buffer = None
    
    print("\nDetecting active ring buffer...")
    for buffer_name in buffers_to_check:
        frame = frame_manager_v2.force_read_frame(buffer_name)
        if frame is not None:
            print(f"✅ Found active buffer: {buffer_name}")
            active_buffer = buffer_name
            break
        else:
            print(f"❌ Buffer not active: {buffer_name}")
    
    if not active_buffer:
        print("\n❌ No active ring buffer found!")
        print("   → Security system may not be running")
        print("   → Run: sudo systemctl status riftech-security-v2")
        return 1
    
    # Monitor for 30 seconds
    print(f"\nMonitoring {active_buffer} for 30 seconds...")
    print("Press Ctrl+C to stop early\n")
    
    try:
        has_issue = monitor_buffer(active_buffer, duration=30)
        
        if has_issue:
            print("\n" + "="*60)
            print("RECOMMENDATIONS")
            print("="*60)
            print("\n1. Check overlay writer logs:")
            print("   journalctl -u riftech-security-v2 -f | grep -E '(overlay|writer|frame)'")
            
            print("\n2. Check capture worker logs:")
            print("   journalctl -u riftech-security-v2 -f | grep -E '(capture|worker|camera)'")
            
            print("\n3. Check system resources:")
            print("   top -p $(pgrep -f 'riftech-security-v2' -d,)"
            
            print("\n4. Restart security system:")
            print("   sudo systemctl restart riftech-security-v2")
            
            return 1
        else:
            print("\n✅ Ring buffer looks healthy!")
            print("   Overlay writer is actively writing frames")
            return 0
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        return 0


if __name__ == "__main__":
    sys.exit(main())
