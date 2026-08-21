#!/usr/bin/env python3
"""
seeBoard PyQt5 Application - Direct Backend Access
Uses same camera streaming pattern as working tkinter app
"""

import sys
import os
import threading
import time
from configparser import ConfigParser
from datetime import datetime
import io
import math
import tempfile

# Add app directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(script_dir, 'app')
sys.path.insert(0, script_dir)
sys.path.insert(0, app_dir)

# PyQt5 imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QGridLayout, QCheckBox,
    QSlider, QComboBox, QScrollArea, QFrame, QGroupBox,
    QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QTimer
from PyQt5.QtGui import QFont, QColor, QImage, QPixmap, QPalette

# Backend imports
import gps_core
import cam_discovery
import map_generator
import route_recorder as route_recorder_module
from route_database import RouteDatabase
from route_recorder import RouteRecorder
from map_renderer import MapRenderer, MapCache

# Global route recorder
_db = None
global_route_recorder = None

def init_route_recorder():
    global _db, global_route_recorder
    _db = RouteDatabase()
    global_route_recorder = RouteRecorder(_db)

# ─── GLOBAL SLIDER STYLESHEET ───
SLIDER_STYLESHEET = """
QSlider {
    border: none;
    outline: none;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #e0e0e0;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #007AFF;
    border-radius: 3px;
}

QSlider::add-page:horizontal {
    background: #e0e0e0;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 18px;
    height: 18px;
    margin: -6px 0;
    background: #007AFF;
    border-radius: 9px;
}
"""
# ============================================================================
# CAMERA STREAMING - Same pattern as tkinter app
# ============================================================================

_streams = {}  # {url: {"running": bool, "frame": bytes|None, "last_frame_time": float}}
_known_urls = set()
_NO_SIGNAL_TIMEOUT = 3


def _is_stale(state, timeout_seconds=5):
    """Check if a camera stream has not received frames for too long."""
    return (time.time() - state.get("last_frame_time", 0)) > timeout_seconds


def _reader(url, state):
    """Background thread: reads MJPEG stream, extracts JPEG frames (from tkinter cam_view.py)"""
    MAX_BUF = 200000
    while state["running"]:
        try:
            import urllib.request
            stream = urllib.request.urlopen(url, timeout=5)
            stream.fp.raw._sock.settimeout(10)
            buf = b""
            while state["running"]:
                chunk = stream.read(4096)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > MAX_BUF:
                    buf = buf[-MAX_BUF:]
                while True:
                    s = buf.find(b"\xff\xd8")
                    e = buf.find(b"\xff\xd9", s + 2) if s != -1 else -1
                    if s != -1 and e != -1:
                        state["frame"] = buf[s:e + 2]
                        state["last_frame_time"] = time.time()
                        buf = buf[e + 2:]
                    else:
                        break
        except Exception:
            pass
        time.sleep(1)


def start_new_cameras():
    """Start streams for newly discovered cameras"""
    global _known_urls
    cameras = cam_discovery.get_cameras()
    new_urls = {url for url in cameras.values()} - _known_urls
    for url in new_urls:
        state = {"running": True, "frame": None, "last_frame_time": 0}  # START AT 0 SO IMMEDIATELY STALE
        t = threading.Thread(target=_reader, args=(url, state), daemon=True)
        t.start()
        _streams[url] = state
        _known_urls.add(url)


def stop_all_cameras():
    """Stop all camera streams"""
    for s in _streams.values():
        s["running"] = False
    _streams.clear()
    _known_urls.clear()


# ============================================================================
# COLLAPSIBLE SECTION WIDGET
# ============================================================================

