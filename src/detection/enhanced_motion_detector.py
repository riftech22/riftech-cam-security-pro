"""
Enhanced Motion Detector
Optimized motion detection for performance optimization
"""

import cv2
import numpy as np
from typing import Tuple, List, Optional
from dataclasses import dataclass
from .base import apply_clahe
from ..core.logger import logger


@dataclass
class MotionBox:
    """Represents a motion detection box"""
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float = 1.0


class EnhancedMotionDetector:
    """
    Enhanced motion detector with background subtraction
    Optimized for performance and accuracy
    """
    
    def __init__(
        self,
        history: int = 500,
        var_threshold: int = 16,
        detect_shadows: bool = True,
        min_motion_area: int = 500,
        enable_roi: bool = True
    ):
        """
        Initialize enhanced motion detector
        
        Args:
            history: Number of frames to keep in history
            var_threshold: Variance threshold for motion detection
            detect_shadows: Whether to detect shadows
            min_motion_area: Minimum area for motion to be considered valid
            enable_roi: Whether to enable ROI (Region of Interest)
        """
        self.history = history
        self.var_threshold = var_threshold
        self.detect_shadows = detect_shadows
        self.min_motion_area = min_motion_area
        self.enable_roi = enable_roi
        
        # Background subtractor
        self.fgbg = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=var_threshold,
            detectShadows=detect_shadows
        )
        
        # ROI mask (optional)
        self.roi_mask = None
        
        # Statistics
        self.frames_processed = 0
        self.motion_frames = 0
        self.total_motion_area = 0
    
    def set_roi(self, roi: np.ndarray):
        """
        Set Region of Interest (ROI) mask
        
        Args:
            roi: Binary mask where white = detect motion, black = ignore
        """
        self.roi_mask = roi
        logger.info("ROI mask set for motion detection")
    
    def detect(
        self,
        frame: np.ndarray,
        return_boxes: bool = True,
        return_mask: bool = False
    ) -> Tuple[bool, List[MotionBox], Optional[np.ndarray]]:
        """
        Detect motion in frame
        
        Args:
            frame: Input frame (BGR)
            return_boxes: Whether to return motion boxes
            return_mask: Whether to return motion mask
            
        Returns:
            Tuple of (has_motion, motion_boxes, motion_mask)
        """
        try:
            # Enhance frame for better detection
            enhanced = apply_clahe(frame)
            
            # Apply background subtraction
            fg_mask = self.fgbg.apply(enhanced)
            
            # Remove shadows if enabled
            if self.detect_shadows:
                fg_mask[fg_mask == 127] = 0  # Remove shadows (gray = 127)
            
            # Apply ROI mask if set
            if self.roi_mask is not None:
                fg_mask = cv2.bitwise_and(fg_mask, self.roi_mask)
            
            # Morphological operations to reduce noise
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
            
            # Find contours
            contours, _ = cv2.findContours(
                fg_mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            motion_boxes = []
            total_motion_area = 0
            
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # Filter small contours (noise)
                if area < self.min_motion_area:
                    continue
                
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                
                # Add to motion boxes
                motion_boxes.append(MotionBox(
                    x1=x,
                    y1=y,
                    x2=x + w,
                    y2=y + h,
                    confidence=1.0
                ))
                
                total_motion_area += area
            
            has_motion = len(motion_boxes) > 0
            
            # Update statistics
            self.frames_processed += 1
            if has_motion:
                self.motion_frames += 1
                self.total_motion_area += total_motion_area
            
            # Calculate motion statistics
            if self.frames_processed % 60 == 0:  # Every ~2 seconds at 30 FPS
                motion_ratio = self.motion_frames / self.frames_processed if self.frames_processed > 0 else 0
                avg_motion_area = self.total_motion_area / self.motion_frames if self.motion_frames > 0 else 0
                logger.debug(
                    f"Motion stats: {motion_ratio:.1%} frames with motion, "
                    f"avg area: {avg_motion_area:.0f}px"
                )
            
            # Return results
            if return_boxes and return_mask:
                return has_motion, motion_boxes, fg_mask
            elif return_boxes:
                return has_motion, motion_boxes, None
            elif return_mask:
                return has_motion, [], fg_mask
            else:
                return has_motion, [], None
                
        except Exception as e:
            logger.error(f"Error in motion detection: {e}")
            return False, [], None
    
    def get_motion_boxes(self, frame: np.ndarray) -> List[MotionBox]:
        """
        Get motion boxes only (convenience method)
        
        Args:
            frame: Input frame
            
        Returns:
            List of motion boxes
        """
        has_motion, boxes, _ = self.detect(frame, return_boxes=True, return_mask=False)
        return boxes if has_motion else []
    
    def has_motion(self, frame: np.ndarray) -> bool:
        """
        Check if frame has motion only (convenience method)
        
        Args:
            frame: Input frame
            
        Returns:
            True if motion detected, False otherwise
        """
        has_motion, _, _ = self.detect(frame, return_boxes=False, return_mask=False)
        return has_motion
    
    def get_motion_ratio(self) -> float:
        """
        Get ratio of frames with motion
        
        Returns:
            Ratio between 0.0 and 1.0
        """
        if self.frames_processed == 0:
            return 0.0
        return self.motion_frames / self.frames_processed
    
    def reset(self):
        """Reset detector statistics"""
        self.frames_processed = 0
        self.motion_frames = 0
        self.total_motion_area = 0
        self.fgbg = cv2.createBackgroundSubtractorMOG2(
            history=self.history,
            varThreshold=self.var_threshold,
            detectShadows=self.detect_shadows
        )
        logger.info("Motion detector reset")
    
    def get_stats(self) -> dict:
        """
        Get detector statistics
        
        Returns:
            Dictionary with statistics
        """
        return {
            "frames_processed": self.frames_processed,
            "motion_frames": self.motion_frames,
            "motion_ratio": self.get_motion_ratio(),
            "avg_motion_area": (
                self.total_motion_area / self.motion_frames 
                if self.motion_frames > 0 else 0
            )
        }
