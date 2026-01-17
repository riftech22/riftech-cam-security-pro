# Riftech Security System

Professional AI-powered security camera system with advanced object detection, face recognition, and zone monitoring capabilities.

## Features

### Core Capabilities
- **AI-Powered Person Detection**: YOLOv8-based real-time person detection
- **Skeleton Tracking**: 33-point pose estimation using MediaPipe
- **Face Recognition**: Trusted person identification using face_recognition library
- **Motion Detection**: Advanced background subtraction with heatmap generation
- **Security Zones**: Polygon-based intrusion detection zones
- **Smart Alerts**: Intelligent alert system with configurable triggers
- **Telegram Notifications**: Real-time alerts to your phone with photos

### System Modes
- **Normal Mode**: Monitoring without intrusion alerts
- **Armed Mode**: Full security with breach detection
- **Alerted Mode**: Active alert state with enhanced monitoring

### Technical Features
- Modular, clean architecture
- Async database operations with SQLite
- Professional logging system
- Configurable settings via YAML
- RTSP and USB camera support
- FFmpeg pipeline for stable RTSP streaming
- Threaded processing for optimal performance

## System Topology

![Riftech Security System Topology](readme_assets/cyber-topology.svg)

## Penjelasan Alur Kerja

### 🔹 Step 1-5: Backend Processing (AI Detection)
```
Camera → FFmpeg → AI Detection → Database → Notifications
   ↓          ↓           ↓            ↓            ↓
 Ambil     Process    Deteksi       Simpan       Kirim
 Video     Stream     Objek/Wajah   Data         Alert
```

**Apa yang terjadi:**
1. **Kamera** mengambil video stream (RTSP/USB/V380)
2. **FFmpeg** mengubah stream menjadi frame-by-frame
3. **AI Detection** memproses setiap frame:
   - YOLO: Deteksi person
   - Face Recognition: Identifikasi wajah terpercaya
   - Motion Detection: Deteksi gerakan
4. **Database**: Menyimpan semua data (alerts, logs, stats)
5. **Notifications**: Kirim alert ke Telegram jika ada security breach

### 🔹 Step 6: Web Server (FastAPI)
```
AI Detection + Database ──→ Web Server (Port 8000)
                          ↓
                    FastAPI Backend
                     • JWT Auth
                     • REST API
                     • WebSocket
                     • Video Stream
```

**Apa yang Web Server lakukan:**
- Menyediakan API endpoints untuk frontend
- Menghandle authentication (JWT tokens)
- Mengirim data real-time via WebSocket
- Streaming video ke frontend
- Menajemen konfigurasi, zones, faces

### 🔹 Step 7: Frontend (Cyber Neon Dashboard)
```
Web Server ──→ Frontend (Web Interface)
                 ↓
          Cyber Neon Theme Dashboard
           • Login Page (Matrix effect)
           • Live Video Feed
           • AI Detection Stats
           • Zone Editor
           • Face Management
           • Alert History
```

**Apa yang Frontend tampilkan:**
- Video live dengan AI overlay
- Statistik real-time (persons, breaches, etc.)
- Editor untuk membuat security zones
- Manajemen wajah terpercaya
- History alerts dengan gambar
- Konfigurasi sistem

### 🔹 Step 8: Mobile Access (Cloudflared Tunnel)
```
Web Server ──→ Cloudflared Tunnel ──→ Global HTTPS Access
                          ↓
                    https://domain-anda.com
```

**Apa yang Cloudflared lakukan:**
- Membuat secure tunnel ke internet
- Memberikan HTTPS/SSL otomatis
- Tidak perlu port forwarding
- Bisa diakses dari mana saja di dunia
- Mobile friendly

## Architecture Overview

- **Cameras**: RTSP, USB, atau V380 split cameras mengambil video
- **FFmpeg**: Memproses dan streaming video frame
- **AI Detection**: YOLO, Face Recognition, Motion Detection
- **Database**: SQLite menyimpan semua data dan konfigurasi
- **Notifications**: Telegram alerts untuk security events
- **Web Server**: FastAPI backend dengan JWT auth dan WebSocket
- **Frontend**: Cyber Neon themed web dashboard
- **Mobile Access**: Cloudflared tunnel untuk global HTTPS access

