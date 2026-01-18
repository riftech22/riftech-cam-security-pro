# 🚀 Riftech Security System V2 - High-Performance Architecture

## 📋 Overview

Dokumentasi ini menjelaskan implementasi arsitektur high-performance untuk Riftech Security System. Arsitektur baru ini menggunakan multi-process decoupled architecture, shared memory, dan motion-first detection untuk mencapai FPS tinggi (30+ FPS) dengan AI processing real-time.

---

## 🏗️ Arsitektur Baru

### **Decoupled Multi-Process Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│              Main Process (Coordinator)                  │
│  - API Server (FastAPI)                              │
│  - WebSocket Server                                    │
│  - Stats Emitter                                      │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Capture Worker (Thread)                    │
│  - Camera capture (30 FPS)                           │
│  - Motion detection (fast)                            │
│  - Write ke shared memory (zero-copy)                  │
│  - TIDAK blocking detection                           │
└────────────┬──────────────────────────────────────────────┘
             │
             │ Frame (30 FPS)
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│              Shared Memory (Zero-Copy)                  │
│  - Frame storage (direct memory access)                │
│  - No disk I/O                                       │
│  - Multiple processes can read simultaneously           │
└────────────┬──────────────────────────────────────────────┘
             │
             │ Read oleh:
             │ 1. Detection Worker (jika ada motion)
             │ 2. API/Web Server (streaming)
             │
      ┌──────┼──────┐
      │      │      │
      ▼      ▼      ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│Detection│ │Tracking │ │  API     │
│Worker  │ │Worker   │ │ Endpoint │
│         │ │         │ │          │
│ - YOLO   │ │ - Track  │ │ - Read   │
│   detect│ │   objects│ │   frame  │
│ - Face  │ │ - Paths  │ │ - Draw   │
│   rec   │ │ - Zones  │ │   overlays│
│         │ │         │ │ - Stream │
│5-10 FPS│ │30 FPS   │ │30 FPS    │
└─────────┘ └─────────┘ └──────────┘
```

---

## 📦 Komponen Baru

### **1. Shared Memory Frame Manager**

**File:** `src/core/frame_manager.py`

**Fitur:**
- Zero-copy frame sharing antar processes
- Thread-safe read/write
- Automatic cleanup of stale frames
- Support untuk multiple cameras

**Key Benefits:**
- ❌ Tidak ada disk I/O (sangat cepat)
- ❌ Tidak ada network I/O (tidak perlu send via socket)
- ✅ Direct memory access (extremely fast)
- ✅ Multiple processes can read simultaneously

**Contoh Penggunaan:**

```python
from src.core.frame_manager import frame_manager
import numpy as np

# Register frame (di initialize)
frame_shape = (720, 1280, 3)  # height, width, channels
frame_manager.register_frame("camera", frame_shape)

# Write frame (di capture worker)
frame = camera.read()  # BGR format
frame_manager.write_frame("camera", frame)

# Read frame (di API/web server)
frame = frame_manager.read_frame("camera")
if frame is not None:
    # Process frame
    processed = process_frame(frame)
```

---

### **2. Enhanced Motion Detector**

**File:** `src/detection/enhanced_motion_detector.py`

**Fitur:**
- Background subtraction (MOG2)
- Morphological operations (noise reduction)
- ROI (Region of Interest) support
- Motion statistics tracking

**Key Benefits:**
- Sangat cepat (< 10ms per frame)
- Filter noise dengan morphological operations
- Return motion boxes untuk YOLO trigger

**Contoh Penggunaan:**

```python
from src.detection.enhanced_motion_detector import EnhancedMotionDetector

# Initialize
motion_detector = EnhancedMotionDetector(
    history=500,           # Frames in history
    var_threshold=16,       # Variance threshold
    detect_shadows=True,     # Detect shadows
    min_motion_area=500      # Minimum area (pixels)
)

# Detect motion
has_motion, motion_boxes, mask = motion_detector.detect(
    frame,
    return_boxes=True,
    return_mask=False
)

if has_motion:
    # Trigger YOLO detection
    detections = yolo_detector.detect(frame)
else:
    # Skip YOLO (save CPU!)
    pass

