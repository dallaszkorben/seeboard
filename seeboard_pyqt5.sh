#!/bin/bash
# seeBoard PyQt5 - GUI Application Launcher

#cd /home/pi/Projects/seeboard || exit 1

# Activate virtual environment
source venv/bin/activate

# Add system packages to Python path to access system-installed PyQt5
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/lib/python3.11/dist-packages:$PYTHONPATH"
export PYTHONUNBUFFERED=1

# Set display - try common options
export DISPLAY=${DISPLAY:-:0}
export QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/python3/dist-packages/PyQt5/plugins/platforms

# Run the application directly (no sudo needed for linuxfb)
python3 app/seeboard_pyqt5.py
