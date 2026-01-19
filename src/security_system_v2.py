"""
Enhanced Security System V2
High-performance security system with multi-process architecture
Uses shared memory, motion-first detection, and real-time streaming
"""

import cv2 as cv2
import numpy as np
import time
import threading
import asyncio
import json
import multiprocessing as mp
from typing import Optional, List, Dict, Callable
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from queue import Queue, Empty

from .core.config import config
from .core.logger import logger
from .core.frame_manager_v2 import frame_manager_v2
from .core.metadata_manager import metadata_manager
from .database.models import db

from .detection.yolo_detector import YOLODetector
from .detection.skeleton_detector import SkeletonDetector
from .detection.face_detector import FaceDetector
from .detection.enhanced_motion_detector import EnhancedMotionDetector, MotionBox
from .detection.base import PersonDetection, apply_clahe
from .utils.zone_manager import ZoneManager
from .camera.capture import CameraCapture, USBCameraCapture, V380SplitCameraCapture
from .notifications.telegram import telegram_notifier, TELEGRAM_AVAILABLE


# Data directories
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TrackedObject:
    """Tracked object with metadata"""
    id: int
    class_name: str
    bbox: tuple
    confidence: float
    center: tuple
    area: int
    skeleton: Optional[List[tuple]] = None
    face_name: Optional[str] = None
    face_confidence: Optional[float] = None
    is_trusted: bool = False
    camera_label: str = ""
    last_seen: float = 0.0
    frame_count: int = 0
    path_data: List[tuple] = field(default_factory=list)
    
    def update(self, bbox: tuple, confidence: float):
        """Update object with new detection"""
        self.bbox = bbox
        self.confidence = confidence
        x1, y1, x2, y2 = bbox
        # Don't assign center directly - calculate from bbox
        center_point = ((x1 + x2) // 2, (y1 + y2) // 2)
        self.area = (x2 - x1) * (y2 - y1)
        self.last_seen = time.time()
        self.frame_count += 1
        
        # Add to path (keep last 50 points)
        self.path_data.append((center_point, time.time()))
        if len(self.path_data) > 50:
            self.path_data.pop(0)


@dataclass
class DetectionResult:
    """Detection result with metadata"""
    camera: str
    camera_label: str = ""
    frame_time: float = 0.0
    persons: List[PersonDetection] = field(default_factory=list)
    motion_boxes: List[MotionBox] = field(default_factory=list)
    has_motion: bool = False


class CaptureWorker:
    """Camera capture worker - runs at full FPS"""
    
    def __init__(
        self,
        camera,
        camera_name: str = "camera",
        motion_detector: Optional[EnhancedMotionDetector] = None,
        is_v380_split: bool = False
    ):
        self.camera = camera
        self.camera_name = camera_name
        self.motion_detector = motion_detector
        self.is_v380_split = is_v380_split
        self.running = False
        self.frame_count = 0
        self.detection_queue = None  # Set externally
        self.thread = None
        self.motion_interval = 1  # Detect every N frames (lower = more frequent detection) - Changed to 1 for REAL-TIME detection
        self.last_motion_time = 0.0
    
    def start(self):
        """Start capture worker"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logger.info(f"Capture worker started for {self.camera_name}")
    
    def _capture_loop(self):
        """Main capture loop - runs at full FPS"""
        logger.info(f"Capture loop started for {self.camera_name}")
        
        target_fps = config.camera.fps
        frame_interval = 1.0 / target_fps
        
        while self.running:
            try:
                start_time = time.time()
                
                # Capture frame
                if isinstance(self.camera, V380SplitCameraCapture):
                    frame_data = self.camera.read()
                    if frame_data is None:
                        time.sleep(0.01)
                        continue
                    
                    full_frame = frame_data['full']
                    top_frame = frame_data['top']
                    bottom_frame = frame_data['bottom']
                else:
                    full_frame = self.camera.read()
                    if full_frame is None:
                        time.sleep(0.01)
                        continue
                    top_frame = None
                    bottom_frame = None
                
                self.frame_count += 1
                
                # Motion detection (fast)
                has_motion = False
                motion_boxes = []
                
                if self.motion_detector and top_frame is not None:
                    has_motion, motion_boxes, _ = self.motion_detector.detect(
                        top_frame,
                        return_boxes=True,
                        return_mask=False
                    )
                
                # Write to V2 ring buffers (V380 split camera: 3 slots, Regular: 1 slot)
                if self.is_v380_split:
                    # Write to 3 raw slots for split camera
                    frame_manager_v2.write_frame("camera_top_raw", top_frame)
                    frame_manager_v2.write_frame("camera_bottom_raw", bottom_frame)
                    frame_manager_v2.write_frame("camera_full_raw", full_frame)
                else:
                    # Write to 1 raw slot for regular camera
                    frame_manager_v2.write_frame("camera_raw", full_frame)
                
                # Send to detection queue ONLY if motion
                if has_motion or self.frame_count % self.motion_interval == 0:
                    if self.detection_queue and not self.detection_queue.full():
                        self.detection_queue.put({
                            'camera': self.camera_name,
                            'frame': full_frame.copy(),
                            'top_frame': top_frame.copy() if top_frame is not None else None,
                            'bottom_frame': bottom_frame.copy() if bottom_frame is not None else None,
                            'frame_time': time.time(),
                            'motion_boxes': motion_boxes,
                            'has_motion': has_motion
                        })
                        self.last_motion_time = time.time()
                
                # Maintain FPS
                elapsed = time.time() - start_time
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
                
            except Exception as e:
                logger.error(f"Capture error in {self.camera_name}: {e}")
                time.sleep(0.1)
        
        logger.info(f"Capture loop stopped for {self.camera_name}")
    
    def stop(self):
        """Stop capture worker"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=3.0)
        logger.info(f"Capture worker stopped for {self.camera_name}")


class DetectionWorker:
    """Detection worker - runs asynchronously"""
    
    def __init__(
        self,
        yolo_detector: YOLODetector,
        skeleton_detector: SkeletonDetector,
        face_detector: FaceDetector,
        zone_manager: ZoneManager
    ):
        self.yolo_detector = yolo_detector
        self.skeleton_detector = skeleton_detector
        self.face_detector = face_detector
        self.zone_manager = zone_manager
        
        self.running = False
        self.detection_queue = None
        self.tracking_queue = None
        self.thread = None
        self.stats = {
            'detections_processed': 0,
            'persons_found': 0,
            'processing_time_ms': 0
        }
    
    def start(self):
        """Start detection worker"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.thread.start()
        logger.info("Detection worker started")
    
    def _detection_loop(self):
        """Main detection loop"""
        logger.info("Detection loop started")
        
        frames_processed = 0
        
        while self.running:
            try:
                # Get frame from queue (blocking but OK)
                item = self.detection_queue.get(timeout=1.0)
                
                frames_processed += 1
                start_time = time.time()
                
                camera_name = item['camera']
                frame = item['frame']
                top_frame = item.get('top_frame')
                bottom_frame = item.get('bottom_frame')
                motion_boxes = item.get('motion_boxes', [])
                has_motion = item.get('has_motion', False)
                
                # YOLO always runs - no motion-first mode for continuous detection
                # This ensures detection of people even when stationary
                
                # Process frames
                result = DetectionResult(
                    camera=camera_name,
                    frame_time=item['frame_time'],
                    motion_boxes=motion_boxes,
                    has_motion=has_motion
                )
                
                if top_frame is not None and bottom_frame is not None:
                    # V380 split camera
                    top_detections = self._process_frame(top_frame, "top")
                    bottom_detections = self._process_frame(bottom_frame, "bottom")
                    
                    # Adjust bottom frame coordinates
                    split_point = frame.shape[0] // 2
                    for det in bottom_detections:
                        x1, y1, x2, y2 = det.bbox
                        # Create new bbox (don't assign directly to avoid read-only issues)
                        new_bbox = (x1, y1 + split_point, x2, y2 + split_point)
                        
                        # Update detection object
                        det.bbox = new_bbox
                        # Note: PersonDetection center is a property, set through bbox
                        det.camera_label = "bottom"
                    
                    result.persons = top_detections + bottom_detections
                else:
                    # Regular camera
                    detections = self._process_frame(frame, "")
                    result.persons = detections
                
                # Send to tracking queue
                if self.tracking_queue:
                    self.tracking_queue.put(result)
                
                logger.info(f"Processing frame #{frames_processed} from camera: {camera_name} - People detected: {len(result.persons)}")
                
                # Update stats
                elapsed = (time.time() - start_time) * 1000
                self.stats['detections_processed'] += 1
                self.stats['persons_found'] += len(result.persons)
                self.stats['processing_time_ms'] = elapsed
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Detection error: {e}")
                time.sleep(0.1)
        
        logger.info("Detection loop stopped")
    
    def _process_frame(self, frame: np.ndarray, camera_label: str) -> List[PersonDetection]:
        """Process single frame through all detectors"""
        # YOLO person detection (skip CLAHE for speed)
        person_detections = self.yolo_detector.detect(frame)
        
        # DISABLED: Skeleton and face detection for ultra-low latency
        # Re-enable after latency is fixed
        # for det in person_detections:
        #     x1, y1, x2, y2 = det.bbox
        #     
        #     # Extract person region
        #     person_region = frame[y1:y2, x1:x2]
        #     if person_region.size > 0:
        #         # Get skeleton
        #         skeleton = self.skeleton_detector.detect(person_region)
        #         if skeleton:
        #             det.skeleton = skeleton
        #             # Adjust skeleton coordinates to full frame
        #             det.skeleton = [(x + x1, y + y1) for x, y in skeleton]
        #         
        #         # Face detection and recognition
        #         face_bboxes = self.face_detector.detect_faces(person_region)
        #         if face_bboxes:
        #             face_recognition = self.face_detector.recognize_face(
        #                 person_region, face_bboxes[0]
        #             )
        #             if face_recognition:
        #                 det.face_confidence = face_recognition['confidence']
        #                 det.is_trusted = face_recognition['is_trusted']
        #                 det.face_name = face_recognition['name']
        #     
        #     # Add camera label if split camera
        #     if camera_label:
        #         det.camera_label = camera_label
        
        # Add camera label for split cameras
        if camera_label:
            for det in person_detections:
                det.camera_label = camera_label
        
        return person_detections
    
    def stop(self):
        """Stop detection worker"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=3.0)
        logger.info("Detection worker stopped")


class TrackingWorker:
    """Object tracking worker"""
    
    def __init__(self, zone_manager: ZoneManager, is_v380_split: bool = False):
        self.zone_manager = zone_manager
        self.is_v380_split = is_v380_split
        self.tracked_objects = {}  # id -> TrackedObject
        self.next_object_id = 1
        
        self.running = False
        self.tracking_queue = None
        self.thread = None
        self.lock = threading.Lock()
    
    def start(self):
        """Start tracking worker"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self.thread.start()
        logger.info("Tracking worker started")
    
    def _tracking_loop(self):
        """Main tracking loop"""
        logger.info("Tracking loop started")
        
        while self.running:
            try:
                # Get detection result from queue
                result = self.tracking_queue.get(timeout=1.0)
                
                camera_name = result.camera
                persons = result.persons
                
                with self.lock:
                    # Update tracked objects
                    current_ids = set()
                    
                    for person in persons:
                        # Find matching tracked object
                        matched = None
                        for obj_id, obj in self.tracked_objects.items():
                            if self._is_same_object(person, obj, camera_name):
                                matched = obj
                                break
                        
                        if matched:
                            # Update existing object
                            matched.update(person.bbox, person.confidence)
                            current_ids.add(matched.id)
                        else:
                            # Create new object
                            new_obj = TrackedObject(
                                id=self.next_object_id,
                                class_name=person.class_name,
                                bbox=person.bbox,
                                confidence=person.confidence,
                                center=person.center,
                                area=person.area,
                                skeleton=person.skeleton,
                                face_name=person.face_name,
                                face_confidence=person.face_confidence,
                                is_trusted=person.is_trusted,
                                camera_label=person.camera_label,
                                last_seen=time.time(),
                                frame_count=1
                            )
                            self.tracked_objects[self.next_object_id] = new_obj
                            current_ids.add(self.next_object_id)
                            self.next_object_id += 1
                    
                    # Cleanup old objects (not seen in 5 seconds)
                    current_time = time.time()
                    to_remove = [
                        obj_id for obj_id, obj in self.tracked_objects.items()
                        if (current_time - obj.last_seen) > 5.0
                    ]
                    
                    for obj_id in to_remove:
                        del self.tracked_objects[obj_id]
                    
                    # Write metadata to shared buffers
                    metadata = [
                        {
                            'id': obj.id,
                            'bbox': obj.bbox,
                            'confidence': obj.confidence,
                            'class_name': obj.class_name,
                            'is_trusted': obj.is_trusted,
                            'face_name': obj.face_name,
                            'camera_label': obj.camera_label,
                            'last_seen': obj.last_seen
                        }
                        for obj in self.tracked_objects.values()
                    ]
                    
                    if self.is_v380_split:
                        # Write separate metadata for top and bottom cameras
                        top_metadata = [m for m in metadata if m['camera_label'] == 'top']
                        bottom_metadata = [m for m in metadata if m['camera_label'] == 'bottom']
                        full_metadata = metadata
                        
                        metadata_manager.write_objects("metadata_top", top_metadata)
                        metadata_manager.write_objects("metadata_bottom", bottom_metadata)
                        metadata_manager.write_objects("metadata_full", full_metadata)
                    else:
                        metadata_manager.write_objects("metadata", metadata)
                
                # Check zone breaches
                person_centers = [person.center for person in persons]
                breached_zones = self.zone_manager.check_breaches(person_centers)
                
                # Handle breaches (callback)
                if breached_zones and hasattr(self, 'on_breach'):
                    self.on_breach(breached_zones, persons, camera_name)
                
                # Handle trusted faces (callback)
                for person in persons:
                    if person.is_trusted and hasattr(self, 'on_trusted_face'):
                        self.on_trusted_face(person, camera_name)
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Tracking error: {e}")
                time.sleep(0.1)
        
        logger.info("Tracking loop stopped")
    
    def _is_same_object(self, person: PersonDetection, tracked_obj: TrackedObject, camera: str) -> bool:
        """Check if person is same as tracked object"""
        # Simple matching based on distance
        if tracked_obj.camera_label and tracked_obj.camera_label != person.camera_label:
            return False
        
        dx = person.center[0] - tracked_obj.center[0]
        dy = person.center[1] - tracked_obj.center[1]
        distance = (dx ** 2 + dy ** 2) ** 0.5
        
        # Match if within 100 pixels
        return distance < 100
    
    def get_tracked_objects(self) -> List[TrackedObject]:
        """Get all tracked objects"""
        with self.lock:
            return list(self.tracked_objects.values())
    
    def stop(self):
        """Stop tracking worker"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=3.0)
        logger.info("Tracking worker stopped")


class EnhancedSecuritySystem:
    """
    Enhanced Security System V2
    High-performance multi-process architecture
    """
    
    def __init__(self):
        # System state
        self.running = False
        self.system_mode = "normal"
        
        # Workers
        self.capture_worker = None
        self.detection_worker = None
        self.tracking_worker = None
        
        # Detectors
        self.yolo_detector = None
        self.skeleton_detector = None
        self.face_detector = None
        self.motion_detector = None
        
        # Zone management
        self.zone_manager = ZoneManager()
        
        # Camera
        self.camera = None
        self.is_v380_split = False
        
        # Queues (for inter-worker communication)
        # INCREASED: Larger queues to prevent frame drops with better performance
        self.detection_queue = mp.Queue(maxsize=20)
        self.tracking_queue = mp.Queue(maxsize=30)
        
        # Statistics
        self.stats = {
            "persons_detected": 0,
            "alerts_triggered": 0,
            "breaches_detected": 0,
            "trusted_faces_seen": 0,
            "uptime": 0,
            "top_camera_persons": 0,
            "bottom_camera_persons": 0,
            "fps": 0.0,
            "motion_ratio": 0.0
        }
        
        # Callbacks
        self.on_alert: Optional[Callable] = None
        self.on_breach: Optional[Callable] = None
        self.on_trusted_face: Optional[Callable] = None
        self.on_new_frame: Optional[Callable] = None
        
        # Alert cooldown
        self.last_alert_time = 0
        self.alert_cooldown = 5.0
        
        # Telegram notifier
        self.telegram_notifier = telegram_notifier
        self.telegram_notifier.security_system = self
        
        # Timing
        self.start_time = 0.0
        self.frame_count = 0
    
    async def initialize(self):
        """Initialize all system components"""
        logger.info("Initializing Enhanced Security System V2...")
        
        # Initialize database
        await db.initialize()
        
        # Initialize detectors
        self.yolo_detector = YOLODetector(confidence=config.detection.yolo_confidence)
        self.yolo_detector.initialize()
        
        self.skeleton_detector = SkeletonDetector()
        self.skeleton_detector.initialize()
        
        self.face_detector = FaceDetector()
        self.face_detector.initialize()
        
        self.motion_detector = EnhancedMotionDetector(
            history=500,
            var_threshold=16,
            detect_shadows=True,
            min_motion_area=500
        )
        
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
        
        # Initialize V2 ring buffers (6 slots total)
        frame_shape = (config.camera.height, config.camera.width, 3)
        
        if self.is_v380_split:
            # Create 6 ring buffers for split camera
            frame_manager_v2.create_ring_buffer("camera_top_raw", frame_shape)
            frame_manager_v2.create_ring_buffer("camera_top_overlay", frame_shape)
            frame_manager_v2.create_ring_buffer("camera_bottom_raw", frame_shape)
            frame_manager_v2.create_ring_buffer("camera_bottom_overlay", frame_shape)
            frame_manager_v2.create_ring_buffer("camera_full_raw", frame_shape)
            frame_manager_v2.create_ring_buffer("camera_full_overlay", frame_shape)
            
            # Create metadata buffers
            metadata_manager.create_metadata("metadata_top", max_objects=20)
            metadata_manager.create_metadata("metadata_bottom", max_objects=20)
            metadata_manager.create_metadata("metadata_full", max_objects=40)
            
            logger.info("Created 6 ring buffers + 3 metadata buffers for split camera")
        else:
            # Create 2 ring buffers for regular camera
            frame_manager_v2.create_ring_buffer("camera_raw", frame_shape)
            frame_manager_v2.create_ring_buffer("camera_overlay", frame_shape)
            
            # Create metadata buffer
            metadata_manager.create_metadata("metadata", max_objects=20)
            
            logger.info("Created 2 ring buffers + 1 metadata buffer for regular camera")
        
        # Create directories
        Path(config.paths.alerts_dir).mkdir(parents=True, exist_ok=True)
        Path(config.paths.snapshots_dir).mkdir(parents=True, exist_ok=True)
        Path(config.paths.recordings_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info("Enhanced Security System V2 initialized successfully")
    
    def start(self):
        """Start the security system"""
        if self.running:
            logger.warning("System already running")
            return
        
        logger.info("Starting Enhanced Security System V2...")
        self.running = True
        self.start_time = time.time()
        
        # Initialize workers
        self.capture_worker = CaptureWorker(
            self.camera,
            "camera",
            self.motion_detector,
            self.is_v380_split
        )
        self.capture_worker.detection_queue = self.detection_queue
        
        self.detection_worker = DetectionWorker(
            self.yolo_detector,
            self.skeleton_detector,
            self.face_detector,
            self.zone_manager
        )
        self.detection_worker.detection_queue = self.detection_queue
        self.detection_worker.tracking_queue = self.tracking_queue
        
        self.tracking_worker = TrackingWorker(self.zone_manager, self.is_v380_split)
        self.tracking_worker.tracking_queue = self.tracking_queue
        
        # Set callbacks
        self.tracking_worker.on_breach = self._handle_breach
        self.tracking_worker.on_trusted_face = self._handle_trusted_face
        
        # Start workers
        if isinstance(self.camera, (CameraCapture, V380SplitCameraCapture)):
            self.camera.start()
        
        self.capture_worker.start()
        self.detection_worker.start()
        self.tracking_worker.start()
        
        # Start Telegram command handler (if enabled)
        if self.telegram_notifier.enabled and TELEGRAM_AVAILABLE:
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
        
        # Start stats updater
        threading.Thread(target=self._update_stats_loop, daemon=True).start()
        
        # Start overlay writer (writes frames with AI overlays for web server)
        threading.Thread(target=self._overlay_writer_loop, daemon=True).start()
        
        logger.info("Enhanced Security System V2 started")
    
    def _update_stats_loop(self):
        """Update statistics periodically"""
        while self.running:
            try:
                # Update basic stats
                self.stats["uptime"] = time.time() - self.start_time
                
                # Update motion stats
                if self.motion_detector:
                    motion_stats = self.motion_detector.get_stats()
                    self.stats["motion_ratio"] = motion_stats["motion_ratio"]
                
                # Update FPS
                if self.stats["uptime"] > 0:
                    self.stats["fps"] = self.capture_worker.frame_count / self.stats["uptime"]
                
                # Update person count
                tracked_objects = self.tracking_worker.get_tracked_objects()
                self.stats["persons_detected"] = len(tracked_objects)
                
                # Update camera-specific stats
                if self.is_v380_split:
                    top_count = sum(1 for obj in tracked_objects if obj.camera_label == "top")
                    bottom_count = sum(1 for obj in tracked_objects if obj.camera_label == "bottom")
                    self.stats["top_camera_persons"] = top_count
                    self.stats["bottom_camera_persons"] = bottom_count
                
                # Save stats to file
                stats_path = DATA_DIR / "stats.json"
                with open(stats_path, 'w') as f:
                    json.dump(self.stats, f, indent=2)
                
                time.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Stats update error: {e}")
                time.sleep(1.0)
    
    def _overlay_writer_loop(self):
        """Write frames with AI overlays to V2 ring buffer for web server"""
        logger.info("Overlay writer loop started")
        
        # Write overlays every frame (no conditions) to prevent flickering
        min_write_interval = 0.03  # Maximum 33 FPS for overlays - Ultra-low latency
        last_write_time = 0.0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check if enough time passed since last write
                if current_time - last_write_time >= min_write_interval:
                    # Get frame with overlays - ALWAYS write, no conditions
                    frame_with_overlays = self.get_frame_with_overlays("camera", {
                        "bounding_boxes": True,
                        "timestamp": True,
                        "zones": True,
                        "skeletons": True
                    })
                    
                    if frame_with_overlays is not None:
                        # Write to V2 ring buffer (not file!)
                        if self.is_v380_split:
                            frame_manager_v2.write_frame("camera_full_overlay", frame_with_overlays)
                        else:
                            frame_manager_v2.write_frame("camera_overlay", frame_with_overlays)
                        
                        last_write_time = current_time
                
                time.sleep(0.02)  # Check every 20ms (50 Hz)
                
            except Exception as e:
                logger.error(f"Overlay writer error: {e}")
                time.sleep(0.1)
        
        logger.info("Overlay writer loop stopped")
    
    def get_frame_with_overlays(
        self,
        camera_name: str = "camera",
        draw_options: Dict = None
    ) -> Optional[np.ndarray]:
        """
        Get frame with AI overlays (thread-safe)
        
        Args:
            camera_name: Name of camera
            draw_options: Dict with draw options
                - bounding_boxes: bool
                - timestamp: bool
                - zones: bool
                - motion_boxes: bool
                - skeletons: bool
                
        Returns:
            Frame with overlays or None
        """
        if draw_options is None:
            draw_options = {
                "bounding_boxes": True,
                "timestamp": True,
                "zones": True,
                "motion_boxes": False,
                "skeletons": True
            }
        
        # Read frame from V2 ring buffer (use force_read for web server style)
        if self.is_v380_split:
            frame = frame_manager_v2.force_read_frame("camera_full_raw")
        else:
            frame = frame_manager_v2.force_read_frame("camera_raw")
        
        if frame is None:
            return None
        
        # Get tracked objects
        tracked_objects = self.tracking_worker.get_tracked_objects()
        
        # Convert to BGR if needed
        if len(frame.shape) == 2 or frame.shape[2] == 1:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        
        # Draw bounding boxes
        if draw_options.get("bounding_boxes"):
            for obj in tracked_objects:
                if time.time() - obj.last_seen < 5.0:  # Only draw recent objects
                    x1, y1, x2, y2 = obj.bbox
                    
                    # Determine color
                    if obj.is_trusted:
                        color = (0, 255, 0)  # Green
                        label = obj.face_name or "Trusted"
                    else:
                        color = (0, 255, 255)  # Cyan
                        label = obj.class_name
                    
                    # Draw bounding box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
                    
                    # Draw skeleton
                    if obj.skeleton and draw_options.get("skeletons"):
                        frame = self.skeleton_detector.draw_skeleton(frame, obj.skeleton, color)
                    
                    # Draw label
                    label = f"{label} {obj.confidence:.2f}"
                    cv2.putText(frame, label, (x1, y1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Draw zones
        if draw_options.get("zones"):
            frame = self.zone_manager.draw_zones(frame, [])
        
        # Draw timestamp
        if draw_options.get("timestamp"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Draw system status
        status_text = f"Mode: {self.system_mode.upper()} | FPS: {self.stats['fps']:.1f} | People: {self.stats['persons_detected']}"
        cv2.putText(frame, status_text, (10, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        return frame
    
    def _handle_breach(self, breached_zones: List[int], detections: List, camera: str):
        """Handle zone breach"""
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_alert_time < self.alert_cooldown:
            return
        
        self.last_alert_time = current_time
        self.stats["breaches_detected"] += 1
        
        # Get frame for alert
        frame = self.get_frame_with_overlays(camera, {"bounding_boxes": True, "timestamp": True})
        if frame is None:
            return
        
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
    
    def _handle_trusted_face(self, detection: PersonDetection, camera: str):
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
    
    def set_mode(self, mode: str):
        """Set system mode"""
        if mode in ["normal", "armed", "alerted"]:
            self.system_mode = mode
            self.zone_manager.is_armed = (mode == "armed")
            logger.info(f"System mode set to: {mode}")
    
    def get_stats(self) -> Dict:
        """Get system statistics"""
        return self.stats.copy()
    
    def _get_fps(self) -> float:
        """Get current FPS"""
        return self.stats['fps'] if 'fps' in self.stats else 0.0
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get current frame from ring buffer for screenshot"""
        try:
            if self.is_v380_split:
                return frame_manager_v2.force_read_frame("camera_full_raw")
            else:
                return frame_manager_v2.force_read_frame("camera_raw")
        except Exception as e:
            logger.error(f"Error getting current frame: {e}")
            return None
    
    def get_system_status(self) -> Dict:
        """Get complete system status"""
        return {
            "running": self.running,
            "mode": self.system_mode,
            "stats": self.stats,
            "zones": self.zone_manager.get_all_zones(),
            "camera": self.camera.get_info() if self.camera else None,
            "tracked_objects": len(self.tracking_worker.get_tracked_objects()) if self.tracking_worker else 0
        }
    
    def stop(self):
        """Stop the security system"""
        logger.info("Stopping Enhanced Security System V2...")
        self.running = False
        
        # Stop workers
        if self.capture_worker:
            self.capture_worker.stop()
        if self.detection_worker:
            self.detection_worker.stop()
        if self.tracking_worker:
            self.tracking_worker.stop()
        
        # Stop camera
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
        
        # Cleanup V2 shared memory
        frame_manager_v2.close_all()
        metadata_manager.close_all()
        
        logger.info("Enhanced Security System V2 stopped")
    
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
        if self.camera:
            self.camera.cleanup()
        
        frame_manager_v2.cleanup_all()
        
        logger.info("Enhanced Security System V2 cleaned up")


# Global instance
enhanced_security_system = EnhancedSecuritySystem()
