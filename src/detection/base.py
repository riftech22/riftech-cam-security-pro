"""
Base Detection Classes
Common interfaces and utilities for detection modules
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

from ..core.logger import logger


@dataclass
class Detection:
    """Base detection data structure"""
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    class_id: int = 0
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get center point of bounding box"""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    
    @property
    def area(self) -> int:
        """Get area of bounding box"""
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)
    
    @property
    def aspect_ratio(self) -> float:
        """Get aspect ratio of bounding box"""
        x1, y1, x2, y2 = self.bbox
        width = x2 - x1
        height = y2 - y1
        return width / height if height > 0 else 0


@dataclass
class PersonDetection(Detection):
    """Person detection with additional attributes"""
    skeleton: Optional[List[Tuple[int, int]]] = None
    face_confidence: Optional[float] = None
    is_trusted: bool = False
    face_name: Optional[str] = None


class BaseDetector(ABC):
    """Abstract base class for detectors"""
    
    def __init__(self):
        self.enabled = True
        self.model = None
        self._initialized = False
    
    @abstractmethod
    def initialize(self):
        """Initialize the detector"""
        pass
    
    @abstractmethod
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Perform detection on frame"""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up resources"""
        pass
    
    def is_initialized(self) -> bool:
        """Check if detector is initialized"""
        return self._initialized
    
    def enable(self):
        """Enable detection"""
        self.enabled = True
        logger.info(f"{self.__class__.__name__} enabled")
    
    def disable(self):
        """Disable detection"""
        self.enabled = False
        logger.info(f"{self.__class__.__name__} disabled")
    
    def toggle(self) -> bool:
        """Toggle detection on/off"""
        if self.enabled:
            self.disable()
            return False
        else:
            self.enable()
            return True


def filter_detections(
    detections: List[Detection],
    min_confidence: float = 0.0,
    min_area: int = 0,
    max_area: int = float('inf'),
    min_aspect_ratio: float = 0.0,
    max_aspect_ratio: float = float('inf')
) -> List[Detection]:
    """
    Filter detections based on criteria
    
    Args:
        detections: List of detections to filter
        min_confidence: Minimum confidence threshold
        min_area: Minimum bounding box area
        max_area: Maximum bounding box area
        min_aspect_ratio: Minimum aspect ratio
        max_aspect_ratio: Maximum aspect ratio
        
    Returns:
        Filtered list of detections
    """
    filtered = []
    
    for det in detections:
        # Confidence filter
        if det.confidence < min_confidence:
            continue
        
        # Area filter
        area = det.area
        if area < min_area or area > max_area:
            continue
        
        # Aspect ratio filter
        aspect = det.aspect_ratio
        if aspect < min_aspect_ratio or aspect > max_aspect_ratio:
            continue
        
        filtered.append(det)
    
    return filtered


def non_max_suppression(
    detections: List[Detection],
    iou_threshold: float = 0.45
) -> List[Detection]:
    """
    Apply Non-Maximum Suppression to remove overlapping detections
    
    Args:
        detections: List of detections
        iou_threshold: IoU threshold for suppression
        
    Returns:
        Filtered list of detections
    """
    if not detections:
        return []
    
    # Sort by confidence (highest first)
    detections = sorted(detections, key=lambda x: x.confidence, reverse=True)
    
    keep = []
    while detections:
        # Keep the highest confidence detection
        current = detections.pop(0)
        keep.append(current)
        
        # Remove overlapping detections
        remaining = []
        for det in detections:
            if calculate_iou(current.bbox, det.bbox) < iou_threshold:
                remaining.append(det)
        detections = remaining
    
    return keep


def calculate_iou(bbox1: Tuple[int, int, int, int], 
                  bbox2: Tuple[int, int, int, int]) -> float:
    """
    Calculate Intersection over Union (IoU) between two bounding boxes
    
    Args:
        bbox1: First bounding box (x1, y1, x2, y2)
        bbox2: Second bounding box (x1, y1, x2, y2)
        
    Returns:
        IoU value between 0 and 1
    """
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2
    
    # Calculate intersection
    x1_i = max(x1_1, x1_2)
    y1_i = max(y1_1, y1_2)
    x2_i = min(x2_1, x2_2)
    y2_i = min(y2_1, y2_2)
    
    if x2_i <= x1_i or y2_i <= y1_i:
        intersection = 0
    else:
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
    
    # Calculate union
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union = area1 + area2 - intersection
    
    if union == 0:
        return 0.0
    
    return intersection / union


def letterbox_resize(
    frame: np.ndarray,
    target_size: Tuple[int, int] = (640, 640),
    color: Tuple[int, int, int] = (114, 114, 114)
) -> Tuple[np.ndarray, Tuple[float, float]]:
    """
    Resize frame with letterbox (maintain aspect ratio)
    
    Args:
        frame: Input frame
        target_size: Target (width, height)
        color: Padding color
        
    Returns:
        Resized frame and scale factors (scale_x, scale_y)
    """
    height, width = frame.shape[:2]
    target_w, target_h = target_size
    
    # Calculate scale
    scale = min(target_w / width, target_h / height)
    new_w = int(width * scale)
    new_h = int(height * scale)
    
    # Resize frame
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    
    # Create letterbox
    letterbox = np.full((target_h, target_w, 3), color, dtype=np.uint8)
    
    # Center the resized frame
    x_offset = (target_w - new_w) // 2
    y_offset = (target_h - new_h) // 2
    letterbox[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
    
    return letterbox, (scale, scale)


def apply_clahe(frame: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """
    Apply Contrast Limited Adaptive Histogram Equalization
    
    Args:
        frame: Input BGR frame
        clip_limit: CLAHE clip limit
        
    Returns:
        Enhanced frame
    """
    # Convert to LAB color space
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    
    # Apply CLAHE to L channel
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    
    # Convert back to BGR
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
