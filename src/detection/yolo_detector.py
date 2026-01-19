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
        self.input_size = 640  # YOLOv8 default input size
        self.COCO_CLASSES = []
    
    @staticmethod
    def letterbox_resize(frame: np.ndarray, target_size: int = 640) -> tuple:
        """
        Resize frame with letterboxing (maintain aspect ratio, no stretching)
        
        Args:
            frame: Input frame (H, W, C)
            target_size: Target size (square)
            
        Returns:
            (resized_frame, scale, padding)
        """
        h, w = frame.shape[:2]
        
        # Calculate scale to fit within target_size while maintaining aspect ratio
        scale = min(target_size / h, target_size / w)
        
        # New dimensions (rounded)
        new_h = int(h * scale)
        new_w = int(w * scale)
        
        # Resize frame (maintain aspect ratio)
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Calculate padding (letterbox)
        pad_h = target_size - new_h
        pad_w = target_size - new_w
        
        # Distribute padding evenly
        pad_top = pad_h // 2
        pad_bottom = pad_h - pad_top
        pad_left = pad_w // 2
        pad_right = pad_w - pad_left
        
        # Add padding (letterbox)
        letterboxed = cv2.copyMakeBorder(
            resized,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114)  # Gray color (common padding color)
        )
        
        return letterboxed, scale, (pad_left, pad_top)
    
    @staticmethod
    def letterbox_coords(coords: tuple, scale: float, padding: tuple) -> tuple:
        """
        Convert coordinates from letterboxed frame back to original frame
        
        Args:
            coords: (x1, y1, x2, y2) in letterboxed frame
            scale: Scale factor used in letterbox_resize
            padding: (pad_left, pad_top) from letterbox_resize
            
        Returns:
            (x1, y1, x2, y2) in original frame
        """
        x1, y1, x2, y2 = coords
        pad_left, pad_top = padding
        
        # Remove padding
        x1 = x1 - pad_left
        y1 = y1 - pad_top
        x2 = x2 - pad_left
        y2 = y2 - pad_top
        
        # Scale back to original size
        x1 = int(x1 / scale)
        y1 = int(y1 / scale)
        x2 = int(x2 / scale)
        y2 = int(y2 / scale)
        
        return (x1, y1, x2, y2)
    
    def initialize(self):
        """Load YOLO model"""
        try:
            logger.info(f"Loading YOLO model from {self.model_path}")
            self.model = YOLO(self.model_path)
            
            # COCO class names (80 classes) - set after model is loaded
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
            
            self._initialized = True
            logger.info("YOLO model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    
    def detect(self, frame: np.ndarray) -> List[PersonDetection]:
        """
        Perform object detection on frame (all COCO classes)
        
        Uses letterboxing to maintain aspect ratio - prevents object distortion
        
        Args:
            frame: Input BGR frame
            
        Returns:
            List of object detections
        """
        if not self.enabled or not self._initialized:
            return []
        
        try:
            # Letterbox resize (maintain aspect ratio, no stretching)
            letterboxed_frame, scale, padding = self.letterbox_resize(frame, self.input_size)
            
            # Run YOLO inference on letterboxed frame
            results = self.model(letterboxed_frame, verbose=False, conf=self.confidence)[0]
            
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
                
                # Convert letterbox coordinates back to original frame coordinates
                # This ensures bounding boxes are accurate to original frame size
                x1, y1, x2, y2 = self.letterbox_coords((x1, y1, x2, y2), scale, padding)
                
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
