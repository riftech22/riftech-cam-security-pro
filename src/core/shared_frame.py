"""
Shared Frame Manager - Cross-process frame sharing
Uses file-based approach for reliable cross-process communication
"""

import numpy as np
import threading
import time
import cv2
from typing import Optional
from pathlib import Path
import pickle

from .logger import logger


class SharedFrameWriter:
    """
    Writer for shared frame
    Writes frames to file that can be read by other processes
    """
    
    def __init__(self, name: str, shape: tuple):
        """
        Initialize shared frame writer
        
        Args:
            name: Frame name (used for filename)
            shape: Frame shape (height, width, channels)
        """
        self.name = name
        self.shape = shape
        self.frame_path = Path(f"data/shared_frames/{name}.jpg")
        self.meta_path = Path(f"data/shared_frames/{name}.meta")
        self.lock = threading.Lock()
        
        # Create directory
        self.frame_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.last_write_time = 0.0
        
    def write(self, frame: np.ndarray) -> bool:
        """
        Write frame to shared file
        
        Args:
            frame: Frame to write
            
        Returns:
            True if successful
        """
        try:
            with self.lock:
                # Write frame as JPEG
                cv2.imwrite(str(self.frame_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                
                # Write metadata
                meta = {
                    'shape': frame.shape,
                    'timestamp': time.time(),
                    'dtype': str(frame.dtype)
                }
                
                with open(self.meta_path, 'wb') as f:
                    pickle.dump(meta, f)
                
                self.last_write_time = time.time()
                return True
                
        except Exception as e:
            logger.error(f"Error writing shared frame {self.name}: {e}")
            return False
    
    def get_last_write_time(self) -> float:
        """Get last write time"""
        return self.last_write_time


class SharedFrameReader:
    """
    Reader for shared frame
    Reads frames from file written by other processes
    """
    
    def __init__(self, name: str):
        """
        Initialize shared frame reader
        
        Args:
            name: Frame name (used for filename)
        """
        self.name = name
        self.frame_path = Path(f"data/shared_frames/{name}.jpg")
        self.meta_path = Path(f"data/shared_frames/{name}.meta")
        self.last_read_time = 0.0
        self.last_shape = None
        
    def read(self) -> Optional[np.ndarray]:
        """
        Read frame from shared file
        
        Returns:
            Frame or None if not available
        """
        try:
            # Check if frame exists
            if not self.frame_path.exists():
                return None
            
            # Check if metadata exists
            if not self.meta_path.exists():
                return None
            
            # Read metadata
            with open(self.meta_path, 'rb') as f:
                meta = pickle.load(f)
            
            # Check if frame is stale (older than 2 seconds)
            if time.time() - meta['timestamp'] > 2.0:
                return None
            
            # Read frame
            frame = cv2.imread(str(self.frame_path))
            
            if frame is None:
                return None
            
            self.last_read_time = time.time()
            self.last_shape = frame.shape
            
            return frame
            
        except Exception as e:
            logger.error(f"Error reading shared frame {self.name}: {e}")
            return None
    
    def get_last_read_time(self) -> float:
        """Get last read time"""
        return self.last_read_time
    
    def is_stale(self, timeout: float = 2.0) -> bool:
        """
        Check if frame is stale
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            True if stale
        """
        return (time.time() - self.last_read_time) > timeout
