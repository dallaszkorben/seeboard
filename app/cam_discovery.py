"""
Camera Discovery — finds ESP32-CAM devices on the network via mDNS.

Cameras advertise themselves as _mjpeg._tcp services.
This module discovers them and provides their stream URLs.
"""

import threading
import time
import socket

try:
    from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False
    print("[CAM_DISCOVERY] Warning: zeroconf not available, camera discovery disabled")

SERVICE_TYPE = "_mjpeg._tcp.local."

_cameras = {}  # {name: "http://ip:port/stream"}
_lock = threading.Lock()
_zeroconf = None
_browser = None


def _on_service_state_change(zeroconf, service_type, name, state_change):
    """Called when a camera appears or disappears on the network."""
    if state_change == ServiceStateChange.Added:
        info = zeroconf.get_service_info(service_type, name)
        if info:
            # Use hostname instead of IP so we can match camera names in config
            # name is like "esp32-cam-f404._mjpeg._tcp.local."
            # We want to extract "esp32-cam-f404" and use "esp32-cam-f404.local"
            hostname = name.split('.')[0]  # "esp32-cam-f404"
            port = info.port
            url = f"http://{hostname}.local:{port}/stream"
            with _lock:
                _cameras[name] = url

    elif state_change == ServiceStateChange.Removed:
        with _lock:
            _cameras.pop(name, None)


def start():
    """Start discovering cameras on the network."""
    if not HAS_ZEROCONF:
        print("[CAM_DISCOVERY] Skipping - zeroconf not available")
        return
    
    global _zeroconf, _browser
    _zeroconf = Zeroconf()
    _browser = ServiceBrowser(_zeroconf, SERVICE_TYPE, handlers=[_on_service_state_change])


def stop():
    """Stop discovery."""
    global _zeroconf, _browser
    if _zeroconf:
        _zeroconf.close()
        _zeroconf = None
        _browser = None


def get_cameras():
    """Return dict of currently discovered cameras: {name: stream_url}"""
    with _lock:
        return dict(_cameras)


def reset():
    """Stop discovery, clear cache, restart. Call before rebuild."""
    global _cameras
    stop()
    with _lock:
        _cameras = {}
    start()
