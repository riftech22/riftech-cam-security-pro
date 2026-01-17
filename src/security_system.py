"""
Main Security System
Core application that integrates all modules for security monitoring
"""

import cv2
import numpy as np
import time
import threading
import asyncio
import json
from typing import Optional, List, Dict, Callable
from datetime import datetime
from pathlib import Path

from .core.config import config
from .core.logger import logger
from .database.models import db

# Shared frame paths for web server
SHARED_FRAME_PATH = Path("data/shared_frame.jpg")
SHARED_STATS_PATH = Path("data/shared_stats.json")

# Ensure data directory exists
Path("data").mkdir(parents=True, exist_ok=True)
from .detection.yolo_detector import YOLODetector
from .detection.skeleton_detector import SkeletonDetector
from .detection.face_detector import FaceDetector
from .detection.motion_detector import MotionDetector
from .detection.base import PersonDetection, apply_clahe
from .utils.zone_manager import ZoneManager
from .camera.capture import CameraCapture, USBCameraCapture, V380SplitCameraCapture
from .notifications.telegram import telegram_notifier, TELEGRAM_AVAILABLE


class SecuritySystem:
    """Main security system orchestrator"""
    
    def __init__(self):
        # System state
        self.running = False
        self.system_mode = "normal"  # normal, armed, alerted
        
        # Detection modules
        self.yolo_detector = None
        self.skeleton_detector = None
        self.face_detector = None
        self.motion_detector = None
        
        # Telegram notifier
        self.telegram_notifier = telegram_notifier
        self.telegram_notifier.security_system = self
        
        # Zone management
        self.zone_manager = ZoneManager()
        
        # Camera
        self.camera = None
        self.current_frame = None
        self.frame_count = 0
        
        # V380 split camera support
        self.is_v380_split = False
        self.top_frame = None
        self.bottom_frame = None
        self.all_detections = []
        
        # Statistics
        self.stats = {
            "persons_detected": 0,
            "alerts_triggered": 0,
            "breaches_detected": 0,
            "trusted_faces_seen": 0,
            "uptime": 0,
            "top_camera_persons": 0,
            "bottom_camera_persons": 0
        }
        
        # Callbacks
        self.on_alert: Optional[Callable] = None
        self.on_breach: Optional[Callable] = None
        self.on_trusted_face: Optional[Callable] = None
        self.on_new_frame: Optional[Callable] = None
        
        # Threading
        self.process_thread = None
        self._lock = threading.Lock()
        
        # Alert cooldown
        self.last_alert_time = 0
        self.alert_cooldown = 5.0  # seconds
    
    async def initialize(self):
        """Initialize all system components"""
        logger.info("Initializing Security System...")
        
        # Initialize database
        await db.initialize()
        
        # Initialize detectors
        self.yolo_detector = YOLODetector(confidence=config.detection.yolo_confidence)
        self.yolo_detector.initialize()
        
        self.skeleton_detector = SkeletonDetector()
        self.skeleton_detector.initialize()
        
        self.face_detector = FaceDetector()
        self.face_detector.initialize()
        
        self.motion_detector = MotionDetector()
        self.motion_detector.initialize()
        
        # Initialize camera
        if config.camera.type == "v380_split":
            self.is_v380_split = True
            self.camera = V380SplitCameraCapture(
                rtsp_url=config.camera.rtsp_url,
                width=config.camera.width,
                height=config.camera.height,
                detect_fps=config.camera.detect_fps
            )
            logger.info("Initialized V380 split camera capture")
        elif config.camera.type == "rtsp":
            self.is_v380_split = False
            self.camera = CameraCapture(
                rtsp_url=config.camera.rtsp_url,
                width=config.camera.width,
                height=config.camera.height
            )
        else:
            self.is_v380_split = False
            self.camera = USBCameraCapture(
                camera_id=config.camera.camera_id,
                width=config.camera.width,
                height=config.camera.height
            )
        
        if not self.camera.initialize():
            raise RuntimeError("Failed to initialize camera")
        
        # Create directories
        Path(config.paths.alerts_dir).mkdir(parents=True, exist_ok=True)
        Path(config.paths.snapshots_dir).mkdir(parents=True, exist_ok=True)
        Path(config.paths.recordings_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info("Security System initialized successfully")
    
    def start(self):
        """Start the security system"""
        if self.running:
            logger.warning("System already running")
            return
        
        logger.info("Starting Security System...")
        self.running = True
        self.start_time = time.time()
        
        # Start camera capture
        if isinstance(self.camera, (CameraCapture, V380SplitCameraCapture)):
            self.camera.start()
        
        # Start processing thread
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.process_thread.start()
        
        # Start Telegram command handler (if enabled)
        if self.telegram_notifier.enabled and TELEGRAM_AVAILABLE:
            # Run in separate thread to avoid event loop conflict
            def run_telegram_handler():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.telegram_notifier.start_command_handler())
                except Exception as e:
                    logger.error(f"Failed to start Telegram command handler: {e}")
            
            telegram_thread = threading.Thread(target=run_telegram_handler, daemon=True)
            telegram_thread.start()
            logger.info("Telegram command handler thread started")
        
        logger.info("Security System started")
    
    def _process_loop(self):
        """Main processing loop"""
        logger.info("Processing loop started")
        
        # Frame skipping to maintain FPS
        process_every_n_frames = max(1, int(30 / config.camera.fps))  # Target 30 FPS processing
        self.frame_count = 0
        last_process_time = time.time()
        
        while self.running:
            try:
                start_time = time.time()
                
                if self.is_v380_split:
                    # Read split frames from V380 camera
                    frame_data = self.camera.read()
                    if frame_data is None:
                        time.sleep(0.01)
                        continue
                    
                    self.current_frame = frame_data['full']
                    self.top_frame = frame_data['top']
                    self.bottom_frame = frame_data['bottom']
                    self.frame_count += 1
                    
                    # Skip processing to maintain FPS
                    if self.frame_count % process_every_n_frames == 0:
                        # Process split frames
                        processed_frame, detections = self._process_split_frames(
                            frame_data['top'],
                            frame_data['bottom'],
                            frame_data['full']
                        )
                        
                        # Write shared frame for web server
                        self._write_shared_frame(processed_frame)
                        
                        # Update stats less frequently
                        self.stats["uptime"] = time.time() - self.start_time
                        
                        # Call frame callback
                        if self.on_new_frame:
                            self.on_new_frame(processed_frame)
                        
                        last_process_time = time.time()
                else:
                    # Read regular frame
                    frame = self.camera.read()
                    if frame is None:
                        time.sleep(0.01)
                        continue
                    
                    self.current_frame = frame
                    self.frame_count += 1
                    
                    # Skip processing to maintain FPS
                    if self.frame_count % process_every_n_frames == 0:
                        # Process regular frame
                        processed_frame, detections = self._process_frame(frame)
                        
                        # Write shared frame for web server
                        self._write_shared_frame(processed_frame)
                        
                        # Update stats
                        self.stats["uptime"] = time.time() - self.start_time
                        
                        # Call frame callback
                        if self.on_new_frame:
                            self.on_new_frame(processed_frame)
                        
                        last_process_time = time.time()
                
                # Calculate actual FPS
                elapsed = time.time() - start_time
                actual_fps = 1.0 / (time.time() - last_process_time) if time.time() > last_process_time else config.camera.fps
                
                # Log FPS every 5 seconds
                if self.frame_count % (5 * config.camera.fps) == 0:
                    logger.info(f"Actual FPS: {actual_fps:.1f} | Target: {config.camera.fps} | Frame skip: {process_every_n_frames}")
                
                # Small sleep to prevent CPU overload
                if elapsed < 0.01:
                    time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Processing error: {e}")
                time.sleep(0.1)
        
        logger.info("Processing loop stopped")
    
    def _write_shared_frame(self, frame: np.ndarray):
        """Write frame to shared file for web server"""
        try:
            # Encode to JPEG with lower quality for faster encoding
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
            _, encoded = cv2.imencode('.jpg', frame, encode_param)
            jpeg_bytes = encoded.tobytes()
            
            # Write to file
            SHARED_FRAME_PATH.write_bytes(jpeg_bytes)
            
            # Write stats less frequently
            if self.frame_count % 10 == 0:  # Every 10 frames
                stats = self.get_stats()
                stats["frame_count"] = self.frame_count
                stats["fps"] = self._get_fps()
                SHARED_STATS_PATH.write_text(json.dumps(stats))
        except Exception as e:
            logger.error(f"Error writing shared frame: {e}")
    
    def _process_frame(self, frame: np.ndarray) -> tuple:
        """
        Process a single frame through all detectors
        
        Args:
            frame: Input frame
            
        Returns:
            Tuple of (processed_frame, detections)
        """
        # Enhance frame
        enhanced_frame = apply_clahe(frame)
        
        # Motion detection
        motion_detected, motion_mask = self.motion_detector.detect(enhanced_frame)
        
        # YOLO person detection
        person_detections = self.yolo_detector.detect(enhanced_frame)
        
        # Skeleton detection for each person
        for det in person_detections:
            x1, y1, x2, y2 = det.bbox
            
            # Extract person region
            person_region = enhanced_frame[y1:y2, x1:x2]
            if person_region.size > 0:
                # Get skeleton
                skeleton = self.skeleton_detector.detect(person_region)
                if skeleton:
                    det.skeleton = skeleton
                    # Adjust skeleton coordinates to full frame
                    det.skeleton = [(x + x1, y + y1) for x, y in skeleton]
                
                # Face detection and recognition
                face_bboxes = self.face_detector.detect_faces(person_region)
                if face_bboxes:
                    face_recognition = self.face_detector.recognize_face(
                        person_region, face_bboxes[0]
                    )
                    if face_recognition:
                        det.face_confidence = face_recognition['confidence']
                        det.is_trusted = face_recognition['is_trusted']
                        det.face_name = face_recognition['name']
        
        # Check zone breaches
        person_centers = [det.center for det in person_detections]
        breached_zones = self.zone_manager.check_breaches(person_centers)
        
        # Handle breaches
        if breached_zones and self.system_mode == "armed":
            self._handle_breach(breached_zones, person_detections, frame)
        
        # Handle trusted faces
        for det in person_detections:
            if det.is_trusted:
                self._handle_trusted_face(det)
        
        # Draw on frame
        display_frame = self._draw_detections(frame, person_detections, breached_zones)
        
        return display_frame, person_detections
    
    def _process_split_frames(
        self,
        top_frame: np.ndarray,
        bottom_frame: np.ndarray,
        full_frame: np.ndarray
    ) -> tuple:
        """
        Process split frames from V380 camera
        
        Args:
            top_frame: Top half of frame (fixed camera)
            bottom_frame: Bottom half of frame (PTZ camera)
            full_frame: Original full frame
            
        Returns:
            Tuple of (processed_frame, all_detections)
        """
        # Process top frame
        top_detections = self._process_single_frame(top_frame, "top")
        self.stats["top_camera_persons"] = len(top_detections)
        
        # Process bottom frame
        bottom_detections = self._process_single_frame(bottom_frame, "bottom")
        self.stats["bottom_camera_persons"] = len(bottom_detections)
        
        # Combine all detections
        self.all_detections = top_detections + bottom_detections
        self.stats["persons_detected"] = len(self.all_detections)
        
        # Draw on full frame
        display_frame = self._draw_split_detections(
            full_frame,
            top_detections,
            bottom_detections
        )
        
        return display_frame, self.all_detections
    
    def _process_single_frame(
        self,
        frame: np.ndarray,
        camera_label: str = ""
    ) -> List[PersonDetection]:
        """
        Process a single frame through all detectors
        
        Args:
            frame: Input frame
            camera_label: Label for this frame (top/bottom)
            
        Returns:
            List of person detections
        """
        # Enhance frame
        enhanced_frame = apply_clahe(frame)
        
        # Motion detection
        motion_detected, motion_mask = self.motion_detector.detect(enhanced_frame)
        
        # YOLO person detection
        person_detections = self.yolo_detector.detect(enhanced_frame)
        
        # Skeleton detection for each person
        for det in person_detections:
            x1, y1, x2, y2 = det.bbox
            
            # Extract person region
            person_region = enhanced_frame[y1:y2, x1:x2]
            if person_region.size > 0:
                # Get skeleton
                skeleton = self.skeleton_detector.detect(person_region)
                if skeleton:
                    det.skeleton = skeleton
                
                # Face detection and recognition
                face_bboxes = self.face_detector.detect_faces(person_region)
                if face_bboxes:
                    face_recognition = self.face_detector.recognize_face(
                        person_region, face_bboxes[0]
                    )
                    if face_recognition:
                        det.face_confidence = face_recognition['confidence']
                        det.is_trusted = face_recognition['is_trusted']
                        det.face_name = face_recognition['name']
            
            # Add camera label if split camera
            if self.is_v380_split:
                det.camera_label = camera_label
        
        return person_detections
    
    def _draw_split_detections(
        self,
        frame: np.ndarray,
        top_detections: List[PersonDetection],
        bottom_detections: List[PersonDetection]
    ) -> np.ndarray:
        """Draw detections on split frame"""
        frame = frame.copy()
        
        # Draw divider line between cameras
        split_point = frame.shape[0] // 2
        cv2.line(frame, (0, split_point), (frame.shape[1], split_point), 
                 (255, 255, 0), 2)
        
        # Draw camera labels
        cv2.putText(frame, "TOP CAMERA (Fixed)", (20, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 4)
        cv2.putText(frame, "BOTTOM CAMERA (PTZ)", (20, split_point + 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 4)
        
        # Draw zones
        frame = self.zone_manager.draw_zones(frame, [])
        
        # Draw top detections
        for det in top_detections:
            x1, y1, x2, y2 = det.bbox
            
            # Determine color
            if det.is_trusted:
                color = (0, 255, 0)  # Green
                label = f"{det.face_name}"
            else:
                color = (0, 0, 255)  # Red
                label = f"Person"
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5)
            
            # Draw skeleton if available
            if det.skeleton:
                frame = self.skeleton_detector.draw_skeleton(frame, det.skeleton, color)
            
            # Draw label
            label = f"{label} {det.confidence:.2f}"
            cv2.putText(frame, label, (x1, y1 - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 4)
        
        # Draw bottom detections
        for det in bottom_detections:
            x1, y1, x2, y2 = det.bbox
            
            # Adjust Y coordinates for bottom camera
            offset = split_point
            
            # Determine color
            if det.is_trusted:
                color = (0, 255, 0)  # Green
                label = f"{det.face_name}"
            else:
                color = (0, 0, 255)  # Red
                label = f"Person"
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1 + offset), (x2, y2 + offset), color, 5)
            
            # Draw skeleton if available
            if det.skeleton:
                adjusted_skeleton = [(x, y + offset) for x, y in det.skeleton]
                frame = self.skeleton_detector.draw_skeleton(frame, adjusted_skeleton, color)
            
            # Draw label
            label = f"{label} {det.confidence:.2f}"
            cv2.putText(frame, label, (x1, y1 - 20 + offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 4)
        
        # Draw system status
        status_text = f"Mode: {self.system_mode.upper()} | FPS: {self._get_fps():.1f}"
        cv2.putText(frame, status_text, (20, frame.shape[0] - 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 4)
        
        # Draw stats
        stats_text = f"Top: {len(top_detections)} | Bottom: {len(bottom_detections)} | Total: {self.stats['persons_detected']}"
        cv2.putText(frame, stats_text, (20, frame.shape[0] - 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
        
        return frame
    
    def _draw_detections(
        self,
        frame: np.ndarray,
        detections: List[PersonDetection],
        breached_zones: List[int]
    ) -> np.ndarray:
        """Draw detections on frame"""
        frame = frame.copy()
        
        # Draw zones
        frame = self.zone_manager.draw_zones(frame, breached_zones)
        
        # Draw persons
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            
            # Determine color
            if det.is_trusted:
                color = (0, 255, 0)  # Green
                label = f"{det.face_name}"
            else:
                color = (0, 255, 255)  # Cyan
                label = f"{det.class_name}"
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5)
            
            # Draw skeleton if available
            if det.skeleton:
                frame = self.skeleton_detector.draw_skeleton(frame, det.skeleton, color)
            
            # Draw label
            label = f"{label} {det.confidence:.2f}"
            cv2.putText(frame, label, (x1, y1 - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 4)
        
        # Draw system status
        status_text = f"Mode: {self.system_mode.upper()} | FPS: {self._get_fps():.1f}"
        cv2.putText(frame, status_text, (20, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 4)
        
        # Draw stats
        stats_text = f"People: {self.stats['persons_detected']} | Breaches: {self.stats['breaches_detected']}"
        cv2.putText(frame, stats_text, (20, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
        
        return frame
    
    def _handle_breach(
        self,
        breached_zones: List[int],
        detections: List[PersonDetection],
        frame: np.ndarray
    ):
        """Handle zone breach"""
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_alert_time < self.alert_cooldown:
            return
        
        self.last_alert_time = current_time
        self.stats["breaches_detected"] += 1
        
        # Save alert image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        alert_path = Path(config.paths.alerts_dir) / f"breach_{timestamp}.jpg"
        cv2.imwrite(str(alert_path), frame)
        
        # Log event
        logger.warning(f"BREACH DETECTED! Zones: {breached_zones}")
        
        # Send Telegram notification
        asyncio.create_task(
            self.telegram_notifier.send_breach_alert(breached_zones, str(alert_path))
        )
        
        # Call callback
        if self.on_breach:
            self.on_breach(breached_zones, detections, str(alert_path))
    
    def _handle_trusted_face(self, detection: PersonDetection):
        """Handle trusted face detection"""
        self.stats["trusted_faces_seen"] += 1
        
        if detection.face_name:
            logger.info(f"Trusted face detected: {detection.face_name}")
            
            # Send Telegram notification
            asyncio.create_task(
                self.telegram_notifier.send_trusted_face_alert(detection.face_name)
            )
            
            if self.on_trusted_face:
                self.on_trusted_face(detection)
    
    def _get_fps(self) -> float:
        """Calculate current FPS"""
        if self.stats["uptime"] > 0:
            return self.frame_count / self.stats["uptime"]
        return 0.0
    
    def set_mode(self, mode: str):
        """Set system mode (normal, armed, alerted)"""
        if mode in ["normal", "armed", "alerted"]:
            self.system_mode = mode
            self.zone_manager.is_armed = (mode == "armed")
            logger.info(f"System mode set to: {mode}")
    
    def get_stats(self) -> Dict:
        """Get system statistics"""
        return self.stats.copy()
    
    def get_system_status(self) -> Dict:
        """Get complete system status"""
        return {
            "running": self.running,
            "mode": self.system_mode,
            "stats": self.stats,
            "fps": self._get_fps(),
            "zones": self.zone_manager.get_all_zones(),
            "camera": self.camera.get_info() if self.camera else None
        }
    
    def stop(self):
        """Stop the security system"""
        logger.info("Stopping Security System...")
        self.running = False
        
        if self.process_thread:
            self.process_thread.join(timeout=3.0)
        
        if self.camera:
            if isinstance(self.camera, (CameraCapture, V380SplitCameraCapture)):
                self.camera.stop()
        
        # Stop Telegram command handler
        if self.telegram_notifier.enabled:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.telegram_notifier.stop_command_handler())
            except Exception as e:
                logger.error(f"Failed to stop Telegram command handler: {e}")
        
        logger.info("Security System stopped")
    
    async def test_telegram(self) -> bool:
        """Test Telegram notification connection"""
        return await self.telegram_notifier.test_connection()
    
    async def cleanup(self):
        """Clean up all resources"""
        self.stop()
        
        if self.yolo_detector:
            self.yolo_detector.cleanup()
        if self.skeleton_detector:
            self.skeleton_detector.cleanup()
        if self.face_detector:
            self.face_detector.cleanup()
        if self.motion_detector:
            self.motion_detector.cleanup()
        if self.camera:
            self.camera.cleanup()
        
        logger.info("Security System cleaned up")


# Global instance
security_system = SecuritySystem()
