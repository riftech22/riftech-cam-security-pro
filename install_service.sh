#!/bin/bash
# Install Riftech Security System as systemd service

set -e

echo "============================================================"
echo "  Riftech Security System - Service Installation"
echo "============================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Get the current username
USERNAME=${SUDO_USER:-$(whoami)}
USERHOME=$(eval echo ~$USERNAME)

echo "Installing service for user: $USERNAME"
echo "Home directory: $USERHOME"
echo ""

# Get installation directory
INSTALL_DIR=$(pwd)
echo "Installation directory: $INSTALL_DIR"
echo ""

# Confirm installation
read -p "Continue with installation? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled"
    exit 1
fi

# Copy service file
echo "Copying service file..."
sed "s|/home/riftech/project/riftech-cam-security-pro|$INSTALL_DIR|g" riftech-security.service > /tmp/riftech-security.service
sed -i "s|User=pi|User=$USERNAME|g" /tmp/riftech-security.service
sed -i "s|Group=pi|Group=$USERNAME|g" /tmp/riftech-security.service
cp /tmp/riftech-security.service /etc/systemd/system/
echo -e "\033[0;32m✓ Service file copied\033[0m"

# Set permissions
echo "Setting permissions..."
chmod 644 /etc/systemd/system/riftech-security.service
echo -e "\033[0;32m✓ Permissions set\033[0m"

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload
echo -e "\033[0;32m✓ Systemd reloaded\033[0m"

echo ""
echo "============================================================"
echo "Installation complete!"
echo "============================================================"
echo ""
echo "Service commands:"
echo "  Start service:   sudo systemctl start riftech-security"
echo "  Stop service:    sudo systemctl stop riftech-security"
echo "  Restart service:  sudo systemctl restart riftech-security"
echo "  Enable on boot:  sudo systemctl enable riftech-security"
echo "  Disable on boot: sudo systemctl disable riftech-security"
echo "  View status:     sudo systemctl status riftech-security"
echo "  View logs:       sudo journalctl -u riftech-security -f"
echo ""
