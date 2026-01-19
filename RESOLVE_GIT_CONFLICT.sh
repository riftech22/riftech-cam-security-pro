#!/bin/bash
# Script to resolve git conflict and get latest changes

echo "=== GIT CONFLICT RESOLUTION ==="
echo ""
echo "Checking local changes in src/core/config.py..."

# Check what changes exist
git diff src/core/config.py

echo ""
echo "=== OPTIONS ==="
echo ""
echo "[OPTION 1] Commit your local changes first (recommended if you made important config changes)"
echo "  git add src/core/config.py"
echo "  git commit -m 'Update config for server'"
echo "  git pull origin main"
echo ""
echo "[OPTION 2] Stash changes temporarily (if you want to keep them but pull first)"
echo "  git stash"
echo "  git pull origin main"
echo "  git stash pop"
echo ""
echo "[OPTION 3] Discard local changes (use GitHub version)"
echo "  git restore src/core.config.py"
echo "  git pull origin main"
echo ""

# Ask user which option
read -p "Choose option (1/2/3): " choice

case $choice in
    1)
        echo ""
        echo "Committing local changes..."
        git add src/core/config.py
        git commit -m "Update config for server"
        echo "Pulling latest changes from GitHub..."
        git pull origin main
        echo "✅ Done! Changes committed and merged."
        ;;
    2)
        echo ""
        echo "Stashing local changes..."
        git stash
        echo "Pulling latest changes from GitHub..."
        git pull origin main
        echo "Restoring your changes..."
        git stash pop
        echo "✅ Done! Your changes restored after pull."
        ;;
    3)
        echo ""
        echo "Discarding local changes..."
        git restore src/core/config.py
        echo "Pulling latest changes from GitHub..."
        git pull origin main
        echo "✅ Done! Using GitHub version of config.py"
        ;;
    *)
        echo "Invalid option. Please run script again and choose 1, 2, or 3."
        exit 1
        ;;
esac

echo ""
echo "=== RUNNING FIX SCRIPT ==="
echo ""
python3 fix_overlay_writer.py
