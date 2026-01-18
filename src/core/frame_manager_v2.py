"""
Ring Buffer Frame Manager V2
High-performance zero-copy frame sharing with ping-pong buffer
"""

import numpy as np
import threading
from typing import Optional, Dict, Tuple
from multiprocessing.shared_memory import SharedMemory
import time
from .logger import logger


class RingBuffer:
    """Ping-pong ring buffer for 2 slots"""
    
    def __init__(self, name: str, shape: Tuple[int, ...], dtype: np.dtype = np.uint8):
        """
        Initialize ring buffer
        
        Args:
            name: Buffer name (used for filename)
            shape: Frame shape (height, width, channels)
            dtype: Data type
        """
        self.name = name
        self.shape = shape
        self.dtype = dtype
        
        # Calculate size
        np_dtype = np.dtype(dtype)
        self.size = int(np.prod(shape)) * np_dtype.itemsize
        
        # Create 2 shared memory slots
        self.slot0 = None
        self.slot1 = None
        self.slot0_arr = None
        self.slot1_arr = None
        
        # Index management (ping-pong)
        self.write_idx = 0  # 0 or 1
        self.read_idx = 0   # 0 or 1
        
        # Synchronization
        self.data_ready = None
        self.lock = threading.Lock()
        self.mp_lock = None
        
        # Create slots
        self._create_slots()
    
    def _create_slots(self):
        """Create 2 shared memory slots"""
        try:
            from multiprocessing import Lock
            self.mp_lock = Lock()
            
            # Slot 0
            self.slot0 = SharedMemory(name=f"{self.name}_0", create=True, size=self.size)
            self.slot0_arr = np.ndarray(self.shape, dtype=self.dtype, buffer=self.slot0.buf)
            
            # Slot 1
            self.slot1 = SharedMemory(name=f"{self.name}_1", create=True, size=self.size)
            self.slot1_arr = np.ndarray(self.shape, dtype=self.dtype, buffer=self.slot1.buf)
            
            from multiprocessing import Event
            self.data_ready = Event()
            
            logger.debug(f"Created ring buffer {self.name} with 2 slots")
            return True
        except Exception as e:
            logger.error(f"Failed to create ring buffer {self.name}: {e}")
            return False
    
    def attach(self):
        """Attach to existing ring buffer"""
        try:
            from multiprocessing import Lock
            self.mp_lock = Lock()
            
            # Attach to slots
            self.slot0 = SharedMemory(name=f"{self.name}_0", create=False)
            self.slot0_arr = np.ndarray(self.shape, dtype=self.dtype, buffer=self.slot0.buf)
            
            self.slot1 = SharedMemory(name=f"{self.name}_1", create=False)
            self.slot1_arr = np.ndarray(self.shape, dtype=self.dtype, buffer=self.slot1.buf)
            
            from multiprocessing import Event
            self.data_ready = Event()
            
            logger.debug(f"Attached to ring buffer {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to attach to ring buffer {self.name}: {e}")
            return False
    
    def write(self, frame: np.ndarray) -> bool:
        """
        Write frame to ring buffer (ping-pong)
        
        Args:
            frame: Frame to write
            
        Returns:
            True if successful
        """
        if frame is None:
            return False
        
        if not isinstance(frame, np.ndarray):
            return False
        
        if frame.shape != self.shape:
            logger.warning(f"Frame shape mismatch: expected {self.shape}, got {frame.shape}")
            return False
        
        try:
            with self.mp_lock:
                # Write to slot that's NOT being read (ping-pong)
                if self.write_idx == 0:
                    np.copyto(self.slot0_arr, frame)
                else:
                    np.copyto(self.slot1_arr, frame)
                
                # Toggle write index
                self.write_idx = 1 - self.write_idx
                
                # Signal that data is ready
                self.data_ready.set()
            
            return True
        except Exception as e:
            logger.error(f"Error writing to ring buffer {self.name}: {e}")
            return False
    
    def read(self) -> Optional[np.ndarray]:
        """
        Read frame from ring buffer
        
        Returns:
            Frame or None if not available
        """
        try:
            # Wait for data (timeout 100ms)
            if not self.data_ready.wait(timeout=0.1):
                return None
            
            with self.mp_lock:
                # Only read if there's new data (read_idx != write_idx)
                if self.read_idx == self.write_idx:
                    # No new data
                    return None
                
                # Read from the slot that was just written
                if self.write_idx == 0:
                    frame = self.slot0_arr.copy()
                else:
                    frame = self.slot1_arr.copy()
                
                # Sync read index with write index
                self.read_idx = self.write_idx
                
                # Clear the event
                self.data_ready.clear()
            
            return frame
        except Exception as e:
            logger.error(f"Error reading from ring buffer {self.name}: {e}")
            return None
    
    def force_read(self) -> Optional[np.ndarray]:
        """
        Force read (even if no new data) - for web server
        
        Returns:
            Last available frame or None
        """
        try:
            with self.mp_lock:
                # Always read from the most recently written slot
                if self.write_idx == 0:
                    frame = self.slot0_arr.copy()
                else:
                    frame = self.slot1_arr.copy()
            
            return frame
        except Exception as e:
            logger.error(f"Error force reading from ring buffer {self.name}: {e}")
            return None
    
    def close(self):
        """Close ring buffer"""
        if self.slot0:
            self.slot0.close()
        if self.slot1:
            self.slot1.close()
        logger.debug(f"Closed ring buffer {self.name}")
    
    def unlink(self):
        """Unlink ring buffer (free resources)"""
        try:
            if self.slot0:
                self.slot0.unlink()
            if self.slot1:
                self.slot1.unlink()
            logger.debug(f"Unlinked ring buffer {self.name}")
        except Exception as e:
            logger.error(f"Error unlinking ring buffer {self.name}: {e}")


