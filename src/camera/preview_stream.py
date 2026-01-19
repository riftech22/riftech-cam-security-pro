"""
Preview Stream - High FPS, Low Latency
Separated from detection pipeline (Frigate-style architecture)
"""

import subprocess
import threading
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class PreviewStream:
    """
    High-FPS preview stream for smooth UI rendering
    Separate from detection pipeline to avoid blocking
    """
    
    def __init__(self, rtsp_url: str, fps_max: int = 30, resolution: str = "640x480"):
        """
        Initialize preview stream
        
        Args:
            rtsp_url: RTSP camera URL
            fps_max: Maximum FPS for preview (default: 30)
            resolution: Resolution (default: 640x480)
        """
        self.rtsp_url = rtsp_url
        self.fps_max = fps_max
        self.resolution = resolution
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
    def start(self):
        """Start preview stream in separate thread"""
        if self.running:
            logger.warning("Preview stream already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_ffmpeg, daemon=True)
        self.thread.start()
        logger.info(f"Preview stream started: {self.resolution} @ {self.fps_max}fps max")
        
    def _run_ffmpeg(self):
        """Run FFmpeg for preview stream"""
        try:
            # FFmpeg command for high-FPS preview (Frigate-style)
            cmd = [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-stimeout", "5000000",
                "-i", self.rtsp_url,
                "-f", "mjpeg",  # MJPEG for streaming
                "-q:v", "5",  # Quality 5 (lower = better)
                "-fpsmax", str(self.fps_max),  # Max FPS (Frigate key!)
                "-vf", f"scale={self.resolution}",  # Resolution
                "-"
            ]
            
            logger.debug(f"Preview FFmpeg command: {' '.join(cmd)}")
            
            # Start FFmpeg process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )
            
            # Read stdout to keep pipe from blocking
            while self.running and self.process.poll() is None:
                try:
                    self.process.stdout.read(1024 * 1024)
                except:
                    break
                    
        except Exception as e:
            logger.error(f"Preview stream error: {e}")
        finally:
            self.stop()
            
    def stop(self):
        """Stop preview stream"""
        self.running = False
        
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None
            
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
            
        logger.info("Preview stream stopped")
        
    def is_running(self) -> bool:
        """Check if preview stream is running"""
        return self.running and self.process and self.process.poll() is None
