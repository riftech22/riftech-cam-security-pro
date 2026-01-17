"""
Face Recognition Module
Uses face_recognition library for trusted person identification
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import face_recognition
import pickle

from ..core.config import config
from ..core.logger import logger


class FaceDetector:
    """Face recognition detector for trusted persons"""
    
    def __init__(self, tolerance: float = 0.6):
        """
        Initialize face detector
        
        Args:
            tolerance: Face recognition tolerance (lower = stricter)
        """
        self.tolerance = tolerance
        self.known_face_encodings = []
        self.known_face_names = []
        self.face_cascade = None
        self._initialized = False
        self.enabled = True
    
    def initialize(self):
        """Initialize face detector and load known faces"""
        try:
            # Load OpenCV Haar cascade for face detection
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            
            # Load known faces
            self._load_known_faces()
            
            self._initialized = True
            logger.info(f"Face detector initialized with {len(self.known_face_names)} known faces")
        except Exception as e:
            logger.error(f"Failed to initialize face detector: {e}")
            raise
    
    def _load_known_faces(self):
        """Load known faces from fixed_images directory"""
        fixed_dir = Path(config.detection.fixed_images_dir)
        
        if not fixed_dir.exists():
            logger.warning(f"Fixed images directory not found: {fixed_dir}")
            return
        
        # Load all face encodings
        for image_path in fixed_dir.glob("*.jpg"):
            name = image_path.stem
            encoding = self._load_face_encoding(image_path)
            
            if encoding is not None:
                self.known_face_encodings.append(encoding)
                self.known_face_names.append(name)
                logger.info(f"Loaded face: {name}")
    
    def _load_face_encoding(self, image_path: Path) -> Optional[np.ndarray]:
        """
        Load face encoding from image
        
        Args:
            image_path: Path to face image
            
        Returns:
            Face encoding or None
        """
        try:
            # Load image
            image = face_recognition.load_image_file(str(image_path))
            
            # Get face encoding
            encodings = face_recognition.face_encodings(image)
            
            if len(encodings) > 0:
                return encodings[0]
            
            logger.warning(f"No face found in {image_path}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to load face encoding from {image_path}: {e}")
            return None
    
    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect face bounding boxes
        
        Args:
            frame: Input BGR frame
            
        Returns:
            List of face bounding boxes (x, y, w, h)
        """
        if not self.enabled or not self._initialized:
            return []
        
        try:
            # Convert to grayscale for Haar cascade
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            return [(x, y, w, h) for (x, y, w, h) in faces]
            
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return []
    
    def recognize_face(
        self,
        frame: np.ndarray,
        face_bbox: Tuple[int, int, int, int]
    ) -> Optional[Dict]:
        """
        Recognize face in bounding box
        
        Args:
            frame: Input BGR frame
            face_bbox: Face bounding box (x, y, w, h)
            
        Returns:
            Dict with name and confidence or None
        """
        if not self.enabled or not self._initialized:
            return None
        
        if len(self.known_face_encodings) == 0:
            return None
        
        try:
            x, y, w, h = face_bbox
            
            # Extract face region
            face_image = frame[y:y+h, x:x+w]
            
            # Get face encoding
            face_encodings = face_recognition.face_encodings(face_image)
            
            if len(face_encodings) == 0:
                return None
            
            unknown_encoding = face_encodings[0]
            
            # Compare with known faces
            matches = face_recognition.compare_faces(
                self.known_face_encodings,
                unknown_encoding,
                tolerance=self.tolerance
            )
            
            if True in matches:
                # Get best match
                face_distances = face_recognition.face_distance(
                    self.known_face_encodings,
                    unknown_encoding
                )
                
                best_match_index = np.argmin(face_distances)
                confidence = 1.0 - face_distances[best_match_index]
                
                return {
                    "name": self.known_face_names[best_match_index],
                    "confidence": float(confidence),
                    "is_trusted": True
                }
            
            return {"name": None, "confidence": 0.0, "is_trusted": False}
            
        except Exception as e:
            logger.error(f"Face recognition error: {e}")
            return None
    
    def reload_faces(self):
        """Reload known faces from directory"""
        logger.info("Reloading known faces...")
        self.known_face_encodings = []
        self.known_face_names = []
        self._load_known_faces()
        logger.info(f"Reloaded {len(self.known_face_names)} known faces")
    
    def set_tolerance(self, tolerance: float):
        """
        Update face recognition tolerance
        
        Args:
            tolerance: New tolerance (0.0 to 1.0, lower = stricter)
        """
        self.tolerance = max(0.0, min(1.0, tolerance))
        logger.info(f"Face tolerance set to {self.tolerance:.2f}")
    
    def cleanup(self):
        """Clean up resources"""
        self.face_cascade = None
        self._initialized = False
        logger.info("Face detector cleaned up")