class FrameManagerV2:
    """
    Frame Manager V2 with Ring Buffer Support
    Manages multiple ring buffers for different views
    """
    
    def __init__(self):
        self.ring_buffers: Dict[str, RingBuffer] = {}
        self._lock = threading.Lock()
    
    def create_ring_buffer(
        self,
        name: str,
        shape: Tuple[int, ...],
        dtype: np.dtype = np.uint8
    ) -> bool:
        """
        Create a new ring buffer
        
        Args:
            name: Buffer name
            shape: Frame shape
            dtype: Data type
            
        Returns:
            True if successful
        """
        with self._lock:
            if name in self.ring_buffers:
                logger.warning(f"Ring buffer {name} already exists")
                return self.ring_buffers[name].attach()
            
            buffer = RingBuffer(name, shape, dtype)
            if buffer._create_slots():
                self.ring_buffers[name] = buffer
                return True
            return False
    
    def write_frame(self, name: str, frame: np.ndarray) -> bool:
        """
        Write frame to ring buffer
        
        Args:
            name: Buffer name
            frame: Frame to write
            
        Returns:
            True if successful
        """
        with self._lock:
            if name not in self.ring_buffers:
                logger.warning(f"Ring buffer {name} not found")
                return False
            
            return self.ring_buffers[name].write(frame)
    
    def read_frame(self, name: str) -> Optional[np.ndarray]:
        """
        Read frame from ring buffer
        
        Args:
            name: Buffer name
            
        Returns:
            Frame or None if not available
        """
        with self._lock:
            if name not in self.ring_buffers:
                return None
            
            return self.ring_buffers[name].read()
    
    def force_read_frame(self, name: str) -> Optional[np.ndarray]:
        """
        Force read frame (for web server - always return last frame)
        
        Args:
            name: Buffer name
            
        Returns:
            Last available frame or None
        """
        with self._lock:
            if name not in self.ring_buffers:
                return None
            
            return self.ring_buffers[name].force_read()
    
    def close_all(self):
        """Close all ring buffers"""
        with self._lock:
            for name, buffer in self.ring_buffers.items():
                buffer.close()
            logger.info(f"Closed all {len(self.ring_buffers)} ring buffers")
    
    def cleanup_all(self):
        """Close and unlink all ring buffers"""
        with self._lock:
            for name, buffer in self.ring_buffers.items():
                buffer.unlink()
            self.ring_buffers.clear()
            logger.info("Cleaned up all ring buffers")


# Global instance
frame_manager_v2 = FrameManagerV2()
