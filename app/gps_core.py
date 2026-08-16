"""
GPS Core — Remote WiFi GPS unit reader.

Reads GPS data from ESP8266 WiFi GPS unit via HTTP.
Falls back to local serial port (/dev/serial0) if available.

Key design:
- Primary: Read from remote ESP8266-GPS unit (http://esp8266-gps.local/gps)
- Fallback: Try local serial port (/dev/serial0) if remote unavailable
- Auto-reconnects on network errors without crashing the GUI.
- Returns raw float lat/lon alongside DMS strings so callers can use either.
"""

import requests
import re
import time
import os
import atexit
import json
import threading

# Try to import serial support (fallback for local GPS)
try:
    import serial
    import pynmea2
    import termios
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# Remote GPS unit endpoint
# Try both hostname (mDNS) and IP address
REMOTE_GPS_HOSTS = [
    'esp8266-gps.local',  # Primary: mDNS hostname
    '10.42.0.98',         # Fallback: known IP
]
REMOTE_GPS_TIMEOUT = 10  # seconds (increased for slower networks)

# Fallback to local serial if remote unavailable
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 9600

# Human-readable names for GPS quality indicator values
QUALITY_NAMES = ['No fix', 'GPS fix', 'DGPS fix', 'PPS fix']

# Controls whether DMS format includes decimal seconds (e.g., 18.99" vs 19").
# Modified at runtime by conf_view when user toggles the setting.
SHOW_DMS_DECIMALS = False


def _dd_to_dms(dd):
    """Convert decimal degrees to DMS string (e.g., 56°10'18").

    Called at display time (not parse time) so that changes to
    SHOW_DMS_DECIMALS take effect immediately without waiting for
    a new GPS sentence.
    """
    if dd is None or dd == 0:
        return "--°--'--\""
    
    d = int(dd)
    m_full = (dd - d) * 60
    m = int(m_full)
    s = (m_full - m) * 60
    if SHOW_DMS_DECIMALS:
        return f"{d}\u00b0{m:02d}'{s:05.2f}\""
    else:
        return f"{d}\u00b0{m:02d}'{int(round(s)):02d}\""


# ═══════════════════════════════════════════════════════════════
# Remote GPS Reader (Primary)
# ═══════════════════════════════════════════════════════════════