## Installation

### Quick Installation (Interactive)

Run the installation script - it will guide you through setup:

```bash
chmod +x install.sh start.sh install_service.sh
./install.sh
```

The interactive installer will ask for:
1. **Camera Configuration**
   - Camera type (RTSP, USB, or V380 Split)
   - RTSP URL or Camera ID
   - Resolution and FPS settings
   
2. **Telegram Notification Setup** (Optional)
   - Enable/disable Telegram notifications
   - Bot Token from @BotFather
   - Chat ID from @userinfobot
   
3. **Detection Settings**
   - YOLO confidence threshold
   - Face recognition tolerance
   - Default system mode

### Manual Configuration

If you prefer to configure manually or need to change settings later:

1. **Edit config.yaml:**
```bash
nano config/config.yaml
```

2. **Common Settings:**

**For RTSP Camera:**
```yaml
camera:
  type: rtsp
  rtsp_url: "rtsp://admin:password@192.168.1.100:554/stream1"
  width: 1280
  height: 720
  fps: 15
```

**For USB Camera:**
```yaml
camera:
  type: usb
  camera_id: 0
  width: 1280
  height: 720
  fps: 15
```

**For V380 Split Camera:**
```yaml
camera:
  type: v380_split
  rtsp_url: "rtsp://admin:password@192.168.1.108:554/live"
  width: 1280
  height: 720
  fps: 15
  detect_fps: 5
```

**For Telegram Notifications:**
```yaml
alerts:
  telegram_enabled: true
  telegram_bot_token: "YOUR_BOT_TOKEN"
  telegram_chat_id: "YOUR_CHAT_ID"
```

3. **Get Telegram Bot Token:**
   - Open Telegram and search for @BotFather
   - Send `/newbot` command
   - Follow instructions to create a bot
   - Copy the bot token

4. **Get Telegram Chat ID:**
   - Open Telegram and search for @userinfobot
   - Send `/start` command
   - Copy your Chat ID

### Prerequisites

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg libsm6 libxext6 libxrender-dev libgl1-mesa-glx
```

**System Dependencies:**
```bash
sudo apt install -y cmake gfortran libopenblas-dev liblapack-dev libx11-dev
```

### Setup Instructions

1. **Clone the repository:**
```bash
git clone <repository-url>
cd riftech-cam-security-pro
```

2. **Run interactive installation:**
```bash
chmod +x install.sh
./install.sh
```

The installer will:
- Install all system and Python dependencies
- Create virtual environment
- Guide you through camera configuration
- Help set up Telegram notifications (optional)
- Configure detection parameters
- Download YOLO model automatically

3. **Add trusted faces (optional):**
```bash
mkdir -p data/trusted_faces
# Copy face images (jpg format) to data/trusted_faces/
# Filename will be used as person name
```

4. **Start the system:**
```bash
./start.sh
```

**Note:** After installation, you can edit `config/config.yaml` manually if needed.

## Configuration

Edit `config/config.yaml` to customize the system:

```yaml
camera:
  type: rtsp  # 'rtsp', 'usb', or 'v380_split'
  rtsp_url: "rtsp://username:password@ip:port/stream"
  camera_id: 0
  width: 1280
  height: 720
  fps: 15
  
  # V380 split camera settings (for type: v380_split)
  split_enabled: false
  detect_fps: 5

detection:
  yolo_confidence: 0.20
  yolo_model: "yolov8n.pt"
  face_tolerance: 0.6
  
paths:
  base_dir: "."
  recordings_dir: "recordings"
  alerts_dir: "alerts"
  snapshots_dir: "snapshots"
  logs_dir: "logs"
  trusted_faces_dir: "trusted_faces"

database:
  path: "security_system.db"

logging:
  level: INFO
  console_enabled: true
  file_enabled: true
