# seeBoard PyQt5 Installation Guide

This document covers the installation and setup steps for deploying the seeBoard PyQt5 application on a Raspberry Pi.

## Current Status

- **Active Application**: `app/seeboard_pyqt5.py` (121 KB, PyQt5-based)
- **Launcher Script**: `seeboard_pyqt5.sh`
- **Legacy Application**: `app/seeboard_tkinter.py` (kept for reference)
- **Last Updated**: August 22, 2024

## Installation Steps on Raspberry Pi

### 1. Clone/Deploy Code to RP

Deploy the repository to the Raspberry Pi:

```bash
# From development machine
rsync -avz --delete ~/Projects/boat/general/Code/seeboard/ pi@10.42.0.1:~/Projects/seeboard/ \
  --exclude=.git --exclude=__pycache__ --exclude=*.pyc
```

This creates the application at `/home/pi/Projects/seeboard` on the RP.

### 2. Create Python Virtual Environment

SSH into the RP and create a virtual environment:

```bash
ssh pi@10.42.0.1
cd /home/pi/Projects/seeboard
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

### 3. Install System PyQt5

PyQt5 compilation from source on Raspberry Pi is unreliable. Use the system packages instead:

```bash
sudo apt-get update
sudo apt-get install -y python3-pyqt5
```

**Note**: `python3-pyqt5.qtwebengine` package is not available in Raspberry Pi repositories. The core PyQt5 package is sufficient for the seeBoard GUI.

### 4. Install Python Dependencies via pip

Install the remaining Python packages in the virtual environment:

```bash
# Activate venv if not already active
source venv/bin/activate

# Install pip packages
pip install pyserial==3.5 pynmea2==1.19.0 zeroconf==0.132.0 py-staticmaps
```

**Verification**:
```bash
source venv/bin/activate
python3 -c 'import serial; print("✓ pyserial")'
python3 -c 'import pynmea2; print("✓ pynmea2")'
python3 -c 'import zeroconf; print("✓ zeroconf")'
python3 -c 'import staticmaps; print("✓ py-staticmaps")'
```

**Package Details**:
- `pyserial` - GPS serial communication
- `pynmea2` - NMEA GPS data parsing
- `zeroconf` - mDNS camera discovery
- `py-staticmaps` - Map rendering with static map tiles

### 5. Update Launcher Script

The launcher script must be configured to access system PyQt5 while using the virtual environment for other packages. Update `seeboard_pyqt5.sh`:

```bash
#!/bin/bash
# seeBoard PyQt5 - GUI Application Launcher

cd /home/pi/Projects/seeboard || exit 1

# Activate virtual environment
source venv/bin/activate

# Add system packages to Python path to access system-installed PyQt5
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/lib/python3.11/dist-packages:$PYTHONPATH"

# Run the application
python3 app/seeboard_pyqt5.py
```

This ensures:
- The venv is activated (provides pyserial, pynmea2, zeroconf)
- System PyQt5 is accessible via PYTHONPATH
- The application runs with all required dependencies

### 4. Enable UART for GPS (One-time Configuration)

GPS communication requires UART to be enabled on the Raspberry Pi:

```bash
sudo raspi-config
# Navigate to: Interface Options → Serial Port
# Set: Login shell: No, Hardware: Yes
# Save and reboot
```

Optionally, add to `/boot/firmware/config.txt`:

```ini
enable_uart=1
dtoverlay=miniuart-bt
```

### 5. GPS Hardware Wiring (NEO-7M → Raspberry Pi)

| NEO-7M | RPi Pin | Function      |
|--------|---------|---------------|
| VCC    | Pin 1   | 3.3V          |
| GND    | Pin 6   | GND           |
| TX     | Pin 10  | GPIO 15 (RXD) |
| RX     | Pin 8   | GPIO 14 (TXD) |

### 6. Configuration

The application uses persistent configuration stored at `~/.seeboard/see_board.cfg`:

```ini
[gps]
show_dms_decimals = False

