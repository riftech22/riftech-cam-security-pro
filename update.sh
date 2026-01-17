#!/bin/bash
# Riftech Security System - Update Script
# This script updates application to newest version

set -e

echo "============================================================"
echo "  Riftech Security System - Update"
echo "============================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if git repository
if [ ! -d ".git" ]; then
    echo -e "${RED}Error: Not a git repository. Cannot update.${NC}"
    echo "Please clone repository first using:"
    echo "  git clone <repository-url> riftech-cam-security-pro"
    exit 1
fi

# Check if there are uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}Warning: You have uncommitted changes.${NC}"
    read -p "Do you want to stash changes? (y/N): " stash_changes
    
    if [[ $stash_changes =~ ^[Yy]$ ]]; then
        echo "Stashing changes..."
        git stash push -m "Update backup $(date)"
        echo -e "${GREEN}✓ Changes stashed${NC}"
    else
        echo -e "${RED}Cannot update with uncommitted changes. Exiting.${NC}"
        exit 1
    fi
fi

echo ""
echo "Step 1: Checking for updates..."
echo "------------------------------------------------------------"

# Fetch latest changes
git fetch origin > /dev/null 2>&1

# Check if updates are available
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master 2>/dev/null)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo -e "${GREEN}Already up to date!${NC}"
    echo "Current version: $(git log -1 --pretty=format:"%h - %s" HEAD)"
    exit 0
fi

echo -e "${BLUE}Updates available!${NC}"
echo ""
echo "Current version:"
git log -1 --pretty=format:"  %h - %s (%ad)" HEAD --date=short
echo ""
echo "Latest version:"
git log -1 --pretty=format:"  %h - %s (%ad)" origin/main --date=short 2>/dev/null || \
git log -1 --pretty=format:"  %h - %s (%ad)" origin/master --date=short
echo ""

read -p "Continue with update? (y/N): " continue_update
if [[ ! $continue_update =~ ^[Yy]$ ]]; then
    echo "Update cancelled."
    exit 0
fi

echo ""
echo "Step 2: Backing up configuration..."
echo "------------------------------------------------------------"

# Backup config file
if [ -f "config/config.yaml" ]; then
    BACKUP_FILE="config/config.yaml.backup.$(date +%Y%m%d_%H%M%S)"
    cp config/config.yaml "$BACKUP_FILE"
    echo -e "${GREEN}✓ Configuration backed up to: $BACKUP_FILE${NC}"
else
    echo -e "${YELLOW}No config.yaml found (will use default)${NC}"
fi

# Backup database
if [ -f "data/security_system.db" ]; then
    DB_BACKUP="data/security_system.db.backup.$(date +%Y%m%d_%H%M%S)"
    cp data/security_system.db "$DB_BACKUP"
    echo -e "${GREEN}✓ Database backed up to: $DB_BACKUP${NC}"
fi

# Backup trusted faces
if [ -d "data/trusted_faces" ]; then
    FACES_BACKUP="data/trusted_faces.backup.$(date +%Y%m%d_%H%M%S).tar.gz"
    tar -czf "$FACES_BACKUP" data/trusted_faces/
    echo -e "${GREEN}✓ Trusted faces backed up to: $FACES_BACKUP${NC}"
fi

# Backup web server config
if [ -f "src/api/web_server.py" ]; then
    WEB_BACKUP="src/api/web_server.py.backup.$(date +%Y%m%d_%H%M%S)"
    cp src/api/web_server.py "$WEB_BACKUP"
    echo -e "${GREEN}✓ Web server config backed up to: $WEB_BACKUP${NC}"
fi

echo ""
echo "Step 3: Updating application..."
echo "------------------------------------------------------------"

# Pull latest changes
echo "Downloading latest changes..."
git pull origin main 2>/dev/null || git pull origin master 2>/dev/null
echo -e "${GREEN}✓ Code updated${NC}"

echo ""
echo "Step 4: Checking for new dependencies..."
echo "------------------------------------------------------------"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
else
    echo -e "${YELLOW}Warning: Virtual environment not found${NC}"
    echo "Please run install.sh first"
    exit 1
fi

# Upgrade pip
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
echo -e "${GREEN}✓ pip upgraded${NC}"

# Check if requirements.txt changed
if git diff --name-only HEAD@{1} HEAD | grep -q "requirements.txt"; then
    echo "requirements.txt has changed, updating dependencies..."
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Dependencies updated${NC}"
else
    echo "No dependency updates required"