```

## Usage

### Quick Start

```bash
./start.sh
```

### Manual Start

```bash
source venv/bin/activate
python3 main.py
```

### System Controls

**Modes:**
- `normal`: Monitoring without breach alerts
- `armed`: Full security with zone breach detection
- `alerted`: Active alert state

**Default Mode:** The system starts in "normal" mode. Change mode via configuration or API (when web interface is available).

### Creating Security Zones

1. Start the system
2. Click on the video feed to draw zone points
3. Complete the zone (3+ points)
4. Set system mode to "armed" to enable breach detection

### Managing Trusted Faces

1. Place face images in `trusted_faces/` directory
2. Use person's name as filename (e.g., `john_doe.jpg`)
3. Restart the system to reload faces

## Architecture

```
riftech-cam-security-pro/
├── src/
│   ├── core/
│   │   ├── config.py          # Configuration management (YAML-based)
│   │   └── logger.py          # Professional logging system
│   ├── database/
│   │   └── models.py          # Async database operations
│   ├── detection/
│   │   ├── base.py            # Base detection classes & utilities
│   │   ├── yolo_detector.py   # YOLOv8 person detection
│   │   ├── skeleton_detector.py # 33-point pose estimation
│   │   ├── face_detector.py   # Face recognition
│   │   └── motion_detector.py # Advanced motion detection
│   ├── camera/
│   │   └── capture.py         # RTSP (FFmpeg) & USB camera
│   ├── utils/
│   │   └── zone_manager.py    # Polygon security zones
│   └── security_system.py     # Main system orchestrator
├── config/
│   ├── config.yaml             # Main configuration
│   └── config.yaml.example    # Configuration template
├── web/
│   └── index.html             # Web interface
├── data/
│   ├── recordings/             # Video recordings
│   ├── alerts/                # Alert images
│   ├── snapshots/             # Manual snapshots
│   ├── logs/                  # System logs
│   ├── trusted_faces/         # Trusted person faces
│   └── fixed_images/         # Fixed face images
├── main.py                    # Application entry point
├── install.sh                 # Installation script
├── start.sh                   # Quick start script
├── install_service.sh         # Systemd service installer
├── riftech-security.service    # Systemd service file
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## System Requirements

### Hardware
- CPU: Quad-core or better (recommended)
- RAM: 8GB minimum, 16GB recommended
- Storage: 20GB+ for recordings and alerts
- Camera: RTSP-capable IP camera or USB webcam

### Software
- Python 3.8+
- FFmpeg (for RTSP streaming)
- CUDA-capable GPU (optional, for faster detection)

### Tested On
- Ubuntu 20.04, 22.04
- Debian 11, 12
- Raspberry Pi OS (with limitations)

## Performance Optimization

### For Better Performance:
1. **Reduce detection resolution**: Set camera resolution to 640x480 in config/config.yaml
2. **Lower FPS**: Set `fps: 10` in config/config.yaml
3. **Use smaller YOLO model**: Change to `yolov8n.pt` (nano)
4. **Disable skeleton detection**: Set `skeleton_enabled: false` in config
5. **Reduce thread count**: Set `thread_count: 2` in config

### V380 Split Camera Configuration

V380 cameras that send 2 views (top/bottom) in a single frame require special configuration:

```yaml
camera:
  type: v380_split
  rtsp_url: "rtsp://admin:password@192.168.1.108:554/live"
  width: 1280
  height: 720
  fps: 15
  split_enabled: true
  detect_fps: 5  # Target FPS for detection processing
```

**How it works:**
- The camera sends a single frame containing 2 views (top and bottom)
- System automatically splits the frame into 2 separate views
- Each view is processed independently by AI detection
- Results are combined and displayed with clear labels:
  - **TOP CAMERA (Fixed)** - Fixed position camera view
  - **BOTTOM CAMERA (PTZ)** - Pan-Tilt-Zoom camera view

**Benefits:**
- AI processes each camera view separately (no confusion)
- Person counts are tracked per camera
- Zone breaches are detected per camera view
- Skeleton and face recognition work on each view independently