class CollapsibleSection(QFrame):
    """Collapsible section with clickable header and arrow"""
    
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.is_collapsed = False
        self.content_height = 0
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header (clickable)
        self.header_btn = QPushButton()
        self.header_btn.setFlat(True)
        self.update_header()
        self.header_btn.clicked.connect(self.toggle_collapse)
        self.header_btn.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 12px 15px;
                border: none;
                border-radius: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #0051d5;
            }
            QPushButton:pressed {
                background-color: #003d9e;
            }
        """)
        main_layout.addWidget(self.header_btn)
        
        # Content container
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(5)
        self.content_widget.setLayout(self.content_layout)
        self.content_widget.setStyleSheet("background-color: white; border: 1px solid #ddd; border-radius: 6px;")
        
        main_layout.addWidget(self.content_widget)
        self.setLayout(main_layout)
    
    def update_header(self):
        """Update header text with arrow"""
        arrow = "▼" if not self.is_collapsed else "▶"
        self.header_btn.setText(f"{arrow}  {self.title}")
    
    def toggle_collapse(self):
        """Toggle collapse/expand immediately"""
        self.is_collapsed = not self.is_collapsed
        
        # Set max height to 0 (hidden) or large number (visible)
        if self.is_collapsed:
            self.content_widget.setMaximumHeight(0)
        else:
            self.content_widget.setMaximumHeight(16777215)  # Qt's max height
        
        self.update_header()
        
        # Force immediate layout update
        self.layout().update()
        self.updateGeometry()
        
        # Update parent layouts all the way up
        parent = self.parent()
        while parent:
            if hasattr(parent, 'layout') and parent.layout():
                parent.layout().update()
            if hasattr(parent, 'updateGeometry'):
                parent.updateGeometry()
            if hasattr(parent, 'update'):
                parent.update()
            parent = parent.parent()
        self.update_header()
    
    def add_to_layout(self, widget):
        """Add widget to content layout"""
        self.content_layout.addWidget(widget)
    
    def add_layout(self, layout):
        """Add layout to content with stretch to fill width"""
        self.content_layout.addLayout(layout, stretch=1)


# ============================================================================
# GPS WORKER
# ============================================================================

class GPSSignals(QObject):
    updated = pyqtSignal(dict)


class GPSWorker(QThread):
    signals = GPSSignals()
    
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
    
    def run(self):
        while not self._stop_event.is_set():
            try:
                data = gps_core.get_latest()
                if data:
                    self.signals.updated.emit(data)
            except Exception as e:
                print(f"[GPS Error] {e}")
            self._stop_event.wait(0.5)
    
    def stop(self):
        self._stop_event.set()


# ============================================================================
# TABS
# ============================================================================

class CoordsTab(QWidget):
    """GPS Coordinates Display - matching tkinter style"""
    
    # Configurable border/padding variable
    COORDS_PADDING = 5  # pixels for border/margin around containers
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.recording = False
        self.initUI()
        
        # Start GPS worker
        self.gps_worker = GPSWorker()
        self.gps_worker.signals.updated.connect(self.update_gps)
        self.gps_worker.start()
    
    def hsv_to_rgb(self, h, s, v):
        """Convert HSV (0-360, 0-100, 0-100) to RGB (0-255, 0-255, 0-255)"""
        h = h / 60.0
        s = s / 100.0
        v = v / 100.0
        
        c = v * s
        x = c * (1 - abs((h % 2) - 1))
        m = v - c
        
        if h < 1:
            r, g, b = c, x, 0
        elif h < 2:
            r, g, b = x, c, 0
        elif h < 3:
            r, g, b = 0, c, x
        elif h < 4:
            r, g, b = 0, x, c
        elif h < 5:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        
        return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))
    
    def initUI(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Load background color
        try:
            brightness = int(self.config.get('coords', 'bg_brightness', fallback='0'))
            color_name = self.config.get('coords', 'bg_color', fallback='black')
        except:
            brightness = 0
            color_name = 'black'
        
        # Ensure coords section exists in config
        if not self.config.has_section('coords'):
            self.config.add_section('coords')
        
        # Save defaults if not present
        if not self.config.has_option('coords', 'bg_color'):
            self.config.set('coords', 'bg_color', color_name)
        if not self.config.has_option('coords', 'bg_brightness'):
            self.config.set('coords', 'bg_brightness', str(brightness))
        
        bg_colors = {
            'black': (0, 0, 40),
            'blue': (225, 100, 40),
            'green': (114, 100, 40),
            'red': (0, 100, 40),
        }
        
        hsv = bg_colors.get(color_name, (0, 0, 40))
        h, s, v_max = hsv
        v = (brightness / 100.0) * v_max
        rgb = self.hsv_to_rgb(h, s, v)
        bg_color_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        
        self.bg_color_hex = bg_color_hex
        print(f"[COORDS] Setting background: color={color_name}, brightness={brightness}, HSV=({h},{s},{v}), RGB={rgb}, HEX={bg_color_hex}")
        
        # Apply background using PALETTE (stronger than stylesheet)
        palette = self.palette()
        qcolor = QColor(bg_color_hex)
        palette.setColor(QPalette.Window, qcolor)
        palette.setColor(QPalette.Base, qcolor)
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        
        # ─── NORTH SECTION: COORDINATES ───
        north_layout = QVBoxLayout()
        north_layout.setContentsMargins(20, 20, 20, 20)
        north_layout.setSpacing(0)
        
        try:
            coord_font_size = int(self.config.get('gps', 'coord_font_size', fallback='65'))
            color_name = self.config.get('gps', 'coord_color', fallback='lime')
            color_map = {
                'yellow': '#FFFF00',
                'white': '#FFFFFF',
                'cyan': '#00FFFF',
                'lime': '#00FF00',
                'red': '#FF0000',
                'orange': '#FFA500',
            }
            color_hex = color_map.get(color_name, '#00FF00')
        except:
            coord_font_size = 65
            color_hex = '#00FF00'
        
        self.lat_label = QLabel("--°--'--\"")
        self.lat_label.setFont(QFont("Helvetica", coord_font_size, QFont.Bold))
        self.lat_label.setStyleSheet(f"color: {color_hex}; background-color: transparent;")
        self.lat_label.setAlignment(Qt.AlignCenter)
        north_layout.addWidget(self.lat_label)
        
        self.lon_label = QLabel("---°--'--\"")
        self.lon_label.setFont(QFont("Helvetica", coord_font_size, QFont.Bold))
        self.lon_label.setStyleSheet(f"color: {color_hex}; background-color: transparent;")
        self.lon_label.setAlignment(Qt.AlignCenter)
        north_layout.addWidget(self.lon_label)
        
        layout.addLayout(north_layout, 1)  # Stretch top
        
        # ─── SOUTH SECTION: METADATA ───
        south_layout = QVBoxLayout()
        south_layout.setContentsMargins(10, 5, 10, 5)
        south_layout.setSpacing(2)
        
        try:
            meta_font_size = int(self.config.get('gps', 'meta_font_size', fallback='12'))
            meta_color_name = self.config.get('gps', 'meta_color', fallback='white')
            meta_color_hex = color_map.get(meta_color_name, '#FFFFFF')
        except:
            meta_font_size = 12
            meta_color_hex = '#FFFFFF'
        
        self.time_label = QLabel("Time: --:--:--")
        self.time_label.setFont(QFont("Helvetica", meta_font_size))
        self.time_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.time_label.setAlignment(Qt.AlignCenter)
        south_layout.addWidget(self.time_label)
        
        self.qual_label = QLabel("Quality: -")
        self.qual_label.setFont(QFont("Helvetica", meta_font_size))
        self.qual_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.qual_label.setAlignment(Qt.AlignCenter)
        south_layout.addWidget(self.qual_label)
        
        self.sat_label = QLabel("Satellites: - used / - visible")
        self.sat_label.setFont(QFont("Helvetica", meta_font_size))
        self.sat_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.sat_label.setAlignment(Qt.AlignCenter)
        south_layout.addWidget(self.sat_label)
        
        self.recording_label = QLabel("")
        self.recording_label.setFont(QFont("Helvetica", meta_font_size))
        self.recording_label.setStyleSheet(f"color: red; background-color: transparent;")
        self.recording_label.setAlignment(Qt.AlignCenter)
        south_layout.addWidget(self.recording_label)
        
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Helvetica", meta_font_size))
        self.status_label.setStyleSheet(f"color: red; background-color: transparent;")
        self.status_label.setAlignment(Qt.AlignCenter)
        south_layout.addWidget(self.status_label)
        
        layout.addLayout(south_layout, 0)  # No stretch bottom
        
        self.setLayout(layout)
    
    def on_tab_shown(self):
        """Called when this tab becomes visible - reload config"""
        try:
            gps_core.SHOW_DMS_DECIMALS = self.config.getboolean('gps', 'show_dms_decimals', fallback=False)
        except:
            gps_core.SHOW_DMS_DECIMALS = False
        
        # Reload coordinates font and color
        try:
            font_size = int(self.config.get('gps', 'coord_font_size', fallback='65'))
            color_name = self.config.get('gps', 'coord_color', fallback='lime')
            color_map = {
                'yellow': '#FFFF00',
                'white': '#FFFFFF',
                'cyan': '#00FFFF',
                'lime': '#00FF00',
                'red': '#FF0000',
                'orange': '#FFA500',
            }
            color_hex = color_map.get(color_name, '#00FF00')
        except:
            font_size = 65
            color_hex = '#00FF00'
        
        self.lat_label.setFont(QFont("Helvetica", font_size, QFont.Bold))
        self.lon_label.setFont(QFont("Helvetica", font_size, QFont.Bold))
        self.lat_label.setStyleSheet(f"color: {color_hex}; background-color: transparent;")
        self.lon_label.setStyleSheet(f"color: {color_hex}; background-color: transparent;")
        
        # Reload metadata font and color
        try:
            meta_font_size = int(self.config.get('gps', 'meta_font_size', fallback='12'))
            meta_color_name = self.config.get('gps', 'meta_color', fallback='white')
            meta_color_hex = color_map.get(meta_color_name, '#FFFFFF')
        except:
            meta_font_size = 12
            meta_color_hex = '#FFFFFF'
        
        self.time_label.setFont(QFont("Helvetica", meta_font_size))
        self.qual_label.setFont(QFont("Helvetica", meta_font_size))
        self.sat_label.setFont(QFont("Helvetica", meta_font_size))
        self.recording_label.setFont(QFont("Helvetica", meta_font_size))
        self.status_label.setFont(QFont("Helvetica", meta_font_size))
        self.time_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.qual_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.sat_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        
        # Reload background color - PALETTE METHOD (strongest)
        try:
            brightness = int(self.config.get('coords', 'bg_brightness', fallback='0'))
            color_name = self.config.get('coords', 'bg_color', fallback='black')
        except:
            brightness = 0
            color_name = 'black'
        
        bg_colors = {
            'black': (0, 0, 40),
            'blue': (225, 100, 40),
            'green': (114, 100, 40),
            'red': (0, 100, 40),
        }
        
        hsv = bg_colors.get(color_name, (0, 0, 40))
        h, s, v_max = hsv
        v = (brightness / 100.0) * v_max
        rgb = self.hsv_to_rgb(h, s, v)
        bg_color_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        
        # Update palette
        palette = self.palette()
        qcolor = QColor(bg_color_hex)
        palette.setColor(QPalette.Window, qcolor)
        palette.setColor(QPalette.Base, qcolor)
        self.setPalette(palette)
        self.setAutoFillBackground(True)
    
    def update_gps(self, data):
        # Get the configured coordinate color
        try:
            color_name = self.config.get('gps', 'coord_color', fallback='lime')
            color_map = {
                'yellow': '#FFFF00',
                'white': '#FFFFFF',
                'cyan': '#00FFFF',
                'lime': '#00FF00',
                'red': '#FF0000',
                'orange': '#FFA500',
            }
            coord_color = color_map.get(color_name, '#00FF00')
        except:
            coord_color = '#00FF00'
        
        if data and data.get('status') == 'fix':
            lat_decimal = data.get('lat', 0)
            lon_decimal = data.get('lon', 0)
            lat_dms = gps_core._dd_to_dms(lat_decimal)
            lon_dms = gps_core._dd_to_dms(lon_decimal)
            
            # Use configured color for fix
            self.lat_label.setStyleSheet(f"color: {coord_color}; background-color: transparent;")
            self.lon_label.setStyleSheet(f"color: {coord_color}; background-color: transparent;")
            
            self.lat_label.setText(lat_dms)
            self.lon_label.setText(lon_dms)
            
            time_str = data.get('time', '--:--:--')
            qual_str = data.get('quality', 'No Fix')
            sats_used = data.get('sats_used', 0)
            sats_visible = data.get('sats_visible', 0)
            
            self.time_label.setText(f"Time: {time_str}")
            self.qual_label.setText(f"Quality: {qual_str}")
            self.sat_label.setText(f"Satellites: {sats_used} used / {sats_visible} visible")
            self.status_label.setText("")
            
            # If recording, add point to route
            if self.recording and data.get('lat') and data.get('lon'):
                try:
                    global_route_recorder.add_point({
                        'lat': data.get('lat'),
                        'lon': data.get('lon'),
                        'time': datetime.now().isoformat()
                    })
                except Exception as e:
                    print(f"[REC] Error adding point: {e}")
        
        elif data and data.get('status') == 'no_fix':
            # Orange for no fix
            self.lat_label.setStyleSheet("color: #FFA500; background-color: transparent;")
            self.lon_label.setStyleSheet("color: #FFA500; background-color: transparent;")
            
            self.lat_label.setText("--°--'--\"")
            self.lon_label.setText("---°--'--\"")
            
            time_str = data.get('time', '--:--:--')
            sats_used = data.get('sats_used', 0)
            sats_visible = data.get('sats_visible', 0)
            
            self.time_label.setText(f"Time: {time_str}")
            self.qual_label.setText("Quality: No fix")
            self.sat_label.setText(f"Satellites: {sats_used} used / {sats_visible} visible")
            self.status_label.setText("Waiting for fix...")
        else:
            # Red for no GPS
            self.lat_label.setStyleSheet("color: #FF0000; background-color: transparent;")
            self.lon_label.setStyleSheet("color: #FF0000; background-color: transparent;")
            
            self.lat_label.setText("--°--'--\"")
            self.lon_label.setText("---°--'--\"")
            self.time_label.setText("Time: --:--:--")
            self.qual_label.setText("Quality: -")
            self.sat_label.setText("Satellites: - used / - visible")
            self.status_label.setText("⚠ No GPS data")
        
        # Update recording status
        if self.recording:
            self.recording_label.setText("🔴 RECORDING")
        else:
            self.recording_label.setText("")
    
    def start_recording(self):
        self.recording = True
        self.rec_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        try:
            global_route_recorder.start_recording({}, {})
            print("[REC] Recording started")
        except Exception as e:
            print(f"[REC] Error: {e}")
            self.recording = False
            self.rec_button.setEnabled(True)
            self.stop_button.setEnabled(False)
    
    def stop_recording(self):
        self.recording = False
        self.rec_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        try:
            global_route_recorder.stop_recording()
            print("[REC] Recording stopped")
        except Exception as e:
            print(f"[REC] Error: {e}")


class MapTab(QWidget):
    """Map Display using py-staticmaps with Cairo rendering"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.gps_data = {}
        self.current_lat = 56.1612
        self.current_lon = 15.5869
        
        # Initialize map renderer
        self.map_renderer = MapRenderer(width=800, height=600)
        
        # Map state
        self.zoom = 13
        self.map_center_lat = self.current_lat  # Separate from GPS position
        self.map_center_lon = self.current_lon
        self.needs_render = True  # Flag to trigger render
        
        # Mouse tracking for pan
        self.last_mouse_pos = None
        self.pan_active = False
        self.pixels_per_degree = 100  # Approximate, will vary with zoom
        
        # Create UI
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Map display label - expand to fill space
        self.map_label = QLabel()
        self.map_label.setAlignment(Qt.AlignCenter)
        self.map_label.setStyleSheet("background-color: #f0f0f0;")
        from PyQt5.QtWidgets import QSizePolicy
        self.map_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.map_label.setMouseTracking(True)
        # Override mouse events
        self.map_label.mousePressEvent = self.map_mouse_press
        self.map_label.mouseMoveEvent = self.map_mouse_move
        self.map_label.mouseReleaseEvent = self.map_mouse_release
        self.map_label.wheelEvent = self.map_wheel_event
        layout.addWidget(self.map_label, 1)  # Stretch factor = 1
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(5, 5, 5, 5)
        
        zoom_in_btn = QPushButton("Zoom +")
        zoom_in_btn.clicked.connect(self.zoom_in)
        button_layout.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("Zoom -")
        zoom_out_btn.clicked.connect(self.zoom_out)
        button_layout.addWidget(zoom_out_btn)
        
        center_btn = QPushButton("Center GPS")
        center_btn.clicked.connect(self.center_on_gps)
        button_layout.addWidget(center_btn)
        
        layout.addLayout(button_layout, 0)  # No stretch
        self.setLayout(layout)
        
        # Timer for render updates (only on demand)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.render_if_needed)
        self.update_timer.start(500)  # Check every 500ms if render needed
        
        # Connect GPS updates (just update position, don't render)
        GPSWorker.signals.updated.connect(self.on_gps_update)
        
        # Initial render
        self.render_map()
    
    def on_gps_update(self, gps_data):
        """Handle GPS position update - just update position, don't re-center"""
        self.gps_data = gps_data
        old_lat = self.current_lat
        old_lon = self.current_lon
        
        self.current_lat = gps_data.get('lat') or 56.1612
        self.current_lon = gps_data.get('lon') or 15.5869
        
        # If this is the first GPS update and map_center is still at default, center on GPS
        if (self.map_center_lat == 56.1612 and self.map_center_lon == 15.5869 and 
            (self.current_lat != 56.1612 or self.current_lon != 15.5869)):
            self.map_center_lat = self.current_lat
            self.map_center_lon = self.current_lon
            print(f"[MAP] Initial center set to GPS: {self.current_lat}, {self.current_lon}")
        
        # If GPS position changed, re-render to update marker position
        if (self.current_lat != old_lat or self.current_lon != old_lon):
            self.needs_render = True
        # Don't update map_center - stays where user moved it
        # In FOLLOW mode (future), we would do: self.map_center_lat = self.current_lat
    
    def render_if_needed(self):
        """Only render if something changed"""
        if self.needs_render:
            self.render_map()
            self.needs_render = False
    
    def render_map(self):
        """Render map at current map center"""
        try:
            # Debug: log positions and widget size
            print(f"[MAP] Rendering at center: {self.map_center_lat}, {self.map_center_lon} (GPS: {self.current_lat}, {self.current_lon})")
            print(f"[MAP] Label size: {self.map_label.width()}x{self.map_label.height()}")
            
            # Use label size or default
            width = self.map_label.width() if self.map_label.width() > 100 else 800
            height = self.map_label.height() if self.map_label.height() > 100 else 600
            
            # Create renderer with actual widget dimensions
            renderer = MapRenderer(width=width, height=height)
            
            # Render map centered on map_center, with GPS position as marker
            pixmap = renderer.render_map(
                lat=self.map_center_lat,
                lon=self.map_center_lon,
                gps_lat=self.current_lat,
                gps_lon=self.current_lon,
                zoom=self.zoom,
                route_points=None,
                coverage_radius=None
            )
            
            if pixmap:
                # Scale to fit exactly - don't use scaledToWidth, use scaled
                scaled_pixmap = pixmap.scaled(
                    self.map_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.map_label.setPixmap(scaled_pixmap)
        except Exception as e:
            self.map_label.setText(f"Error rendering map: {e}")
    
    def zoom_in(self):
        """Increase zoom level"""
        if self.zoom < 18:
            self.zoom += 1
            self.needs_render = True
    
    def zoom_out(self):
        """Decrease zoom level"""
        if self.zoom > 1:
            self.zoom -= 1
            self.needs_render = True
    
    def center_on_gps(self):
        """Center map on current GPS position"""
        self.map_center_lat = self.current_lat
        self.map_center_lon = self.current_lon
        self.needs_render = True
    
    def map_mouse_press(self, event):
        """Handle mouse press for panning"""
        self.last_mouse_pos = event.pos()
        self.pan_active = True
    
    def map_mouse_move(self, event):
        """Handle mouse move for panning"""
        if self.pan_active and self.last_mouse_pos:
            # Calculate delta in pixels
            dx = event.pos().x() - self.last_mouse_pos.x()
            dy = event.pos().y() - self.last_mouse_pos.y()
            
            # Get current map dimensions
            map_width = self.map_label.width()
            map_height = self.map_label.height()
            
            if map_width > 0 and map_height > 0:
                # Calculate degrees per pixel
                # At zoom level z, the world is 256*2^z pixels wide
                # which spans 360 degrees longitude
                pixels_per_degree_lon = (256 * (2 ** self.zoom)) / 360
                
                # Latitude is similar but with different aspect ratio
                pixels_per_degree_lat = (256 * (2 ** self.zoom)) / 180
                
                # Convert pixel movement to degree movement
                delta_lon = -dx / pixels_per_degree_lon
                delta_lat = dy / pixels_per_degree_lat
                
                # Pan map
                self.map_center_lat += delta_lat
                self.map_center_lon += delta_lon
                
                # Clamp to valid ranges
                self.map_center_lat = max(-85, min(85, self.map_center_lat))
                self.map_center_lon = ((self.map_center_lon + 180) % 360) - 180
                
                self.last_mouse_pos = event.pos()
                self.needs_render = True
    
    def map_mouse_release(self, event):
        """Handle mouse release for panning"""
        self.pan_active = False
        self.last_mouse_pos = None
    
    def map_wheel_event(self, event):
        """Handle mouse wheel for zooming - zoom toward cursor position"""
        # Get cursor position relative to map widget
        cursor_pos = event.pos()
        map_width = self.map_label.width()
        map_height = self.map_label.height()
        
        if map_width > 0 and map_height > 0:
            # Calculate what lat/lon is under the cursor BEFORE zooming
            pixels_per_degree_lon = (256 * (2 ** self.zoom)) / 360
            pixels_per_degree_lat = (256 * (2 ** self.zoom)) / 180
            
            # Offset from center to cursor in degrees
            cursor_offset_lon = (cursor_pos.x() - map_width / 2) / pixels_per_degree_lon
            cursor_offset_lat = -(cursor_pos.y() - map_height / 2) / pixels_per_degree_lat
            
            # Lat/lon under cursor before zoom
            lat_under_cursor = self.map_center_lat + cursor_offset_lat
            lon_under_cursor = self.map_center_lon + cursor_offset_lon
            
            # Do the zoom
            old_zoom = self.zoom
            if event.angleDelta().y() > 0:
                if self.zoom < 18:
                    self.zoom += 1
            else:
                if self.zoom > 1:
                    self.zoom -= 1
            
            # After zoom, recalculate pixels per degree at new zoom
            if self.zoom != old_zoom:
                new_pixels_per_degree_lon = (256 * (2 ** self.zoom)) / 360
                new_pixels_per_degree_lat = (256 * (2 ** self.zoom)) / 180
                
                # Move map center so same lat/lon is under cursor
                self.map_center_lon = lon_under_cursor - (cursor_pos.x() - map_width / 2) / new_pixels_per_degree_lon
                self.map_center_lat = lat_under_cursor + (cursor_pos.y() - map_height / 2) / new_pixels_per_degree_lat
                
                self.needs_render = True
        
        event.accept()
    
    def closeEvent(self, event):
        """Cleanup on close"""
        self.update_timer.stop()
        super().closeEvent(event)


class CamTab(QWidget):
    """Camera Display - uses same pattern as tkinter"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        layout = QVBoxLayout()
        self.cam_label = QLabel("Searching for cameras...")
        self.cam_label.setFont(QFont("Arial", 14))
        self.cam_label.setFixedSize(800, 600)  # FIXED SIZE - DO NOT GROW
        self.cam_label.setStyleSheet("border: 1px solid black; background: black;")
        self.cam_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.cam_label)
        self.setLayout(layout)
        
        # Track expired cameras (had frames before, lost signal after grace period)
        self.expired_cameras = {}  # url -> expiry_time
        
        # Timer to update camera display every 50ms (same as tkinter)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(50)
    
    def on_tab_shown(self):
        """Called when CAM tab becomes visible - reload config to get updated rotations"""
        config_file = os.path.expanduser("~/Projects/seeboard/see_board.cfg")
        self.config.read(config_file)
    
    def update_display(self):
        """Update camera display"""
        try:
            start_new_cameras()
            urls = list(_streams.keys())
            grace_period = int(self.config.get('camera_settings', 'grace_period_seconds', fallback='5'))
            
            # Log state
            log_msg = f"[DISPLAY] URLs: {len(urls)}, Expired: {len(self.expired_cameras)}\n"
            
            # Update expired camera tracking
            # Remove from expired if signal returns
            for url in list(self.expired_cameras.keys()):
                if _streams.get(url) and not _is_stale(_streams[url], timeout_seconds=grace_period):
                    log_msg += f"  [RECOVERED] {url}\n"
                    del self.expired_cameras[url]
            
            # Check for cameras that should be marked as PERMANENTLY expired
            # (stale for grace_period AND had frames before)
            for url in urls:
                if url not in self.expired_cameras:
                    if _streams[url].get("last_frame_time", 0) > 0:  # Had frames before
                        if _is_stale(_streams[url], timeout_seconds=grace_period):
                            log_msg += f"  [PERMANENTLY EXPIRED] {url}\n"
                            self.expired_cameras[url] = time.time()
            
            # Filter out PERMANENTLY expired cameras ONLY
            active_urls = [u for u in urls if u not in self.expired_cameras]
            log_msg += f"Active URLs: {len(active_urls)}\n"
            
            for url in active_urls:
                has_frame = bool(_streams[url].get("frame"))
                is_stale = _is_stale(_streams[url], timeout_seconds=grace_period)
                log_msg += f"  [{url.split('/')[-1]}] frame={has_frame}, stale={is_stale}\n"
            
            with open('/tmp/seeboard_display.log', 'a') as f:
                f.write(log_msg)
            if not urls:
                self.cam_label.setText("Searching for cameras...")
                return
            
            # Fixed composite size
            w, h = 800, 600
            
            # Cameras to display: all EXCEPT permanently expired ones
            display_urls = [u for u in urls if u not in self.expired_cameras]
            
            if not display_urls:
                self.cam_label.setText("All cameras expired...")
                return
            
            # Setup grid based on displayable cameras
            n = len(display_urls)
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            cell_w = w // cols
            cell_h = h // rows
            
            from PIL import Image, ImageDraw, ImageFont, ImageEnhance
            composite = Image.new("RGB", (w, h), "black")
            
            for i, url in enumerate(display_urls):
                # Extract hostname
                try:
                    host_part = url.split("://")[1].split(":")[0]
                    hostname = host_part.replace(".local", "")
                except:
                    hostname = "unknown"
                
                # Get frame
                frame_data = _streams[url].get("frame")
                is_stale = _is_stale(_streams[url], timeout_seconds=grace_period)
                
                log_msg += f"    Drawing {hostname}: frame={bool(frame_data)}, stale={is_stale}\n"
                
                # Create image
                if frame_data:
                    img = Image.open(__import__('io').BytesIO(frame_data))
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    
                    # Apply rotation
                    rot = 0
                    if self.config.has_section('camera_rotations'):
                        for opt in self.config.options('camera_rotations'):
                            if hostname in opt:
                                rot = self.config.getint('camera_rotations', opt)
                    if rot > 0:
                        img = img.rotate(-rot, expand=True)
                    
                    # Dim if stale
                    if is_stale:
                        img = img.convert('L').convert('RGB')
                        img = ImageEnhance.Brightness(img).enhance(0.5)
                    
                    # Resize
                    scale = min(cell_w / img.width, cell_h / img.height)
                    new_size = (int(img.width * scale), int(img.height * scale))
                    img = img.resize(new_size)
                else:
                    # No frame - create BLACK PLACEHOLDER at cell size
                    img = Image.new("RGB", (cell_w, cell_h), "black")
                
                # DRAW TEXT HERE (on frame or placeholder, before any padding)
                draw = ImageDraw.Draw(img)
                font_size = int(self.config.get('camera_settings', 'label_font_size', fallback='16'))
                color_name = self.config.get('camera_settings', 'label_color', fallback='white')
                colors = {'white': (255,255,255), 'yellow': (255,255,0), 'cyan': (0,255,255), 'lime': (0,255,0), 'red': (255,0,0)}
                color = colors.get(color_name, (255,255,255))
                
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                except:
                    font = ImageFont.load_default()
                
                # Clean hostname
                display = hostname.split("._")[0] if "._" in hostname else hostname
                
                # Draw label (bottom-left)
                bbox = draw.textbbox((0, 0), display, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                x = 5
                y = img.height - text_h - 5
                
                draw.rectangle([(x-3, y-3), (x+text_w+3, y+text_h+3)], fill=(0,0,0,200))
                draw.text((x, y), display, fill=color, font=font)
                
                # NO SIGNAL if frame hasn't been updated recently (< 100ms)
                last_update = time.time() - _streams[url].get("last_frame_time", 0)
                frame_is_stale_immediately = last_update > 0.1  # No update in 100ms
                
                if frame_is_stale_immediately:
                    # Show NO SIGNAL immediately
                    try:
                        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(img.height // 8))
                    except:
                        font_big = ImageFont.load_default()
                    
                    bbox = draw.textbbox((0, 0), "NO SIGNAL", font=font_big)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]
                    x = (img.width - tw) // 2
                    y = (img.height - th) // 2
                    draw.rectangle([(x-10, y-10), (x+tw+10, y+th+10)], fill=(255,255,255))
                    draw.text((x, y), "NO SIGNAL", fill=(0,0,0), font=font_big)
                
                # NOW pad to cell size (only if we have a REAL frame, not placeholder)
                if frame_data and not is_stale:
                    cell = Image.new("RGB", (cell_w, cell_h), "black")
                    paste_x = (cell_w - img.width) // 2
                    paste_y = (cell_h - img.height) // 2
                    cell.paste(img, (paste_x, paste_y))
                    img = cell
                
                # Paste to composite
                r = i // cols
                c = i % cols
                composite.paste(img, (c * cell_w, r * cell_h))
            
            # Display
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                composite.save(f.name)
                pixmap = __import__('PyQt5.QtGui', fromlist=['QPixmap']).QPixmap(f.name)
                __import__('os').unlink(f.name)
            
            self.cam_label.setPixmap(pixmap)
            self.cam_label.setText("")
            
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
    
    def closeEvent(self, event):
        self.timer.stop()
        stop_all_cameras()
        super().closeEvent(event)


class ConfTab(QWidget):
    """Configuration - with GPS, Camera, Map sections - professional styling - auto-save"""
    
    def __init__(self, config, main_window=None):
        super().__init__()
        self.config = config
        self.main_window = main_window
        self.camera_section = None  # Will be set during initUI
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #f5f5f5;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #f5f5f5;
                width: 20px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #007AFF;
                border: 1px solid #0051d5;
                border-radius: 8px;
                min-height: 30px;
                margin: 3px 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #0051d5;
                border: 1px solid #003d9e;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #003d9e;
                border: 1px solid #002570;
            }
            QScrollBar::up-arrow:vertical {
                border: none;
                background: none;
            }
            QScrollBar::down-arrow:vertical {
                border: none;
                background: none;
            }
            QScrollBar::add-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
        """)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: #f5f5f5;")
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        
        # ─── GPS SECTION (COLLAPSIBLE) ───
        gps_section = CollapsibleSection("GPS")
        
        dms_layout = QHBoxLayout()
        dms_label = QLabel("Show DMS Decimals:")
        dms_label.setStyleSheet("font-size: 12px; color: #333; border: none;")
        dms_layout.addWidget(dms_label)
        self.dms_checkbox = QCheckBox()
        self.dms_checkbox.setChecked(
            self.config.getboolean('gps', 'show_dms_decimals', fallback=False))
        self.dms_checkbox.stateChanged.connect(self.save_config)
        self.dms_checkbox.setStyleSheet("""
            QCheckBox {
                min-height: 20px;
                border: none;
                outline: none;
            }
            QCheckBox::indicator {
                border: none;
                outline: none;
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #ffffff;
                border: 1px solid #cccccc;
            }
            QCheckBox::indicator:checked {
                background-color: #007AFF;
                border: 1px solid #007AFF;
            }
        """)
        dms_layout.addWidget(self.dms_checkbox)
        dms_layout.addStretch()
        gps_section.add_layout(dms_layout)
        
        scroll_layout.addWidget(gps_section)
        scroll_layout.addSpacing(10)
        
        # ─── COORDINATES SETTINGS (inside GPS section) ───
        coord_box, coord_layout = self._create_bordered_section("Coordinates")
        
        # Font size
        font_layout = QHBoxLayout()
        font_label = QLabel("Font Size:")
        font_label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
        font_layout.addWidget(font_label)
        
        self.font_size_slider = QSlider(Qt.Horizontal)
        self.font_size_slider.setMinimum(60)
        self.font_size_slider.setMaximum(120)
        self.font_size_slider.setStyleSheet(SLIDER_STYLESHEET)
        try:
            font_size = int(self.config.get('gps', 'coord_font_size', fallback='65'))
            self.font_size_slider.setValue(font_size)
        except:
            self.font_size_slider.setValue(65)
        
        self.font_size_slider.valueChanged.connect(self.save_config)
        font_layout.addWidget(self.font_size_slider)
        
        self.font_size_value = QLabel(str(self.font_size_slider.value()))
        self.font_size_value.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
        self.font_size_slider.valueChanged.connect(lambda v: self.font_size_value.setText(str(v)))
        font_layout.addWidget(self.font_size_value)
        coord_layout.addLayout(font_layout)
        
        # Color
        color_layout = QHBoxLayout()
        color_label = QLabel("Color:")
        color_label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
        color_layout.addWidget(color_label)
        
        saved_coord_color = self.config.get('gps', 'coord_color', fallback='lime')
        self.coord_color_buttons = {}
        colors = {
            'yellow': '#FFFF00',
            'white': '#FFFFFF',
            'cyan': '#00FFFF',
            'lime': '#00FF00',
            'red': '#FF0000',
            'orange': '#FFA500',
        }
        
        for color_name, color_hex in colors.items():
            btn = QPushButton(color_name.upper())
            text_color = '#000000' if color_name in ['yellow', 'white', 'cyan', 'lime'] else '#FFFFFF'
            is_selected = saved_coord_color == color_name
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    color: {text_color};
                    font-size: 10px;
                    font-weight: bold;
                    padding: 8px 12px;
                    border: {'4px solid #007AFF' if is_selected else '2px solid #ddd'};
                    border-radius: 6px;
                    min-width: 50px;
                }}
                QPushButton:hover {{
                    border: 3px solid #007AFF;
                    background-color: {color_hex};
                }}
                QPushButton:pressed {{
                    border: 4px solid #0051d5;
                }}
            """)
            btn.clicked.connect(lambda checked, c=color_name: self.set_coord_color(c))
            self.coord_color_buttons[color_name] = btn
            color_layout.addWidget(btn)
        
        self.selected_coord_color = saved_coord_color
        color_layout.addStretch()
        coord_layout.addLayout(color_layout)
        
        # Coordinates box will be added to GPS section later
        
        # ─── METADATA SETTINGS (inside GPS section) ───
        meta_box, meta_layout = self._create_bordered_section("Metadata")
        
        # Font size
        meta_font_layout = QHBoxLayout()
        meta_font_label = QLabel("Font Size:")
        meta_font_label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
        meta_font_layout.addWidget(meta_font_label)
        
        self.meta_font_size_slider = QSlider(Qt.Horizontal)
        self.meta_font_size_slider.setMinimum(8)
        self.meta_font_size_slider.setMaximum(48)
        self.meta_font_size_slider.setStyleSheet(SLIDER_STYLESHEET)
        try:
            meta_font_size = int(self.config.get('gps', 'meta_font_size', fallback='12'))
            self.meta_font_size_slider.setValue(meta_font_size)
        except:
            self.meta_font_size_slider.setValue(12)
        
        self.meta_font_size_slider.valueChanged.connect(self.save_config)
        meta_font_layout.addWidget(self.meta_font_size_slider)
        
        self.meta_font_size_value = QLabel(str(self.meta_font_size_slider.value()))
        self.meta_font_size_value.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
        self.meta_font_size_slider.valueChanged.connect(lambda v: self.meta_font_size_value.setText(str(v)))
        meta_font_layout.addWidget(self.meta_font_size_value)
        meta_layout.addLayout(meta_font_layout)
        
        # Color
        meta_color_layout = QHBoxLayout()
        meta_color_label = QLabel("Color:")
        meta_color_label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
        meta_color_layout.addWidget(meta_color_label)
        
        saved_meta_color = self.config.get('gps', 'meta_color', fallback='white')
        self.meta_color_buttons = {}
        
        for color_name, color_hex in colors.items():
            btn = QPushButton(color_name.upper())
            text_color = '#000000' if color_name in ['yellow', 'white', 'cyan', 'lime'] else '#FFFFFF'
            is_selected = saved_meta_color == color_name
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    color: {text_color};
                    font-size: 10px;
                    font-weight: bold;
                    padding: 8px 12px;
                    border: {'4px solid #007AFF' if is_selected else '2px solid #ddd'};
                    border-radius: 6px;
                    min-width: 50px;
                }}
                QPushButton:hover {{
                    border: 3px solid #007AFF;
                    background-color: {color_hex};
                }}
                QPushButton:pressed {{
                    border: 4px solid #0051d5;
                }}
            """)
            btn.clicked.connect(lambda checked, c=color_name: self.set_meta_color(c))
            self.meta_color_buttons[color_name] = btn
            meta_color_layout.addWidget(btn)
        
        self.selected_meta_color = saved_meta_color
        meta_color_layout.addStretch()
        meta_layout.addLayout(meta_color_layout)
        
        # Metadata box will be added to GPS section later
        
        # ─── BACKGROUND SETTINGS (inside GPS section) ───
        bg_box, bg_layout = self._create_bordered_section("Background")
        
        # Background color selection
        bg_color_layout = QHBoxLayout()
        bg_color_label = QLabel("Color:")
        bg_color_label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
        bg_color_layout.addWidget(bg_color_label)
        
        saved_bg_color = self.config.get('coords', 'bg_color', fallback='black')
        self.bg_color_buttons = {}
        
        # HSV color definitions: (Hue, Saturation, Value_max)
        bg_colors = {
            'black': (0, 0, 40),      # H irrelevant, S=0, V goes 0-40
            'blue': (225, 100, 40),   # H=225, S=100, V goes 0-40
            'green': (114, 100, 40),  # H=114, S=100, V goes 0-40
            'red': (0, 100, 40),      # H=0, S=100, V goes 0-40
        }
        
        for color_name in ['black', 'blue', 'green', 'red']:
            hsv = bg_colors[color_name]
            # Get RGB for the max value (100 slider) for button display
            rgb_max = self.hsv_to_rgb(hsv[0], hsv[1], hsv[2])
            rgb_hex = f"#{rgb_max[0]:02x}{rgb_max[1]:02x}{rgb_max[2]:02x}"
            
            btn = QPushButton(color_name.upper())
            is_selected = saved_bg_color == color_name
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {rgb_hex};
                    color: #FFFFFF;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 8px 15px;
                    border: {'4px solid #007AFF' if is_selected else '2px solid #ddd'};
                    border-radius: 6px;
                    min-width: 70px;
                }}
                QPushButton:hover {{
                    border: 3px solid #007AFF;
                }}
                QPushButton:pressed {{
                    border: 4px solid #0051d5;
                }}
            """)
            # Connect button click
            btn.clicked.connect(lambda checked, c=color_name: self.set_bg_color(c))
            self.bg_color_buttons[color_name] = btn
            bg_color_layout.addWidget(btn)
        
        self.selected_bg_color = saved_bg_color
        bg_color_layout.addStretch()
        bg_layout.addLayout(bg_color_layout)
        
        # Background brightness slider
        bg_slider_layout = QHBoxLayout()
        bg_label = QLabel("Brightness:")
        bg_label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
        bg_slider_layout.addWidget(bg_label)
        
        saved_brightness = int(self.config.get('coords', 'bg_brightness', fallback='0'))
        self.bg_brightness_slider = QSlider(Qt.Horizontal)
        self.bg_brightness_slider.setMinimum(0)
        self.bg_brightness_slider.setMaximum(100)
        self.bg_brightness_slider.setStyleSheet(SLIDER_STYLESHEET)
        self.bg_brightness_slider.setValue(saved_brightness)
        self.bg_brightness_slider.valueChanged.connect(self.on_bg_brightness_changed)
        self.bg_brightness_slider.valueChanged.connect(self.save_config)
        bg_slider_layout.addWidget(self.bg_brightness_slider)
        
        self.bg_brightness_value = QLabel(f"{saved_brightness}")
        self.bg_brightness_value.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
        bg_slider_layout.addWidget(self.bg_brightness_value)
        
        bg_layout.addLayout(bg_slider_layout)
        
        # Add all GPS-related content to the GPS collapsible section
        gps_section.add_to_layout(coord_box)
        gps_section.add_to_layout(meta_box)
        gps_section.add_to_layout(bg_box)
        
        scroll_layout.addSpacing(10)
        
        # ─── MAP SECTION (COLLAPSIBLE) ───
        map_section = CollapsibleSection("Map")
        map_label = QLabel("(No settings available)")
        map_label.setStyleSheet("font-size: 12px; color: #999;")
        map_section.add_to_layout(map_label)
        scroll_layout.addWidget(map_section)
        
        scroll_layout.addSpacing(10)
        
        # ─── CAMERA SECTION (COLLAPSIBLE) ───
        self.camera_section = CollapsibleSection("Camera")
        camera_section = self.camera_section
        
        # ─── GRACE PERIOD SLIDER (AT TOP OF CAMERA SECTION) ───
        grace_period_layout = QHBoxLayout()
        grace_label = QLabel("No Signal Grace Period:")
        grace_label.setStyleSheet("font-size: 12px; color: #333; min-width: 160px; border: none;")
        grace_period_layout.addWidget(grace_label)
        
        saved_grace_period = int(self.config.get('camera_settings', 'grace_period_seconds', fallback='10'))
        self.grace_period_slider = QSlider(Qt.Horizontal)
        self.grace_period_slider.setMinimum(1)
        self.grace_period_slider.setMaximum(60)
        self.grace_period_slider.setStyleSheet(SLIDER_STYLESHEET)
        self.grace_period_slider.blockSignals(True)
        self.grace_period_slider.setValue(saved_grace_period)
        self.grace_period_slider.blockSignals(False)
        self.grace_period_slider.valueChanged.connect(self.on_grace_period_changed)
        self.grace_period_slider.valueChanged.connect(self.on_grace_period_released)
        grace_period_layout.addWidget(self.grace_period_slider)
        
        self.grace_period_value = QLabel(f"{saved_grace_period}s")
        self.grace_period_value.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
        grace_period_layout.addWidget(self.grace_period_value)
        grace_period_layout.addStretch()
        
        camera_section.add_layout(grace_period_layout)
        
        # Camera Label Font Size
        font_size_layout = QHBoxLayout()
        font_size_label = QLabel("Camera Label Font Size:")
        font_size_label.setStyleSheet("font-size: 12px; color: #333; min-width: 160px; border: none;")
        font_size_layout.addWidget(font_size_label)
        
        saved_label_font_size = int(self.config.get('camera_settings', 'label_font_size', fallback='16'))
        self.camera_label_font_size_slider = QSlider(Qt.Horizontal)
        self.camera_label_font_size_slider.setMinimum(8)
        self.camera_label_font_size_slider.setMaximum(32)
        self.camera_label_font_size_slider.setStyleSheet(SLIDER_STYLESHEET)
        self.camera_label_font_size_slider.blockSignals(True)
        self.camera_label_font_size_slider.setValue(saved_label_font_size)
        self.camera_label_font_size_slider.blockSignals(False)
        self.camera_label_font_size_slider.valueChanged.connect(self.save_config)
        font_size_layout.addWidget(self.camera_label_font_size_slider)
        
        self.camera_label_font_size_value = QLabel(f"{saved_label_font_size}px")
        self.camera_label_font_size_value.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 50px; border: none;")
        self.camera_label_font_size_slider.valueChanged.connect(lambda v: self.camera_label_font_size_value.setText(f"{v}px"))
        font_size_layout.addWidget(self.camera_label_font_size_value)
        font_size_layout.addStretch()
        camera_section.add_layout(font_size_layout)
        
        # Camera Label Color
        color_layout = QHBoxLayout()
        color_label = QLabel("Camera Label Color:")
        color_label.setStyleSheet("font-size: 12px; color: #333; min-width: 160px; border: none;")
        color_layout.addWidget(color_label)
        
        saved_label_color = self.config.get('camera_settings', 'label_color', fallback='white')
        self.camera_label_color_buttons = {}
        colors = {'white': '#FFFFFF', 'yellow': '#FFFF00', 'cyan': '#00FFFF', 'lime': '#00FF00', 'red': '#FF0000'}
        
        for color_name, color_hex in colors.items():
            btn = QPushButton(color_name.capitalize())
            is_selected = saved_label_color == color_name
            text_color = '#000000' if color_name in ['white', 'yellow', 'cyan', 'lime'] else '#FFFFFF'
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    color: {text_color};
                    font-size: 11px;
                    font-weight: bold;
                    padding: 6px 10px;
                    border: {'3px solid #000' if is_selected else '2px solid #ddd'};
                    border-radius: 4px;
                    min-width: 50px;
                }}
            """)
            
            btn.clicked.connect(lambda checked, c=color_name: self.set_camera_label_color(c))
            self.camera_label_color_buttons[color_name] = btn
            color_layout.addWidget(btn)
        
        color_layout.addStretch()
        camera_section.add_layout(color_layout)
        
        # Get cameras
        cameras = cam_discovery.get_cameras()
        self.camera_combos = {}
        
        if cameras:
            for cam_name in sorted(cameras.keys()):
                # Camera name header
                # Remove mDNS suffix for display
                display_cam_name = cam_name
                if '._' in display_cam_name:
                    display_cam_name = display_cam_name.split('._')[0]
                
                cam_name_label = QLabel(display_cam_name)
                cam_name_label.setStyleSheet("""
                    QLabel {
                        font-size: 12px;
                        color: #333;
                        font-weight: bold;
                        margin-top: 10px;
                        border: none;
                        outline: none;
                        background: transparent;
                    }
                """)
                camera_section.add_to_layout(cam_name_label)
                
                # Rotation buttons layout
                rotation_layout = QHBoxLayout()
                rotation_layout.setSpacing(8)
                
                rotation_buttons = {}
                saved_rotation = int(self.config.get('camera_rotations', cam_name, fallback='0'))
                
                for angle in [0, 90, 180, 270]:
                    btn = QPushButton(f"{angle}°")
                    is_selected = saved_rotation == angle
                    
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {'#007AFF' if is_selected else '#e0e0e0'};
                            color: {'#FFFFFF' if is_selected else '#333'};
                            font-size: 11px;
                            font-weight: bold;
                            padding: 8px 12px;
                            border: {'4px solid #007AFF' if is_selected else '2px solid #ddd'};
                            border-radius: 6px;
                            min-width: 50px;
                        }}
                        QPushButton:hover {{
                            border: 3px solid #007AFF;
                        }}
                        QPushButton:pressed {{
                            border: 4px solid #0051d5;
                        }}
                    """)
                    
                    # Factory function to properly capture loop variables
                    def make_rotation_handler(camera_name, rotation_angle):
                        return lambda: self.set_camera_rotation(camera_name, rotation_angle)
                    
                    btn.clicked.connect(make_rotation_handler(cam_name, angle))
                    rotation_buttons[angle] = btn
                    rotation_layout.addWidget(btn)
                
                self.camera_combos[cam_name] = rotation_buttons
                rotation_layout.addStretch()
                camera_section.add_layout(rotation_layout)
        # Don't show "No cameras found" - cameras might just be loading
        
        scroll_layout.addWidget(camera_section)
        
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        
        layout.addWidget(scroll)
        
        self.setLayout(layout)
    
    def _create_section_header(self, text):
        """Create a section header label with professional styling"""
        label = QLabel(text)
        label.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            color: white;
            background-color: #1976D2;
            padding: 10px 8px;
            border-radius: 3px;
            margin-top: 5px;
        """)
        label.setMinimumHeight(35)
        return label
    
    def _create_bordered_section(self, title):
        """Create a QGroupBox with title (no border, no frame)"""
        group = QGroupBox(title)
        group.setFlat(True)  # Remove the frame completely
        group.setStyleSheet("""
            QGroupBox {
                border: none;
                margin-top: 10px;
                padding-top: 0px;
                font-size: 12px;
                font-weight: bold;
                color: #333;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 0px;
                padding: 0px 0px 0px 0px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        group.setLayout(layout)
        return group, layout
    
    def _create_bordered_box(self, title):
        """Create a bordered box container with title"""
        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #fafafa;
                margin-top: 15px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title label (positioned at top-left border)
        title_label = QLabel(f"  {title}  ")
        title_label.setStyleSheet("""
            background-color: #f5f5f5;
            color: #333;
            font-size: 11px;
            font-weight: bold;
            padding: 2px 4px;
            margin: -8px 10px 0px 10px;
        """)
        layout.addWidget(title_label, alignment=Qt.AlignTop)
        
        # Content area
        self._current_box_content = QVBoxLayout()
        self._current_box_content.setContentsMargins(15, 10, 15, 10)
        self._current_box_content.setSpacing(12)
        
        layout.addLayout(self._current_box_content)
        container.setLayout(layout)
        
        return container, self._current_box_content
    
    def hsv_to_rgb(self, h, s, v):
        """Convert HSV (0-360, 0-100, 0-100) to RGB (0-255, 0-255, 0-255)"""
        h = h / 60.0
        s = s / 100.0
        v = v / 100.0
        
        c = v * s
        x = c * (1 - abs((h % 2) - 1))
        m = v - c
        
        if h < 1:
            r, g, b = c, x, 0
        elif h < 2:
            r, g, b = x, c, 0
        elif h < 3:
            r, g, b = 0, c, x
        elif h < 4:
            r, g, b = 0, x, c
        elif h < 5:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        
        return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))
    
    def set_coord_color(self, color_name):
        """Set coordinate color and update button styling"""
        self.selected_coord_color = color_name
        
        # Update button styling
        colors = {
            'yellow': '#FFFF00',
            'white': '#FFFFFF',
            'cyan': '#00FFFF',
            'lime': '#00FF00',
            'red': '#FF0000',
            'orange': '#FFA500',
        }
        
        for name, btn in self.coord_color_buttons.items():
            color_hex = colors[name]
            text_color = '#000000' if name in ['yellow', 'white', 'cyan', 'lime'] else '#FFFFFF'
            border = '#000000' if name == color_name else '#ccc'
            border_width = '3px' if name == color_name else '2px'
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    color: {text_color};
                    font-size: 11px;
                    font-weight: bold;
                    padding: 8px 12px;
                    border: {border_width} solid {border};
                    border-radius: 4px;
                    min-width: 60px;
                }}
                QPushButton:pressed {{
                    border: 3px solid #333;
                }}
            """)
        
        self.save_config()
    
    def set_meta_color(self, color_name):
        """Set metadata color and update button styling"""
        self.selected_meta_color = color_name
        
        # Update button styling
        colors = {
            'yellow': '#FFFF00',
            'white': '#FFFFFF',
            'cyan': '#00FFFF',
            'lime': '#00FF00',
            'red': '#FF0000',
            'orange': '#FFA500',
        }
        
        for name, btn in self.meta_color_buttons.items():
            color_hex = colors[name]
            text_color = '#000000' if name in ['yellow', 'white', 'cyan', 'lime'] else '#FFFFFF'
            border = '#000000' if name == color_name else '#ccc'
            border_width = '3px' if name == color_name else '2px'
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    color: {text_color};
                    font-size: 11px;
                    font-weight: bold;
                    padding: 8px 12px;
                    border: {border_width} solid {border};
                    border-radius: 4px;
                    min-width: 60px;
                }}
                QPushButton:pressed {{
                    border: 3px solid #333;
                }}
            """)
        
        self.save_config()
    
    def set_bg_color(self, color_name):
        """Set background color and update button styling"""
        self.selected_bg_color = color_name
        
        # Update button styling - highlight selected color
        bg_colors = {
            'black': (0, 0, 40),
            'blue': (225, 100, 40),
            'green': (114, 100, 40),
            'red': (0, 100, 40),
        }
        
        for name, btn in self.bg_color_buttons.items():
            hsv = bg_colors[name]
            rgb_max = self.hsv_to_rgb(hsv[0], hsv[1], hsv[2])
            rgb_hex = f"#{rgb_max[0]:02x}{rgb_max[1]:02x}{rgb_max[2]:02x}"
            border = '#FFFFFF' if name == color_name else '#ccc'
            border_width = '3px' if name == color_name else '2px'
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {rgb_hex};
                    color: #FFFFFF;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 8px 15px;
                    border: {border_width} solid {border};
                    border-radius: 3px;
                    min-width: 70px;
                }}
                QPushButton:pressed {{
                    border: 3px solid #FFF;
                }}
            """)
        
        self.save_config()
        self.update_coords_background()
    
    def on_bg_brightness_changed(self, value):
        """Handle background brightness slider change - update COORDS tab in real-time"""
        self.bg_brightness_value.setText(str(value))
        self.update_coords_background()
    
    def on_grace_period_changed(self, value):
        """Handle grace period slider change - update display value"""
        self.grace_period_value.setText(f"{value}s")
    
    def on_grace_period_released(self):
        """Handle grace period slider release - save to config immediately"""
        value = self.grace_period_slider.value()
        if not self.config.has_section('camera_settings'):
            self.config.add_section('camera_settings')
        self.config.set('camera_settings', 'grace_period_seconds', str(value))
        
        config_file = os.path.expanduser("~/Projects/seeboard/see_board.cfg")
        with open(config_file, 'w') as f:
            self.config.write(f)
    
    def set_camera_label_color(self, color_name):
        """Set camera label color and update button styling"""
        # Update button styling
        colors = {'white': '#FFFFFF', 'yellow': '#FFFF00', 'cyan': '#00FFFF', 'lime': '#00FF00', 'red': '#FF0000'}
        
        for name, btn in self.camera_label_color_buttons.items():
            color_hex = colors[name]
            text_color = '#000000' if name in ['white', 'yellow', 'cyan', 'lime'] else '#FFFFFF'
            border = '#000000' if name == color_name else '#ccc'
            border_width = '3px' if name == color_name else '2px'
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    color: {text_color};
                    font-size: 11px;
                    font-weight: bold;
                    padding: 6px 10px;
                    border: {border_width} solid {border};
                    border-radius: 4px;
                    min-width: 50px;
                }}
            """)
        
        self.save_config()
    
    def update_coords_background(self):
        """Update the COORDS tab background based on current color and brightness"""
        brightness = self.bg_brightness_slider.value()
        color_name = self.selected_bg_color
        
        # HSV color definitions
        bg_colors = {
            'black': (0, 0, 40),
            'blue': (225, 100, 40),
            'green': (114, 100, 40),
            'red': (0, 100, 40),
        }
        
        hsv = bg_colors.get(color_name, (0, 0, 40))
        h, s, v_max = hsv
        v = (brightness / 100.0) * v_max
        rgb = self.hsv_to_rgb(h, s, v)
        bg_color_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        
        # Update COORDS tab
        if self.main_window:
            self.main_window.coords_tab.setStyleSheet(f"background-color: {bg_color_hex};")
    
    
    
    def on_tab_shown(self):
        """Called when CONF tab becomes visible - refresh camera list"""
        import cam_discovery as cam_disc
        
        # Get current cameras
        cameras = cam_disc.get_cameras()
        
        # Get expired cameras from CAM tab
        expired_urls = set()
        if self.main_window and hasattr(self.main_window, 'cam_tab'):
            expired_urls = set(self.main_window.cam_tab.expired_cameras.keys())
        
        # Rebuild camera section with fresh list
        if self.camera_section:
            # Clear ONLY camera items (skip first 3: grace period label, slider, value)
            # Count how many widgets to skip (grace period takes 3 widget slots)
            items_to_keep = 3  # grace_label, grace_period_slider container, grace_period_value
            
            # Remove everything AFTER the grace period widgets
            while self.camera_section.content_layout.count() > items_to_keep:
                item = self.camera_section.content_layout.takeAt(items_to_keep)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    # It's a layout, delete its widgets
                    while item.layout().count():
                        child_item = item.layout().takeAt(0)
                        if child_item.widget():
                            child_item.widget().deleteLater()
            
            # Re-add cameras if found
            self.camera_combos = {}
            
            if cameras and len(cameras) > 0:
                for cam_name in sorted(cameras.keys()):
                    # Skip expired cameras - don't show in CONF tab
                    cam_url = cameras[cam_name]
                    if cam_url in expired_urls:
                        continue
                    
                    # Camera name header
                    # Remove mDNS suffix for display
                    display_cam_name = cam_name
                    if '._' in display_cam_name:
                        display_cam_name = display_cam_name.split('._')[0]
                    
                    cam_name_label = QLabel(display_cam_name)
                    cam_name_label.setStyleSheet("""
                        QLabel {
                            font-size: 12px;
                            color: #333;
                            font-weight: bold;
                            margin-top: 10px;
                            border: none;
                            outline: none;
                            background: transparent;
                        }
                    """)
                    self.camera_section.add_to_layout(cam_name_label)
                    
                    # Rotation buttons layout
                    rotation_layout = QHBoxLayout()
                    rotation_layout.setSpacing(8)
                    
                    rotation_buttons = {}
                    saved_rotation = int(self.config.get('camera_rotations', cam_name, fallback='0'))
                    
                    for angle in [0, 90, 180, 270]:
                        btn = QPushButton(f"{angle}°")
                        is_selected = saved_rotation == angle
                        
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#007AFF' if is_selected else '#e0e0e0'};
                                color: {'#FFFFFF' if is_selected else '#333'};
                                font-size: 11px;
                                font-weight: bold;
                                padding: 8px 12px;
                                border: {'4px solid #007AFF' if is_selected else '2px solid #ddd'};
                                border-radius: 6px;
                                min-width: 50px;
                            }}
                            QPushButton:hover {{
                                border: 3px solid #007AFF;
                            }}
                            QPushButton:pressed {{
                                border: 4px solid #0051d5;
                            }}
                        """)
                        
                        # Factory function to properly capture loop variables
                        def make_rotation_handler(camera_name, rotation_angle):
                            return lambda: self.set_camera_rotation(camera_name, rotation_angle)
                        
                        btn.clicked.connect(make_rotation_handler(cam_name, angle))
                        rotation_buttons[angle] = btn
                        rotation_layout.addWidget(btn)
                    
                    self.camera_combos[cam_name] = rotation_buttons
                    rotation_layout.addStretch()
                    self.camera_section.add_layout(rotation_layout)
            # Don't show "No cameras found" - cameras might just be loading
            # Keep previous camera list visible if discovery didn't find anything yet
    
    def set_camera_rotation(self, camera_name, angle):
        """Set camera rotation and update button styling"""
        try:
            if not self.config.has_section('camera_rotations'):
                self.config.add_section('camera_rotations')
            
            # Ensure camera_name is string
            if not isinstance(camera_name, str):
                camera_name = str(camera_name)
            
            self.config.set('camera_rotations', camera_name, str(angle))
            
            # Update button styling
            if camera_name in self.camera_combos:
                buttons_dict = self.camera_combos[camera_name]
                
                # Handle both dict (rotation buttons) and old QComboBox
                if isinstance(buttons_dict, dict):
                    for angle_btn, btn in buttons_dict.items():
                        is_selected = angle_btn == angle
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#007AFF' if is_selected else '#e0e0e0'};
                                color: {'#FFFFFF' if is_selected else '#333'};
                                font-size: 11px;
                                font-weight: bold;
                                padding: 8px 12px;
                                border: {'4px solid #007AFF' if is_selected else '2px solid #ddd'};
                                border-radius: 6px;
                                min-width: 50px;
                            }}
                            QPushButton:hover {{
                                border: 3px solid #007AFF;
                            }}
                            QPushButton:pressed {{
                                border: 4px solid #0051d5;
                            }}
                        """)
            
            self.save_config()
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def save_config(self):
        """Save configuration to file (called on every change)"""
        # DMS decimals
        self.config.set('gps', 'show_dms_decimals', str(self.dms_checkbox.isChecked()))
        gps_core.SHOW_DMS_DECIMALS = self.dms_checkbox.isChecked()
        
        # Coordinate font size
        self.config.set('gps', 'coord_font_size', str(self.font_size_slider.value()))
        
        # Coordinate color
        self.config.set('gps', 'coord_color', self.selected_coord_color)
        
        # Metadata font size
        self.config.set('gps', 'meta_font_size', str(self.meta_font_size_slider.value()))
        
        # Metadata color
        self.config.set('gps', 'meta_color', self.selected_meta_color)
        
        # Background color and brightness
        if not self.config.has_section('coords'):
            self.config.add_section('coords')
        self.config.set('coords', 'bg_color', self.selected_bg_color)
        self.config.set('coords', 'bg_brightness', str(self.bg_brightness_slider.value()))
        
        # Camera settings (label font size and color)
        if not self.config.has_section('camera_settings'):
            self.config.add_section('camera_settings')
        self.config.set('camera_settings', 'label_font_size', str(self.camera_label_font_size_slider.value()))
        # Find selected camera label color
        for color_name, btn in self.camera_label_color_buttons.items():
            if '3px solid' in btn.styleSheet():
                self.config.set('camera_settings', 'label_color', color_name)
                break
        
        # Per-camera rotations
        if not self.config.has_section('camera_rotations'):
            self.config.add_section('camera_rotations')
        
        for cam_name, buttons_dict in self.camera_combos.items():
            # buttons_dict is now a dict of angle -> button, not a QComboBox
            if isinstance(buttons_dict, dict):
                # Find which button is selected (has blue background)
                # For now, we've already saved it in set_camera_rotation()
                # so we just need to make sure the config is written
                pass
            else:
                # Legacy support if somehow still a QComboBox
                rotation = buttons_dict.currentIndex() * 90
                self.config.set('camera_rotations', cam_name, str(rotation))
        
        # Write config file
        config_file = os.path.expanduser("~/Projects/seeboard/see_board.cfg")
        with open(config_file, 'w') as f:
            self.config.write(f)


class PathsTab(QWidget):
    """Paths Tab - shows existing recorded paths"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("Recorded Paths")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # Paths list
        self.paths_list = QListWidget()
        self.paths_list.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:hover {
                background-color: #e8e8e8;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
        """)
        layout.addWidget(self.paths_list)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_paths)
        layout.addWidget(refresh_btn)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Load paths on startup
        self.refresh_paths()
    
    def refresh_paths(self):
        """Refresh the list of recorded paths from database"""
        self.paths_list.clear()
        
        try:
            # Get paths from global route recorder's database
            if global_route_recorder and global_route_recorder.db and global_route_recorder.db.connection:
                cursor = global_route_recorder.db.connection.cursor()
                cursor.execute("SELECT route_id, name FROM routes ORDER BY created_at DESC")
                rows = cursor.fetchall()
                
                if rows:
                    for row in rows:
                        path_name = row[1]  # name column
                        item = QListWidgetItem(path_name)
                        self.paths_list.addItem(item)
                else:
                    item = QListWidgetItem("No paths recorded yet")
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                    self.paths_list.addItem(item)
            else:
                item = QListWidgetItem("Path database not initialized")
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.paths_list.addItem(item)
        except Exception as e:
            print(f"[PATHS] Error loading paths: {e}")
            item = QListWidgetItem(f"Error: {str(e)}")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.paths_list.addItem(item)


class SeeBoardApp(QMainWindow):
    """Main Application"""
    
    # Tab names - easily configurable in one place
    TAB_NAMES = {
        'coords': 'GPS',
        'map': 'MAP',
        'paths': 'PATHS',
        'cam': 'CAM',
        'conf': 'CONF'
    }
    
    def __init__(self):
        super().__init__()
        
        # Load config
        config_file = os.path.expanduser("~/Projects/seeboard/see_board.cfg")
        self.config = ConfigParser()
        self.config.read(config_file)
        
        for section in ['gps', 'coords', 'route_recording', 'camera_rotations', 'cam']:
            if not self.config.has_section(section):
                self.config.add_section(section)
        
        self.setWindowTitle("seeBoard - GPS & Camera Dashboard")
        self.setGeometry(100, 100, 800, 600)
        
        # Create tabs
        self.tabs = QTabWidget()
        self.coords_tab = CoordsTab(self.config)
        self.map_tab = MapTab(self.config)
        self.paths_tab = PathsTab(self.config)
        self.cam_tab = CamTab(self.config)
        self.conf_tab = ConfTab(self.config, self)
        
        self.tabs.addTab(self.coords_tab, self.TAB_NAMES['coords'])
        self.tabs.addTab(self.map_tab, self.TAB_NAMES['map'])
        self.tabs.addTab(self.paths_tab, self.TAB_NAMES['paths'])
        self.tabs.addTab(self.cam_tab, self.TAB_NAMES['cam'])
        self.tabs.addTab(self.conf_tab, self.TAB_NAMES['conf'])
        
        # Connect tab change signal
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        self.setCentralWidget(self.tabs)
        
        # Start backend services
        print("[APP] Starting backend services...")
        gps_core.start_background_reader()
        cam_discovery.start()
        start_new_cameras()
    
    def on_tab_changed(self, index):
        """Handle tab change - refresh settings on visible tabs"""
        current_tab = self.tabs.currentWidget()
        if hasattr(current_tab, 'on_tab_shown'):
            current_tab.on_tab_shown()
    
    def closeEvent(self, event):
        print("[APP] Shutting down...")
        stop_all_cameras()
        try:
            gps_core.stop_background_reader()
        except:
            pass
        try:
            cam_discovery.stop()
        except:
            pass
        try:
            self.coords_tab.gps_worker.stop()
            self.coords_tab.gps_worker.wait(1000)
        except:
            pass
        print("[APP] Shutdown complete")
        event.accept()


def main():
    init_route_recorder()
    app = QApplication(sys.argv)
    window = SeeBoardApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