fi

echo ""
echo "Step 5: Checking for configuration changes..."
echo "------------------------------------------------------------"

# Check if config structure changed
if git diff --name-only HEAD@{1} HEAD | grep -q "config/config.yaml.example"; then
    echo ""
    echo -e "${YELLOW}Configuration structure has changed!${NC}"
    echo "New settings may be available."
    echo ""
    read -p "Do you want to review the new configuration? (y/N): " review_config
    
    if [[ $review_config =~ ^[Yy]$ ]]; then
        echo ""
        echo "New configuration example:"
        echo "------------------------------------------------------------"
        cat config/config.yaml.example
        echo "------------------------------------------------------------"
        echo ""
        echo "Your current configuration is preserved."
        echo "Edit config/config.yaml if you want to add new settings."
    fi
else
    echo "No configuration changes required"
fi

# Check if web server changed
if git diff --name-only HEAD@{1} HEAD | grep -q "src/api/web_server.py"; then
    echo -e "${YELLOW}Web server code has been updated${NC}"
    echo "Note: You may need to update admin credentials in src/api/web_server.py"
fi

echo ""
echo "Step 6: Restarting services (if running)..."
echo "------------------------------------------------------------"

# Check if security system service is running
if systemctl is-active --quiet riftech-security 2>/dev/null; then
    echo "Restarting security system service..."
    sudo systemctl restart riftech-security
    echo -e "${GREEN}✓ Security system service restarted${NC}"
else
    echo "Security system service not running"
fi

# Check if web server service is running
if systemctl is-active --quiet riftech-web-server 2>/dev/null; then
    echo "Restarting web server service..."
    sudo systemctl restart riftech-web-server
    echo -e "${GREEN}✓ Web server service restarted${NC}"
else
    echo "Web server service not running"
fi

# Wait a bit and check services
if systemctl is-active --quiet riftech-security 2>/dev/null || systemctl is-active --quiet riftech-web-server 2>/dev/null; then
    echo ""
    sleep 2
    
    if systemctl is-active --quiet riftech-security; then
        echo -e "${GREEN}✓ Security system service is running${NC}"
    else
        echo -e "${RED}✗ Security system service failed to start${NC}"
        echo "Check logs with: sudo journalctl -u riftech-security -f"
    fi
    
    if systemctl is-active --quiet riftech-web-server; then
        echo -e "${GREEN}✓ Web server service is running${NC}"
    else
        echo -e "${RED}✗ Web server service failed to start${NC}"
        echo "Check logs with: sudo journalctl -u riftech-web-server -f"
    fi
fi

echo ""
echo "Step 7: Setting permissions..."
echo "------------------------------------------------------------"

chmod +x start.sh start-web.sh install.sh update.sh 2>/dev/null
echo -e "${GREEN}✓ Script permissions updated${NC}"

echo ""
echo "============================================================"
echo -e "${GREEN}Update completed successfully!${NC}"
echo "============================================================"
echo ""
echo "What's new in this update:"
git log HEAD@{1}..HEAD --pretty=format:"  • %s"
echo ""
echo "Backups created:"
if [ -f "$BACKUP_FILE" ]; then
    echo "  Config: $BACKUP_FILE"
fi
if [ -f "$DB_BACKUP" ]; then
    echo "  Database: $DB_BACKUP"
fi
if [ -f "$FACES_BACKUP" ]; then
    echo "  Trusted faces: $FACES_BACKUP"
fi
if [ -f "$WEB_BACKUP" ]; then
    echo "  Web server: $WEB_BACKUP"
fi
echo ""
echo "Next steps:"
echo "1. Review config/config.yaml if configuration changed"
echo "2. Review src/api/web_server.py if web server changed"
echo "3. Update admin credentials if needed"
echo "4. Review backup files if needed"
echo "5. Restart the system if not using systemd service"
echo ""
echo "Manual restart:"
echo "  Security System: ./start.sh"
echo "  Web Server: ./start-web.sh"
echo ""
echo "To restore from backup (if needed):"
echo "  cp config/config.yaml.backup.YYYYMMDD_HHMMSS config/config.yaml"
echo "  cp data/security_system.db.backup.YYYYMMDD_HHMMSS data/security_system.db"
echo "  cp src/api/web_server.py.backup.YYYYMMDD_HHMMSS src/api/web_server.py"
echo ""