**Performance tips for V380:**
- Set `detect_fps: 5` for lower CPU usage
- Use `yolov8n.pt` (nano model) for faster processing
- Disable skeleton detection if not needed

### GPU Acceleration:
```bash
# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# YOLO will automatically use GPU if available
```

## Updating the Application

### Automatic Update Script

Use the built-in update script to get the latest version:

```bash
./update.sh
```

The update script will:
1. Check for available updates
2. Backup your current configuration, database, and trusted faces
3. Download and apply latest changes
4. Update dependencies if needed
5. Restart the service (if running)
6. Show you what's new in the update

### What Gets Backed Up

The update script automatically backs up:
- **Configuration** (`config/config.yaml`) → `config/config.yaml.backup.YYYYMMDD_HHMMSS`
- **Database** (`data/security_system.db`) → `data/security_system.db.backup.YYYYMMDD_HHMMSS`
- **Trusted Faces** (`data/trusted_faces/`) → `data/trusted_faces.backup.YYYYMMDD_HHMMSS.tar.gz`

### Restoring from Backup

If something goes wrong after an update, you can restore:

```bash
# Restore configuration
cp config/config.yaml.backup.YYYYMMDD_HHMMSS config/config.yaml

# Restore database
cp data/security_system.db.backup.YYYYMMDD_HHMMSS data/security_system.db

# Restore trusted faces
tar -xzf data/trusted_faces.backup.YYYYMMDD_HHMMSS.tar.gz
```

### Manual Update

If you prefer to update manually:

```bash
# Backup your data
cp config/config.yaml config/config.yaml.backup
cp data/security_system.db data/security_system.db.backup

# Pull latest changes
git pull origin main

# Update dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Restart if using service
sudo systemctl restart riftech-security
```

## Telegram Notifications

### Setup

Enable Telegram notifications to receive alerts on your phone:

1. **Create Telegram Bot:**
   - Open Telegram and search for @BotFather
   - Send `/newbot` command
   - Follow instructions to create a bot
   - Copy the bot token (format: `1234567890:ABCdefGHI...`)

2. **Get Your Chat ID:**
   - Open Telegram and search for @userinfobot
   - Send `/start` command
   - Copy your Chat ID (a number)

3. **Configure in config.yaml:**
```yaml
alerts:
  telegram_enabled: true
  telegram_bot_token: "YOUR_BOT_TOKEN"
  telegram_chat_id: "YOUR_CHAT_ID"
```

4. **Test Notifications:**
```bash
# Run this command to test
source venv/bin/activate
python3 -c "
import asyncio
from src.security_system import security_system
asyncio.run(security_system.test_telegram())
"
```

### Alert Types

The system sends Telegram notifications for:

🚨 **Zone Breach Alert**
- Triggered when someone enters a protected zone
- Includes photo of the breach
- Shows breached zone numbers
- Sent only when system is in "armed" mode

👥 **Person Detection Alert**
- Triggered when persons are detected
- Shows total, trusted, and unknown count
- Optional photo attachment
- Configurable threshold

✅ **Trusted Face Alert**
- Triggered when trusted face is recognized
- Shows person's name
- Useful for access monitoring

⚠️ **System Alert**
- Camera connection issues
- System errors
- Important system events

### Alert Message Format

Alerts are formatted with emojis and structured information:

```
🚨 ZONE BREACH DETECTED!

Breached Zones: 1, 2
System Mode: ARMED
Time: 2024-01-18 12:00:00

[Attached photo]
```

### Troubleshooting Telegram

**Not Receiving Alerts:**
- Verify `telegram_enabled: true` in config.yaml
- Check bot token is correct (no extra spaces)
- Verify chat ID is correct
- Start a chat with your bot (send /start)
- Check system logs in `data/logs/`

**Token Errors:**
- Ensure bot token format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
- Get new token from @BotFather if needed
- Check for typos in token

**Chat ID Errors:**
- Use @userinfobot to get correct Chat ID
- Group chats need Chat ID with prefix `-100`
- Private chats use Chat ID as plain number

