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
    """YOLOv8 detector for person detection"""
    
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
        Perform person detection on frame
        
        Args:
            frame: Input BGR frame
            
        Returns:
            List of person detections
        """
        if not self.enabled or not self._initialized:
            return []
        
        try:
            # Run YOLO inference
            results = self.model(frame, verbose=False, conf=self.confidence)[0]
            
            logger.debug(f"YOLO inference complete - total boxes: {len(results.boxes)}")
            
            detections = []
            
            # Process results
            for box in results.boxes:
                class_id = int(box.cls[0])
                
                # Only detect persons (class 0 in COCO)
                if class_id == 0:
                    confidence = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    
                    # Create person detection
                    detection = PersonDetection(
                        class_name="person",
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
