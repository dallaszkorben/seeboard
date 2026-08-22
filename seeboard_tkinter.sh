#!/bin/bash
# Start seeBoard: activate hotspot, then launch the app

# export DISPLAY=:0

# Activate GREEN-BEAN WiFi AP
sudo nmcli connection up Hotspot

# Activate virtual environment and run
source ~/Projects/seeboard/venv/bin/activate
cd ~/Projects/seeboard
python app/seeboard.py
