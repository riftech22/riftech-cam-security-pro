# Streaming Solution - Root Cause & Fix

## 🔍 Root Cause Analysis

### **Architecture Issue:**

```
Camera RTSP
    ↓
FFmpeg (fps=5) → Limited ke 5 FPS
    ↓
Capture Worker (fps=5)
    ↓
Shared Memory (updates 5 FPS)
    ↓
Streaming Endpoint (reads from shared memory)
    ↓
Browser (stuck because frame only updates 5 FPS)
```

### **Why Frigate Works:**

Frigate menggunakan **separate streams**:
```
Camera RTSP
    ↓
┌─────────────────┬─────────────────┐
↓                 ↓
Preview Stream    Detection Stream
- FFmpeg fps=30   - FFmpeg fps=5
- Direct to UI     - For AI only
- No bottleneck    - Separate pipeline
```

---

## 💡 Current System Limitation

System saat ini **tidak punya separate streams**:
- Single capture worker mengisi shared memory
- Semua (detection, streaming, recording) baca dari shared memory yang sama
- FPS terbatas oleh capture worker (fps=5 dari config)

---

## ✅ Working Solution (Realistic)

### **Option 1: Increase Capture FPS (Quick Fix)**

**Keuntungan:**
- Mudah diimplementasi
- Coba increase FPS dari 5 ke 15
- Streaming akan lebih smooth

**Kerugian:**
- Detection akan lebih sering (lebih berat)
- Memory/CPU usage akan naik

**Implementation:**
1. Increase `detect_fps` di config ke 15
2. Update FFmpeg untuk fps=15
3. Restart service

---

### **Option 2: Separate Preview Stream (Proper Solution)**

**Keuntungan:**
- Preview stream high FPS (30)
- Detection stream low FPS (5)
- Sesuai arsitektur Frigate

**Kerugian:**
- Perlu refactoring besar
- Perlu separate FFmpeg processes
- Perlu update banyak kode

**Implementation Steps:**
1. Buat `PreviewStream` class (sudah ada di src/camera/preview_stream.py)
2. Update `CaptureWorker` untuk jalan tanpa FPS limit
3. Update web server untuk streaming dari `PreviewStream`
4. Update detection untuk menggunakan low-FPS stream

**Estimated Time:** 2-3 hours refactoring

---

## 🎯 Recommended Action

### **For Now (Quick Fix): Increase FPS to 15**

```bash
# Update config
nano config/config.yaml

# Change:
detect_fps: 5 → detect_fps: 15

# Save: Ctrl+O, Enter, Ctrl+X

# Restart
sudo systemctl restart riftech-security-v2

# Monitor
sudo journalctl -u riftech-security-v2 -f | grep "FPS:"
```

Expected FPS: **10-15** (2-3x better dari 4.8)

---

### **For Future (Proper Fix): Implement Separate Streams**

Buat separate FFmpeg processes:
1. **Preview Stream:** FFmpeg fps=30 → Web UI
2. **Detection Stream:** FFmpeg fps=5 → AI Processing
3. **Recording Stream:** FFmpeg fps=15 → Storage

Ini butuh:
- Refactoring `CaptureWorker` class
- Update `web_server.py` `/api/stream` endpoint
- Update `security_system_v2.py` architecture
- Testing dan debugging

---

## 📊 Performance Comparison

### **Current (fps=5):**
- Preview: 4.8 FPS (macet)
- Detection: 4.8 FPS
- CPU: 18%
- Memory: 808MB

### **After Increase FPS to 15:**
- Preview: 10-15 FPS (lebih smooth)
- Detection: 10-15 FPS (lebih berat)
- CPU: 25-35%
- Memory: 900MB-1GB

### **After Separate Streams (Frigate-style):**
- Preview: 25-30 FPS (sangat smooth) ⭐
- Detection: 5 FPS (optimal untuk AI)
- CPU: 20-25%
- Memory: 900MB-1GB

---

## 🔧 Troubleshooting Current Issue

### **Check Why Stream Stuck:**

```bash
# 1. Check FFmpeg process
ps aux | grep ffmpeg

# 2. Check actual FFmpeg FPS
# Look for ffmpeg output in logs
sudo journalctl -u riftech-security-v2 -f | grep ffmpeg

# 3. Check frame updates
# Frame should update at configured FPS
```

### **Possible Issues:**

1. **Network Latency** - RTSP connection slow
2. **Camera Capability** - Camera hanya support 5 FPS
3. **FFmpeg Buffer** - Buffering issue
4. **Shared Memory** - Frame tidak terupdate cepat

---

## 💡 Next Steps

1. **Immediate:** Increase detect_fps to 15
2. **Test:** Cek apakah stream lebih smooth
3. **Monitor:** Cek CPU/Memory usage
4. **Decide:** Lanjut ke separate streams atau cukup dengan FPS 15

---

## 📝 Conclusion

Masalah stream macet bukan karena FFmpeg parameter, tapi karena:
1. **Architecture limitation** - single stream untuk semua
2. **FPS bottleneck** - terbatas di detect_fps=5
3. **Shared memory** - frame hanya update 5 FPS

**Solusi cepat:** Increase detect_fps ke 15
**Solusi proper:** Implement separate streams (Frigate-style)
