#!/bin/bash
# Riftech Security System - Installation Script
# This script automates installation process with interactive configuration

set -e

echo "============================================================"
echo "  Riftech Security System - Installation"
echo "============================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}Note: Running without sudo. Some commands may fail.${NC}"
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VERSION=$VERSION_ID
    echo -e "${GREEN}Detected OS: $OS $VERSION${NC}"
else
    echo -e "${RED}Cannot detect OS. Exiting.${NC}"
    exit 1
fi

echo ""
echo "Step 1: Installing system dependencies..."
echo "------------------------------------------------------------"

if command -v apt-get &> /dev/null; then
    echo "Using apt-get package manager..."
    sudo apt-get update
    sudo apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        ffmpeg \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgl1-mesa-glx \
        cmake \
        gfortran \
        libopenblas-dev \
        liblapack-dev \
        libx11-dev \
        git \
        wget \
        curl
elif command -v yum &> /dev/null; then
    echo "Using yum package manager..."
    sudo yum install -y \
        python3 \
        python3-pip \
        ffmpeg \
        cmake \
        gcc-gfortran \
        openblas-devel \
        lapack-devel \
        libX11-devel \
        git
    sudo yum groupinstall -y "Development Tools"
else
    echo -e "${RED}Unsupported package manager. Please install dependencies manually.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ System dependencies installed${NC}"
echo ""

echo "Step 2: Creating virtual environment..."
echo "------------------------------------------------------------"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
fi

echo ""
echo "Step 3: Activating virtual environment..."
echo "------------------------------------------------------------"

source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

echo ""
echo "Step 4: Upgrading pip..."
echo "------------------------------------------------------------"

pip install --upgrade pip setuptools wheel
echo -e "${GREEN}✓ pip upgraded${NC}"

echo ""
echo "Step 5: Installing Python dependencies..."
echo "------------------------------------------------------------"

pip install -r requirements.txt
echo -e "${GREEN}✓ Python dependencies installed${NC}"

echo ""
echo "Step 6: Creating directories..."
echo "------------------------------------------------------------"

mkdir -p data/recordings
mkdir -p data/alerts
mkdir -p data/snapshots
mkdir -p data/logs
mkdir -p data/trusted_faces
mkdir -p data/fixed_images
mkdir -p logs
echo -e "${GREEN}✓ Directories created${NC}"

echo ""
echo "Step 7: Configuration Setup"
echo "------------------------------------------------------------"

