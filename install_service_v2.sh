#!/bin/bash
# Install Riftech Security System V2 as systemd service

set -e

echo "============================================================"
echo "  Riftech Security System V2 - Service Installation"
echo "  High-Performance Architecture"
echo "============================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Get current username
USERNAME=${SUDO_USER:-$(whoami)}
USERHOME=$(eval echo ~$USERNAME)

echo "Installing services for user: $USERNAME"
echo "Home directory: $USERHOME"
echo ""

# Get installation directory
INSTALL_DIR=$(pwd)
echo "Installation directory: $INSTALL_DIR"
echo ""

# Check if virtual environment exists
if [ ! -d "$INSTALL_DIR/venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run install.sh first."
    exit 1
fi

# Confirm installation
read -p "Continue with installation? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled"
    exit 1
fi

echo ""
echo "============================================================"
echo "  Installing Riftech Security System V2 Service"
echo "============================================================"
echo ""

# Copy security system V2 service file
echo "Copying riftech-security-v2.service..."
sed "s|/root/riftech-cam-security-pro|$INSTALL_DIR|g" riftech-security-v2.service > /tmp/riftech-security-v2.service
sed -i "s|User=root|User=$USERNAME|g" /tmp/riftech-security-v2.service
sed -i "s|Group=root|Group=$USERNAME|g" /tmp/riftech-security-v2.service
sed -i "s|$USERHOME/venv|$INSTALL_DIR/venv|g" /tmp/riftech-security-v2.service
cp /tmp/riftech-security-v2.service /etc/systemd/system/
chmod 644 /etc/systemd/system/riftech-security-v2.service
echo -e "\033[0;32m✓ Security system V2 service installed\033[0m"

echo ""
echo "============================================================"
echo "  Installing Riftech Web Server Service"
echo "============================================================"
echo ""

# Copy web server service file
echo "Copying riftech-web-server.service..."
sed "s|/root/riftech-cam-security-pro|$INSTALL_DIR|g" riftech-web-server.service > /tmp/riftech-web-server.service
sed -i "s|User=root|User=$USERNAME|g" /tmp/riftech-web-server.service
sed -i "s|Group=root|Group=$USERNAME|g" /tmp/riftech-web-server.service
sed -i "s|$USERHOME/venv|$INSTALL_DIR/venv|g" /tmp/riftech-web-server.service
cp /tmp/riftech-web-server.service /etc/systemd/system/
chmod 644 /etc/systemd/system/riftech-web-server.service
echo -e "\033[0;32m✓ Web server service installed\033[0m"

echo ""
echo "============================================================"
echo "  Configuring Auto-Start on Boot"
echo "============================================================"
echo ""

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload
echo -e "\033[0;32m✓ Systemd reloaded\033[0m"

# Enable services for auto-start on boot
echo ""
echo "Enabling services to start on boot..."
systemctl enable riftech-security-v2.service
echo -e "\033[0;32m✓ Security system V2 enabled for auto-start\033[0m"

systemctl enable riftech-web-server.service
echo -e "\033[0;32m✓ Web server enabled for auto-start\033[0m"

echo ""
echo "============================================================"
echo "  Starting Services"
echo "============================================================"
echo ""

# Start services
echo "Starting services..."
systemctl start riftech-security-v2.service
echo -e "\033[0;32m✓ Security system V2 started\033[0m"

sleep 2
systemctl start riftech-web-server.service
echo -e "\033[0;32m✓ Web server started\033[0m"

echo ""
echo "============================================================"
echo "  Installation Complete!"
echo "============================================================"
echo ""
echo "Services are now running and will auto-start on boot!"
echo ""
echo "🚀 System V2 Features:"
echo "   • 30 FPS Capture (3-6x faster)"
echo "   • 50-70% lower CPU usage"
echo "   • < 500ms latency (2-10x faster)"
echo "   • MJPEG streaming (real-time)"
echo "   • Motion-first detection"
echo "   • Shared memory (zero-copy)"
echo "   • Object path tracking"
echo ""
echo "Web Interface:"
echo "  Local:  http://localhost:8000"
echo "  Remote: http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Live Stream (MJPEG):"
echo "  http://$(hostname -I | awk '{print $1}'):8000/api/stream"
echo ""
echo "Service commands:"
echo ""
echo "  Security System V2:"
echo "    Start:   sudo systemctl start riftech-security-v2"
echo "    Stop:    sudo systemctl stop riftech-security-v2"
echo "    Restart: sudo systemctl restart riftech-security-v2"
echo "    Status:  sudo systemctl status riftech-security-v2"
echo "    Logs:    sudo journalctl -u riftech-security-v2 -f"
echo ""
echo "  Web Server:"
echo "    Start:   sudo systemctl start riftech-web-server"
echo "    Stop:    sudo systemctl stop riftech-web-server"
echo "    Restart: sudo systemctl restart riftech-web-server"
echo "    Status:  sudo systemctl status riftech-web-server"
echo "    Logs:    sudo journalctl -u riftech-web-server -f"
echo ""
echo "  Auto-Start on Boot:"
echo "    Enable:  sudo systemctl enable riftech-security-v2"
echo "    Disable: sudo systemctl disable riftech-security-v2"
echo ""
echo "Note: Old system (riftech-security) is still available as fallback."
echo "To use old system:"
echo "  sudo systemctl disable riftech-security-v2"
echo "  sudo systemctl enable riftech-security"
echo "  sudo systemctl start riftech-security"
echo ""