# Get statistics
stats = motion_detector.get_stats()
print(f"Motion ratio: {stats['motion_ratio']:.1%}")
```

---

### **3. Enhanced Security System V2**

**File:** `src/security_system_v2.py`

**Fitur Utama:**

#### **A. Capture Worker**
- Capture frame di 30 FPS (full speed)
- Motion detection real-time
- Write ke shared memory (zero-copy)
- Send ke detection queue HANYA jika ada motion
- Tidak blocking detection

#### **B. Detection Worker**
- Process frames dari queue (asynchronous)
- YOLO detection HANYA jika ada motion
- Skeleton & face detection
- Send ke tracking queue

#### **C. Tracking Worker**
- Track objects across frames
- Path tracking (history 50 points)
- Zone breach detection
- Trusted face handling

**Contoh Penggunaan:**

```python
import asyncio
from src.security_system_v2 import enhanced_security_system

async def main():
    # Initialize
    await enhanced_security_system.initialize()
    
    # Start system
    enhanced_security_system.start()
    
    # Set mode
    enhanced_security_system.set_mode("armed")
    
    # Get stats
    stats = enhanced_security_system.get_stats()
    print(f"FPS: {stats['fps']:.1f}")
    print(f"Persons detected: {stats['persons_detected']}")
    print(f"Motion ratio: {stats['motion_ratio']:.1%}")
    
    # Get frame with overlays
    draw_options = {
        "bounding_boxes": True,
        "timestamp": True,
        "zones": True,
        "motion_boxes": False,
        "skeletons": True
    }
    
    frame = enhanced_security_system.get_frame_with_overlays("camera", draw_options)
    if frame is not None:
        # Save frame
        cv2.imwrite("output.jpg", frame)
    
    # Stop system
    await asyncio.sleep(60)  # Run for 60 seconds
    await enhanced_security_system.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### **4. MJPEG Streaming Endpoint**

**File:** `src/api/web_server.py` (updated)

**Fitur:**
- Real-time MJPEG streaming
- Configurable overlays (bbox, timestamp, zones, skeletons)
- Adjustable FPS dan resolution
- Automatic fallback ke old system

**API Endpoints:**

#### **GET /api/stream**
Live video streaming dengan MJPEG

**Query Parameters:**
- `bbox` (bool, default: true) - Show bounding boxes
- `timestamp` (bool, default: true) - Show timestamp
- `zones` (bool, default: true) - Show zones
- `skeletons` (bool, default: true) - Show skeletons
- `motion_boxes` (bool, default: false) - Show motion boxes
- `fps` (int, default: 15) - Streaming FPS
- `height` (int, default: 720) - Frame height

**Contoh:**
```html
<img src="/api/stream?bbox=1&timestamp=1&zones=1&fps=15&height=720" />
```

#### **GET /api/frame.jpg**
Latest single frame dengan overlays

**Query Parameters:**
- `bbox` (bool, default: true)
- `timestamp` (bool, default: true)
- `zones` (bool, default: true)
- `skeletons` (bool, default: true)
- `height` (int, default: 720)

**Contoh:**
```javascript
const response = await fetch('/api/frame.jpg?bbox=1&height=720');
const blob = await response.blob();
const img = document.createElement('img');
img.src = URL.createObjectURL(blob);
document.body.appendChild(img);
```

---

## 🚀 Migration Guide

### **Dari Old System ke V2**

#### **Step 1: Update Imports**

**Old:**
```python
from src.security_system import security_system
```

**New:**
```python
from src.security_system_v2 import enhanced_security_system
```

#### **Step 2: Update Initialization**

**Old:**
```python
await security_system.initialize()
security_system.start()
```

**New:**
```python
await enhanced_security_system.initialize()
enhanced_security_system.start()
```

#### **Step 3: Update Frame Access**

**Old:**
```python
# Read from file
frame = cv2.imread("data/shared_frame.jpg")
```

**New:**
```python
# Read from shared memory
from src.core.frame_manager import frame_manager
frame = frame_manager.read_frame("camera")
```

#### **Step 4: Update Streaming**

