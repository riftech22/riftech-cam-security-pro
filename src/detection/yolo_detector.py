"""
YOLOv8 Object Detection Module
Uses Ultralytics YOLOv8 for person detection
"""

import cv2
import numpy as np
from typing import List
from pathlib import Path

from ultralytics import YOLO

from .base import Detection, PersonDetection, filter_detections, non_max_suppression
from ..core.logger import logger


class YOLODetector:
    """YOLOv8 detector for all object detection (COCO 80 classes)"""
    
    def __init__(self, model_path: str = "yolov8n.pt", confidence: float = 0.20):
        """
        Initialize YOLO detector
        
        Args:
            model_path: Path to YOLO model file
            confidence: Detection confidence threshold
        """
        self.model_path = model_path
        self.confidence = confidence
        self.model = None
        self._initialized = False
        self.enabled = True
        
        # COCO class names (80 classes)
        self.COCO_CLASSES = [
            "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
            "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
            "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
            "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
            "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
            "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
            "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard",
            "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
            "teddy bear", "hair drier", "toothbrush"
        ]
    
    def initialize(self):
        """Load YOLO model"""
        try:
            logger.info(f"Loading YOLO model from {self.model_path}")
            self.model = YOLO(self.model_path)
            self._initialized = True
            logger.info("YOLO model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    
    def detect(self, frame: np.ndarray) -> List[PersonDetection]:
        """
        Perform object detection on frame (all COCO classes)
        
        Args:
            frame: Input BGR frame
            
        Returns:
            List of object detections
        """
        if not self.enabled or not self._initialized:
            return []
        
        try:
            # Run YOLO inference
            results = self.model(frame, verbose=False, conf=self.confidence)[0]
            
            logger.debug(f"YOLO inference complete - total boxes: {len(results.boxes)}")
            
            detections = []
            
            # Process results - DETECT ALL CLASSES
            for box in results.boxes:
                class_id = int(box.cls[0])
                
                # Get class name
                if class_id < len(self.COCO_CLASSES):
                    class_name = self.COCO_CLASSES[class_id]
                else:
                    class_name = f"unknown_{class_id}"
                
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # Create detection (use base Detection class for all objects)
                detection = PersonDetection(
                    class_name=class_name,
                    confidence=confidence,
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    class_id=class_id
                )
                
                detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"YOLO detection error: {e}")
            return []
    
    def set_confidence(self, confidence: float):
        """
        Update confidence threshold
        
        Args:
            confidence: New confidence threshold (0.0 to 1.0)
        """
        self.confidence = max(0.0, min(1.0, confidence))
        logger.info(f"YOLO confidence set to {self.confidence:.2f}")
    
    def get_model_info(self) -> dict:
        """Get model information"""
        if not self._initialized:
            return {}
        
        return {
            "model_path": str(self.model_path),
            "confidence": self.confidence,
            "enabled": self.enabled
        }
    
    def cleanup(self):
        """Clean up resources"""
        self.model = None
        self._initialized = False
        logger.info("YOLO detector cleaned up")