**Photo Not Attached:**
- Check `alerts/` directory has write permissions
- Verify alert photo path exists
- Ensure enough disk space
- Check Telegram bot has permission to send photos

## Telegram Bot Commands

Once Telegram is enabled and configured, you can send commands directly to your bot to control the security system from anywhere!

### Getting Started

1. **Start** bot:
   - Open Telegram and search for your bot
   - Send `/start` command
   - You should see a welcome message with **menu buttons**

2. **Use menu buttons:**
   - Simply tap the buttons below - no need to type commands!
   - The menu always stays visible for easy access

3. **Type commands (optional):**
   - You can also type commands manually (e.g., `/status`)
   - Use `/help` to see all available commands

### Menu Buttons

The bot provides **interactive menu buttons** that appear below every message. Simply tap the button to execute the command - no typing required!

#### Main Menu

```
┌─────────────┬─────────────┐
│  📊 Status  │  📈 Stats   │
├─────────────┼─────────────┤
│  🎮 Mode    │  📸 Screenshot│
├─────────────┼─────────────┤
│  📍 Zones   │  ⚙️ Config   │
├─────────────┴─────────────┤
│  ❓ Help    │  🧪 Test    │
└──────────────────────────┘
```

- **📊 Status** - Get current system status
- **📈 Stats** - Get detailed statistics
- **🎮 Mode** - Change system mode (opens submenu)
- **📸 Screenshot** - Send current camera frame
- **📍 Zones** - List all security zones
- **⚙️ Config** - Show current configuration
- **❓ Help** - Show help and command list
- **🧪 Test** - Send test message

#### Mode Selection Menu

```
┌─────────────┬─────────────┐
│  ✅ Normal  │  🔵 Armed   │
├─────────────┼─────────────┤
│  🔴 Alerted │  ⬅️ Back    │
└─────────────┴─────────────┘
```

This menu appears when you tap **🎮 Mode**. Select a mode and it will be applied immediately.

- **✅ Normal** - Monitoring without alerts
- **🔵 Armed** - Full security with breach alerts
- **🔴 Alerted** - Active alert state
- **⬅️ Back** - Return to main menu

### Available Commands

#### 📊 **Status & Information**

**`/status`** or tap **📊 Status**
- Get current system status
- Shows: Running state, Mode, FPS, Statistics
- Example output:
  ```
  📊 System Status
  
  🔵 Running: ✅ Yes
  🎮 Mode: ARMED
  📹 FPS: 15.2
  
  👥 Statistics:
    • Persons detected: 5
    • Breaches: 2
    • Trusted faces: 3
    • Alerts: 2
    • Uptime: 3600s
  ```

**`/stats`** or tap **📈 Stats**
- Get detailed statistics
- Shows: Detection counts, Performance metrics
- Example output:
  ```
  📈 Detailed Statistics
  
  👥 Detection:
    • Persons detected: 5
    • Alerts triggered: 2
    • Breaches detected: 2
    • Trusted faces seen: 3
  
  ⏱️ Performance:
    • Uptime: 3600s (60.0min)
    • FPS: 15.2
  ```

**`/config`** or tap **⚙️ Config**
- Show current configuration
- Displays camera, detection, and alert settings
- Example output:
  ```
  ⚙️ Current Configuration
  
  📹 Camera:
    • Type: rtsp
    • Resolution: 1280x720
    • FPS: 15
    • URL: rtsp://192.168.1.100:554/stream
  
  🎯 Detection:
    • YOLO model: yolov8n.pt
    • Confidence: 0.20
    • Face tolerance: 0.6
  
  🔔 Alerts:
    • Telegram: ✅
    • Breach mode: armed
  ```

#### 🎮 **System Control**

**`/mode [normal|armed|alerted]`** or tap **🎮 Mode**
- Change system mode
- Tap **🎮 Mode** button → Select from submenu
- Or type: `/mode armed`
- Example output:
  ```
  📍 Current mode: ARMED
  
  📝 Available modes:
    • normal - Monitoring without alerts
    • armed - Full security with breach alerts
    • alerted - Active alert state
  
  📝 Select a mode below:
  
  [Mode menu appears]
  ```