**Old:**
```javascript
// Polling frame files
setInterval(() => {
    const img = document.getElementById('live-preview');
    img.src = `/api/frame.jpg?timestamp=${Date.now()}`;
}, 100);
```

**New:**
```javascript
// MJPEG streaming
const img = document.getElementById('live-preview');
img.src = '/api/stream?bbox=1&timestamp=1&fps=15&height=720';
```

---

## ⚙️ Konfigurasi

### **Performance Tuning**

#### **1. Motion Detection Sensitivity**

Edit `src/detection/enhanced_motion_detector.py` atau inisialisasi dengan custom params:

```python
motion_detector = EnhancedMotionDetector(
    history=500,           # Higher = more stable background
    var_threshold=16,       # Lower = more sensitive
    detect_shadows=True,     # True = detect shadows as motion
    min_motion_area=500      # Lower = detect smaller motion
)
```

#### **2. Detection Interval**

Edit `src/security_system_v2.py` di `CaptureWorker`:

```python
self.motion_interval = 5  # Detect setiap N frames (default: 5)
```

- `motion_interval = 1` - Detect semua frames (100% CPU, high accuracy)
- `motion_interval = 5` - Detect setiap 5 frame (20% CPU, good accuracy)
- `motion_interval = 10` - Detect setiap 10 frame (10% CPU, lower accuracy)

#### **3. FPS Settings**

Edit `config/config.yaml`:

```yaml
camera:
  fps: 30              # Capture FPS
  detect_fps: 10        # Detection FPS (old system, not used in V2)
```

---

## 📊 Performance Metrics

### **Expected Performance (Single Camera, 1080p):**

| Component | Old System | New System (V2) | Improvement |
|-----------|-------------|------------------|-------------|
| **Capture FPS** | 5-10 FPS | 30 FPS | **3-6x** |
| **Detection FPS** | 5-10 FPS | 5-10 FPS | Same |
| **Streaming FPS** | 5-10 FPS | 30 FPS | **3-6x** |
| **CPU Usage** | 100% | 30-50% | **50-70% less** |
| **Latency** | 1-5 seconds | < 500ms | **2-10x faster** |
| **Memory Usage** | 500 MB | 1 GB | Higher (shared memory) |

### **Multi-Camera Performance:**

| Cameras | Capture FPS | Detection FPS | CPU Usage | GPU Usage |
|---------|-------------|---------------|------------|------------|
| 1x 1080p | 30 FPS | 5-10 FPS | 30-50% | 20-30% |
| 2x 1080p | 60 FPS | 10-20 FPS | 50-70% | 40-50% |
| 4x 720p | 120 FPS | 20-40 FPS | 60-80% | 60-80% |

---

## 🐛 Troubleshooting

### **Problem: FPS rendah (< 15 FPS)**

**Solutions:**
1. Cek motion detector sensitivity:
   ```python
   stats = motion_detector.get_stats()
   print(f"Motion ratio: {stats['motion_ratio']:.1%}")
   ```
   Jika motion ratio tinggi (> 50%), increase `var_threshold` atau `min_motion_area`

2. Increase `motion_interval` untuk mengurangi detection frequency:
   ```python
   capture_worker.motion_interval = 10  # Detect setiap 10 frame
   ```

3. Cek CPU usage:
   ```bash
   htop
   ```
   Jika CPU > 90%, upgrade hardware atau reduce resolution

### **Problem: Motion tidak terdeteksi**

**Solutions:**
1. Lower `var_threshold`:
   ```python
   motion_detector = EnhancedMotionDetector(var_threshold=8)
   ```

2. Lower `min_motion_area`:
   ```python
   motion_detector = EnhancedMotionDetector(min_motion_area=100)
   ```

3. Disable shadow detection:
   ```python
   motion_detector = EnhancedMotionDetector(detect_shadows=False)
   ```

### **Problem: Shared memory error**

**Solution:**
Clean up shared memory:
```bash
# Linux
ipcs -m  # List shared memory segments
ipcrm -M <shmid>  # Remove specific segment

# Atau restart sistem
python -c "from src.core.frame_manager import frame_manager; frame_manager.cleanup_all()"
```

### **Problem: Streaming lambat / buffering**

