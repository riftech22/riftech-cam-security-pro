#!/bin/bash
# Quick fix for git conflict and run diagnostic

echo "=== STEP 1: Discard local config changes ==="
git checkout src/core/config.py

echo ""
echo "=== STEP 2: Pull latest from GitHub ==="
git pull origin main

echo ""
echo "=== STEP 3: Run diagnostic script ==="
python3 fix_overlay_writer.py

echo ""
echo "=== DONE ==="