**`/screenshot`** or tap **📸 Screenshot**
- Send current camera frame as photo
- Captures current frame from camera
- Saves to `snapshots/` directory
- Example output:
  ```
  📸 Screenshot
  ⏰ 2024-01-18 12:00:00
  
  [Attached photo]
  ```

#### 📍 **Zones**

**`/zones`** or tap **📍 Zones**
- List all security zones
- Shows zone IDs, point counts, and armed status
- Example output:
  ```
  📍 Security Zones
  
  🔷 Zone 1
     Points: 4
     Armed: ✅
  
  🔷 Zone 2
     Points: 6
     Armed: ✅
  ```

#### 🧪 **Testing**

**`/test`** or tap **🧪 Test**
- Send a test message
- Verifies bot is working
- Useful for checking connectivity
- Example output:
  ```
  ✅ Test Message
  
  🤖 Riftech Security Bot is working!
  ⏰ 2024-01-18 12:00:00
  ```

#### 📖 **Help**

**`/help`** or tap **❓ Help**
- Show all available commands
- Displays command list with descriptions
- Example output:
  ```
  📖 Available Commands
  
  📊 Status & Info
  /status or 📊 Status - Get system status
  /stats or 📈 Stats - Get statistics
  /config or ⚙️ Config - Show current config
  
  🎮 System Control
  /mode or 🎮 Mode - Change system mode
  /screenshot or 📸 Screenshot - Send current frame
  
  📍 Zones
  /zones or 📍 Zones - List security zones
  
  🧪 Testing
  /test or 🧪 Test - Send test message
  
  📖 /help or ❓ Help - Show this help message
  ```

**`/status`**
- Get current system status
- Shows: Running state, Mode, FPS, Statistics
- Example output:
  ```
  📊 System Status
  
  🔵 Running: ✅ Yes
  🎮 Mode: ARMED
  📹 FPS: 15.2
  
  👥 Statistics:
    • Persons detected: 5
    • Breaches: 2
    • Trusted faces: 3
    • Alerts: 2
    • Uptime: 3600s
  ```

**`/stats`**
- Get detailed statistics
- Shows: Detection counts, Performance metrics
- Example output:
  ```
  📈 Detailed Statistics
  
  👥 Detection:
    • Persons detected: 5
    • Alerts triggered: 2
    • Breaches detected: 2
    • Trusted faces seen: 3
  
  ⏱️ Performance:
    • Uptime: 3600s (60.0min)
    • FPS: 15.2
  ```

**`/config`**
- Show current configuration
- Displays camera, detection, and alert settings
- Example output:
  ```
  ⚙️ Current Configuration
  
  📹 Camera:
    • Type: rtsp
    • Resolution: 1280x720
    • FPS: 15
    • URL: rtsp://192.168.1.100:554/stream
  
  🎯 Detection:
    • YOLO model: yolov8n.pt
    • Confidence: 0.20
    • Face tolerance: 0.6
  
  🔔 Alerts:
    • Telegram: ✅
    • Breach mode: armed
  ```

#### 🎮 **System Control**

**`/mode [normal|armed|alerted]`**
- Change system mode
- Without arguments: Show current mode and available modes
- With argument: Change to specified mode
- Examples:
  ```
  /mode              # Shows current mode
  /mode armed        # Change to armed mode
  /mode normal       # Change to normal mode
  /mode alerted      # Change to alerted mode
  ```
- Example output:
  ```
  📍 Current mode: ARMED
  
  📝 Available modes:
    • normal - Monitoring without alerts
    • armed - Full security with breach alerts
    • alerted - Active alert state
  
  📝 Usage: /mode [normal|armed|alerted]
  ```

**`/screenshot`**
- Send current camera frame as photo
- Captures the current frame from the camera
- Saves to `snapshots/` directory
- Example output:
  ```
  📸 Screenshot
  ⏰ 2024-01-18 12:00:00
  
  [Attached photo]
  ```

#### 📍 **Zones**