**Solutions:**
1. Reduce streaming FPS:
   ```html
   <img src="/api/stream?fps=10&height=480" />
   ```

2. Reduce JPEG quality (faster encoding):
   ```python
   # Edit src/api/web_server.py
   jpeg_bytes = encode_frame_to_jpeg(frame, quality=60)
   ```

3. Use wired network (bukan WiFi)

---

## 🔧 Advanced Features

### **Custom ROI (Region of Interest)**

Hanya detect motion di area tertentu:

```python
import cv2
import numpy as np

# Create ROI mask (white = detect, black = ignore)
roi_mask = np.zeros((height, width), dtype=np.uint8)
roi_mask[y1:y2, x1:x2] = 255  # Rectangle area

# Set ROI ke motion detector
motion_detector.set_roi(roi_mask)
```

### **Object Path Tracking**

V2 secara otomatis track path objects:

```python
from src.security_system_v2 import enhanced_security_system

# Get tracked objects
tracked_objects = enhanced_security_system.tracking_worker.get_tracked_objects()

for obj in tracked_objects:
    print(f"Object {obj.id}: {obj.class_name}")
    print(f"Confidence: {obj.confidence:.2f}")
    print(f"Path points: {len(obj.path_data)}")
    
    # Draw path
    for i in range(1, len(obj.path_data)):
        (x1, y1), _ = obj.path_data[i-1]
        (x2, y2), _ = obj.path_data[i]
        cv2.line(frame, (x1, y1), (x2, y2), color, 2)
```

### **Real-time Stats Monitoring**

```python
import json
from pathlib import Path

# Read stats from file
stats_path = Path("data/stats.json")
if stats_path.exists():
    stats = json.loads(stats_path.read_text())
    print(f"FPS: {stats['fps']:.1f}")
    print(f"Persons: {stats['persons_detected']}")
    print(f"Motion ratio: {stats['motion_ratio']:.1%}")
```

---

## 📝 Best Practices

### **1. Use Enhanced System for New Features**

Gunakan `enhanced_security_system` untuk fitur baru:
- MJPEG streaming real-time
- Object path tracking
- Low-latency alerts
- High FPS monitoring

### **2. Keep Old System for Legacy Compatibility**

Old system tetap tersedia sebagai fallback:
- File-based frame sharing (data/shared_frame.jpg)
- Stats file (data/shared_stats.json)
- WebSocket updates

### **3. Monitor Performance Metrics**

Pantau metrics secara berkala:
- FPS (harus ~30 FPS)
- Motion ratio (ideal 10-30%)
- CPU usage (harus < 80%)
- Memory usage (harus < 2 GB)

### **4. Tune untuk Environment**

Adjust settings berdasarkan:
- Camera resolution (higher = more CPU)
- Network bandwidth (affects streaming)
- Hardware specs (CPU/GPU/RAM)
- Environment (indoor vs outdoor)

---

## 🎯 Key Takeaways

### **Performance Improvements:**
1. ✅ **3-6x higher FPS** (30 FPS vs 5-10 FPS)
2. ✅ **50-70% lower CPU** (motion-first detection)
3. ✅ **2-10x lower latency** (< 500ms vs 1-5s)
4. ✅ **Real-time streaming** (MJPEG vs polling)

### **Technical Innovations:**
1. ✅ **Decoupled multi-process** architecture
2. ✅ **Shared memory** zero-copy frame sharing
3. ✅ **Motion-first** detection (skip YOLO jika tidak ada motion)
4. ✅ **Thread-safe** frame access
5. ✅ **Lazy drawing** (on-demand overlays)

### **Feature Retention:**
1. ✅ All existing features preserved
2. ✅ YOLO detection (person)
3. ✅ Skeleton detection
4. ✅ Face recognition
5. ✅ Zone management
6. ✅ Telegram notifications
7. ✅ Alert handling

---

## 📞 Support

Jika mengalami masalah:
1. Cek log files di `logs/`
2. Pastikan shared memory dibersihkan
3. Verify config di `config/config.yaml`
4. Monitor resources dengan `htop` dan `nvidia-smi`

---

**Copyright © 2026 Riftech Security System**
**Version: 2.0.0 - High-Performance Architecture**
