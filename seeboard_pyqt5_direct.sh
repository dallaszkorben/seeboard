#!/bin/bash
# seeBoard PyQt5 - Simple GUI Application Launcher

cd ~/Projects/seeboard

# Activate virtual environment
source venv/bin/activate

# Make system packages available to venv
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH

# Use X11 display (desktop environment)
export DISPLAY=:0
export PYTHONUNBUFFERED=1

# Run the app
python3 app/seeboard_pyqt5_direct.py
