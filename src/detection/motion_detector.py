"""
Motion Detection Module
Uses frame difference and background subtraction for motion detection
"""

import cv2
import numpy as np
from typing import Optional, Tuple

from ..core.logger import logger


class MotionDetector:
    """Motion detector using background subtraction"""
    
    def __init__(self, threshold: int = 15, min_area: int = 500):
        """
        Initialize motion detector
        
        Args:
            threshold: Motion detection threshold (0-255)
            min_area: Minimum area for motion region
        """
        self.threshold = threshold
        self.min_area = min_area
        self.bg_subtractor = None
        self._initialized = False
        self.enabled = True
        self.heatmap = None
        self.heatmap_alpha = 0.95
    
    def initialize(self):
        """Initialize background subtractor"""
        try:
            logger.info("Initializing motion detector")
            # Use MOG2 for better results with gradual lighting changes
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=500,
                varThreshold=16,
                detectShadows=True
            )
            self._initialized = True
            logger.info("Motion detector initialized")
        except Exception as e:
            logger.error(f"Failed to initialize motion detector: {e}")
            raise
    
    def detect(self, frame: np.ndarray) -> Tuple[bool, np.ndarray]:
        """
        Detect motion in frame
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Tuple of (motion_detected, motion_mask)
        """
        if not self.enabled or not self._initialized:
            return False, np.zeros_like(frame)
        
        try:
            # Apply background subtraction
            fg_mask = self.bg_subtractor.apply(frame)
            
            # Remove shadows (gray pixels)
            _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
            
            # Apply morphological operations to reduce noise
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
            
            # Find contours
            contours, _ = cv2.findContours(
                fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            
            # Check for motion
            motion_detected = False
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > self.min_area:
                    motion_detected = True
                    break
            
            return motion_detected, fg_mask
            
        except Exception as e:
            logger.error(f"Motion detection error: {e}")
            return False, np.zeros_like(frame)
    
    def get_heatmap(self, frame: np.ndarray, motion_mask: np.ndarray) -> np.ndarray:
        """
        Update and get motion heatmap
        
        Args:
            frame: Current frame
            motion_mask: Motion detection mask
            
        Returns:
            Heatmap overlay
        """
        if self.heatmap is None:
            self.heatmap = np.zeros_like(frame)
        
        # Add motion regions to heatmap
        motion_regions = cv2.bitwise_and(frame, frame, mask=motion_mask)
        self.heatmap = cv2.addWeighted(
            self.heatmap,
            self.heatmap_alpha,
            motion_regions,
            1 - self.heatmap_alpha,
            0
        )
        
        # Create heatmap overlay
        heatmap_colored = cv2.applyColorMap(
            cv2.cvtColor(self.heatmap, cv2.COLOR_BGR2GRAY),
            cv2.COLORMAP_JET
        )
        
        return cv2.addWeighted(frame, 0.7, heatmap_colored, 0.3, 0)
    
    def reset_heatmap(self):
        """Reset heatmap accumulator"""
        self.heatmap = None
        logger.info("Motion heatmap reset")
    
    def set_threshold(self, threshold: int):
        """
        Update motion threshold
        
        Args:
            threshold: New threshold (0-255)
        """
        self.threshold = max(0, min(255, threshold))
        logger.info(f"Motion threshold set to {self.threshold}")
    
    def set_min_area(self, min_area: int):
        """
        Update minimum motion area
        
        Args:
            min_area: New minimum area in pixels
        """
        self.min_area = max(0, min_area)
        logger.info(f"Motion minimum area set to {self.min_area}")
    
    def cleanup(self):
        """Clean up resources"""
        self.bg_subtractor = None
        self.heatmap = None
        self._initialized = False
        logger.info("Motion detector cleaned up")
