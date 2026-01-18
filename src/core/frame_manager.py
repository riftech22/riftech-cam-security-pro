"""
Shared Memory Frame Manager
High-performance zero-copy frame sharing between processes
"""

import numpy as np
import threading
from typing import Optional, Dict, Tuple
from multiprocessing.shared_memory import SharedMemory
import time

from .logger import logger


class SharedMemoryFrame:
    """Wrapper for shared memory frame"""
    
    def __init__(self, name: str, shape: Tuple[int, ...], dtype: np.dtype = np.uint8):
        self.name = name
        self.shape = shape
        self.dtype = dtype
        # Convert dtype to numpy dtype to get itemsize
        np_dtype = np.dtype(dtype)
        self.size = int(np.prod(shape)) * np_dtype.itemsize
        self.shm: Optional[SharedMemory] = None
        self.np_array: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._last_update_time = 0.0
    
    def create(self):
        """Create shared memory"""
        try:
            self.shm = SharedMemory(name=self.name, create=True, size=self.size)
            self.np_array = np.ndarray(self.shape, dtype=self.dtype, buffer=self.shm.buf)
            logger.debug(f"Created shared memory: {self.name} with shape {self.shape}")
            return True
        except FileExistsError:
            # Already exists, just attach
            return self.attach()
        except Exception as e:
            logger.error(f"Failed to create shared memory {self.name}: {e}")
            return False
    
    def attach(self):
        """Attach to existing shared memory"""
        try:
            self.shm = SharedMemory(name=self.name, create=False)
            self.np_array = np.ndarray(self.shape, dtype=self.dtype, buffer=self.shm.buf)
            logger.debug(f"Attached to shared memory: {self.name}")
            return True
        except FileNotFoundError:
            logger.error(f"Shared memory {self.name} not found")
            return False
        except Exception as e:
            logger.error(f"Failed to attach to shared memory {self.name}: {e}")
            return False
    
    def write(self, frame: np.ndarray):
        """Write frame to shared memory (thread-safe)"""
        if self.np_array is None:
            logger.warning(f"Shared memory {self.name} not initialized")
            return False
        
        try:
            with self._lock:
                if frame.shape != self.shape:
                    logger.warning(f"Frame shape mismatch: expected {self.shape}, got {frame.shape}")
                    return False
                
                # Zero-copy write
                np.copyto(self.np_array, frame)
                self._last_update_time = time.time()
                return True
        except Exception as e:
            logger.error(f"Error writing to shared memory {self.name}: {e}")
            return False
    
    def read(self) -> Optional[np.ndarray]:
        """Read frame from shared memory (thread-safe)"""
        if self.np_array is None:
            return None
        
        try:
            with self._lock:
                # Return a copy to avoid race conditions
                return self.np_array.copy()
        except Exception as e:
            logger.error(f"Error reading from shared memory {self.name}: {e}")
            return None
    
    def get_update_time(self) -> float:
        """Get last update time"""
        return self._last_update_time
    
    def is_stale(self, timeout: float = 5.0) -> bool:
        """Check if frame is stale (not updated recently)"""
        return (time.time() - self._last_update_time) > timeout
    
    def close(self):
        """Close shared memory"""
        if self.shm is not None:
            try:
                self.shm.close()
                logger.debug(f"Closed shared memory: {self.name}")
            except Exception as e:
                logger.error(f"Error closing shared memory {self.name}: {e}")
    
    def unlink(self):
        """Unlink shared memory (free resources)"""
        if self.shm is not None:
            try:
                self.shm.unlink()
                logger.debug(f"Unlinked shared memory: {self.name}")
            except Exception as e:
                logger.error(f"Error unlinking shared memory {self.name}: {e}")


class FrameManager:
    """
    Manage shared memory frames for multiple cameras
    Provides zero-copy frame sharing between processes
    """
    
    def __init__(self):
        self.frames: Dict[str, SharedMemoryFrame] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup_time = time.time()
    
    def register_frame(
        self,
        name: str,
        shape: Tuple[int, ...],
        dtype: np.dtype = np.uint8
    ) -> bool:
        """Register a new frame in shared memory"""
        with self._lock:
            if name in self.frames:
                logger.warning(f"Frame {name} already registered")
                return self.frames[name].attach()
            
            frame = SharedMemoryFrame(name, shape, dtype)
            if frame.create():
                self.frames[name] = frame
                return True
            return False
    
    def write_frame(self, name: str, frame: np.ndarray) -> bool:
        """Write frame to shared memory"""
        with self._lock:
            if name not in self.frames:
                logger.warning(f"Frame {name} not registered")
                return False
            
            return self.frames[name].write(frame)
    
    def read_frame(self, name: str) -> Optional[np.ndarray]:
        """Read frame from shared memory"""
        with self._lock:
            if name not in self.frames:
                return None
            
            return self.frames[name].read()
    
    def get_frame_update_time(self, name: str) -> float:
        """Get last update time for a frame"""
        with self._lock:
            if name not in self.frames:
                return 0.0
            
            return self.frames[name].get_update_time()
    
    def is_frame_stale(self, name: str, timeout: float = 5.0) -> bool:
        """Check if frame is stale"""
        with self._lock:
            if name not in self.frames:
                return True
            
            return self.frames[name].is_stale(timeout)
    
    def cleanup_stale_frames(self):
        """Clean up stale frames"""
        current_time = time.time()
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return
        
        with self._lock:
            for name, frame in list(self.frames.items()):
                if frame.is_stale(timeout=10.0):
                    logger.info(f"Cleaning up stale frame: {name}")
                    frame.unlink()
                    del self.frames[name]
            
            self._last_cleanup_time = current_time
    
    def close_all(self):
        """Close all shared memory frames"""
        with self._lock:
            for name, frame in self.frames.items():
                frame.close()
            logger.info(f"Closed all {len(self.frames)} shared memory frames")
    
    def cleanup_all(self):
        """Close and unlink all shared memory frames"""
        with self._lock:
            for name, frame in self.frames.items():
                frame.unlink()
            self.frames.clear()
            logger.info("Cleaned up all shared memory frames")


# Global instance
frame_manager = FrameManager()