[cam]
rotation = 0
```

Copy the configuration from development machine if needed:

```bash
scp ~/Projects/boat/general/Code/seeboard/home/pi/.seeboard/see_board.cfg \
  pi@10.42.0.1:~/.seeboard/see_board.cfg
```

## Running the Application

### Via SSH (for testing)

```bash
ssh pi@10.42.0.1
cd /home/pi/Projects/seeboard
source venv/bin/activate
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/lib/python3.11/dist-packages:$PYTHONPATH"
python3 app/seeboard_pyqt5.py
```

### Via Launcher Script

```bash
cd /home/pi/Projects/seeboard
./seeboard_pyqt5.sh
```

The launcher script automatically sets up the environment and runs the application.

### On the Raspberry Pi Touchscreen

Connect to the Pi's display/touchscreen and:

1. Open a terminal
2. Run: `cd /home/pi/Projects/seeboard && ./seeboard_pyqt5.sh`
3. Or manually: `cd /home/pi/Projects/seeboard && source venv/bin/activate && export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/lib/python3.11/dist-packages:$PYTHONPATH" && python3 app/seeboard_pyqt5.py`

## Installation Summary (August 22, 2024)

### Completed Steps

1. ✅ **Code deployed to RP**: `/home/pi/Projects/seeboard`
2. ✅ **Virtual environment created**: `/home/pi/Projects/seeboard/venv`
3. ✅ **System PyQt5 installed**: `sudo apt-get install -y python3-pyqt5`
4. ✅ **pip dependencies installed**:
   - pyserial 3.5 (GPS serial communication)
   - pynmea2 1.19.0 (NMEA GPS data parsing)
   - zeroconf 0.132.0 (mDNS camera discovery)
   - py-staticmaps 0.5.0 (Map rendering with static tiles)
5. ✅ **Launcher script updated and renamed**: `seeboard_pyqt5.sh` with PYTHONPATH configuration
6. ✅ **All imports verified**: All modules import successfully

### Key Design Decisions

**Why System PyQt5?**
- PyQt5 from PyPI requires compilation (uses SIP builder), which is unreliable on Raspberry Pi
- System packages are pre-compiled and tested for ARM architecture
- System PyQt5 (5.15.9) is sufficient for the seeBoard GUI needs

**Why Virtual Environment?**
- Isolates application dependencies from system Python
- Allows easy management of pip packages (pyserial, pynmea2, zeroconf)
- Prevents conflicts with system packages

**PYTHONPATH Configuration**
- Virtual environment provides: pyserial, pynmea2, zeroconf, py-staticmaps
- System provides: PyQt5 (via /usr/lib/python3/dist-packages, /usr/lib/python3.11/dist-packages)
- Launcher script automatically exports PYTHONPATH to make both available

**Map Rendering**
- `py-staticmaps` is used by `MapRenderer` to render offline maps with path lines and position markers
- Reference: See `docs/METHODS_REFERENCE.md` for map rendering implementation details

### Next Steps

1. Test the application on the RP touchscreen
2. Verify GPS data reception via `/dev/serial0`
3. Test camera discovery and streaming
4. Configure persistent settings in `~/.seeboard/see_board.cfg`
5. Set up autostart via systemd or crontab if needed

## Troubleshooting

### PyQt5 Import Error

**Problem**: `ModuleNotFoundError: No module named 'PyQt5'`

**Solution**: 
- Ensure PYTHONPATH includes system packages: `export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/lib/python3.11/dist-packages:$PYTHONPATH"`
- Verify system PyQt5 is installed: `dpkg -l | grep python3-pyqt5`
- If missing, install: `sudo apt-get install -y python3-pyqt5`

### Other Modules Not Found (pyserial, pynmea2, zeroconf)

**Problem**: `ModuleNotFoundError: No module named 'serial'` or similar

