#!/bin/bash

# test_map_qgraphicsview.sh - Launch QGraphicsView map viewer
# 
# Smart launcher that detects display and runs with proper environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[INFO] seeBoard Map Viewer (QGraphicsView)"
echo "[INFO] ══════════════════════════════════════════════════"
echo ""

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    DEVICE=$(cat /proc/device-tree/model 2>/dev/null || echo "Raspberry Pi")
    echo "[INFO] Device: $DEVICE"
else
    DEVICE="Unknown"
fi

echo ""

# Run with display
if [ -n "$DISPLAY" ]; then
    echo "[INFO] Display detected: $DISPLAY"
    echo "[INFO] Qt plugins: $QT_QPA_PLATFORM_PLUGIN_PATH"
    echo "[INFO] Launching application..."
    echo ""
    
    python3 test_map_qgraphicsview.py
else
    echo "[WARNING] No DISPLAY environment variable set"
    echo "[INFO] Set DISPLAY before running:"
    echo ""
    echo "  export DISPLAY=:0"
    echo "  bash $(basename "$0")"
    echo ""
    echo "Or run on Raspberry Pi with:"
    echo ""
    echo "  DISPLAY=:0 bash $(basename "$0")"
    echo ""
fi
