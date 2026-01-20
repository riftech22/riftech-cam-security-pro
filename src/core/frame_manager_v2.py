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
        """Create 2 shared memory slots (or attach to existing)"""
        try:
            from multiprocessing import Lock
            self.mp_lock = Lock()
            
            # Slot 0 - try to create, if exists then attach
            try:
                self.slot0 = SharedMemory(name=f"{self.name}_0", create=True, size=self.size)
                logger.debug(f"Created new shared memory slot for {self.name}_0")
            except FileExistsError:
                # Already exists, try to attach
                try:
                    self.slot0 = SharedMemory(name=f"{self.name}_0", create=False)
                    logger.debug(f"Attached to existing shared memory {self.name}_0")
                except Exception as attach_err:
                    logger.error(f"Failed to attach to {self.name}_0: {attach_err}")
                    return False
            
            self.slot0_arr = np.ndarray(self.shape, dtype=self.dtype, buffer=self.slot0.buf)
            
            # Slot 1 - try to create, if exists then attach
            try:
                self.slot1 = SharedMemory(name=f"{self.name}_1", create=True, size=self.size)
                logger.debug(f"Created new shared memory slot for {self.name}_1")
            except FileExistsError:
                # Already exists, try to attach
                try:
                    self.slot1 = SharedMemory(name=f"{self.name}_1", create=False)
                    logger.debug(f"Attached to existing shared memory {self.name}_1")
                except Exception as attach_err:
                    logger.error(f"Failed to attach to {self.name}_1: {attach_err}")
                    return False
            
            self.slot1_arr = np.ndarray(self.shape, dtype=self.dtype, buffer=self.slot1.buf)
            
            from multiprocessing import Event
            self.data_ready = Event()
            
            logger.info(f"Ring buffer {self.name} ready with 2 slots")
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
        Detects active slot by comparing pixel changes
        
        Returns:
            Last available frame or None
        """
        try:
            # Acquire lock to ensure atomic read
            with self.mp_lock:
                # CRITICAL FIX: When attached to existing buffer, write_idx is unknown
                # Solution: Read both slots and return the one with more activity
                # This works even if write_idx is out of sync
                
                # Simple approach: Try slot (1 - write_idx) first
                # If that fails or looks stale, try the other slot
                
                read_slot = 1 - self.write_idx
                
                if read_slot == 0:
                    frame = self.slot0_arr.copy()
                    other_frame = self.slot1_arr.copy()
                else:
                    frame = self.slot1_arr.copy()
                    other_frame = self.slot0_arr.copy()
                
                # Check if frame is valid (not all zeros)
                if np.mean(frame) < 10:  # Frame is too dark/black
                    # Try other slot
                    if np.mean(other_frame) > 10:
                        frame = other_frame
                        # Update write_idx to match
                        self.write_idx = 0 if read_slot == 1 else 1
                
                # Additional check: Compare variance to detect stale frame
                # A live frame should have some variance
                if np.var(frame) < 100:  # Very low variance = stale/static frame
                    if np.var(other_frame) > 100:
                        frame = other_frame
                        # Update write_idx to match
                        self.write_idx = 0 if read_slot == 1 else 1
            
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
            shape: Frame shape (height, width, channels) or (width, height, channels)
            dtype: Data type
            
        Returns:
            True if successful
        """
        # Auto-detect and correct shape if needed
        # OpenCV/FFmpeg uses (height, width, channels) but sometimes passed as (width, height, channels)
        if len(shape) == 3:
            # Assume it's (height, width, channels) by default
            h, w, c = shape
            # If width > height and they're very different, swap them
            if w > h and abs(w - h) > 100:  # Only swap if clearly wrong
                logger.debug(f"Detected shape mismatch, swapping: ({h}, {w}, {c}) -> ({w}, {h}, {c})")
                shape = (w, h, c)
        
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
        Write frame to ring buffer (auto-resize with aspect ratio if needed)
        
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
            # CRITICAL: Maintain aspect ratio!
            if frame.shape != buffer.shape:
                import cv2
                frame_height, frame_width = frame.shape[:2]
                target_height, target_width = buffer.shape[:2]
                
                # Calculate aspect ratio
                frame_aspect = frame_width / frame_height
                target_aspect = target_width / target_height
                
                # If aspect ratios are similar (within 5%), resize directly
                # Otherwise, maintain frame aspect ratio
                if abs(frame_aspect - target_aspect) / target_aspect < 0.05:
                    # Similar aspect ratio - resize directly
                    frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
                else:
                    # Different aspect ratio - maintain frame's aspect ratio
                    # Fit within target dimensions
                    scale = min(target_width / frame_width, target_height / frame_height)
                    new_width = int(frame_width * scale)
                    new_height = int(frame_height * scale)
                    
                    # Resize maintaining aspect ratio
                    resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
                    
                    # Add padding (letterbox) to fill target dimensions
                    pad_left = (target_width - new_width) // 2
                    pad_right = target_width - new_width - pad_left
                    pad_top = (target_height - new_height) // 2
                    pad_bottom = target_height - new_height - pad_top
                    
                    frame = cv2.copyMakeBorder(
                        resized,
                        pad_top,
                        pad_bottom,
                        pad_left,
                        pad_right,
                        cv2.BORDER_CONSTANT,
                        value=(0, 0, 0)  # Black padding
                    )
            
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
        Auto-attaches to existing ring buffer if not found
        
        Args:
            name: Buffer name
            
        Returns:
            Last available frame or None
        """
        with self._lock:
            # If buffer not in our dictionary, try to attach to existing one
            if name not in self.ring_buffers:
                if self._attach_existing_buffer(name):
                    logger.debug(f"Auto-attached to existing ring buffer: {name}")
                else:
                    # Buffer doesn't exist anywhere
                    return None
            
            return self.ring_buffers[name].force_read()
    
    def _attach_existing_buffer(self, name: str) -> bool:
        """
        Attach to existing ring buffer (created by another process)
        
        Args:
            name: Buffer name
            
        Returns:
            True if successful
        """
        try:
            from multiprocessing import Lock
            mp_lock = Lock()
            
            # Try to attach to both slots
            slot0 = SharedMemory(name=f"{name}_0", create=False)
            slot1 = SharedMemory(name=f"{name}_1", create=False)
            
            # Infer shape from slot0 buffer size
            buffer_size = slot0.size
            
            # Try common shapes for camera frames
            # (height, width, channels) with uint8
            possible_shapes = [
                (480, 640, 3),
                (720, 1280, 3),
                (1080, 1920, 3),
                (360, 640, 3),
                (720, 960, 3),
            ]
            
            for shape in possible_shapes:
                expected_size = np.prod(shape) * np.dtype(np.uint8).itemsize
                if buffer_size == expected_size:
                    logger.debug(f"Inferred shape {shape} for buffer {name}")
                    break
            else:
                # Try to infer from size directly
                # size = height * width * 3
                # So: height * width = size / 3
                pixel_count = buffer_size // 3
                
                # Try common aspect ratios
                for ratio in [4/3, 16/9, 3/2]:
                    width = int((pixel_count * ratio) ** 0.5)
                    height = pixel_count // width
                    
                    # Round to reasonable sizes
                    width = (width // 8) * 8  # Multiple of 8
                    height = (height // 8) * 8
                    
                    expected_size = height * width * 3
                    if buffer_size == expected_size:
                        shape = (height, width, 3)
                        logger.debug(f"Inferred shape {shape} from buffer size {buffer_size}")
                        break
                else:
                    # Fallback
                    shape = (480, 640, 3)
                    logger.warning(f"Could not infer shape for buffer {name} (size={buffer_size}), using default {shape}")
            
            # Create numpy arrays from buffers
            slot0_arr = np.ndarray(shape, dtype=np.uint8, buffer=slot0.buf)
            slot1_arr = np.ndarray(shape, dtype=np.uint8, buffer=slot1.buf)
            
            from multiprocessing import Event
            data_ready = Event()
            
            # Create RingBuffer object and attach
            buffer = RingBuffer(name, shape, np.uint8)
            buffer.slot0 = slot0
            buffer.slot1 = slot1
            buffer.slot0_arr = slot0_arr
            buffer.slot1_arr = slot1_arr
            buffer.data_ready = data_ready
            buffer.mp_lock = mp_lock
            
            # CRITICAL: Don't assume write_idx!
            # The security system constantly updates write_idx (0, 1, 0, 1...)
            # If we assume write_idx=0, we'll read from wrong slot
            # Solution: Check both slots and detect which is more recent
            # by comparing pixel changes or simply start with write_idx=0
            # and let force_read handle it correctly
            buffer.write_idx = 0  # Initial guess, will be corrected by reads
            buffer.read_idx = 0
            
            self.ring_buffers[name] = buffer
            logger.info(f"Successfully attached to existing ring buffer: {name} (shape={shape})")
            return True
            
        except FileNotFoundError:
            # Ring buffer doesn't exist
            logger.debug(f"Ring buffer {name} does not exist")
            return False
        except Exception as e:
            logger.error(f"Failed to attach to ring buffer {name}: {e}")
            return False
    
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
