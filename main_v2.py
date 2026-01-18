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
            logger.info(f"Detection: YOLO Always Running (No Motion-First)")
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
