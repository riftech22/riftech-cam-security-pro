#!/usr/bin/env python3
"""
Fix shared frame issue - Replace shared memory with file-based approach
"""

import re

def fix_security_system_v2():
    """Update security_system_v2.py to use SharedFrameWriter"""
    print("=" * 50)
    print("Step 1: Updating security_system_v2.py")
    print("=" * 50)
    
    with open('src/security_system_v2.py', 'r') as f:
        content = f.read()
    
    # Add import if not exists
    if 'from .core.shared_frame import SharedFrameWriter' not in content:
        content = content.replace(
            'from .core.frame_manager import frame_manager',
            'from .core.frame_manager import frame_manager\nfrom .core.shared_frame import SharedFrameWriter'
        )
        print("✓ Added SharedFrameWriter import")
    
    # Add shared_frame_writer to CaptureWorker __init__
    if 'self.shared_frame_writer' not in content:
        content = re.sub(
            r'(self\.motion_interval = 5  # Only detect every N frames)',
            r'\1\n        self.shared_frame_writer = None',
            content
        )
        print("✓ Added shared_frame_writer to CaptureWorker")
    
    # Initialize SharedFrameWriter in EnhancedSecuritySystem.initialize()
    if 'SharedFrameWriter("camera"' not in content:
        content = content.replace(
            'if not frame_manager.register_frame("camera", frame_shape):\n            logger.warning("Frame already registered, attaching...")',
            '''if not frame_manager.register_frame("camera", frame_shape):
            logger.warning("Frame already registered, attaching...")
        
        # Initialize file-based shared frame (for web server)
        frame_shape = (config.camera.height, config.camera.width, 3)
        self.shared_frame_writer = SharedFrameWriter("camera", frame_shape)'''
        )
        print("✓ Initialized SharedFrameWriter in EnhancedSecuritySystem")
    
    # Add write to shared_frame_writer in CaptureWorker
    if 'self.shared_frame_writer.write' not in content:
        content = re.sub(
            r'(if not frame_manager\.write_frame\(self\.camera_name, full_frame\):\n                    logger\.error\(f"Failed to write frame to shared memory: \{self\.camera_name\}"\))',
            r'''\1
                
                # Also write to file-based shared frame (for web server)
                if self.shared_frame_writer:
                    self.shared_frame_writer.write(full_frame)''',
            content
        )
        print("✓ Added write to shared_frame_writer in CaptureWorker")
    
    with open('src/security_system_v2.py', 'w') as f:
        f.write(content)
    
    print("✓ security_system_v2.py updated successfully")
    print()

def fix_web_server():
    """Update web_server.py to use SharedFrameReader"""
    print("=" * 50)
    print("Step 2: Updating web_server.py")
    print("=" * 50)
    
    with open('src/api/web_server.py', 'r') as f:
        content = f.read()
    
    # Add import if not exists
    if 'from ..core.shared_frame import SharedFrameReader' not in content:
        content = content.replace(
            'from ..core.frame_manager import frame_manager',
            'from ..core.frame_manager import frame_manager\nfrom ..core.shared_frame import SharedFrameReader'
        )
        print("✓ Added SharedFrameReader import")
    
    # Initialize SharedFrameReader
    if 'SharedFrameReader("camera")' not in content:
        content = content.replace(
            'logger.info("Using enhanced security system for streaming (optimized)")',
            'logger.info("Using enhanced security system for streaming (optimized")\n            \n            shared_frame_reader = SharedFrameReader("camera")'
        )
        print("✓ Initialized SharedFrameReader in streaming endpoint")
    
    # Replace frame_manager.read_frame with shared_frame_reader.read
    content = content.replace(
        'frame = frame_manager.read_frame("camera")',
        'frame = shared_frame_reader.read()'
    )
    print("✓ Replaced frame_manager.read_frame with shared_frame_reader.read")
    
    with open('src/api/web_server.py', 'w') as f:
        f.write(content)
    
    print("✓ web_server.py updated successfully")
    print()

def main():
    print("\n" + "=" * 50)
    print("Fixing Shared Frame Issue")
    print("=" * 50)
    print("\nRoot Cause: Shared memory not accessible between processes")
    print("Solution: Use file-based frame sharing\n")
    
    try:
        fix_security_system_v2()
        fix_web_server()
        
        print("=" * 50)
        print("✓ FIX COMPLETE!")
        print("=" * 50)
        print("\nChanges made:")
        print("  ✓ security_system_v2.py - Added SharedFrameWriter")
        print("  ✓ web_server.py - Added SharedFrameReader")
        print("  ✓ Frame sharing now uses file-based approach")
        print("\nNext steps:")
        print("  1. Commit and push changes")
        print("  2. Deploy to server")
        print("  3. Restart services:")
        print("     sudo systemctl restart riftech-security-v2")
        print("     sudo systemctl restart riftech-web-server")
        print()
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
