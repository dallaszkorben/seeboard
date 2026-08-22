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
from route_database import PathDatabase
from route_recorder import RouteRecorder
from map_renderer import MapRenderer, MapCache
from config_loader import ConfigLoader

# Global route recorder
_db = None
global_route_recorder = None

def init_route_recorder():
    global _db, global_route_recorder
    _db = PathDatabase()
    global_route_recorder = RouteRecorder(_db)


def create_styled_button(text, bg_color_hex, text_color, state='active', width=None, height=None):
    """
    Create a styled button with consistent appearance across the app
    
    Args:
        text: Button text
        bg_color_hex: Background color in hex format (#RRGGBB)
        text_color: Text color (name or hex)
        state: Button state - 'active' (enabled, clickable), 'selected' (active with highlight), or 'inactive' (disabled, grey)
        width: Optional fixed width in pixels
        height: Optional fixed height in pixels
    
    Returns:
        QPushButton with applied stylesheet
    """
    btn = QPushButton(text)
    
    if state == 'active':
        # Active state: enabled, bright color, no special border
        stylesheet = f"""
            QPushButton {{
                background-color: {bg_color_hex};
                color: {text_color};
                font-size: 12px;
                font-weight: bold;
                padding: 10px 15px;
                border: 2px solid #ddd;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border: 2px solid #007AFF;
                background-color: {bg_color_hex};
            }}
            QPushButton:pressed {{
                border: 2px solid #0051d5;
                background-color: {_darken_color(bg_color_hex, 20)};
            }}
        """
        btn.setEnabled(True)
    
    elif state == 'selected':
        # Selected state: enabled, bright color, blue border to show it's selected
        hover_color = _lighten_color(bg_color_hex, 15)
        pressed_color = _darken_color(bg_color_hex, 25)
        stylesheet = f"""
            QPushButton {{
                background-color: {bg_color_hex};
                color: {text_color};
                font-size: 12px;
                font-weight: bold;
                padding: 10px 15px;
                border: 4px solid #007AFF;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border: 4px solid #0051d5;
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                border: 4px solid #003d9e;
                background-color: {pressed_color};
            }}
        """
        btn.setEnabled(True)
    
    elif state == 'inactive':
        # Inactive state: disabled, grey color
        stylesheet = """
            QPushButton {
                background-color: #999999;
                color: #666666;
                font-size: 12px;
                font-weight: bold;
                padding: 10px 15px;
                border: 2px solid #777777;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #999999;
                border: 2px solid #777777;
            }
            QPushButton:pressed {
                background-color: #999999;
                border: 2px solid #777777;
            }
        """
        btn.setEnabled(False)
    
    btn.setStyleSheet(stylesheet)
    
    if width is not None and height is not None:
        btn.setFixedSize(width, height)
    elif width is not None:
        btn.setMinimumWidth(width)
    elif height is not None:
        btn.setFixedHeight(height)
    
    return btn


def _lighten_color(hex_color, amount):
    """Lighten a hex color by the given amount"""
    hex_color = hex_color.lstrip('#')
    r = min(255, int(hex_color[0:2], 16) + amount)
    g = min(255, int(hex_color[2:4], 16) + amount)
    b = min(255, int(hex_color[4:6], 16) + amount)
    return f'#{r:02x}{g:02x}{b:02x}'


