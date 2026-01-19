"""
Ring Buffer Frame Manager V2
High-performance zero-copy frame sharing with ping-pong buffer
"""

import numpy as np
import cv2
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
            # Acquire lock for both memory and event
            with self.mp_lock:
                # Write to slot that's NOT being read (ping-pong)
                if self.write_idx == 0:
                    np.copyto(self.slot0_arr, frame)
                else:
                    np.copyto(self.slot1_arr, frame)
                
                # Toggle write index
                self.write_idx = 1 - self.write_idx
                
                # Signal that data is ready (inside lock to prevent race condition)
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
            # Event wait is outside lock to allow other writers
            if not self.data_ready.wait(timeout=0.1):
                return None
            
            # Acquire lock for reading
            with self.mp_lock:
                # Double-check after acquiring lock (prevents race condition)
                if self.read_idx == self.write_idx:
                    # No new data - might have been consumed by another reader
                    return None
                
                # Read from the slot that was just written
                if self.write_idx == 0:
                    frame = self.slot0_arr.copy()
                else:
                    frame = self.slot1_arr.copy()
                
                # Sync read index with write index
                self.read_idx = self.write_idx
                
                # Clear the event (inside lock to prevent race condition)
                self.data_ready.clear()
            
            return frame
        except Exception as e:
            logger.error(f"Error reading from ring buffer {self.name}: {e}")
            return None
    
    def force_read(self) -> Optional[np.ndarray]:
        """
        Force read (even if no new data) - for web server
        Thread-safe read of latest frame without affecting indices
        
        Returns:
            Last available frame or None
        """
        try:
            # Acquire lock to ensure atomic read
            with self.mp_lock:
                # Always read from the most recently written slot (write_idx points to next write)
                # So the last written is at (1 - write_idx)
                read_slot = 1 - self.write_idx
                
                if read_slot == 0:
                    frame = self.slot0_arr.copy()
                else:
                    frame = self.slot1_arr.copy()
            
            return frame
        except Exception as e:
            logger.error(f"Error force reading from ring buffer {self.name}: {e}")
            return None
    
    def close(self):
        """Close ring buffer"""
        try:
            if self.slot0:
                self.slot0.close()
            if self.slot1:
                self.slot1.close()
            # Clear the event to prevent any waiters
            if self.data_ready:
                self.data_ready.clear()
            logger.debug(f"Closed ring buffer {self.name}")
        except Exception as e:
            logger.error(f"Error closing ring buffer {self.name}: {e}")
    
    def unlink(self):
        """Unlink ring buffer (free resources)"""
        try:
            # First close all resources
            self.close()
            
            # Then unlink shared memory (this actually frees the memory)
            if self.slot0:
                self.slot0.unlink()
            if self.slot1:
                self.slot1.unlink()
            
            logger.debug(f"Unlinked ring buffer {self.name}")
        except FileNotFoundError:
            # Shared memory already unlinked (not an error)
            logger.debug(f"Ring buffer {self.name} already unlinked")
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
            shape: Frame shape (height, width, channels)
            dtype: Data type
            
        Returns:
            True if successful
        """
        with self._lock:
            if name in self.ring_buffers:
                logger.warning(f"Ring buffer {name} already exists")
                return self.ring_buffers[name].attach()
            
            # Limit frame size for shared memory (max 1280x720)
            # Larger frames will cause SharedMemory creation to fail
            height, width, channels = shape
            max_width = 1280
            max_height = 720
            
            if width > max_width or height > max_height:
                # Calculate new size maintaining aspect ratio
                aspect_ratio = width / height
                if width > max_width:
                    width = max_width
                    height = int(width / aspect_ratio)
                if height > max_height:
                    height = max_height
                    width = int(height * aspect_ratio)
                
                # Ensure minimum size
                width = max(width, 640)
                height = max(height, 480)
                
                logger.warning(f"Resizing frame for {name}: {shape[0]}x{shape[1]} -> {height}x{width}")
                shape = (height, width, channels)
            
            buffer = RingBuffer(name, shape, dtype)
            if buffer._create_slots():
                self.ring_buffers[name] = buffer
                return True
            return False
    
    def write_frame(self, name: str, frame: np.ndarray) -> bool:
        """
        Write frame to ring buffer (auto-resize if needed)
        
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
            
            buffer = self.ring_buffers[name]
            
            # Resize frame if size doesn't match buffer
            if frame.shape != buffer.shape:
                import cv2
                frame = cv2.resize(frame, (buffer.shape[1], buffer.shape[0]), interpolation=cv2.INTER_LINEAR)
            
            return buffer.write(frame)
    
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
        """Close and unlink all ring buffers with error handling"""
        with self._lock:
            errors = 0
            for name, buffer in self.ring_buffers.items():
                try:
                    buffer.unlink()
                except Exception as e:
                    logger.error(f"Error cleaning up ring buffer {name}: {e}")
                    errors += 1
            
            self.ring_buffers.clear()
            
            if errors > 0:
                logger.warning(f"Cleaned up {len(self.ring_buffers) - errors}/{len(self.ring_buffers)} ring buffers with {errors} errors")
            else:
                logger.info(f"Cleaned up all {len(self.ring_buffers)} ring buffers")


# Global instance
frame_manager_v2 = FrameManagerV2()