**`/zones`**
- List all security zones
- Shows zone IDs, point counts, and armed status
- Example output:
  ```
  📍 Security Zones
  
  🔷 Zone 1
     Points: 4
     Armed: ✅
  
  🔷 Zone 2
     Points: 6
     Armed: ✅
  ```

#### 🧪 **Testing**

**`/test`**
- Send a test message
- Verifies bot is working
- Useful for checking connectivity
- Example output:
  ```
  ✅ Test Message
  
  🤖 Riftech Security Bot is working!
  ⏰ 2024-01-18 12:00:00
  ```

#### 📖 **Help**

**`/help`**
- Show all available commands
- Displays command list with descriptions
- Example output:
  ```
  📖 Available Commands
  
  📊 Status & Info
  /status - Get system status
  /stats - Get statistics
  /config - Show current config
  
  🎮 System Control
  /mode [normal|armed|alerted] - Change system mode
  /screenshot - Send current frame
  
  📍 Zones
  /zones - List security zones
  
  🧪 Testing
  /test - Send test message
  
  📖 /help - Show this help message
  ```

### Usage Examples with Menu Buttons

**Daily Monitoring:**
```
1. Tap 📊 Status   # Check if system is running
2. Tap 📸 Screenshot  # See what's happening now
3. Tap 📈 Stats    # Check today's statistics
```

**Security Control:**
```
1. Tap 🎮 Mode     # Open mode selection
2. Tap 🔵 Armed    # Arm the system when leaving
3. Tap 📊 Status   # Confirm system is armed

When returning:
1. Tap 🎮 Mode     # Open mode selection
2. Tap ✅ Normal   # Disarm when returning home
```

**Checking Zones:**
```
1. Tap 📍 Zones    # List all security zones
2. Tap 📸 Screenshot  # View current frame
```

**Troubleshooting:**
```
1. Tap 🧪 Test     # Verify bot is working
2. Tap 📊 Status   # Check system state
3. Tap ⚙️ Config   # Verify configuration
```

**Using Commands (Alternative):**
You can also type commands instead of using buttons:
```
/status          # Same as tapping 📊 Status
/screenshot      # Same as tapping 📸 Screenshot
/mode armed      # Same as tapping 🎮 Mode → 🔵 Armed
```

### Authorization

Only users with the correct Chat ID (configured in `config.yaml`) can use commands. If someone tries to use the bot who isn't authorized, they'll see:
```
⛔ You are not authorized to use this bot.
```

### Tips

1. **Use menu buttons** - Tap buttons instead of typing commands for faster access
2. **Use `/mode` frequently** - Switch between `normal` and `armed` as needed
3. **Check `/status` regularly** - Monitor system health and performance
4. **Use `/screenshot`** - Get visual confirmation of what's camera sees
5. **Combine with alerts** - Get automatic alerts AND check on-demand status
6. **Test connectivity** - Use 🧪 Test if you're not receiving alerts
7. **Menu always visible** - Menu buttons stay below every message for easy access
8. **Both ways work** - You can tap buttons OR type commands, both work!

### Common Workflows

**Morning Routine:**
```
/status         # Check if system ran overnight
/stats          # Review night statistics
/mode normal    # Disarm for daily activity
/screenshot     # Quick check of premises
```

**Leaving Home:**
```
/zones          # Confirm zones are set
/mode armed     # Arm the system
/status         # Confirm armed state
```

**Suspicious Activity:**
```
/screenshot     # See what's happening
/status         # Check current alerts
/stats          # Review recent activity
/mode alerted    # Put system on high alert
```

### Troubleshooting Commands

**Commands not responding:**
- Check if system is running
- Verify bot is started (send `/start`)
- Check system logs in `data/logs/`
- Verify Telegram is enabled in config

**Unauthorized access message:**
- Check your Chat ID in config.yaml
- Use @userinfobot to get correct Chat ID
- Restart system after changing config

**Screenshot fails:**
- Check if camera is running
- Verify `snapshots/` directory has write permissions
- Check for sufficient disk space

### Disabling Telegram

