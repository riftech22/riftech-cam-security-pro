"""
Skeleton Detection Module
Uses MediaPipe for 33-point pose estimation
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
import mediapipe as mp

from ..core.logger import logger


class SkeletonDetector:
    """MediaPipe pose detector for skeleton tracking"""
    
    # MediaPipe pose connections
    POSE_CONNECTIONS = [
        (0, 1), (0, 2), (1, 3), (2, 4),  # Face
        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),  # Arms
        (5, 11), (6, 12), (11, 12),  # Torso
        (11, 13), (13, 15), (12, 14), (14, 16)  # Legs
    ]
    
    def __init__(self):
        """Initialize MediaPipe pose detector"""
        self.pose = None
        self._initialized = False
        self.enabled = True
    
    def initialize(self):
        """Load MediaPipe pose model"""
        try:
            logger.info("Initializing MediaPipe pose detector")
            # Try new API first
            try:
                from mediapipe.tasks import python
                from mediapipe.tasks.python import vision
                self.pose = vision.PoseLandmarker.create_from_options(
                    vision.PoseLandmarkerOptions(
                        base_options=python.BaseOptions(model_asset_path=''),
                        num_poses=1,
                        min_pose_detection_confidence=0.5,
                        min_pose_presence_confidence=0.5,
                        min_tracking_confidence=0.5
                    )
                )
            except (ImportError, AttributeError):
                # Fallback to old API
                self.pose = mp.solutions.pose.Pose(
                    static_image_mode=False,
                    model_complexity=1,
                    smooth_landmarks=True,
                    enable_segmentation=False,
                    smooth_segmentation=False,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
            self._initialized = True
            logger.info("MediaPipe pose detector initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe: {e}")
            logger.warning("Skeleton detection disabled, continuing without it")
            self.enabled = False
            self._initialized = True
    
    def detect(self, frame: np.ndarray) -> Optional[List[Tuple[int, int]]]:
        """
        Detect skeleton landmarks
        
        Args:
            frame: Input BGR frame
            
        Returns:
            List of 33 (x, y) landmark coordinates or None
        """
        if not self.enabled or not self._initialized:
            return None
        
        try:
            # Convert to RGB for MediaPipe
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Run pose detection
            results = self.pose.process(frame_rgb)
            
            if not results.pose_landmarks:
                return None
            
            # Extract landmarks
            landmarks = []
            h, w = frame.shape[:2]
            
            for landmark in results.pose_landmarks.landmark:
                x = int(landmark.x * w)
                y = int(landmark.y * h)
                landmarks.append((x, y))
            
            return landmarks
            
        except Exception as e:
            logger.error(f"Skeleton detection error: {e}")
            return None
    
    def draw_skeleton(
        self,
        frame: np.ndarray,
        landmarks: List[Tuple[int, int]],
        color: Tuple[int, int, int] = (0, 255, 255)
    ) -> np.ndarray:
        """
        Draw skeleton on frame
        
        Args:
            frame: Input frame
            landmarks: List of landmark coordinates
            color: Drawing color (BGR)
            
        Returns:
            Frame with skeleton drawn
        """
        if not landmarks:
            return frame
        
        frame = frame.copy()
        
        # Draw connections
        for connection in self.POSE_CONNECTIONS:
            idx1, idx2 = connection
            if idx1 < len(landmarks) and idx2 < len(landmarks):
                pt1 = landmarks[idx1]
                pt2 = landmarks[idx2]
                cv2.line(frame, pt1, pt2, color, 2)
        
        # Draw landmarks
        for i, landmark in enumerate(landmarks):
            # Different colors for different body parts
            if i < 11:  # Face and upper body
                landmark_color = (0, 255, 255)
            else:  # Lower body
                landmark_color = (0, 200, 200)
            
            cv2.circle(frame, landmark, 3, landmark_color, -1)
            cv2.circle(frame, landmark, 5, (255, 255, 255), 1)
        
        return frame
    
    def get_tighter_bbox(
        self,
        landmarks: List[Tuple[int, int]],
        padding: int = 20
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Get tighter bounding box from skeleton landmarks
        
        Args:
            landmarks: List of landmark coordinates
            padding: Padding around bbox
            
        Returns:
            Bounding box (x1, y1, x2, y2) or None
        """
        if not landmarks:
            return None
        
        x_coords = [pt[0] for pt in landmarks]
        y_coords = [pt[1] for pt in landmarks]
        
        x1 = min(x_coords) - padding
        y1 = min(y_coords) - padding
        x2 = max(x_coords) + padding
        y2 = max(y_coords) + padding
        
        return (x1, y1, x2, y2)
    
    def cleanup(self):
        """Clean up resources"""
        if self.pose:
            self.pose.close()
        self._initialized = False
        logger.info("Skeleton detector cleaned up")
