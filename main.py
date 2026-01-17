#!/usr/bin/env python3
"""
Riftech Security System - Main Entry Point
Professional AI-powered security camera system
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import config
from src.core.logger import logger
from src.security_system import security_system


class SecurityApp:
    """Main application class"""
    
    def __init__(self):
        self.security_system = security_system
        self.running = False
    
    async def initialize(self):
        """Initialize the application"""
        logger.info("=" * 60)
        logger.info("Riftech Security System Starting...")
        logger.info("=" * 60)
        
        try:
            await self.security_system.initialize()
            logger.info("Application initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
    
    def start(self):
        """Start the application"""
        try:
            self.security_system.start()
            self.running = True
            
            logger.info("=" * 60)
            logger.info("Riftech Security System Running!")
            logger.info(f"Mode: {self.security_system.system_mode}")
            logger.info("Press Ctrl+C to stop")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Failed to start: {e}")
            raise
    
    async def stop(self):
        """Stop the application"""
        if not self.running:
            return
        
        logger.info("Stopping Riftech Security System...")
        self.running = False
        
        await self.security_system.cleanup()
        
        logger.info("=" * 60)
        logger.info("Riftech Security System Stopped")
        logger.info("=" * 60)
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main async entry point"""
    app = SecurityApp()
    app.setup_signal_handlers()
    
    try:
        await app.initialize()
        app.start()
        
        # Keep running until stopped
        while app.running:
            await asyncio.sleep(1)
            
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
