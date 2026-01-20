"""
Camera Capture Module
Handles video capture from RTSP streams with FFmpeg pipeline
Supports V380 split frame cameras
"""

import cv2
import numpy as np
import subprocess
from typing import Optional, Tuple, Dict
import threading
import queue
import time

from ..core.logger import logger


class CameraCapture:
    """Camera capture using FFmpeg pipeline for RTSP streams"""
    
    def __init__(self, rtsp_url: str, width: int = 1280, height: int = 720):
        """
        Initialize camera capture
        
        Args:
            rtsp_url: RTSP stream URL
            width: Frame width
            height: Frame height
        """
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
        self.fps = 15
        
        # FFmpeg command - Using MJPEG for more reliable RTSP streaming
        self.ffmpeg_cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-stimeout', '5000000',  # 5 second timeout
            '-i', rtsp_url,
            '-vf', f'fps={self.fps},scale={width}:{height}',
            '-f', 'mjpeg',  # Use MJPEG instead of rawvideo
            '-q:v', '3',  # JPEG quality (2-31, lower is better)
            '-'
        ]
        
        # Capture state
        self.process = None
        self.frame_queue = queue.Queue(maxsize=10)
        self.running = False
        self.capture_thread = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        Initialize FFmpeg pipeline
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"Starting FFmpeg pipeline for {self.rtsp_url}")
            self.process = subprocess.Popen(
                self.ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )
            self._initialized = True
            logger.info("FFmpeg pipeline started")
            return True
        except Exception as e:
            logger.error(f"Failed to start FFmpeg: {e}")
            return False
    
    def start(self):
        """Start capture thread"""
        if not self._initialized:
            if not self.initialize():
                return
        
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        logger.info("Camera capture started")
    
    def _capture_loop(self):
        """Capture loop running in separate thread - Using MJPEG for reliability"""
        frame_bytes = b''
        fps_counter = 0
        fps_time = time.time()
        consecutive_errors = 0
        
        while self.running and self.process:
            try:
                # Read data from FFmpeg (MJPEG format)
                data = self.process.stdout.read(1024)
                
                if not data:
                    if consecutive_errors < 10:
                        logger.debug(f"No data from FFmpeg (attempt {consecutive_errors + 1})")
                    consecutive_errors += 1
                    if consecutive_errors > 100:
                        logger.error("No more data from FFmpeg, attempting reconnect...")
                        self.initialize()
                        consecutive_errors = 0
                    time.sleep(0.1)
                    continue
                
                frame_bytes += data
                consecutive_errors = 0
                
                # Check for JPEG end marker (JPEG ends with FF D9)
                if b'\xff\xd9' in frame_bytes:
                    # Extract complete frame
                    end_marker = frame_bytes.find(b'\xff\xd9') + 2
                    jpeg_data = frame_bytes[:end_marker]
                    frame_bytes = frame_bytes[end_marker:]
                    
                    # Decode JPEG to numpy array
                    frame = cv2.imdecode(
                        np.frombuffer(jpeg_data, dtype=np.uint8),
                        cv2.IMREAD_COLOR
                    )
                    
                    if frame is not None:
                        # Put in queue (drop if full)
                        try:
                            self.frame_queue.put_nowait(frame)
                            fps_counter += 1
                        except queue.Full:
                            # Drop oldest frame
                            try:
                                self.frame_queue.get_nowait()
                                self.frame_queue.put_nowait(frame)
                            except queue.Empty:
                                pass
                
                # Calculate FPS every second
                if time.time() - fps_time >= 1.0:
                    self.fps = fps_counter
                    fps_counter = 0
                    fps_time = time.time()
                    if self.fps > 0:
                        logger.debug(f"Capture FPS: {self.fps}")
                
            except Exception as e:
                logger.error(f"Capture error: {e}")
                consecutive_errors += 1
                time.sleep(0.1)
        
        logger.info("Camera capture loop stopped")
    
    def read(self) -> Optional[np.ndarray]:
        """
        Read a frame from the queue
        
        Returns:
            Frame or None if no frame available
        """
        try:
            return self.frame_queue.get(timeout=1.0)
        except queue.Empty:
            return None
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """
        Get the latest frame without blocking
        
        Returns:
            Latest frame or None
        """
        try:
            # Get all frames in queue
            frames = []
            while not self.frame_queue.empty():
                frames.append(self.frame_queue.get_nowait())
            
            # Return the latest one
            return frames[-1] if frames else None
        except Exception as e:
            logger.error(f"Error getting latest frame: {e}")
            return None
    
    def stop(self):
        """Stop capture"""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        logger.info("Camera capture stopped")
    
    def cleanup(self):
        """Clean up resources"""
        self.stop()
        
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None
        
        self._initialized = False
        logger.info("Camera capture cleaned up")
    
    def is_connected(self) -> bool:
        """Check if camera is connected"""
        return self._initialized and self.process is not None and self.process.poll() is None
    
    def get_info(self) -> dict:
        """Get camera information"""
        return {
            "rtsp_url": self.rtsp_url,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "connected": self.is_connected(),
            "running": self.running
        }