def _darken_color(hex_color, amount):
    """Darken a hex color by the given amount"""
    hex_color = hex_color.lstrip('#')
    r = max(0, int(hex_color[0:2], 16) - amount)
    g = max(0, int(hex_color[2:4], 16) - amount)
    b = max(0, int(hex_color[4:6], 16) - amount)
    return f'#{r:02x}{g:02x}{b:02x}'

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
        
        # Load background color using centralized config loader
        brightness = self.config.get_int('coords', 'bg_brightness', default=0)
        color_name = self.config.get_str('coords', 'bg_color', default='black')
        
        # Ensure coords section exists and save defaults if not present
        self.config.ensure_section('coords')
        if brightness == 0:
            self.config.set_value('coords', 'bg_brightness', 0)
        if color_name == 'black':
            self.config.set_value('coords', 'bg_color', color_name)
        
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
        
        # ─── COORDINATES CONTAINER (lat/lon together) ───
        coords_container = QWidget()
        coords_layout = QVBoxLayout()
        coords_layout.setContentsMargins(0, 0, 0, 0)
        coords_layout.setSpacing(-5)
        coords_layout.addStretch()  # Add space before
        
        try:
            coord_font_size = self.config.get_int('gps', 'coord_font_size', default=65)
            color_name = self.config.get_str('gps', 'coord_color', default='lime')
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
        self.lat_label.setStyleSheet(f"color: {color_hex}; background-color: transparent; margin: 0px; padding: 0px;")
        self.lat_label.setAlignment(Qt.AlignCenter)
        coords_layout.addWidget(self.lat_label)
        
        self.lon_label = QLabel("---°--'--\"")
        self.lon_label.setFont(QFont("Helvetica", coord_font_size, QFont.Bold))
        self.lon_label.setStyleSheet(f"color: {color_hex}; background-color: transparent; margin: 0px; padding: 0px;")
        self.lon_label.setAlignment(Qt.AlignCenter)
        coords_layout.addWidget(self.lon_label)
        
        coords_layout.addStretch()  # Add space after
        coords_container.setLayout(coords_layout)
        layout.addWidget(coords_container, 1)  # Stretch top
        
        # ─── METADATA CONTAINER (time, quality, satellites) ───
        metadata_container = QWidget()
        south_layout = QVBoxLayout()
        south_layout.setContentsMargins(10, 5, 10, 5)
        south_layout.setSpacing(2)
        
        meta_font_size = self.config.get_int('gps', 'meta_font_size', default=12)
        meta_color_name = self.config.get_str('gps', 'meta_color', default='white')
        meta_color_hex = color_map.get(meta_color_name, '#FFFFFF')
        
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
        
        metadata_container.setLayout(south_layout)
        layout.addWidget(metadata_container, 0)  # No stretch bottom
        
        self.setLayout(layout)
    
    def on_tab_shown(self):
        """Called when this tab becomes visible - reload config"""
        gps_core.SHOW_DMS_DECIMALS = self.config.get_bool('gps', 'show_dms_decimals', default=False)
        
        # Reload coordinates font and color
        font_size = self.config.get_int('gps', 'coord_font_size', default=65)
        color_name = self.config.get_str('gps', 'coord_color', default='lime')
        color_map = {
            'yellow': '#FFFF00',
            'white': '#FFFFFF',
            'cyan': '#00FFFF',
            'lime': '#00FF00',
            'red': '#FF0000',
            'orange': '#FFA500',
        }
        color_hex = color_map.get(color_name, '#00FF00')
        
        self.lat_label.setFont(QFont("Helvetica", font_size, QFont.Bold))
        self.lon_label.setFont(QFont("Helvetica", font_size, QFont.Bold))
        self.lat_label.setStyleSheet(f"color: {color_hex}; background-color: transparent;")
        self.lon_label.setStyleSheet(f"color: {color_hex}; background-color: transparent;")
        
        # Reload metadata font and color
        meta_font_size = self.config.get_int('gps', 'meta_font_size', default=12)
        meta_color_name = self.config.get_str('gps', 'meta_color', default='white')
        meta_color_hex = color_map.get(meta_color_name, '#FFFFFF')
        
        self.time_label.setFont(QFont("Helvetica", meta_font_size))
        self.qual_label.setFont(QFont("Helvetica", meta_font_size))
        self.sat_label.setFont(QFont("Helvetica", meta_font_size))
        self.recording_label.setFont(QFont("Helvetica", meta_font_size))
        self.status_label.setFont(QFont("Helvetica", meta_font_size))
        self.time_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.qual_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.sat_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        
        # Reload background color - PALETTE METHOD (strongest)
        brightness = self.config.get_int('coords', 'bg_brightness', default=0)
        color_name = self.config.get_str('coords', 'bg_color', default='black')
        
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
            color_name = self.config.get_str('gps', 'coord_color', default='lime')
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
        
        # Recording state
        self.is_recording = False
        self.current_recording_path_id = None
        self.current_recording_color = None
        self.map_mode = "FREE"  # FREE or FOLLOW
        
        # Initialize route recorder
        from route_database import PathDatabase
        from route_recorder import RouteRecorder
        self.db = PathDatabase()
        self.recorder = RouteRecorder(self.db)
        
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
        
        # Recording buttons
        rec_button_layout = QHBoxLayout()
        rec_button_layout.setContentsMargins(5, 5, 5, 5)
        rec_button_layout.setSpacing(5)
        
        # REC button: Green, active state
        self.rec_btn = create_styled_button("REC", "#00CC00", "white", state='active')
        self.rec_btn.clicked.connect(self.start_recording)
        rec_button_layout.addWidget(self.rec_btn, 1)  # Stretch factor = 1
        
        # STOP button: Red, inactive state (until recording starts)
        self.stop_btn = create_styled_button("STOP", "#FF4444", "white", state='inactive')
        self.stop_btn.clicked.connect(self.stop_recording)
        rec_button_layout.addWidget(self.stop_btn, 1)  # Stretch factor = 1
        
        layout.addLayout(rec_button_layout, 0)  # No stretch
        self.setLayout(layout)
        
        # Timer for render updates (only on demand)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.render_if_needed)
        self.update_timer.timeout.connect(self.record_gps_point_if_needed)
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
        
        # If in FOLLOW mode, center on GPS position
        if self.map_mode == "FOLLOW":
            self.map_center_lat = self.current_lat
            self.map_center_lon = self.current_lon
        
        # If GPS position changed, re-render to update marker position
        if (self.current_lat != old_lat or self.current_lon != old_lon):
            self.needs_render = True
        # Don't update map_center in FREE mode - stays where user moved it
    
    def render_if_needed(self):
        """Only render if something changed"""
        if self.needs_render:
            self.render_map()
            self.needs_render = False
    
    def render_map(self):
        """Render map at current map center"""
        try:
            # Use label size or default
            width = self.map_label.width() if self.map_label.width() > 100 else 800
            height = self.map_label.height() if self.map_label.height() > 100 else 600
            
            # Create renderer with actual widget dimensions
            renderer = MapRenderer(width=width, height=height)
            
            # Get current recording path points if recording
            route_points = None
            if self.is_recording and self.current_recording_path_id:
                current_points = self.recorder.get_current_route_points()
                if current_points:
                    route_points = [
                        (p['latitude'], p['longitude'])
                        for p in current_points
                    ]
            
            # Get visible paths to display
            visible_paths = self.get_visible_paths()
            
            # Render map centered on map_center, with GPS position as marker
            pixmap = renderer.render_map(
                lat=self.map_center_lat,
                lon=self.map_center_lon,
                gps_lat=self.current_lat,
                gps_lon=self.current_lon,
                zoom=self.zoom,
                route_points=route_points,
                coverage_radius=None,
                path_color=self.current_recording_color or 'RED',
                position_radius=self.config.get_int('map', 'position_radius', default=2),
                position_font_size=self.config.get_int('map', 'position_font_size', default=8),
                path_width=self.config.get_int('map', 'path_width', default=1),
                visible_paths=visible_paths
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
    
    def get_visible_paths(self):
        """Get list of visible recorded paths from database with their points
        
        Returns:
            List of dicts: [{
                'path_id': int,
                'name': str,
                'color': str,
                'points': [(lat, lon), ...],
                'width': int
            }, ...]
        """
        visible_paths = []
        try:
            if global_route_recorder and global_route_recorder.db and global_route_recorder.db.connection:
                cursor = global_route_recorder.db.connection.cursor()
                
                # Get all visible paths
                cursor.execute("""
                    SELECT path_id, name, color, line_width 
                    FROM paths 
                    WHERE is_visible = 1 
                    ORDER BY created_at DESC
                """)
                paths = cursor.fetchall()
                
                for path_row in paths:
                    path_id = path_row[0]
                    path_name = path_row[1]
                    path_color = path_row[2] or 'RED'
                    path_width = path_row[3] or 1
                    
                    # Get all points for this path
                    cursor.execute("""
                        SELECT latitude, longitude 
                        FROM path_points 
                        WHERE path_id = ? 
                        ORDER BY sequence ASC
                    """, (path_id,))
                    points = cursor.fetchall()
                    
                    if points:
                        visible_paths.append({
                            'path_id': path_id,
                            'name': path_name,
                            'color': path_color,
                            'points': [(p[0], p[1]) for p in points],
                            'width': path_width
                        })
        except Exception as e:
            print(f"[MAP] Error getting visible paths: {e}")
        
        return visible_paths
    
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
    
    def start_recording(self):
        """Start recording a new path"""
        if self.is_recording:
            return
        
        # Get recording color from config
        self.current_recording_color = self.config.get_str('map', 'recording_color', default='RED')
        
        # Create recording config
        recording_config = {
            'line_color': self.current_recording_color,
            'line_width': 3,
            'line_style': 'continuous',
            'sampling_mode': 'time',  # Use time-based sampling
            'sampling_value': float(self.config.get_str('map', 'time_based_sampling', default='15s').rstrip('s'))
        }
        
        # Start recording
        self.current_recording_path_id = self.recorder.start_recording(
            {
                'lat': self.current_lat,
                'lon': self.current_lon,
                'lat_raw': self.current_lat,
                'lon_raw': self.current_lon
            },
            recording_config
        )
        
        self.is_recording = True
        self.map_mode = "FOLLOW"
        
        # Update button states with new style
        self._update_recording_button_styles()
        
        print(f"[MAP] Recording started: path_id={self.current_recording_path_id}, color={self.current_recording_color}")
        self.needs_render = True
    
    def stop_recording(self):
        """Stop recording the current path"""
        if not self.is_recording:
            return
        
        # Stop recorder
        stopped_id = self.recorder.stop_recording()
        
        self.is_recording = False
        self.map_mode = "FREE"
        self.current_recording_path_id = None
        
        # Update button states with new style
        self._update_recording_button_styles()
        
        print(f"[MAP] Recording stopped: path_id={stopped_id}")
        self.needs_render = True
    
    def _update_recording_button_styles(self):
        """Update REC/STOP button styles based on recording state"""
        if self.is_recording:
            # Recording: REC is inactive (grey), STOP is selected (red with blue border)
            self.rec_btn.setStyleSheet(create_styled_button("REC", "#00CC00", "white", state='inactive').styleSheet())
            self.rec_btn.setEnabled(False)
            
            self.stop_btn.setStyleSheet(create_styled_button("STOP", "#FF4444", "white", state='selected').styleSheet())
            self.stop_btn.setEnabled(True)
        else:
            # Not recording: REC is active (green), STOP is inactive (grey)
            self.rec_btn.setStyleSheet(create_styled_button("REC", "#00CC00", "white", state='active').styleSheet())
            self.rec_btn.setEnabled(True)
            
            self.stop_btn.setStyleSheet(create_styled_button("STOP", "#FF4444", "white", state='inactive').styleSheet())
            self.stop_btn.setEnabled(False)
    
    def record_gps_point_if_needed(self):
        """Check if we should record current GPS point based on sampling criteria"""
        if not self.is_recording or not self.gps_data:
            return
        
        # Check if we should record this point
        if self.recorder.should_record_point(self.gps_data):
            # Record it with full GPS data
            point_id = self.recorder.add_point(self.gps_data)
            if point_id:
                print(f"[MAP] Point recorded: point_id={point_id}")
                self.needs_render = True
    
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
        # Config is automatically persisted by ConfigLoader, no need to reload
        pass
    
    def update_display(self):
        """Update camera display"""
        try:
            start_new_cameras()
            urls = list(_streams.keys())
            grace_period = self.config.get_int('camera_settings', 'grace_period_seconds', default=5)
            
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
                    if self.config.config.has_section('camera_rotations'):
                        for opt in self.config.config.options('camera_rotations'):
                            if hostname in opt:
                                rot = self.config.get_int('camera_rotations', opt, default=0)
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
                font_size = self.config.get_int('camera_settings', 'label_font_size', default=16)
                color_name = self.config.get_str('camera_settings', 'label_color', default='white')
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
        # Common color button stylesheet template
        def get_button_stylesheet(bg_color_hex, text_color, is_selected):
            return f"""
                QPushButton {{
                    background-color: {bg_color_hex};
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
                    background-color: {bg_color_hex};
                }}
                QPushButton:pressed {{
                    border: 4px solid #0051d5;
                }}
            """
        
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
            self.config.get_bool('gps', 'show_dms_decimals', default=False))
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
        font_size = self.config.get_int('gps', 'coord_font_size', default=65)
        self.font_size_slider.setValue(font_size)
        
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
        
        saved_coord_color = self.config.get_str('gps', 'coord_color', default='lime')
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
            btn.setStyleSheet(get_button_stylesheet(color_hex, text_color, is_selected))
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
            meta_font_size = self.config.get_int('gps', 'meta_font_size', default=12)
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
        
        saved_meta_color = self.config.get_str('gps', 'meta_color', default='white')
        self.meta_color_buttons = {}
        
        for color_name, color_hex in colors.items():
            btn = QPushButton(color_name.upper())
            text_color = '#000000' if color_name in ['yellow', 'white', 'cyan', 'lime'] else '#FFFFFF'
            is_selected = saved_meta_color == color_name
            btn.setStyleSheet(get_button_stylesheet(color_hex, text_color, is_selected))
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
        
        saved_bg_color = self.config.get_str('coords', 'bg_color', default='black')
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
            btn.setStyleSheet(get_button_stylesheet(rgb_hex, '#FFFFFF', is_selected))
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
        
        saved_brightness = self.config.get_int('coords', 'bg_brightness', default=0)
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
        
        # Record group box (with 1px border)
        record_box = QGroupBox("Record")
        record_box.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                font-size: 12px;
                font-weight: bold;
                color: #333;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0px 5px 0px 0px;
            }
        """)
        record_layout = QVBoxLayout()
        record_layout.setContentsMargins(10, 5, 10, 5)
        record_layout.setSpacing(5)
        
        # Time based sampling
        time_layout = QHBoxLayout()
        time_label = QLabel("Time based:")
        time_label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
        time_layout.addWidget(time_label)
        
        self.time_buttons = {}
        times = ["10s", "15s", "20s", "30s"]
        
        # Load saved time selection
        saved_time = self.config.get_str('map', 'time_based_sampling', default='15s')
        
        for time_str in times:
            btn = QPushButton(time_str)
            is_selected = time_str == saved_time
            btn.setStyleSheet(get_button_stylesheet("#2196F3", "white", is_selected))
            btn.setCheckable(True)
            btn.setChecked(is_selected)
            btn.clicked.connect(lambda checked, t=time_str: self.on_time_selected(t))
            self.time_buttons[time_str] = btn
            time_layout.addWidget(btn)
        
        self.selected_time = saved_time
        
        time_layout.addStretch()
        record_layout.addLayout(time_layout)
        
        # Color for recording path
        color_layout = QHBoxLayout()
        color_label = QLabel("Path color:")
        color_label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
        color_layout.addWidget(color_label)
        
        saved_rec_color = self.config.get_str('map', 'recording_color', default='RED')
        self.rec_color_buttons = {}
        rec_colors = {
            'RED': '#FF0000',
            'BLUE': '#0000FF',
            'GREEN': '#00FF00',
            'YELLOW': '#FFFF00',
            'CYAN': '#00FFFF',
            'MAGENTA': '#FF00FF',
            'ORANGE': '#FFA500',
            'PURPLE': '#800080',
        }
        
        for color_name, color_hex in rec_colors.items():
            btn = QPushButton()
            text_color = '#000000' if color_name in ['YELLOW', 'CYAN'] else '#FFFFFF'
            is_selected = saved_rec_color == color_name
            btn.setMinimumWidth(60)
            btn.setMaximumWidth(60)
            btn.setFixedHeight(30)
            # Use narrow stylesheet without min/max width constraints
            stylesheet = f"""
                QPushButton {{
                    background-color: {color_hex};
                    color: {text_color};
                    font-size: 10px;
                    font-weight: bold;
                    padding: 6px 2px;
                    border: {'4px solid #007AFF' if is_selected else '2px solid #ddd'};
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 3px solid #007AFF;
                    background-color: {color_hex};
                }}
                QPushButton:pressed {{
                    border: 4px solid #0051d5;
                }}
            """
            btn.setStyleSheet(stylesheet)
            btn.clicked.connect(lambda checked, c=color_name: self.on_rec_color_selected(c))
            self.rec_color_buttons[color_name] = btn
            color_layout.addWidget(btn)
        
        self.selected_rec_color = saved_rec_color
        color_layout.addStretch()
        record_layout.addLayout(color_layout)
        
        # Path width slider
        path_width_layout = QHBoxLayout()
        path_width_label = QLabel("Path width:")
        path_width_label.setStyleSheet("font-size: 12px; color: #333; min-width: 100px; border: none;")
        path_width_layout.addWidget(path_width_label)
        
        self.path_width_slider = QSlider(Qt.Horizontal)
        self.path_width_slider.setMinimum(1)
        self.path_width_slider.setMaximum(8)
        self.path_width_slider.setStyleSheet(SLIDER_STYLESHEET)
        path_width = self.config.get_int('map', 'path_width', default=1)
        self.path_width_slider.setValue(path_width)
        
        self.path_width_slider.valueChanged.connect(self.save_config)
        path_width_layout.addWidget(self.path_width_slider)
        
        self.path_width_value = QLabel(str(self.path_width_slider.value()))
        self.path_width_value.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
        self.path_width_slider.valueChanged.connect(lambda v: self.path_width_value.setText(str(v)))
        path_width_layout.addWidget(self.path_width_value)
        record_layout.addLayout(path_width_layout)
        
        # Position radius slider
        radius_layout = QHBoxLayout()
        radius_label = QLabel("Position radius:")
        radius_label.setStyleSheet("font-size: 12px; color: #333; min-width: 100px; border: none;")
        radius_layout.addWidget(radius_label)
        
        self.position_radius_slider = QSlider(Qt.Horizontal)
        self.position_radius_slider.setMinimum(1)
        self.position_radius_slider.setMaximum(10)
        self.position_radius_slider.setStyleSheet(SLIDER_STYLESHEET)
        position_radius = self.config.get_int('map', 'position_radius', default=2)
        self.position_radius_slider.setValue(position_radius)
        
        self.position_radius_slider.valueChanged.connect(self.save_config)
        radius_layout.addWidget(self.position_radius_slider)
        
        self.position_radius_value = QLabel(str(self.position_radius_slider.value()))
        self.position_radius_value.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
        self.position_radius_slider.valueChanged.connect(lambda v: self.position_radius_value.setText(str(v)))
        radius_layout.addWidget(self.position_radius_value)
        record_layout.addLayout(radius_layout)
        
        # Position font size slider
        pos_font_layout = QHBoxLayout()
        pos_font_label = QLabel("Position font:")
        pos_font_label.setStyleSheet("font-size: 12px; color: #333; min-width: 100px; border: none;")
        pos_font_layout.addWidget(pos_font_label)
        
        self.position_font_size_slider = QSlider(Qt.Horizontal)
        self.position_font_size_slider.setMinimum(6)
        self.position_font_size_slider.setMaximum(16)
        self.position_font_size_slider.setStyleSheet(SLIDER_STYLESHEET)
        position_font_size = self.config.get_int('map', 'position_font_size', default=8)
        self.position_font_size_slider.setValue(position_font_size)
        
        self.position_font_size_slider.valueChanged.connect(self.save_config)
        pos_font_layout.addWidget(self.position_font_size_slider)
        
        self.position_font_size_value = QLabel(str(self.position_font_size_slider.value()))
        self.position_font_size_value.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
        self.position_font_size_slider.valueChanged.connect(lambda v: self.position_font_size_value.setText(str(v)))
        pos_font_layout.addWidget(self.position_font_size_value)
        record_layout.addLayout(pos_font_layout)
        
        record_box.setLayout(record_layout)
        map_section.add_to_layout(record_box)
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
        
        saved_grace_period = self.config.get_int('camera_settings', 'grace_period_seconds', default=10)
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
        
        saved_label_font_size = self.config.get_int('camera_settings', 'label_font_size', default=16)
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
        
        saved_label_color = self.config.get_str('camera_settings', 'label_color', default='white')
        self.camera_label_color_buttons = {}
        colors = {'white': '#FFFFFF', 'yellow': '#FFFF00', 'cyan': '#00FFFF', 'lime': '#00FF00', 'red': '#FF0000'}
        
        for color_name, color_hex in colors.items():
            btn = QPushButton(color_name.capitalize())
            is_selected = saved_label_color == color_name
            text_color = '#000000' if color_name in ['white', 'yellow', 'cyan', 'lime'] else '#FFFFFF'
            btn.setStyleSheet(get_button_stylesheet(color_hex, text_color, is_selected))
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
                saved_rotation = self.config.get_int('camera_rotations', cam_name, default=0)
                
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
    
    def on_rec_color_selected(self, color_name):
        """Handle recording path color selection"""
        # Stylesheet for color buttons (no min/max width constraints)
        def get_color_button_stylesheet(bg_color_hex, text_color, is_selected):
            return f"""
                QPushButton {{
                    background-color: {bg_color_hex};
                    color: {text_color};
                    font-size: 10px;
                    font-weight: bold;
                    padding: 6px 2px;
                    border: {'4px solid #007AFF' if is_selected else '2px solid #ddd'};
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 3px solid #007AFF;
                    background-color: {bg_color_hex};
                }}
                QPushButton:pressed {{
                    border: 4px solid #0051d5;
                }}
            """
        
        # Update all color buttons
        rec_colors = {
            'RED': '#FF0000', 'BLUE': '#0000FF', 'GREEN': '#00FF00', 'YELLOW': '#FFFF00',
            'CYAN': '#00FFFF', 'MAGENTA': '#FF00FF', 'ORANGE': '#FFA500', 'PURPLE': '#800080',
        }
        
        for c, btn in self.rec_color_buttons.items():
            is_selected = (c == color_name)
            text_color = '#000000' if c in ['YELLOW', 'CYAN'] else '#FFFFFF'
            btn.setStyleSheet(get_color_button_stylesheet(rec_colors[c], text_color, is_selected))
        
        self.selected_rec_color = color_name
        print(f"[CONF] Selected recording path color: {color_name}")
        self.save_config()
    
    def on_time_selected(self, time_str):
        """Handle time selection for recording"""
        # Get the common stylesheet function
        def get_button_stylesheet(bg_color_hex, text_color, is_selected):
            return f"""
                QPushButton {{
                    background-color: {bg_color_hex};
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
                    background-color: {bg_color_hex};
                }}
                QPushButton:pressed {{
                    border: 4px solid #0051d5;
                }}
            """
        
        # Update all buttons
        for t, btn in self.time_buttons.items():
            is_selected = (t == time_str)
            btn.setChecked(is_selected)
            btn.setStyleSheet(get_button_stylesheet("#2196F3", "white", is_selected))
        
        self.selected_time = time_str
        print(f"[CONF] Selected time-based sampling: {time_str}")
        self.save_config()
    
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
        self.config.set_value('camera_settings', 'grace_period_seconds', str(value))
    
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
                    saved_rotation = self.config.get_int('camera_rotations', cam_name, default=0)
                    
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
            self.config.ensure_section('camera_rotations')
            
            # Ensure camera_name is string
            if not isinstance(camera_name, str):
                camera_name = str(camera_name)
            
            self.config.set_value('camera_rotations', camera_name, str(angle))
            
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
        self.config.set_value('gps', 'show_dms_decimals', str(self.dms_checkbox.isChecked()))
        gps_core.SHOW_DMS_DECIMALS = self.dms_checkbox.isChecked()
        
        # Coordinate font size
        self.config.set_value('gps', 'coord_font_size', str(self.font_size_slider.value()))
        
        # Coordinate color
        self.config.set_value('gps', 'coord_color', self.selected_coord_color)
        
        # Metadata font size
        self.config.set_value('gps', 'meta_font_size', str(self.meta_font_size_slider.value()))
        
        # Metadata color
        self.config.set_value('gps', 'meta_color', self.selected_meta_color)
        
        # Background color and brightness
        self.config.ensure_section('coords')
        self.config.set_value('coords', 'bg_color', self.selected_bg_color)
        self.config.set_value('coords', 'bg_brightness', str(self.bg_brightness_slider.value()))
        
        # Map time-based sampling
        self.config.ensure_section('map')
        self.config.set_value('map', 'time_based_sampling', self.selected_time)
        self.config.set_value('map', 'recording_color', self.selected_rec_color)
        self.config.set_value('map', 'position_radius', str(self.position_radius_slider.value()))
        self.config.set_value('map', 'position_font_size', str(self.position_font_size_slider.value()))
        self.config.set_value('map', 'path_width', str(self.path_width_slider.value()))
        
        # Camera settings (label font size and color)
        self.config.ensure_section('camera_settings')
        self.config.set_value('camera_settings', 'label_font_size', str(self.camera_label_font_size_slider.value()))
        # Find selected camera label color
        for color_name, btn in self.camera_label_color_buttons.items():
            if '3px solid' in btn.styleSheet():
                self.config.set_value('camera_settings', 'label_color', color_name)
                break
        
        # Per-camera rotations
        self.config.ensure_section('camera_rotations')
        
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
                self.config.set_value('camera_rotations', cam_name, str(rotation))


class PathsTab(QWidget):
    """Paths Tab - shows existing recorded paths with delete buttons"""
    
    def __init__(self, config, main_window=None):
        super().__init__()
        self.config = config
        self.main_window = main_window  # Reference to parent window for triggering map refresh
        self.paths_data = {}  # Store path_id -> name mapping
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("Recorded Paths")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # Paths list with scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        
        self.paths_container = QWidget()
        self.paths_layout = QVBoxLayout()
        self.paths_layout.setContentsMargins(5, 5, 5, 5)
        self.paths_layout.setSpacing(5)
        self.paths_container.setLayout(self.paths_layout)
        scroll.setWidget(self.paths_container)
        layout.addWidget(scroll)
        
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
        # Clear existing items
        while self.paths_layout.count():
            child = self.paths_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.paths_data.clear()
        
        try:
            # Get paths from global route recorder's database
            if global_route_recorder and global_route_recorder.db and global_route_recorder.db.connection:
                cursor = global_route_recorder.db.connection.cursor()
                cursor.execute("SELECT path_id, name FROM paths ORDER BY created_at DESC")
                rows = cursor.fetchall()
                
                if rows:
                    for row in rows:
                        path_id = row[0]
                        path_name = row[1]
                        self.paths_data[path_id] = path_name
                        
                        # Create row with path name and delete button
                        row_widget = self._create_path_row(path_id, path_name)
                        self.paths_layout.addWidget(row_widget)
                else:
                    label = QLabel("No paths recorded yet")
                    label.setStyleSheet("color: #999; font-style: italic; padding: 10px;")
                    self.paths_layout.addWidget(label)
            else:
                label = QLabel("Path database not initialized")
                label.setStyleSheet("color: #999; font-style: italic; padding: 10px;")
                self.paths_layout.addWidget(label)
        except Exception as e:
            print(f"[PATHS] Error loading paths: {e}")
            label = QLabel(f"Error: {str(e)}")
            label.setStyleSheet("color: red; padding: 10px;")
            self.paths_layout.addWidget(label)
        
        self.paths_layout.addStretch()
    
    def _create_path_row(self, path_id, path_name):
        """Create a row widget with path name and action buttons"""
        row = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(10, 5, 10, 5)
        row_layout.setSpacing(10)
        
        # Path name label
        name_label = QLabel(path_name)
        name_label.setStyleSheet("font-size: 12px; color: #333;")
        row_layout.addWidget(name_label, 1)  # Stretch
        
        # Visibility checkbox (at beginning of button block)
        vis_checkbox = QCheckBox()
        try:
            cursor = global_route_recorder.db.connection.cursor()
            cursor.execute("SELECT is_visible FROM paths WHERE path_id = ?", (path_id,))
            row_data = cursor.fetchone()
            is_visible = bool(row_data[0]) if row_data else False
        except:
            is_visible = False
        
        vis_checkbox.setChecked(is_visible)
        vis_checkbox.stateChanged.connect(lambda state: self.toggle_path_visibility(path_id, state))
        vis_checkbox.setStyleSheet("""
            QCheckBox {
                min-height: 20px;
                border: none;
            }
            QCheckBox::indicator {
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
        row_layout.addWidget(vis_checkbox)
        
        # Get path color from database
        try:
            cursor = global_route_recorder.db.connection.cursor()
            cursor.execute("SELECT color FROM paths WHERE path_id = ?", (path_id,))
            row_data = cursor.fetchone()
            path_color = row_data[0] if row_data else 'RED'
        except:
            path_color = 'RED'
        
        # Color mapping
        color_map = {
            'RED': '#FF0000',
            'BLUE': '#0000FF',
            'GREEN': '#00FF00',
            'YELLOW': '#FFFF00',
            'CYAN': '#00FFFF',
            'MAGENTA': '#FF00FF',
            'ORANGE': '#FFA500',
            'PURPLE': '#800080',
        }
        
        path_color_hex = color_map.get(path_color, '#FF0000')
        
        # Color button - shows actual path color
        color_btn = QPushButton()
        color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {path_color_hex};
                color: white;
                border: 2px solid #333;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 12px;
                font-weight: bold;
                min-width: 30px;
                max-width: 30px;
            }}
            QPushButton:hover {{
                border: 2px solid #000;
            }}
            QPushButton:pressed {{
                border: 3px solid #000;
            }}
        """)
        color_btn.clicked.connect(lambda: self.set_path_color(path_id, path_name))
        row_layout.addWidget(color_btn)
        
        # Edit button (pencil)
        edit_btn = QPushButton("✎")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 16px;
                font-weight: bold;
                min-width: 30px;
                max-width: 30px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0056b3;
            }
        """)
        edit_btn.clicked.connect(lambda: self.edit_path_name(path_id, path_name))
        row_layout.addWidget(edit_btn)
        
        # Delete button (X icon)
        delete_btn = QPushButton("✕")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 16px;
                font-weight: bold;
                min-width: 30px;
                max-width: 30px;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
            QPushButton:pressed {
                background-color: #990000;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_path(path_id, path_name))
        row_layout.addWidget(delete_btn)
        
        # Container background
        row.setLayout(row_layout)
        row.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        
        return row
    
    def delete_path(self, path_id, path_name):
        """Delete a path from database and refresh list"""
        try:
            # Show confirmation dialog
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "Delete Path",
                f"Are you sure you want to delete '{path_name}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if global_route_recorder and global_route_recorder.db:
                    global_route_recorder.db.delete_route(path_id)
                    print(f"[PATHS] Deleted path: {path_name} (ID: {path_id})")
                    self.refresh_paths()
        except Exception as e:
            print(f"[PATHS] Error deleting path {path_id}: {e}")
    
    def toggle_path_visibility(self, path_id, state):
        """Toggle visibility of a path and refresh map display"""
        try:
            is_visible = state == 2  # Qt.Checked = 2
            if global_route_recorder and global_route_recorder.db:
                cursor = global_route_recorder.db.connection.cursor()
                cursor.execute("UPDATE paths SET is_visible = ? WHERE path_id = ?", (is_visible, path_id))
                global_route_recorder.db.connection.commit()
                print(f"[PATHS] Path {path_id} visibility set to {is_visible}")
                
                # Trigger map re-render to show/hide the path
                # Find the MapTab and request a render
                if hasattr(self, 'main_window') and self.main_window:
                    if hasattr(self.main_window, 'map_tab'):
                        self.main_window.map_tab.render_map()
        except Exception as e:
            print(f"[PATHS] Error toggling path visibility {path_id}: {e}")
    
    def set_path_color(self, path_id, path_name):
        """Set color for a path"""
        try:
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton
            
            # Create color selection dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Set Color for '{path_name}'")
            dialog.setGeometry(100, 100, 300, 150)
            
            layout = QVBoxLayout()
            
            colors = {
                'RED': '#FF0000',
                'BLUE': '#0000FF',
                'GREEN': '#00FF00',
                'YELLOW': '#FFFF00',
                'CYAN': '#00FFFF',
                'MAGENTA': '#FF00FF',
                'ORANGE': '#FFA500',
                'PURPLE': '#800080',
            }
            
            buttons_layout = QHBoxLayout()
            
            def select_color(color_name):
                if global_route_recorder and global_route_recorder.db:
                    cursor = global_route_recorder.db.connection.cursor()
                    cursor.execute("UPDATE paths SET color = ? WHERE path_id = ?", (color_name, path_id))
                    global_route_recorder.db.connection.commit()
                    print(f"[PATHS] Set path '{path_name}' color to {color_name}")
                    dialog.close()
                    self.refresh_paths()
                    # Trigger map re-render to show updated color
                    if self.main_window and hasattr(self.main_window, 'map_tab'):
                        self.main_window.map_tab.render_map()
            
            for color_name, color_hex in colors.items():
                btn = QPushButton(color_name)
                text_color = '#000000' if color_name in ['YELLOW', 'CYAN'] else '#FFFFFF'
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color_hex};
                        color: {text_color};
                        font-size: 10px;
                        font-weight: bold;
                        padding: 8px 12px;
                        border: none;
                        border-radius: 4px;
                        min-width: 50px;
                    }}
                    QPushButton:hover {{
                        border: 2px solid #000;
                    }}
                """)
                btn.clicked.connect(lambda checked, c=color_name: select_color(c))
                buttons_layout.addWidget(btn)
            
            layout.addLayout(buttons_layout)
            dialog.setLayout(layout)
            dialog.exec_()
        except Exception as e:
            print(f"[PATHS] Error setting path color {path_id}: {e}")
    
    def edit_path_name(self, path_id, old_name):
        """Edit the name of a path"""
        try:
            from PyQt5.QtWidgets import QInputDialog, QMessageBox
            
            new_name, ok = QInputDialog.getText(
                self,
                "Edit Path Name",
                "Enter new path name:",
                text=old_name
            )
            
            if ok and new_name and new_name != old_name:
                if global_route_recorder and global_route_recorder.db:
                    # Check if new name already exists
                    cursor = global_route_recorder.db.connection.cursor()
                    cursor.execute("SELECT COUNT(*) FROM paths WHERE name = ? AND path_id != ?", (new_name, path_id))
                    exists = cursor.fetchone()[0] > 0
                    
                    # If exists, append original name with dash
                    if exists:
                        final_name = f"{new_name}-{old_name}"
                    else:
                        final_name = new_name
                    
                    # Update database
                    cursor.execute("UPDATE paths SET name = ? WHERE path_id = ?", (final_name, path_id))
                    global_route_recorder.db.connection.commit()
                    print(f"[PATHS] Renamed path from '{old_name}' to '{final_name}'")
                    self.refresh_paths()
        except Exception as e:
            print(f"[PATHS] Error editing path name {path_id}: {e}")


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
        config = ConfigParser()
        config.read(config_file)
        
        # Create centralized config loader
        self.config = ConfigLoader(config)
        self.config.ensure_sections(['gps', 'coords', 'route_recording', 'camera_rotations', 'cam', 'map'])
        
        self.setWindowTitle("seeBoard - GPS & Camera Dashboard")
        self.setGeometry(100, 100, 800, 600)
        
        # Create tabs (pass ConfigLoader to all tabs)
        self.tabs = QTabWidget()
        self.coords_tab = CoordsTab(self.config)
        self.map_tab = MapTab(self.config)
        self.paths_tab = PathsTab(self.config, self)
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