# Check if config already exists
if [ -f "config/config.yaml" ]; then
    echo -e "${YELLOW}Configuration file already exists${NC}"
    read -p "Do you want to reconfigure? (y/N): " reconfigure
    if [[ ! $reconfigure =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Skipping configuration${NC}"
    else
        rm config/config.yaml
        CONFIG_NEEDED=true
    fi
else
    CONFIG_NEEDED=true
fi

if [ "$CONFIG_NEEDED" = true ]; then
    echo ""
    echo "=========================================="
    echo -e "${BLUE}  Camera Configuration${NC}"
    echo "=========================================="
    
    # Camera type selection
    echo ""
    echo "Select camera type:"
    echo "  1) RTSP IP Camera"
    echo "  2) USB Camera"
    echo "  3) V380 Split Camera (Dual-view)"
    read -p "Enter choice [1-3]: " camera_choice
    
    case $camera_choice in
        1)
            CAMERA_TYPE="rtsp"
            echo ""
            echo -e "${BLUE}RTSP Camera Configuration${NC}"
            echo "Format: rtsp://username:password@ip:port/stream"
            read -p "Enter RTSP URL: " rtsp_url
            read -p "Enter width [1280]: " width
            read -p "Enter height [720]: " height
            read -p "Enter FPS [15]: " fps
            read -p "Enter detection FPS [5]: " detect_fps
            width=${width:-1280}
            height=${height:-720}
            fps=${fps:-15}
            detect_fps=${detect_fps:-5}
            ;;
        2)
            CAMERA_TYPE="usb"
            echo ""
            echo -e "${BLUE}USB Camera Configuration${NC}"
            read -p "Enter USB Camera ID [0]: " camera_id
            read -p "Enter width [1280]: " width
            read -p "Enter height [720]: " height
            read -p "Enter FPS [15]: " fps
            read -p "Enter detection FPS [5]: " detect_fps
            camera_id=${camera_id:-0}
            width=${width:-1280}
            height=${height:-720}
            fps=${fps:-15}
            detect_fps=${detect_fps:-5}
            rtsp_url="rtsp://admin:password@192.168.1.100:554/stream1"
            ;;
        3)
            CAMERA_TYPE="v380_split"
            echo ""
            echo -e "${BLUE}V380 Split Camera Configuration${NC}"
            echo "Format: rtsp://username:password@ip:port/stream"
            read -p "Enter RTSP URL: " rtsp_url
            read -p "Enter width [1280]: " width
            read -p "Enter height [720]: " height
            read -p "Enter FPS [15]: " fps
            read -p "Enter detection FPS [5]: " detect_fps
            width=${width:-1280}
            height=${height:-720}
            fps=${fps:-15}
            detect_fps=${detect_fps:-5}
            ;;
        *)
            echo -e "${RED}Invalid choice. Using default RTSP configuration.${NC}"
            CAMERA_TYPE="rtsp"
            rtsp_url="rtsp://admin:password@192.168.1.100:554/stream1"
            width=1280
            height=720
            fps=15
            detect_fps=5
            ;;
    esac
    
    echo ""
    echo "=========================================="
    echo -e "${BLUE}  Telegram Notification Setup${NC}"
    echo "=========================================="
    
    read -p "Enable Telegram notifications? (y/N): " enable_telegram
    
    if [[ $enable_telegram =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${BLUE}Get your Telegram Bot Token:${NC}"
        echo "1. Open Telegram and search for @BotFather"
        echo "2. Send /newbot command"
        echo "3. Follow the instructions to create a bot"
        echo "4. Copy the bot token (looks like: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)"
        echo ""
        read -p "Enter Telegram Bot Token: " bot_token
        
        echo ""
        echo -e "${BLUE}Get your Chat ID:${NC}"
        echo "1. Open Telegram and search for @userinfobot"
        echo "2. Send /start command"
        echo "3. Copy your Chat ID (a number)"
        echo ""
        read -p "Enter Telegram Chat ID: " chat_id
        
        TELEGRAM_ENABLED="true"
    else
        echo -e "${YELLOW}Telegram notifications disabled${NC}"
        TELEGRAM_ENABLED="false"
        bot_token="YOUR_BOT_TOKEN_HERE"
        chat_id="YOUR_CHAT_ID_HERE"
    fi
    
    echo ""
    echo "=========================================="
    echo -e "${BLUE}  Detection Settings${NC}"
    echo "=========================================="
    
    read -p "YOLO confidence threshold [0.20]: " yolo_conf
    read -p "Face tolerance [0.6]: " face_tolerance
    read -p "Default mode [normal]: " default_mode
    
    yolo_conf=${yolo_conf:-0.20}
    face_tolerance=${face_tolerance:-0.6}
    default_mode=${default_mode:-normal}
    
    # Create config file
    echo ""
    echo "Creating config/config.yaml..."
    
    cat > config/config.yaml << EOF
# Riftech Security System Configuration
# Automatically generated by install.sh

camera:
  # Camera type: $CAMERA_TYPE
  type: $CAMERA_TYPE
  
  # RTSP Settings
  rtsp_url: "$rtsp_url"
  
  # USB Camera Settings
  camera_id: $camera_id
  
  # Camera resolution and framerate
  width: $width
  height: $height
  fps: $fps
  
  # Detection FPS
  detect_fps: $detect_fps

detection:
  # YOLO person detection
  yolo_confidence: $yolo_conf
  yolo_model: "yolov8n.pt"
  
  # Face recognition
  face_tolerance: $face_tolerance
  
  # Motion detection
  motion_threshold: 15
  motion_min_area: 500
  
  # Skeleton detection
  skeleton_enabled: true

paths:
  # Base directory for all data
  base_dir: "data"
  
  # Data directories
  recordings_dir: "data/recordings"
  alerts_dir: "data/alerts"
  snapshots_dir: "data/snapshots"
  logs_dir: "data/logs"
  trusted_faces_dir: "data/trusted_faces"
  fixed_images_dir: "data/fixed_images"

database:
  # SQLite database path
  path: "data/security_system.db"
  
  # Automatic cleanup
  cleanup_days: 30

logging:
  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  level: INFO
  
  # Log format
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
  # Output settings
  console_enabled: true
  file_enabled: true
  
  # File rotation
  max_file_size: 10485760
  backup_count: 5

alerts:
  # Alert behavior
  cooldown_seconds: 5
  snapshot_on_alert: true
  recording_duration: 30
  
  # Telegram notifications
  telegram_enabled: $TELEGRAM_ENABLED
  telegram_bot_token: "$bot_token"
  telegram_chat_id: "$chat_id"

system:
  # Startup mode
  default_mode: $default_mode
  
  # Performance settings
  enable_gpu: true
  thread_count: 4
EOF
    
    echo -e "${GREEN}✓ Configuration file created${NC}"
    echo ""
    echo -e "${BLUE}Configuration Summary:${NC}"
    echo "  Camera Type: $CAMERA_TYPE"
    if [ "$CAMERA_TYPE" = "rtsp" ] || [ "$CAMERA_TYPE" = "v380_split" ]; then
        echo "  RTSP URL: $rtsp_url"
    fi
    if [ "$CAMERA_TYPE" = "usb" ]; then
        echo "  Camera ID: $camera_id"
    fi
    echo "  Resolution: ${width}x${height} @ ${fps} FPS"
    echo "  Detection FPS: ${detect_fps}"
    echo "  Telegram: $TELEGRAM_ENABLED"
    echo "  Default Mode: $default_mode"
fi

echo ""
echo "Step 8: Downloading YOLO model..."
echo "------------------------------------------------------------"

if [ ! -f "yolov8n.pt" ]; then
    echo "Downloading YOLOv8n model (may take a few minutes)..."
    python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
    echo -e "${GREEN}✓ YOLO model downloaded${NC}"
else
    echo -e "${YELLOW}YOLO model already exists${NC}"
fi

echo ""
echo "Step 9: Setting permissions..."
echo "------------------------------------------------------------"

chmod +x start.sh
chmod +x start-web.sh
chmod +x install.sh
chmod +x update.sh
echo -e "${GREEN}✓ Permissions set${NC}"

echo ""
echo "============================================================"
echo -e "${GREEN}Installation completed successfully!${NC}"
echo "============================================================"
echo ""
echo "What would you like to do next?"
echo ""
echo "1. Start Security System + Web Server (Recommended)"
echo "2. Start Security System Only"
echo "3. Start Web Server Only"
echo ""
read -p "Enter choice [1-3]: " start_choice

case $start_choice in
    1)
        echo ""
        echo "Starting Security System + Web Server..."
        echo "  - Security System: http://localhost:5000"
        echo "  - Web Interface: http://localhost:8000"
        echo ""
        # Start both services
        ./start.sh &
        sleep 3
        ./start-web.sh
        ;;
    2)
        echo ""
        echo "Starting Security System..."
        echo "  - System: http://localhost:5000"
        echo ""
        ./start.sh
        ;;
    3)
        echo ""
        echo "Starting Web Server..."
        echo "  - Web Interface: http://localhost:8000"
        echo ""
        ./start-web.sh
        ;;
    *)
        echo ""
        echo "Manual start:"
        echo "  Security System: ./start.sh"
        echo "  Web Server: ./start-web.sh"
        echo ""
        ;;
esac

echo ""
echo "For detailed instructions, see:"
echo "  - README.md (Main documentation)"
echo "  - WEB_SERVER_README.md (Web interface guide)"
echo "  - CLOUDFLARED_SETUP.md (Mobile access setup)"
echo ""