To disable Telegram notifications:

```yaml
alerts:
  telegram_enabled: false
```

Or run the interactive installer again and choose not to enable Telegram.

## Troubleshooting

### Camera Not Connecting
- Check RTSP URL format: `rtsp://username:password@ip:port/stream`
- Verify network connectivity
- Ensure camera credentials are correct
- Try using TCP transport (default in FFmpeg command)

### Detection Not Working
- Verify YOLO model downloaded: Check for `yolov8n.pt` in project root
- Lower confidence threshold in config/config.yaml: `yolo_confidence: 0.10`
- Check camera resolution (too low/high may affect detection)
- Verify camera type is correct: `type: rtsp` or `type: usb`
- Check RTSP URL format: `rtsp://username:password@ip:port/stream`

### Face Recognition Issues
- Ensure face images are in `data/trusted_faces/` or `data/fixed_images/`
- Use clear, front-facing photos (minimum 200x200 pixels)
- Adjust face tolerance in config/config.yaml: 0.4 (stricter) to 0.8 (looser)
- Add multiple images per person for better recognition
- Images should be in JPG format with person's name as filename

### High CPU Usage
- Reduce FPS in configuration
- Use smaller YOLO model
- Disable motion detection if not needed
- Reduce skeleton detection frequency

### System Crashes
- Check logs in `logs/` directory
- Verify all dependencies installed correctly
- Ensure sufficient disk space for recordings
- Check camera is properly disconnected on exit

## API Reference (Coming Soon)

A REST API will be available for:
- System status monitoring
- Mode switching
- Zone management
- Alert retrieval
- Statistics access

## Web Interface (Coming Soon)

A professional web dashboard will provide:
- Live video feed with overlays
- Zone editor
- Alert history
- System statistics
- Trusted face management
- Real-time notifications

## Service Installation

Install as systemd service for automatic startup:

```bash
sudo ./install_service.sh
```

Then manage with:
```bash
sudo systemctl start riftech-security    # Start service
sudo systemctl stop riftech-security     # Stop service
sudo systemctl restart riftech-security  # Restart service
sudo systemctl enable riftech-security   # Enable on boot
sudo systemctl disable riftech-security  # Disable on boot
sudo systemctl status riftech-security   # Check status
sudo journalctl -u riftech-security -f  # View logs
```

## Web Interface

A web interface is available at `web/index.html`. It provides:
- System status display
- Mode switching (Normal, Armed, Alerted)
- Real-time statistics
- Recent alerts
- Live video feed (when API is connected)

To use the web interface, open `web/index.html` in a web browser. Note that full functionality requires the REST API to be enabled.

## Version 2.0.0 (Pro) - What's New

### Architecture Improvements
- Complete modular architecture rewrite
- YAML-based configuration system
- Async database operations with aiosqlite
- Professional logging with rotation
- Type hints throughout codebase

### Performance Enhancements
- Threaded processing for better CPU utilization
- Optimized FFmpeg pipeline for RTSP
- Configurable thread count
- GPU auto-detection and utilization

### Stability Improvements
- Comprehensive error handling
- Graceful shutdown on signals
- Automatic recovery from camera failures
- Alert cooldown system

### New Features
- 33-point skeleton tracking
- Advanced motion detection with heatmaps
- Polygon-based security zones
- Trusted face management
- System mode switching (Normal/Armed/Alerted)
- Web interface with real-time stats
- **V380 split camera support** - Process dual-view cameras separately

## License

This project is proprietary software. All rights reserved.

## Support

For issues and questions:
- Email: support@riftech.com
- Documentation: [Link to documentation]
- Issues: [Link to issue tracker]

## Changelog

### Version 2.0.0 (Pro)
- Complete rewrite with modular architecture
- Async database operations
- Improved performance
- Better error handling
- Professional logging system
- Enhanced configuration management

### Version 1.0.0
- Initial release
- Basic person detection
- Simple alert system
- Web interface

## Acknowledgments

- YOLOv8 by Ultralytics
- MediaPipe by Google
- OpenCV
- face_recognition library