def read_gps_remote():
    """Read GPS data from remote ESP8266 WiFi unit.
    
    Tries multiple hosts (mDNS hostname, then IP) with fallback.
    
    Returns:
        dict with 'status' key:
            'fix'     — valid position (includes lat/lon/time/quality/sats)
            'no_fix'  — GPS running but no satellite lock yet
            'no_data' — network error or timeout
            'error'   — HTTP error
        None — if all attempts fail
    """
    for host in REMOTE_GPS_HOSTS:
        url = f'http://{host}/gps'
        try:
            response = requests.get(url, timeout=REMOTE_GPS_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if we have a fix
                if data.get('fix') == 1 and data.get('lat') and data.get('lng'):
                    return {
                        'status': 'fix',
                        'time': data.get('time', '--:--:--'),
                        'lat': data.get('lat'),
                        'lat_raw': data.get('lat'),
                        'lat_dir': 'N' if data.get('lat', 0) >= 0 else 'S',
                        'lon': data.get('lng'),
                        'lon_raw': data.get('lng'),
                        'lon_dir': 'E' if data.get('lng', 0) >= 0 else 'W',
                        'quality': QUALITY_NAMES[min(1, 3)],  # GPS fix
                        'sats_used': str(data.get('satellites', 0)),
                        'sats_visible': str(data.get('satellites', 0)),
                    }
                else:
                    # No fix yet
                    return {
                        'status': 'no_fix',
                        'time': data.get('time', '--:--:--'),
                        'sats_used': str(data.get('satellites', 0)),
                        'sats_visible': str(data.get('satellites', 0)),
                    }
            
            elif response.status_code == 503:
                # GPS unit running but no fix yet
                return {
                    'status': 'no_fix',
                    'time': '--:--:--',
                    'sats_used': '0',
                    'sats_visible': '0',
                }
        except Exception:
            # This host failed, try next one
            continue
    
    # All hosts failed
    return None


# ═══════════════════════════════════════════════════════════════
# Local Serial Fallback (Secondary)
# ═══════════════════════════════════════════════════════════════

_ser = None
_original_termios = None

def _save_port_settings():
    """Save the serial port's original termios settings."""
    global _original_termios
    if not SERIAL_AVAILABLE or _original_termios is not None:
        return
    try:
        fd = os.open(SERIAL_PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        _original_termios = termios.tcgetattr(fd)
        os.close(fd)
    except Exception:
        pass


def _restore_port_settings():
    """Restore the serial port to its original termios state."""
    global _original_termios
    if not SERIAL_AVAILABLE or _original_termios is None:
        return
    try:
        fd = os.open(SERIAL_PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        termios.tcsetattr(fd, termios.TCSANOW, _original_termios)
        os.close(fd)
    except Exception:
        pass


def open_serial():
    """Open the GPS serial port. Returns True on success, False on failure."""
    global _ser
    if not SERIAL_AVAILABLE:
        return False
        
    if _ser:
        try:
            _ser.close()
        except Exception:
            pass
        _ser = None

    _save_port_settings()

    try:
        _ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
        _ser.reset_input_buffer()
        return True
    except Exception as e:
        print(f"Cannot open serial port: {e}")
        _ser = None
        return False


def read_gps_serial():
    """Read GPS data from local serial port (fallback).
    
    Returns dict with 'status' key or None.
    """
    global _ser
    if not SERIAL_AVAILABLE or not _ser or not _ser.is_open:
        if not open_serial():
            return None

    try:
        raw = _ser.readline()
    except Exception as e:
        try:
            _ser.close()
        except Exception:
            pass
        _ser = None
        return None

    if not raw:
        return {'status': 'no_data'}

    line = raw.decode('ascii', errors='replace').strip()
    if not line or not line.startswith('$'):
        return None

    # Only process GGA sentences (position + quality)
    if not (line.startswith('$GPGGA') or line.startswith('$GNGGA')):
        return None

    try:
        msg = pynmea2.parse(line)
    except Exception:
        return None

    if msg.lat_dir:
        return {
            'status': 'fix',
            'time': str(msg.timestamp),
            'lat': msg.latitude,
            'lat_raw': msg.latitude,
            'lat_dir': msg.lat_dir,
            'lon': msg.longitude,
            'lon_raw': msg.longitude,
            'lon_dir': msg.lon_dir,
            'quality': QUALITY_NAMES[min(msg.gps_qual, 3)],
            'sats_used': str(msg.num_sats or '0'),
            'sats_visible': str(msg.num_sats or '0'),
        }
    else:
        return {
            'status': 'no_fix',
            'time': str(msg.timestamp),
            'sats_used': str(msg.num_sats or '0'),
            'sats_visible': str(msg.num_sats or '0'),
        }


def close():
    """Close serial port and restore original termios settings."""
    global _ser
    if SERIAL_AVAILABLE and _ser:
        try:
            _ser.close()
        except Exception:
            pass
        _ser = None
    _restore_port_settings()


# ═══════════════════════════════════════════════════════════════
# Main GPS Reader (with Fallback Logic)
# ═══════════════════════════════════════════════════════════════

def read_gps():
    """Read GPS data with fallback priority.
    
    Priority:
    1. Try remote ESP8266-GPS unit first (WiFi)
    2. Fall back to local serial port if remote fails
    3. Return no_data if both fail
    
    Returns dict with 'status' key or None.
    """
    # Try remote GPS first (primary)
    data = read_gps_remote()
    if data is not None:
        return data
    
    # Fallback to local serial (secondary)
    if SERIAL_AVAILABLE:
        data = read_gps_serial()
        if data is not None:
            return data
    
    # Both failed
    return {'status': 'no_data'}


# ═══════════════════════════════════════════════════════════════
# Background GPS Reader Thread
# ═══════════════════════════════════════════════════════════════

_latest_data = None
_gps_thread = None
_gps_running = False


def _gps_reader_loop():
    """Background thread: continuously reads GPS and stores latest result."""
    global _latest_data
    _error_count = 0
    
    while _gps_running:
        data = read_gps()
        
        if data is not None and data.get('status') in ('fix', 'no_fix'):
            _latest_data = data
            _error_count = 0
        elif data is not None and data.get('status') == 'error':
            _error_count += 1
            if _error_count >= 3:
                _latest_data = None
        elif data is not None and data.get('status') == 'no_data':
            _error_count += 1
            if _error_count >= 10:
                _latest_data = None
        
        # Small sleep to prevent tight loop
        if data is None or (data and data.get('status') == 'no_data'):
            time.sleep(0.5)
        else:
            time.sleep(0.1)


def start_background_reader():
    """Start the background GPS reader thread."""
    global _gps_thread, _gps_running
    _gps_running = True
    _gps_thread = threading.Thread(target=_gps_reader_loop, daemon=True)
    _gps_thread.start()


def stop_background_reader():
    """Stop the background GPS reader thread."""
    global _gps_running
    _gps_running = False


def get_latest():
    """Get the latest GPS data (non-blocking, called from main thread)."""
    return _latest_data


# Cleanup on exit
atexit.register(close)
