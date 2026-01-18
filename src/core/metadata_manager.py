"""
Metadata Manager - Shared Tracking Data
Manages lightweight tracking metadata (no frame copies!)
"""

import numpy as np
import cv2
import threading
from typing import Optional, List, Dict
from multiprocessing.shared_memory import SharedMemory
import pickle
from dataclasses import dataclass, asdict

from .logger import logger


@dataclass
class TrackingObjectMetadata:
    """Lightweight tracking object metadata (no frame copy!)"""
    id: int
    bbox: tuple  # (x1, y1, x2, y2)
    confidence: float
    class_name: str
    is_trusted: bool
    face_name: Optional[str]
    camera_label: str
    last_seen: float


class SharedMetadata:
    """Shared memory for tracking metadata"""
    
    def __init__(self, name: str, max_objects: int = 20):
        """
        Initialize shared metadata
        
        Args:
            name: Metadata name
            max_objects: Maximum number of tracked objects
        """
        self.name = name
        self.max_objects = max_objects
        self.shm: Optional[SharedMemory] = None
        self.np_array: Optional[np.ndarray] = None
        self._lock = None
        
        # Create shared memory
        self._create()
    
    def _create(self):
        """Create shared memory (or attach if exists)"""
        try:
            from multiprocessing import Lock
            self._lock = Lock()
            
            # Create shared memory for metadata
            # Each object: id(4) + bbox(16) + confidence(4) + trusted(1) + face_name(32) + label(8) + timestamp(8) ≈ 73 bytes
            metadata_size = self.max_objects * 100  # 100 bytes per object (safe margin)
            
            try:
                self.shm = SharedMemory(name=self.name, create=True, size=metadata_size)
                self.np_array = np.zeros(metadata_size, dtype=np.uint8)
                logger.debug(f"Created shared metadata: {self.name} ({metadata_size} bytes)")
            except FileNotFoundError:
                # Metadata already exists, attach instead
                return self.attach()
            
            return True
        except Exception as e:
            # Try to attach if create fails
            return self.attach()
    
    def attach(self):
        """Attach to existing shared memory"""
        try:
            from multiprocessing import Lock
            self._lock = Lock()
            
            self.shm = SharedMemory(name=self.name, create=False)
            self.np_array = np.ndarray(self.shm.size, dtype=np.uint8, buffer=self.shm.buf)
            
            logger.debug(f"Attached to shared metadata: {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to attach to shared metadata {self.name}: {e}")
            return False
    
    def write_objects(self, objects: List[Dict]) -> bool:
        """
        Write objects to shared metadata
        
        Args:
            objects: List of tracking objects as dicts
            
        Returns:
            True if successful
        """
        if self.np_array is None:
            return False
        
        try:
            with self._lock:
                # Serialize objects to bytes
                data = pickle.dumps(objects)
                
                # Write to shared memory
                data_bytes = np.frombuffer(data, dtype=np.uint8)
                
                if len(data_bytes) > len(self.np_array):
                    logger.warning(f"Metadata too large: {len(data_bytes)} > {len(self.np_array)}")
                    return False
                
                self.np_array[:len(data_bytes)] = data_bytes
                
                logger.debug(f"Wrote {len(objects)} objects to {self.name}")
                return True
        except Exception as e:
            logger.error(f"Error writing metadata {self.name}: {e}")
            return False
    
    def read_objects(self) -> Optional[List[Dict]]:
        """
        Read objects from shared metadata
        
        Returns:
            List of objects or None
        """
        if self.np_array is None:
            return None
        
        try:
            with self._lock:
                # Deserialize from bytes
                # Find end of data (zero padding after actual data)
                non_zero = np.nonzero(self.np_array)[0]
                
                if len(non_zero) == 0:
                    return []
                
                end_idx = non_zero[-1] + 1
                data_bytes = self.np_array[:end_idx]
                
                objects = pickle.loads(data_bytes.tobytes())
                
                logger.debug(f"Read {len(objects)} objects from {self.name}")
                return objects
        except Exception as e:
            logger.error(f"Error reading metadata {self.name}: {e}")
            return None
    
    def close(self):
        """Close shared memory"""
        if self.shm:
            self.shm.close()
            logger.debug(f"Closed shared metadata: {self.name}")
    
    def unlink(self):
        """Unlink shared memory (free resources)"""
        if self.shm:
            try:
                self.shm.unlink()
                logger.debug(f"Unlinked shared metadata: {self.name}")
            except Exception as e:
                logger.error(f"Error unlinking shared metadata {self.name}: {e}")


class MetadataManager:
    """
    Manager for multiple shared metadata buffers
    Manages metadata for different views (top, bottom, full)
    """
    
    def __init__(self):
        self.metadatas: Dict[str, SharedMetadata] = {}
        self._lock = threading.Lock()
    
    def create_metadata(self, name: str, max_objects: int = 20) -> bool:
        """
        Create a new shared metadata buffer
        
        Args:
            name: Metadata name
            max_objects: Maximum number of tracked objects
            
        Returns:
            True if successful
        """
        with self._lock:
            if name in self.metadatas:
                logger.warning(f"Metadata {name} already exists")
                return self.metadatas[name].attach()
            
            metadata = SharedMetadata(name, max_objects)
            if metadata._create():
                self.metadatas[name] = metadata
                return True
            return False
    
    def write_objects(self, name: str, objects: List[Dict]) -> bool:
        """
        Write objects to metadata
        
        Args:
            name: Metadata name
            objects: List of tracking objects
            
        Returns:
            True if successful
        """
        with self._lock:
            if name not in self.metadatas:
                logger.warning(f"Metadata {name} not found")
                return False
            
            return self.metadatas[name].write_objects(objects)
    
    def read_objects(self, name: str) -> Optional[List[Dict]]:
        """
        Read objects from metadata
        
        Args:
            name: Metadata name
            
        Returns:
            List of objects or None
        """
        with self._lock:
            if name not in self.metadatas:
                return None
            
            return self.metadatas[name].read_objects()
    
    def close_all(self):
        """Close all shared metadata"""
        with self._lock:
            for name, metadata in self.metadatas.items():
                metadata.close()
            logger.info(f"Closed all {len(self.metadatas)} shared metadata")
    
    def cleanup_all(self):
        """Close and unlink all shared metadata"""
        with self._lock:
            for name, metadata in self.metadatas.items():
                metadata.unlink()
            self.metadatas.clear()
            logger.info("Cleaned up all shared metadata")


# Global instance
metadata_manager = MetadataManager()
