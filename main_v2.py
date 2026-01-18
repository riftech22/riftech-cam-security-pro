#!/usr/bin/env python3
"""
Riftech Security System V2 - Main Entry Point
High-Performance AI-Powered Security Camera System
Uses Shared Memory, Motion-First Detection, and Multi-Process Architecture
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import config
from src.core.logger import logger
from src.security_system_v2 import enhanced_security_system


def apply_shared_frame_fix():
    """
    Automatically apply shared frame fix on first run
    This ensures file-based frame sharing works for all users
    """
    import re
    
    # Fix flag file
    flag_file = Path("data/.shared_frame_fix_applied")
    flag_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if fix already applied
    if flag_file.exists():
        return True
    
    logger.info("=" * 60)
    logger.info("Applying Shared Frame Fix (Automatic)")
    logger.info("=" * 60)
    
    try:
        # Update security_system_v2.py
        with open('src/security_system_v2.py', 'r') as f:
            ss_content = f.read()
        
        # Add import
        if 'from .core.shared_frame import SharedFrameWriter' not in ss_content:
            ss_content = ss_content.replace(
                'from .core.frame_manager import frame_manager',
                'from .core.frame_manager import frame_manager\nfrom .core.shared_frame import SharedFrameWriter'
            )
            logger.info("✓ Added SharedFrameWriter import")
        
        # Add shared_frame_writer to CaptureWorker
        if 'self.shared_frame_writer' not in ss_content:
            ss_content = re.sub(
                r'(self\.motion_interval = 5  # Only detect every N frames)',
                r'\1\n        self.shared_frame_writer = None',
                ss_content
            )
            logger.info("✓ Added shared_frame_writer to CaptureWorker")
        
        # Initialize SharedFrameWriter in EnhancedSecuritySystem
        if 'SharedFrameWriter("camera"' not in ss_content:
            ss_content = ss_content.replace(
                'if not frame_manager.register_frame("camera", frame_shape):\n            logger.warning("Frame already registered, attaching...")',
                '''if not frame_manager.register_frame("camera", frame_shape):
            logger.warning("Frame already registered, attaching...")
        
        # Initialize file-based shared frame (for web server)
        frame_shape = (config.camera.height, config.camera.width, 3)
        self.shared_frame_writer = SharedFrameWriter("camera", frame_shape)'''
            )
            logger.info("✓ Initialized SharedFrameWriter in EnhancedSecuritySystem")
        
        # Add write to shared_frame_writer
        if 'self.shared_frame_writer.write' not in ss_content:
            ss_content = re.sub(
                r'(if not frame_manager\.write_frame\(self\.camera_name, full_frame\):\n                    logger\.error\(f"Failed to write frame to shared memory: \{self\.camera_name\}"\))',
                r'''\1
                
                # Also write to file-based shared frame (for web server)
                if self.shared_frame_writer:
                    self.shared_frame_writer.write(full_frame)''',
                ss_content
            )
            logger.info("✓ Added write to shared_frame_writer in CaptureWorker")
        
        # Write back
        with open('src/security_system_v2.py', 'w') as f:
            f.write(ss_content)
        
        # Update web_server.py
        with open('src/api/web_server.py', 'r') as f:
            ws_content = f.read()
        
        # Add import
        if 'from ..core.shared_frame import SharedFrameReader' not in ws_content:
            ws_content = ws_content.replace(
                'from ..core.frame_manager import frame_manager',
                'from ..core.frame_manager import frame_manager\nfrom ..core.shared_frame import SharedFrameReader'
            )
            logger.info("✓ Added SharedFrameReader import")
        
        # Initialize SharedFrameReader
        if 'SharedFrameReader("camera")' not in ws_content:
            ws_content = ws_content.replace(
                'logger.info("Using enhanced security system for streaming (optimized)")',
                'logger.info("Using enhanced security system for streaming (optimized)")\n            \n            shared_frame_reader = SharedFrameReader("camera")'
            )
            logger.info("✓ Initialized SharedFrameReader in streaming endpoint")
        
        # Replace read_frame call
        ws_content = ws_content.replace(
            'frame = frame_manager.read_frame("camera")',
            'frame = shared_frame_reader.read()'
        )
        logger.info("✓ Replaced frame_manager.read_frame with shared_frame_reader.read")
        
        # Write back
        with open('src/api/web_server.py', 'w') as f:
            f.write(ws_content)
        
        # Create flag file
        flag_file.touch()
        
        logger.info("=" * 60)
        logger.info("✓ Shared Frame Fix Applied Successfully!")
        logger.info("=" * 60)
        logger.info("Changes:")
        logger.info("  ✓ security_system_v2.py - Added SharedFrameWriter")
        logger.info("  ✓ web_server.py - Added SharedFrameReader")
        logger.info("  ✓ File-based frame sharing enabled")
        logger.info("")
        logger.info("This fix ensures cross-process frame sharing works correctly.")
        logger.info("You should restart the application to apply all changes.")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.warning(f"Failed to apply shared frame fix: {e}")
        logger.warning("This may cause streaming issues. Please run fix_shared_frame.py manually.")
        return False


class SecurityAppV2:
    """Main application class for V2"""
    
    def __init__(self):
        self.security_system = enhanced_security_system
        self.running = False
    
    async def initialize(self):
        """Initialize application"""
        logger.info("=" * 60)
        logger.info("Riftech Security System V2 Starting...")
        logger.info("High-Performance Architecture")
        logger.info("=" * 60)
        
        try:
            await self.security_system.initialize()
            logger.info("Application initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize: {e}", exc_info=True)
            raise
    
    def start(self):
        """Start application"""
        try:
            self.security_system.start()
            self.running = True
            
            logger.info("=" * 60)
            logger.info("Riftech Security System V2 Running!")
            logger.info(f"Mode: {self.security_system.system_mode}")
            logger.info(f"Capture FPS: {config.camera.fps}")
            logger.info(f"Detection: Motion-First Enabled")
            logger.info(f"Streaming: MJPEG Enabled")
            logger.info("Press Ctrl+C to stop")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Failed to start: {e}", exc_info=True)
            raise
    
    async def stop(self):
        """Stop application"""
        if not self.running:
            return
        
        logger.info("Stopping Riftech Security System V2...")
        self.running = False
        
        await self.security_system.cleanup()
        
        logger.info("=" * 60)
        logger.info("Riftech Security System V2 Stopped")
        logger.info("=" * 60)
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            if self.running:
                loop = asyncio.get_event_loop()
                loop.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main async entry point"""
    # Apply shared frame fix automatically on first run
    apply_shared_frame_fix()
    
    app = SecurityAppV2()
    app.setup_signal_handlers()
    
    try:
        await app.initialize()
        app.start()
        
        # Print initial stats after 3 seconds
        await asyncio.sleep(3)
        stats = app.security_system.get_stats()
        logger.info(f"Current FPS: {stats['fps']:.1f}")
        logger.info(f"Persons Detected: {stats['persons_detected']}")
        logger.info(f"Motion Ratio: {stats['motion_ratio']:.1%}")
        
        # Keep running until stopped
        while app.running:
            # Print stats every 30 seconds
            await asyncio.sleep(30)
            if app.running:
                stats = app.security_system.get_stats()
                logger.info(f"Stats - FPS: {stats['fps']:.1f}, "
                          f"People: {stats['persons_detected']}, "
                          f"Motion: {stats['motion_ratio']:.1%}")
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        await app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)
