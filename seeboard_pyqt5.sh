#!/bin/bash
# seeBoard PyQt5 - GUI Application Launcher

cd /home/pi/Projects/seeboard || exit 1

# Activate virtual environment
source venv/bin/activate

# Add system packages to Python path to access system-installed PyQt5
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/lib/python3.11/dist-packages:$PYTHONPATH"

# Use framebuffer display (Raspberry Pi touchscreen)
export DISPLAY=:0
export PYTHONUNBUFFERED=1

# Run the application
python3 app/seeboard_pyqt5.py