**Solution**:
- Activate the virtual environment: `source /home/pi/Projects/seeboard/venv/bin/activate`
- Verify packages are installed: `pip list | grep -E 'pyserial|pynmea2|zeroconf'`
- If missing, install: `pip install pyserial==3.5 pynmea2==1.19.0 zeroconf==0.132.0`

### PyQt5 Compilation Failed (historical)

**Problem**: `sipbuild.pyproject.PyProjectOptionException: qmake`

**Context**: This was the original issue when attempting to install PyQt5 from PyPI via pip

**Solution Applied**: Switched to system PyQt5 package (`apt-get install python3-pyqt5`) instead of pip-based compilation

### GPS Not Detected

- Verify UART is enabled: `ls -la /dev/serial0`
- Check wiring against the table in this document
- Test with: `cat /dev/serial0` (you should see GPS NMEA data)

### Application Hangs or Crashes

- Check for sufficient disk space: `df -h`
- Verify all cameras are properly connected and discoverable via mDNS
- Review application logs if available
- Ensure touchscreen drivers are installed: `sudo apt-get install xserver-xorg-input-evdev`

### Virtual Environment Issues

**Problem**: `venv/bin/activate: No such file or directory`

**Solution**:
- Recreate the venv: `cd /home/pi/Projects/seeboard && python3 -m venv venv`
- Ensure you're in the correct directory before activating

### Launcher Script Fails

**Problem**: Running `./seeboard_pyqt5.sh` produces errors

**Solution**:
1. Ensure script is executable: `chmod +x /home/pi/Projects/seeboard/seeboard_pyqt5.sh`
2. Check script permissions: `ls -la /home/pi/Projects/seeboard/seeboard_pyqt5.sh`
3. Run manually to see actual error: `bash -x /home/pi/Projects/seeboard/seeboard_pyqt5.sh`

## Project Structure

```
/home/pi/Projects/seeboard/
├── seeboard_pyqt5.sh               ← PyQt5 launcher
├── seeboard_tkinter.sh             ← Legacy tkinter launcher
├── venv/                           ← Python virtual environment
├── app/
│   ├── seeboard_pyqt5.py           ← Main PyQt5 application
│   ├── seeboard_tkinter.py         ← Legacy tkinter app
│   ├── gps_core.py                 ← GPS module
│   ├── cam_discovery.py            ← Camera discovery
│   ├── route_database.py           ← Route/path database
│   ├── route_recorder.py           ← Route recording
│   ├── map_renderer.py             ← Map rendering
│   ├── config_loader.py            ← Configuration loader
│   └── views/
│       ├── coords_view.py
│       ├── map_view.py
│       ├── cam_view.py
│       └── conf_view.py
└── [other files]
```

## Network Configuration

The Raspberry Pi acts as a WiFi access point:

- **SSID**: GREEN-BEAN
- **IP Address**: 10.42.0.1 (from dev machine)
- **Camera Discovery**: Via mDNS on same network

## Development Workflow

1. Make changes on development machine
2. Deploy via rsync: `rsync -avz --delete ~/Projects/boat/general/Code/seeboard/ pi@10.42.0.1:~/Projects/seeboard/ --exclude=.git`
3. SSH into RP and test: `cd /home/pi/Projects/seeboard && source venv/bin/activate && python3 app/seeboard_pyqt5.py`
4. Commit and push changes

## Known Issues

- PyQt5 compilation on Raspberry Pi can be slow or fail on systems with limited resources
- System PyQt5 packages may have version mismatches
- Camera discovery requires cameras to be on the same WiFi network (GREEN-BEAN hotspot)

## References

- PyQt5 Documentation: https://www.riverbankcomputing.com/static/Docs/PyQt5/
- Raspberry Pi Serial Configuration: https://www.raspberrypi.com/documentation/computers/configuration.html#configuring-uarts
- NEO-7M GPS Module: Datasheet in `/docs/esp8266_gps_unit.md`
