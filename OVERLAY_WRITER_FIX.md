# Fix Error "Overlay Writer Unable to Read Frame"

## Status
✅ Script diagnostic sudah di-push ke GitHub  
📦 Commit: `4c64473`  
🔗 Repo: https://github.com/riftech22/riftech-cam-security-pro

## Informasi Sistem
- **Server Ubuntu**: 10.26.27.104
- **Kamera V380**: 10.26.27.196:554
- **Error**: Overlay writer gagal membaca frame (FPS: 0.0)

## Langkah-langkah Perbaikan di Server Ubuntu

### 1. SSH ke Server Ubuntu

```bash
ssh user@10.26.27.104
cd /path/to/riftech-cam-security-pro
```

### 2. Pull Update dari GitHub

```bash
git pull origin main
```

### 3. Jalankan Script Diagnostic

```bash
python3 fix_overlay_writer.py
```

Script ini akan melakukan 6 pengecekan:
1. ✅ FFmpeg installation
2. ✅ Python dependencies  
3. ✅ Shared memory limits
4. ✅ Camera connectivity (network)
5. ✅ FFmpeg RTSP capture test
6. ✅ System logs untuk error

### 4. Pilih Solusi Berdasarkan Hasil Diagnostic

#### Opsi 1: Restart Service (Coba ini dulu)

```bash
sudo systemctl stop riftech-security-v2
sudo systemctl start riftech-security-v2
journalctl -u riftech-security-v2 -f
```

Lihat apakah error masih muncul.

#### Opsi 2: Clear Shared Memory

Jika service restart tidak membantu, coba clear shared memory:

```bash
sudo rm -f /dev/shm/riftech_*
sudo systemctl restart riftech-security-v2
journalctl -u riftech-security-v2 -f
```

#### Opsi 3: Increase Shared Memory Size

Jika shared memory penuh:

```bash
sudo mount -o remount,size=2G /dev/shm
sudo systemctl restart riftech-security-v2
```

#### Opsi 4: Test Kamera Langsung dengan FFmpeg

Untuk memastikan kamera bisa diakses:

```bash
ffmpeg -rtsp_transport tcp -i rtsp://admin:Kuncong203@10.26.27.196:554/live/ch00_0 -vf fps=5 -f null -
```

Jika ini berhasil, berarti kamera OK, masalah di aplikasi.

#### Opsi 5: Cek Resolusi Stream Kamera

```bash
ffmpeg -rtsp_transport tcp -i rtsp://admin:Kuncong203@10.26.27.196:554/live/ch00_0 -v info -f null - 2>&1 | grep 'Stream'
```

Pastikan resolusi kamera sesuai dengan config (1280x720).

#### Opsi 6: Install Missing Dependencies

Jika diagnostic menunjukkan missing packages:

```bash
sudo apt update
sudo apt install -y ffmpeg python3-pip
pip install -r requirements.txt
```

#### Opsi 7: Reinstall FFmpeg (Jika corrupt)

```bash
sudo apt remove --purge ffmpeg
sudo apt autoremove
sudo apt install -y ffmpeg
```

### 5. Monitoring Setelah Perbaikan

Setelah menerapkan fix, monitor log:

```bash
journalctl -u riftech-security-v2 -f
```

Cari tanda-tanda perbaikan:
- ✅ FPS > 0 (misal: FPS: 5.0 atau FPS: 15.0)
- ✅ Tidak ada "Overlay writer unable to read frame"
- ✅ Camera capture started
- ✅ Ring buffers created

## Common Issues & Solutions

### Issue 1: "Connection refused"
**Cause**: Kamera offline atau salah password  
**Fix**: Cek kamera V380, pastikan online dan password benar

### Issue 2: "Shared memory not available"
**Cause**: /dev/shm penuh atau permission issue  
**Fix**: 
```bash
sudo rm -f /dev/shm/riftech_*
sudo mount -o remount,size=2G /dev/shm
```

### Issue 3: "Frame shape mismatch"
**Cause**: Resolusi kamera tidak sesuai config  
**Fix**: Cek resolusi kamera dengan ffmpeg, update config.yaml

### Issue 4: "FFmpeg not found"
**Cause**: FFmpeg belum terinstall  
**Fix**: `sudo apt install ffmpeg`

### Issue 5: FPS tetap 0
**Cause**: Capture worker crash  
**Fix**: Cek log lengkap: `journalctl -u riftech-security-v2 -n 100`

## Verifikasi Berhasil

Setelah perbaikan, buka web interface di browser:
```
http://10.26.27.104:8080
```

Check:
- ✅ Video stream tampil
- ✅ FPS > 0 di status
- ✅ Detection bekerja (bounding boxes muncul)
- ✅ Tidak ada error di log

## Jika Masih Gagal

Jalankan script diagnostic lengkap:

```bash
python3 diagnose_camera.py
```

Kirim hasil output diagnostic untuk analisis lebih lanjut.

## Contact

Untuk bantuan lebih lanjut, kirim:
1. Hasil `python3 fix_overlay_writer.py`
2. Log lengkap: `journalctl -u riftech-security-v2 -n 200 > debug.log`
3. FFmpeg test output