class USBCameraCapture:
    """USB camera capture using OpenCV"""
    
    def __init__(self, camera_id: int = 0, width: int = 1280, height: int = 720):
        """
        Initialize USB camera capture
        
        Args:
            camera_id: Camera ID
            width: Frame width
            height: Frame height
        """
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.cap = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        Initialize camera
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"Initializing USB camera {self.camera_id}")
            self.cap = cv2.VideoCapture(self.camera_id)
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera {self.camera_id}")
                return False
            
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, 15)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
            self._initialized = True
            logger.info(f"USB camera {self.camera_id} initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            return False
    
    def read(self) -> Optional[np.ndarray]:
        """
        Read a frame
        
        Returns:
            Frame or None
        """
        if not self._initialized:
            return None
        
        ret, frame = self.cap.read()
        return frame if ret else None
    
    def release(self):
        """Release camera"""
        if self.cap:
            self.cap.release()
            self.cap = None
        self._initialized = False
        logger.info("USB camera released")
    
    def is_connected(self) -> bool:
        """Check if camera is connected"""
        return self._initialized and self.cap is not None and self.cap.isOpened()
    
    def get_info(self) -> dict:
        """Get camera information"""
        return {
            "camera_id": self.camera_id,
            "width": self.width,
            "height": self.height,
            "connected": self.is_connected()
        }


class V380SplitCameraCapture:
    """
    V380 Split Camera Capture using FFmpeg pipeline
    Handles cameras that send 2 views (top/bottom) in single frame
    """
    
    def __init__(
        self,
        rtsp_url: str,
        width: int = 1280,
        height: int = 720,
        detect_fps: int = 5
    ):
        """
        Initialize V380 split camera capture
        
        Args:
            rtsp_url: RTSP stream URL
            width: Frame width (full frame)
            height: Frame height (full frame, will be split in half)
            detect_fps: Target FPS for detection
        """
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
        self.fps = detect_fps
        
        # Split settings
        self.split_height = height // 2  # Each half gets half the height
        self.split_width = width
        
        # FFmpeg command for capture
        self.ffmpeg_cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-stimeout', '5000000',  # 5 second timeout
            '-i', rtsp_url,
            '-vf', f'fps={detect_fps},scale={width}:{height}',
            '-f', 'image2pipe',
            '-vcodec', 'mjpeg',
            '-q:v', '2',
            '-'
        ]
        
        # Capture state
        self.process = None
        self.frame_queue = queue.Queue(maxsize=10)
        self.running = False
        self.capture_thread = None
        self._initialized = False
        
        # Statistics
        self.capture_fps = 0
        self.frame_count = 0
        
    def initialize(self) -> bool:
        """
        Initialize FFmpeg pipeline
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"Starting V380 FFmpeg pipeline for {self.rtsp_url}")
            logger.info(f"Frame will be split: {self.width}x{self.height} -> 2x {self.width}x{self.split_height}")
            self.process = subprocess.Popen(
                self.ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )
            self._initialized = True
            logger.info("V380 FFmpeg pipeline started")
            return True
        except Exception as e:
            logger.error(f"Failed to start V380 FFmpeg: {e}")
            return False
    
    def start(self):
        """Start capture thread"""
        if not self._initialized:
            if not self.initialize():
                return
        
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        logger.info("V380 camera capture started")
    
    def _capture_loop(self):
        """Capture loop running in separate thread"""
        frame_bytes = b''
        fps_counter = 0
        fps_time = time.time()
        
        while self.running and self.process:
            try:
                # Read data from FFmpeg
                data = self.process.stdout.read(1024)
                
                if not data:
                    logger.warning("No more data from FFmpeg")
                    break
                
                frame_bytes += data
                
                # Check for JPEG end marker (JPEG ends with FF D9)
                if b'\xff\xd9' in frame_bytes:
                    # Extract complete frame
                    end_marker = frame_bytes.find(b'\xff\xd9') + 2
                    jpeg_data = frame_bytes[:end_marker]
                    frame_bytes = frame_bytes[end_marker:]
                    
                    # Decode JPEG to numpy array
                    frame = cv2.imdecode(
                        np.frombuffer(jpeg_data, dtype=np.uint8),
                        cv2.IMREAD_COLOR
                    )
                    
                    if frame is not None:
                        # Split frame into top and bottom
                        # CRITICAL: Frame must be resized to expected size first!
                        frame_height, frame_width = frame.shape[:2]
                        
                        # Resize to expected dimensions if different
                        if frame_width != self.width or frame_height != self.height:
                            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
                            logger.debug(f"Resized frame from {frame_height}x{frame_width} to {self.height}x{self.width}")
                        
                        # Now split at the correct height
                        split_point = self.height // 2
                        
                        top_frame = frame[:split_point, :, :]
                        bottom_frame = frame[split_point:, :, :]
                        
                        # Put split frames into queue
                        try:
                            self.frame_queue.put({
                                'timestamp': time.time(),
                                'top': top_frame,
                                'bottom': bottom_frame,
                                'full': frame  # Original frame for display
                            }, block=False)
                            
                            fps_counter += 1
                            
                        except queue.Full:
                            # Drop oldest frame
                            try:
                                self.frame_queue.get_nowait()
                                self.frame_queue.put({
                                    'timestamp': time.time(),
                                    'top': top_frame,
                                    'bottom': bottom_frame,
                                    'full': frame
                                }, block=False)
                            except queue.Empty:
                                pass
                
                # Calculate FPS
                if time.time() - fps_time >= 1.0:
                    self.capture_fps = fps_counter
                    fps_counter = 0
                    fps_time = time.time()
                
            except Exception as e:
                logger.error(f"V380 capture error: {e}")
                time.sleep(0.1)
        
        logger.info("V380 capture loop stopped")
    
    def read(self) -> Optional[Dict]:
        """
        Read split frames from queue
        
        Returns:
            Dictionary with 'top', 'bottom', and 'full' frames, or None
        """
        try:
            return self.frame_queue.get(timeout=1.0)
        except queue.Empty:
            return None
    
    def get_latest_frame(self) -> Optional[Dict]:
        """
        Get latest split frames without blocking
        
        Returns:
            Dictionary with 'top', 'bottom', and 'full' frames, or None
        """
        try:
            # Get all frames in queue
            frames = []
            while not self.frame_queue.empty():
                frames.append(self.frame_queue.get_nowait())
            
            # Return latest one
            return frames[-1] if frames else None
        except Exception as e:
            logger.error(f"Error getting latest V380 frame: {e}")
            return None
    
    def stop(self):
        """Stop capture"""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        logger.info("V380 camera capture stopped")
    
    def cleanup(self):
        """Clean up resources"""
        self.stop()
        
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None
        
        self._initialized = False
        logger.info("V380 camera capture cleaned up")
    
    def is_connected(self) -> bool:
        """Check if camera is connected"""
        return self._initialized and self.process is not None and self.process.poll() is None
    
    def get_info(self) -> dict:
        """Get camera information"""
        return {
            "rtsp_url": self.rtsp_url,
            "width": self.width,
            "height": self.height,
            "split_height": self.split_height,
            "fps": self.fps,
            "capture_fps": self.capture_fps,
            "connected": self.is_connected(),
            "running": self.running,
            "type": "v380_split"
        }
