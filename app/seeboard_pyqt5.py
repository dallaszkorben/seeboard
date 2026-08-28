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

# Setup logging to file immediately
LOG_FILE = '/tmp/seeboard_debug.log'
def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    log_msg = f"[{timestamp}] {msg}\n"
    print(log_msg.strip())  # Also to stdout
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_msg)
    except:
        pass

log("=== SEEBOARD STARTING ===")

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
    QListWidget, QListWidgetItem, QGraphicsView, QGraphicsScene, QTabBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QTimer, QRectF, QPoint, QPointF, QEvent, QSize
from PyQt5.QtGui import QFont, QColor, QImage, QPixmap, QPalette, QPen

# PIL imports
from PIL import Image, ImageDraw

# Backend imports
import gps_core
import cam_discovery
import map_generator
import route_recorder as route_recorder_module
from route_database import PathDatabase
from route_recorder import RouteRecorder
from map_renderer import MapRenderer, MapCache
from config_loader import ConfigLoader

log("PyQt5 and backend imports OK")

# ============================================================================
# CUSTOM TAB BAR - Dynamic sizing to content
# ============================================================================

class DynamicTabBar(QTabBar):
    """QTabBar that sizes tabs to their content instead of fixed width."""
    
    def tabSizeHint(self, index):
        """Return size hint based on tab text - allows dynamic sizing."""
        size = super().tabSizeHint(index)
        # Get the text for this tab
        text = self.tabText(index)
        # Calculate width based on text length + padding
        # Approximate: each character is ~7 pixels at default font size
        width = len(text) * 7 + 32  # 32 pixels for padding and borders
        size.setWidth(max(width, 60))  # Minimum 60 pixels
        return size

# Global route recorder
_db = None
global_route_recorder = None

def init_route_recorder(config=None):
    global _db, global_route_recorder
    _db = PathDatabase(config)
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


# ============================================================================
# MAP IMPLEMENTATION (QGraphicsView + MBTiles)
# ============================================================================

class MapRenderer:
    """Render map tiles from MBTiles."""
    
    def __init__(self, mbtiles_path):
        self.mbtiles = MBTilesReader(mbtiles_path)
    
    def render_map_canvas(self, zoom, center_lat, center_lon, canvas_width, canvas_height, gps_lat=None, gps_lon=None):
        """
        Render map by compositing tiles from MBTiles.
        
        Returns PIL Image with map tiles and GPS marker.
        """
        # Get center in world coordinates
        center_x, center_y = WebMercator.lat_lon_to_world(center_lat, center_lon, zoom)
        
        # Create blank canvas
        canvas = Image.new('RGB', (canvas_width, canvas_height), color='#e8e8e8')
        
        # Calculate visible tile range
        tile_size = 256
        tile_x_start = int((center_x - canvas_width / 2) / tile_size)
        tile_y_start = int((center_y - canvas_height / 2) / tile_size)
        tile_x_end = int((center_x + canvas_width / 2) / tile_size) + 2
        tile_y_end = int((center_y + canvas_height / 2) / tile_size) + 2
        
        # Load and composite tiles
        for tx in range(tile_x_start, tile_x_end):
            for ty in range(tile_y_start, tile_y_end):
                # Wrap X coordinate for world wrapping
                wrapped_tx = tx % (2 ** zoom)
                
                tile_img = self.mbtiles.get_tile(zoom, wrapped_tx, ty)
                if tile_img:
                    # Calculate pixel position on canvas
                    px = (tx * tile_size) - (center_x - canvas_width / 2)
                    py = (ty * tile_size) - (center_y - canvas_height / 2)
                    canvas.paste(tile_img, (int(px), int(py)))
        
        # Draw GPS marker if we have position
        if gps_lat is not None and gps_lon is not None:
            self._draw_gps_marker(canvas, gps_lat, gps_lon, zoom, center_x, center_y, canvas_width, canvas_height)
        
        return canvas
    
    def _draw_gps_marker(self, canvas, gps_lat, gps_lon, zoom, center_x, center_y, canvas_width, canvas_height):
        """Draw water droplet GPS marker on canvas."""
        # Convert GPS position to pixel coordinates
        gps_world_x, gps_world_y = WebMercator.lat_lon_to_world(gps_lat, gps_lon, zoom)
        
        px = (gps_world_x - center_x) + canvas_width / 2
        py = (gps_world_y - center_y) + canvas_height / 2
        
        # Only draw if marker is within canvas bounds
        if -50 < px < canvas_width + 50 and -50 < py < canvas_height + 50:
            draw = ImageDraw.Draw(canvas)
            
            # Water droplet: teardrop shape
            radius = 12
            px_int = int(px)
            py_int = int(py)
            
            drop_points = [
                # Top rounded part
                (px_int - radius, py_int - radius + 4),
                (px_int - radius + 2, py_int - radius),
                (px_int, py_int - radius - 2),
                (px_int + radius - 2, py_int - radius),
                (px_int + radius, py_int - radius + 4),
                # Right side - taper down
                (px_int + radius - 1, py_int),
                (px_int + radius - 2, py_int + 6),
                (px_int + radius - 4, py_int + 12),
                (px_int + radius - 6, py_int + 18),
                # Bottom point
                (px_int, py_int + 28),
                # Left side - taper down
                (px_int - radius + 6, py_int + 18),
                (px_int - radius + 4, py_int + 12),
                (px_int - radius + 2, py_int + 6),
                (px_int - radius + 1, py_int),
            ]
            
            # Draw black outline
            draw.polygon(drop_points, outline='#000000', width=1)
            # Draw red fill
            draw.polygon(drop_points, fill='#FF0000')
            # Draw white inner outline
            draw.polygon(drop_points, outline='#FFFFFF', width=1)
            
            # Label above droplet
            draw.text((px_int - 15, py_int - 30), "GPS", fill='#FFFFFF')
            
            # Label above droplet
            draw.text((int(px - 15), int(py - 28)), "GPS", fill='#FFFFFF')


# ============================================================================
# GPS RECEIVER THREAD
# ============================================================================

class GPSReceiver(QThread):
    """GPS data receiver thread."""
    
    position_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.running = True
    
    def run(self):
        """Emit dummy GPS data."""
        dummy_data = {
            'status': 'fix',
            'lat': 56.161200,
            'lon': 15.586900,
            'time': '12:00:00',
            'quality': 'Fix',
            'sats_used': 12,
            'sats_visible': 18
        }
        self.position_updated.emit(dummy_data)


# ============================================================================
# MAP CANVAS - QGRAPHICSVIEW BASED
# ============================================================================

class MapCanvas(QGraphicsView):
    """
    PyQt5 Map Viewer using QGraphicsView (proven architecture).
    
    Pan: Middle mouse button drag
    Zoom: Mouse wheel or +/- buttons
    Recenter: R key
    """
    
    # Available zoom levels from MBTiles
    AVAILABLE_ZOOMS = [8, 10, 12, 14, 16, 17]
    
    def __init__(self, mbtiles_path):
        super().__init__()
        
        # Initialize scene
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # Map renderer
        self.renderer = MapRenderer(mbtiles_path)
        
        # Map state
        self.zoom = 12
        self.center_lat = 56.161200
        self.center_lon = 15.586900
        self.canvas_width = 600
        self.canvas_height = 400
        
        # Pan offset in pixels (from user dragging or button clicks)
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        
        # GPS position
        self.gps_lat = None
        self.gps_lon = None
        
        # Scene pixmap item
        self._pixmap_item = None
        
        # Pan/zoom settings
        self.pan_button = Qt.MiddleButton
        self.pan_speed_multiplier = 0.92  # Adjust this to speed up/slow down touch panning
                                           # Fine-tuned for natural feel with rendering lag
        
        # Pan tracking
        self._is_panning = False
        self._last_pan_pos = None
        self._scene_position = None
        
        # Pinch-to-zoom tracking
        self._pinch_start_distance = 0
        
        # Zoom tracking
        self._is_zooming = False
        self._pixel_position = QPoint()
        
        # Display settings
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Create overlay zoom buttons
        self._create_overlay_buttons()
        
        # Initial render
        self.render_map()
    
    def _create_overlay_buttons(self):
        """Create overlay zoom buttons at top-left corner of map."""
        # Create a widget to hold the buttons
        button_widget = QWidget(self)
        button_layout = QVBoxLayout(button_widget)
        button_layout.setContentsMargins(10, 10, 10, 10)
        button_layout.setSpacing(8)
        
        # Zoom in button (+)
        self.btn_zoom_plus = QPushButton("+")
        self.btn_zoom_plus.setMinimumSize(60, 60)
        self.btn_zoom_plus.setFont(QFont("Arial", 24, QFont.Bold))
        self.btn_zoom_plus.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 150, 200, 200);
                color: white;
                border: 2px solid white;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0, 170, 220, 220);
            }
            QPushButton:pressed {
                background-color: rgba(0, 120, 180, 200);
            }
        """)
        self.btn_zoom_plus.clicked.connect(self.zoom_in)
        button_layout.addWidget(self.btn_zoom_plus)
        
        # Zoom out button (-)
        self.btn_zoom_minus = QPushButton("−")
        self.btn_zoom_minus.setMinimumSize(60, 60)
        self.btn_zoom_minus.setFont(QFont("Arial", 32, QFont.Bold))
        self.btn_zoom_minus.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 150, 200, 200);
                color: white;
                border: 2px solid white;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0, 170, 220, 220);
            }
            QPushButton:pressed {
                background-color: rgba(0, 120, 180, 200);
            }
        """)
        self.btn_zoom_minus.clicked.connect(self.zoom_out)
        button_layout.addWidget(self.btn_zoom_minus)
        
        # Add stretch at end
        button_layout.addStretch()
        
        # Position widget at top-left
        button_widget.move(0, 0)
        button_widget.setMaximumWidth(100)
        button_widget.show()
    
    def render_map(self):
        """Render map and apply pan offset, loading extra tiles for coverage."""
        # Skip if already rendering to prevent race conditions
        if self._is_zooming:
            return
        
        self._is_zooming = True
        
        try:
            # Load all visible paths from database
            visible_paths = []
            try:
                if global_route_recorder and global_route_recorder.db and global_route_recorder.db.connection:
                    cursor = global_route_recorder.db.connection.cursor()
                    cursor.execute("""
                        SELECT path_id, color FROM paths WHERE is_visible = 1
                    """)
                    visible_path_rows = cursor.fetchall()
                    
                    # Fetch points for each visible path
                    for path_id, color in visible_path_rows:
                        cursor.execute("""
                            SELECT latitude, longitude FROM path_points 
                            WHERE path_id = ? 
                            ORDER BY timestamp ASC
                        """, (path_id,))
                        points = cursor.fetchall()
                        if points:
                            visible_paths.append({
                                'points': points,
                                'color': color or 'RED'
                            })
            except Exception as e:
                print(f"[MAP] Error loading visible paths: {e}")
            
            # Create a larger canvas to accommodate pan offset
            expanded_width = self.canvas_width + abs(self.pan_offset_x) + 512
            expanded_height = self.canvas_height + abs(self.pan_offset_y) + 512
            
            # Get recording points and settings if actively recording
            recording_points = None
            recording_color = 'RED'
            recording_point_diameter = 8
            
            if hasattr(self, 'parent_map_tab') and hasattr(self.parent_map_tab, 'is_recording') and self.parent_map_tab.is_recording:
                recording_points = getattr(self.parent_map_tab, 'current_recording_points', [])
                recording_color = getattr(self.parent_map_tab, 'current_recording_color', 'RED')
                recording_point_diameter = self.parent_map_tab.config.get_int(
                    'route_recording', 'point_diameter', default=8
                )
            
            # Render tiles to PIL Image at current zoom level (larger area)
            canvas = self.renderer.render_map_canvas(
                self.zoom, self.center_lat, self.center_lon,
                expanded_width, expanded_height,
                self.gps_lat, self.gps_lon,
                visible_paths=visible_paths,
                recording_points=recording_points,
                recording_color=recording_color,
                recording_point_diameter=recording_point_diameter
            )
            
            # Create output canvas at normal size
            output = Image.new('RGB', (self.canvas_width, self.canvas_height), color='white')
            
            # Calculate source position
            # Start from center of expanded canvas (256 pixels from edge)
            # Then apply pan offset
            src_x = 256 + self.pan_offset_x
            src_y = 256 + self.pan_offset_y
            
            # Clamp to valid range
            src_x = max(0, min(src_x, expanded_width - self.canvas_width))
            src_y = max(0, min(src_y, expanded_height - self.canvas_height))
            
            # Crop the expanded canvas and paste into output
            crop_box = (src_x, src_y, src_x + self.canvas_width, src_y + self.canvas_height)
            cropped = canvas.crop(crop_box)
            output.paste(cropped, (0, 0))
            
            # Convert PIL Image to QPixmap
            pil_image = output.convert('RGB')
            data = pil_image.tobytes('raw', 'RGB')
            qimage = QImage(data, self.canvas_width, self.canvas_height,
                           self.canvas_width * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)
            
            # Update the scene pixmap
            if self._pixmap_item is None:
                self._pixmap_item = self.scene.addPixmap(pixmap)
                self.setSceneRect(QRectF(pixmap.rect()))
            else:
                self._pixmap_item.setPixmap(pixmap)
                self.setSceneRect(QRectF(pixmap.rect()))
                
        except Exception as e:
            print(f"Error rendering map: {e}")
        finally:
            self._is_zooming = False
    
    def set_gps_position(self, lat, lon):
        """Update GPS position (marker only, do NOT re-render or interfere with map view)."""
        # Just store the GPS position
        # The marker will be drawn on the NEXT render
        # Do NOT call render_map() here - that interferes with panning!
        self.gps_lat = lat
        self.gps_lon = lon
    
    def recenter_on_gps(self):
        """
        Center the map on the current GPS position.
        The water droplet will move to the center of the window.
        """
        if self.gps_lat is not None and self.gps_lon is not None:
            # Simply set center to GPS position
            self.center_lat = self.gps_lat
            self.center_lon = self.gps_lon
            
            # ZERO out any pan offset
            self.pan_offset_x = 0
            self.pan_offset_y = 0
            
            # Use normal render_map() flow (not custom rendering)
            self.render_map()
    
    def pan_by(self, pixel_dx, pixel_dy):
        """
        Pan by accumulating pixel offset. Tiles will be rendered to fill the area.
        
        ⚠️ CRITICAL WARNING ⚠️
        DO NOT CHANGE THIS PANNING CONCEPT WITHOUT EXPLICIT USER APPROVAL!
        
        Args:
            pixel_dx: Pixels to pan horizontally
            pixel_dy: Pixels to pan vertically
        """
        # Accumulate pan offset
        self.pan_offset_x += pixel_dx
        self.pan_offset_y += pixel_dy
        
        # Re-render with the new offset (renderer will load appropriate tiles)
        self.render_map()
    
    def zoom_in(self):
        """Zoom in to next available zoom level, keeping window center position fixed."""
        available_zooms = self.AVAILABLE_ZOOMS
        
        # Find next higher zoom level
        for zoom in available_zooms:
            if zoom > self.zoom:
                # Before zoom: calculate what lat/lon is at window center
                center_lat_before, center_lon_before = self._get_window_center_coords()
                
                # Change zoom
                self.zoom = zoom
                
                # After zoom: adjust center_lat/center_lon so the same point stays at window center
                if center_lat_before is not None and center_lon_before is not None:
                    self.center_lat = center_lat_before
                    self.center_lon = center_lon_before
                    self.pan_offset_x = 0
                    self.pan_offset_y = 0
                
                self.render_map()
                return
    
    def zoom_out(self):
        """Zoom out to previous available zoom level, keeping window center position fixed."""
        available_zooms = self.AVAILABLE_ZOOMS
        
        # Find next lower zoom level (in reverse)
        for zoom in reversed(available_zooms):
            if zoom < self.zoom:
                # Before zoom: calculate what lat/lon is at window center
                center_lat_before, center_lon_before = self._get_window_center_coords()
                
                # Change zoom
                self.zoom = zoom
                
                # After zoom: adjust center_lat/center_lon so the same point stays at window center
                if center_lat_before is not None and center_lon_before is not None:
                    self.center_lat = center_lat_before
                    self.center_lon = center_lon_before
                    self.pan_offset_x = 0
                    self.pan_offset_y = 0
                
                self.render_map()
                return
    
    def _get_window_center_coords(self):
        """Calculate what lat/lon is at the center of the window."""
        try:
            # Get current center in world coordinates
            center_world_x, center_world_y = WebMercator.lat_lon_to_world(
                self.center_lat, self.center_lon, self.zoom
            )
            
            # The window displays an expanded canvas, cropped at (256 + pan_offset_x, 256 + pan_offset_y)
            # So the window top-left pixel corresponds to world position:
            crop_start_x = 256 + self.pan_offset_x
            crop_start_y = 256 + self.pan_offset_y
            
            # Window center pixel maps to world position:
            window_center_world_x = center_world_x - (self.canvas_width / 2) + crop_start_x + (self.canvas_width / 2)
            window_center_world_y = center_world_y - (self.canvas_height / 2) + crop_start_y + (self.canvas_height / 2)
            
            # Simplify: window center = (center_world) + pan_offset
            window_center_world_x = center_world_x + self.pan_offset_x
            window_center_world_y = center_world_y + self.pan_offset_y
            
            # Convert back to lat/lon
            lat, lon = WebMercator.world_to_lat_lon(
                window_center_world_x, window_center_world_y, self.zoom
            )
            
            return lat, lon
        except Exception as e:
            print(f"Error calculating window center coords: {e}")
            return None, None
    
    # ────── MOUSE EVENTS (PyQtImageViewer pattern) ──────
    
    def mousePressEvent(self, event):
        """Handle mouse press - start panning with middle button."""
        if event.button() == self.pan_button:
            # Store the starting position for drag calculation
            self._last_pan_pos = event.pos()
            self._is_panning = True
            event.accept()
            return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move - pan when dragging with middle button."""
        if self._is_panning and self._last_pan_pos is not None:
            # Calculate how far the mouse moved
            delta = event.pos() - self._last_pan_pos
            
            # Pan by OPPOSITE amount (invert delta so dragging left pans the map left)
            self.pan_by(-delta.x(), -delta.y())
            
            # Update last position for next move event
            self._last_pan_pos = event.pos()
            event.accept()
            return
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release - stop panning."""
        if event.button() == self.pan_button:
            self._is_panning = False
            self._last_pan_pos = None
            event.accept()
            return
        
        super().mouseReleaseEvent(event)
    
    def wheelEvent(self, event):
        """Handle mouse wheel zoom - FETCHES tiles at available zoom levels only."""
        available_zooms = self.AVAILABLE_ZOOMS
        
        if event.angleDelta().y() > 0:
            # Zoom in - find next higher available zoom level
            for zoom in available_zooms:
                if zoom > self.zoom:
                    self.zoom = zoom
                    self.render_map()
                    break
        else:
            # Zoom out - find next lower available zoom level
            for zoom in reversed(available_zooms):
                if zoom < self.zoom:
                    self.zoom = zoom
                    self.render_map()
                    break
        
        event.accept()
        event.accept()
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_R:
            self.recenter_on_gps()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self.zoom_in()
        elif event.key() == Qt.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key_BracketRight:  # ] key - increase pan speed
            self.pan_speed_multiplier += 0.1
            self.pan_speed_multiplier = min(self.pan_speed_multiplier, 3.0)  # Max 3x
        elif event.key() == Qt.Key_BracketLeft:  # [ key - decrease pan speed
            self.pan_speed_multiplier -= 0.1
            self.pan_speed_multiplier = max(self.pan_speed_multiplier, 0.5)  # Min 0.5x
        else:
            super().keyPressEvent(event)
    
    def event(self, event):
        """Handle touch events - pan with 1 finger, zoom with 2 fingers."""
        from PyQt5.QtCore import QEvent
        import math
        
        if event.type() == QEvent.TouchBegin or event.type() == QEvent.TouchUpdate or event.type() == QEvent.TouchEnd:
            touch_event = event
            
            if not touch_event.touchPoints():
                return super().event(event)
            
            num_fingers = len(touch_event.touchPoints())
            
            # ──── PINCH-TO-ZOOM (2+ fingers) ────
            if num_fingers >= 2:
                point1 = touch_event.touchPoints()[0].pos()
                point2 = touch_event.touchPoints()[1].pos()
                
                # Calculate distance between two touch points
                dx = point2.x() - point1.x()
                dy = point2.y() - point1.y()
                current_distance = math.sqrt(dx*dx + dy*dy)
                
                if event.type() == QEvent.TouchBegin:
                    self._pinch_start_distance = current_distance
                    self._is_panning = False  # Disable pan during pinch
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchUpdate:
                    # On first 2-finger contact, TouchUpdate arrives instead of TouchBegin
                    # So initialize pinch_start_distance here if not already set
                    if not hasattr(self, '_pinch_start_distance') or self._pinch_start_distance == 0:
                        self._pinch_start_distance = current_distance
                        event.accept()
                        return True
                    
                    distance_change = current_distance - self._pinch_start_distance
                    
                    # Pinch threshold: require 15+ pixels change to zoom
                    if distance_change > 15:
                        self.zoom_in()
                        self._pinch_start_distance = current_distance  # Reset for next zoom
                    elif distance_change < -15:
                        self.zoom_out()
                        self._pinch_start_distance = current_distance  # Reset for next zoom
                    
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchEnd:
                    self._pinch_start_distance = 0
                    self._is_panning = False
                    event.accept()
                    return True
            
            # ──── SINGLE FINGER PAN ────
            elif num_fingers == 1:
                touch_point = touch_event.touchPoints()[0]
                pos = touch_point.pos().toPoint()
                
                if event.type() == QEvent.TouchBegin:
                    # Start pan with first touch
                    self._last_pan_pos = pos
                    self._is_panning = True
                    self._pinch_start_distance = 0
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchUpdate:
                    # Pan with finger movement (only if still single finger)
                    if self._last_pan_pos is not None and self._is_panning and not hasattr(self, '_pinch_start_distance') or self._pinch_start_distance == 0:
                        delta = pos - self._last_pan_pos
                        # Apply pan speed multiplier to make map follow finger faster/slower
                        pan_dx = int(-delta.x() * self.pan_speed_multiplier)
                        pan_dy = int(-delta.y() * self.pan_speed_multiplier)
                        # Pan by OPPOSITE amount (invert delta so dragging left pans the map left)
                        self.pan_by(pan_dx, pan_dy)
                        self._last_pan_pos = pos
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchEnd:
                    # Stop pan when finger lifted
                    self._is_panning = False
                    self._last_pan_pos = None
                    event.accept()
                    return True
        
        return super().event(event)
    
    def resizeEvent(self, event):
        """Maintain zoom on resize."""
        super().resizeEvent(event)
        self.canvas_width = self.width()
        self.canvas_height = self.height()
        # Don't re-render on every resize - keep display smooth
        # QGraphicsView handles scaling automatically


# ============================================================================
# MAIN WINDOW
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
    
    def __init__(self, config, scale_factor=1.0):
        super().__init__()
        self.config = config
        self.scale_factor = scale_factor
        # Configurable border/padding variable - dynamic based on screen
        self.COORDS_PADDING = int(5 * scale_factor)  # pixels for border/margin around containers
        self.recording = False
        self.initUI()
    
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
        """
        ═══════════════════════════════════════════════════════════════════
        ⚠️  CONTAINER STRUCTURE - DO NOT MODIFY UNLESS EXPLICITLY REQUESTED
        ═══════════════════════════════════════════════════════════════════
        
        The GPS tab uses a FIXED 3-CONTAINER LAYOUT:
        
        1. NORTH: Coordinates (Latitude & Longitude in DMS format)
        2. MIDDLE: Spacer (stretches to fill available vertical space)
        3. SOUTH: Metadata (Time, Quality, Satellites)
        
        Changes to this structure (adding/removing containers, changing layout
        types, modifying stretch factors, etc.) require explicit user approval.
        
        ⚠️  Only modify:
           - Font sizes, colors, text content within existing labels
           - Spacing/padding within containers (not between them)
           - Label styling (but not container arrangement)
           
        DO NOT modify without user permission:
           - Container arrangement or layout hierarchy
           - Stretch factors (1 for spacer, 0 for others)
           - Number of containers or their purpose
           - Main layout orientation
        ═══════════════════════════════════════════════════════════════════
        """
        # Main layout - vertical
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Get background color from config
        try:
            bg_brightness = self.config.get_int('coords', 'bg_brightness', default=40)
            bg_color_name = self.config.get_str('coords', 'bg_color', default='black')
            
            bg_colors = {
                'black': (0, 0, 40),
                'blue': (225, 100, 40),
                'green': (114, 100, 40),
                'red': (0, 100, 40),
            }
            
            hsv = bg_colors.get(bg_color_name, (0, 0, 40))
            h, s, v_max = hsv
            v = (bg_brightness / 100.0) * v_max
            rgb = self.hsv_to_rgb(h, s, v)
            bg_color_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        except:
            bg_color_hex = "#000028"
        
        # ─── NORTH CONTAINER: Coordinates ───
        coordinates_container = QWidget()
        coordinates_container.setStyleSheet(f"background-color: {bg_color_hex};")
        coords_layout = QVBoxLayout()
        coords_layout.setContentsMargins(0, 0, 0, 0)
        coords_layout.setSpacing(0)
        
        # Get coordinate style from config
        try:
            coord_font_size = self.config.get_int('gps', 'coord_font_size', default=65)
            coord_color_name = self.config.get_str('gps', 'coord_color', default='lime')
            color_map = {
                'yellow': '#FFFF00',
                'white': '#FFFFFF',
                'cyan': '#00FFFF',
                'lime': '#00FF00',
                'red': '#FF0000',
                'orange': '#FFA500',
            }
            coord_color_hex = color_map.get(coord_color_name, '#00FF00')
        except:
            coord_font_size = 65
            coord_color_hex = '#00FF00'
        
        # Latitude label
        self.lat_label = QLabel("--°--'--\"")
        self.lat_label.setFont(QFont("Helvetica", coord_font_size, QFont.Bold))
        self.lat_label.setStyleSheet(f"color: {coord_color_hex}; background-color: transparent; margin: 0px; padding: 0px;")
        self.lat_label.setAlignment(Qt.AlignCenter)
        coords_layout.addWidget(self.lat_label)
        
        # Longitude label
        self.lon_label = QLabel("---°--'--\"")
        self.lon_label.setFont(QFont("Helvetica", coord_font_size, QFont.Bold))
        self.lon_label.setStyleSheet(f"color: {coord_color_hex}; background-color: transparent; margin: 0px; padding: 0px;")
        self.lon_label.setAlignment(Qt.AlignCenter)
        coords_layout.addWidget(self.lon_label)
        
        coordinates_container.setLayout(coords_layout)
        main_layout.addWidget(coordinates_container)
        
        # ─── MIDDLE CONTAINER: Spacer (stretches) ───
        spacer_container = QWidget()
        spacer_container.setStyleSheet(f"background-color: {bg_color_hex};")
        spacer_layout = QVBoxLayout()
        spacer_layout.setContentsMargins(0, 0, 0, 0)
        spacer_layout.setSpacing(0)
        spacer_container.setLayout(spacer_layout)
        main_layout.addWidget(spacer_container, 1)  # This stretches to fill available space
        
        # ─── SOUTH CONTAINER: Metadata ───
        metadata_container = QWidget()
        metadata_container.setStyleSheet(f"background-color: {bg_color_hex};")
        metadata_layout = QVBoxLayout()
        metadata_layout.setContentsMargins(0, 0, 0, 0)
        metadata_layout.setSpacing(2)
        
        # Get metadata style from config
        try:
            meta_font_size = self.config.get_int('gps', 'meta_font_size', default=12)
            meta_color_name = self.config.get_str('gps', 'meta_color', default='white')
            meta_color_hex = color_map.get(meta_color_name, '#FFFFFF')
        except:
            meta_font_size = 12
            meta_color_hex = '#FFFFFF'
        
        # Time label
        self.time_label = QLabel("Time: --:--:--")
        self.time_label.setFont(QFont("Helvetica", meta_font_size))
        self.time_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.time_label.setAlignment(Qt.AlignCenter)
        metadata_layout.addWidget(self.time_label)
        
        # Quality label
        self.qual_label = QLabel("Quality: No Fix")
        self.qual_label.setFont(QFont("Helvetica", meta_font_size))
        self.qual_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.qual_label.setAlignment(Qt.AlignCenter)
        metadata_layout.addWidget(self.qual_label)
        
        # Satellites label
        self.sat_label = QLabel("Satellites: - used / - visible")
        self.sat_label.setFont(QFont("Helvetica", meta_font_size))
        self.sat_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.sat_label.setAlignment(Qt.AlignCenter)
        metadata_layout.addWidget(self.sat_label)
        
        metadata_container.setLayout(metadata_layout)
        main_layout.addWidget(metadata_container)
        
        self.setLayout(main_layout)
        
        # Store these for later use
        self.coordinates_container = coordinates_container
        self.spacer_container = spacer_container
        self.metadata_container = metadata_container
        
        # Start GPS worker
        self.gps_worker = GPSWorker()
        self.gps_worker.signals.updated.connect(self.update_gps)
        self.gps_worker.start()
    
    def update_gps(self, data):
        """Handle GPS updates"""
        # Get the configured coordinate color
        try:
            coord_color_name = self.config.get_str('gps', 'coord_color', default='lime')
            color_map = {
                'yellow': '#FFFF00',
                'white': '#FFFFFF',
                'cyan': '#00FFFF',
                'lime': '#00FF00',
                'red': '#FF0000',
                'orange': '#FFA500',
            }
            coord_color = color_map.get(coord_color_name, '#00FF00')
        except:
            coord_color = '#00FF00'
        
        # Get metadata color
        try:
            meta_color_name = self.config.get_str('gps', 'meta_color', default='white')
            color_map = {
                'yellow': '#FFFF00',
                'white': '#FFFFFF',
                'cyan': '#00FFFF',
                'lime': '#00FF00',
                'red': '#FF0000',
                'orange': '#FFA500',
            }
            meta_color = color_map.get(meta_color_name, '#FFFFFF')
        except:
            meta_color = '#FFFFFF'
        
        if data and data.get('status') == 'fix':
            # Have GPS fix
            lat_decimal = data.get('lat', 0)
            lon_decimal = data.get('lon', 0)
            
            # Convert to DMS format
            lat_dms = gps_core._dd_to_dms(lat_decimal)
            lon_dms = gps_core._dd_to_dms(lon_decimal)
            
            # Update coordinate labels
            self.lat_label.setStyleSheet(f"color: {coord_color}; background-color: transparent; margin: 0px; padding: 0px;")
            self.lon_label.setStyleSheet(f"color: {coord_color}; background-color: transparent; margin: 0px; padding: 0px;")
            self.lat_label.setText(lat_dms)
            self.lon_label.setText(lon_dms)
            
            # Update metadata
            time_str = data.get('time', '--:--:--')
            qual_str = data.get('quality', 'Fix')
            sats_used = data.get('sats_used', 0)
            sats_visible = data.get('sats_visible', 0)
            
            self.time_label.setText(f"Time: {time_str}")
            self.qual_label.setText(f"Quality: {qual_str}")
            self.sat_label.setText(f"Satellites: {sats_used} used / {sats_visible} visible")
        
        elif data and data.get('status') == 'no_fix':
            # Have GPS but no fix (searching for satellites)
            self.lat_label.setStyleSheet(f"color: #FFA500; background-color: transparent; margin: 0px; padding: 0px;")
            self.lon_label.setStyleSheet(f"color: #FFA500; background-color: transparent; margin: 0px; padding: 0px;")
            self.lat_label.setText("--°--'--\"")
            self.lon_label.setText("---°--'--\"")
            
            time_str = data.get('time', '--:--:--')
            sats_used = data.get('sats_used', 0)
            sats_visible = data.get('sats_visible', 0)
            
            self.time_label.setText(f"Time: {time_str}")
            self.qual_label.setText("Quality: Searching...")
            self.sat_label.setText(f"Satellites: {sats_used} used / {sats_visible} visible")
        
        else:
            # No GPS data
            self.lat_label.setStyleSheet(f"color: #FF0000; background-color: transparent; margin: 0px; padding: 0px;")
            self.lon_label.setStyleSheet(f"color: #FF0000; background-color: transparent; margin: 0px; padding: 0px;")
            self.lat_label.setText("--°--'--\"")
            self.lon_label.setText("---°--'--\"")
            
            self.time_label.setText("Time: --:--:--")
            self.qual_label.setText("Quality: No Signal")
            self.sat_label.setText("Satellites: - used / - visible")
        
        # Forward GPS data to MapTab for map rendering
        if hasattr(self, 'map_tab_reference') and self.map_tab_reference and data:
            self.map_tab_reference.on_gps_update(data)
    
    def start_recording(self):
        """Start recording route"""
        pass
    
    def stop_recording(self):
        """Stop recording route"""
        pass
    
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
        self.time_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.qual_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")
        self.sat_label.setStyleSheet(f"color: {meta_color_hex}; background-color: transparent;")


# ============================================================================
# TOUCH-ENABLED MAP LABEL
# ============================================================================

class TouchMapLabel(QLabel):
    """QLabel with touch pan and pinch-zoom support."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pan_callback = None  # Will be set by MapTab
        self.zoom_in_callback = None
        self.zoom_out_callback = None
        
        # Touch tracking
        self._is_panning = False
        self._last_pan_pos = None
        self._pinch_start_distance = 0
        self.pan_speed_multiplier = 0.92
        
        # Enable touch events
        self.setAttribute(Qt.WA_AcceptTouchEvents)
    
    def event(self, event):
        """Handle touch events - pan with 1 finger, zoom with 2 fingers."""
        from PyQt5.QtCore import QEvent
        
        if event.type() == QEvent.TouchBegin or event.type() == QEvent.TouchUpdate or event.type() == QEvent.TouchEnd:
            touch_event = event
            
            if not touch_event.touchPoints():
                return super().event(event)
            
            num_fingers = len(touch_event.touchPoints())
            
            # ──── PINCH-TO-ZOOM (2+ fingers) ────
            if num_fingers >= 2:
                point1 = touch_event.touchPoints()[0].pos()
                point2 = touch_event.touchPoints()[1].pos()
                
                # Calculate distance between two touch points
                dx = point2.x() - point1.x()
                dy = point2.y() - point1.y()
                current_distance = math.sqrt(dx*dx + dy*dy)
                
                if event.type() == QEvent.TouchBegin:
                    self._pinch_start_distance = current_distance
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchUpdate:
                    # On first 2-finger contact, TouchUpdate arrives instead of TouchBegin
                    if self._pinch_start_distance == 0:
                        self._pinch_start_distance = current_distance
                        event.accept()
                        return True
                    
                    distance_change = current_distance - self._pinch_start_distance
                    
                    # Pinch threshold: require 15+ pixels change to zoom
                    if distance_change > 15:
                        if self.zoom_in_callback:
                            self.zoom_in_callback()
                        self._pinch_start_distance = current_distance
                    elif distance_change < -15:
                        if self.zoom_out_callback:
                            self.zoom_out_callback()
                        self._pinch_start_distance = current_distance
                    
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchEnd:
                    self._pinch_start_distance = 0
                    event.accept()
                    return True
            
            # ──── SINGLE FINGER PAN ────
            elif num_fingers == 1:
                touch_point = touch_event.touchPoints()[0]
                pos = touch_point.pos().toPoint()
                
                if event.type() == QEvent.TouchBegin:
                    self._last_pan_pos = pos
                    self._is_panning = True
                    self._pinch_start_distance = 0
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchUpdate:
                    if self._last_pan_pos is not None and self._is_panning:
                        delta = pos - self._last_pan_pos
                        pan_dx = int(-delta.x() * self.pan_speed_multiplier)
                        pan_dy = int(-delta.y() * self.pan_speed_multiplier)
                        
                        if self.pan_callback:
                            self.pan_callback(pan_dx, pan_dy)
                        
                        self._last_pan_pos = pos
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchEnd:
                    self._is_panning = False
                    self._last_pan_pos = None
                    event.accept()
                    return True
        
        return super().event(event)


# ============================================================================
# NEW MAP TAB - QGraphicsView with MBTiles (Proven Architecture)
# ============================================================================

import sqlite3
import io
import math
from pathlib import Path
from PyQt5.QtCore import Qt, QRectF, QPoint, QPointF, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsView, QGraphicsScene, QSizePolicy
)
from PIL import Image, ImageDraw


# ============================================================================
# WEB MERCATOR PROJECTION & COORDINATE CONVERSION
# ============================================================================

class WebMercator:
    """Web Mercator coordinate conversion utilities."""
    TILE_SIZE = 256
    MAX_LAT = 85.051129
    
    @staticmethod
    def lat_lon_to_world(lat, lon, zoom):
        """Convert latitude/longitude to world coordinates at given zoom level."""
        lat = max(-WebMercator.MAX_LAT, min(WebMercator.MAX_LAT, lat))
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        
        C = (WebMercator.TILE_SIZE / (2 * math.pi)) * (2 ** zoom)
        
        x = C * (lon_rad + math.pi)
        y = C * (math.pi - math.log(math.tan(math.pi / 4 + lat_rad / 2)))
        
        return x, y
    
    @staticmethod
    def world_to_lat_lon(world_x, world_y, zoom):
        """Convert world coordinates back to latitude/longitude."""
        C = (WebMercator.TILE_SIZE / (2 * math.pi)) * (2 ** zoom)
        
        lon = (world_x / C) - math.pi
        lat = 2 * math.atan(math.exp(math.pi - world_y / C)) - math.pi / 2
        
        return math.degrees(lat), math.degrees(lon)
    
    @staticmethod
    def world_to_pixel(world_x, world_y, center_x, center_y, canvas_w, canvas_h):
        """Convert world coordinates to pixel coordinates on canvas."""
        pixel_x = int((world_x - center_x) + canvas_w / 2)
        pixel_y = int((world_y - center_y) + canvas_h / 2)
        return pixel_x, pixel_y
    
    @staticmethod
    def lat_lon_to_tile(lat, lon, zoom):
        """Convert lat/lon to tile X/Y indices."""
        lat = max(-WebMercator.MAX_LAT, min(WebMercator.MAX_LAT, lat))
        
        tile_x = int((lon + 180) / 360 * (2 ** zoom))
        
        lat_rad = math.radians(lat)
        tile_y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * (2 ** zoom))
        
        return tile_x, tile_y


# ============================================================================
# MBTILES TILE READER
# ============================================================================

class MBTilesReader:
    """Read tiles from MBTiles (SQLite) database."""
    
    def __init__(self, mbtiles_path):
        self.mbtiles_path = mbtiles_path
        self.conn = sqlite3.connect(mbtiles_path)
    
    def get_tile(self, zoom, tile_x, tile_y):
        """Read a single tile from MBTiles (with TMS Y conversion)."""
        # Convert XYZ to TMS convention
        tms_y = (2 ** zoom - 1) - tile_y
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                (zoom, tile_x, tms_y)
            )
            result = cursor.fetchone()
            
            if result:
                tile_data = result[0]
                img = Image.open(io.BytesIO(tile_data))
                return img
        except Exception as e:
            pass
        
        return None
    
    def close(self):
        if self.conn:
            self.conn.close()


# ============================================================================
# MAP RENDERER
# ============================================================================

class MapRenderer:
    """Render map tiles from MBTiles with GPS marker and recorded routes."""
    
    def __init__(self, mbtiles_path):
        self.mbtiles = MBTilesReader(mbtiles_path)
    
    def render_map_canvas(self, zoom, center_lat, center_lon, canvas_width, canvas_height, 
                         gps_lat=None, gps_lon=None, route_points=None, route_color='RED', route_width=2,
                         visible_paths=None, recording_points=None, recording_color='RED', 
                         recording_point_diameter=8):
        """
        Render map by compositing tiles from MBTiles.
        
        Args:
            visible_paths: List of dicts with 'points' and 'color' (saved paths)
            recording_points: List of (lat, lon) tuples for current recording
            recording_color: Color for recording points and lines
            recording_point_diameter: Diameter of recorded point circles in pixels
        """
        # Get center in world coordinates
        center_x, center_y = WebMercator.lat_lon_to_world(center_lat, center_lon, zoom)
        
        # Create blank canvas
        canvas = Image.new('RGB', (canvas_width, canvas_height), color='#e8e8e8')
        
        # Calculate visible tile range
        tile_size = 256
        tile_x_start = int((center_x - canvas_width / 2) / tile_size)
        tile_y_start = int((center_y - canvas_height / 2) / tile_size)
        tile_x_end = int((center_x + canvas_width / 2) / tile_size) + 2
        tile_y_end = int((center_y + canvas_height / 2) / tile_size) + 2
        
        # Load and composite tiles
        for tx in range(tile_x_start, tile_x_end):
            for ty in range(tile_y_start, tile_y_end):
                # Wrap X coordinate for world wrapping
                wrapped_tx = tx % (2 ** zoom)
                
                tile_img = self.mbtiles.get_tile(zoom, wrapped_tx, ty)
                if tile_img:
                    # Calculate pixel position on canvas
                    px = (tx * tile_size) - (center_x - canvas_width / 2)
                    py = (ty * tile_size) - (center_y - canvas_height / 2)
                    canvas.paste(tile_img, (int(px), int(py)))
        
        # Draw all visible recorded paths from database
        if visible_paths:
            draw = ImageDraw.Draw(canvas)
            
            for path_data in visible_paths:
                points = path_data.get('points', [])
                color = path_data.get('color', 'RED')
                path_color_rgb = self._color_name_to_rgb(color)
                line_width = 2  # Fixed width for saved paths
                
                # Draw lines with black border (outer) and colored inner line
                prev_px, prev_py = None, None
                for lat, lon in points:
                    point_x, point_y = WebMercator.lat_lon_to_world(lat, lon, zoom)
                    px = (point_x - center_x) + canvas_width / 2
                    py = (point_y - center_y) + canvas_height / 2
                    
                    if prev_px is not None:
                        # Draw black border (outer line)
                        border_width = line_width + 2
                        draw.line([(prev_px, prev_py), (px, py)], fill='#000000', width=border_width)
                        
                        # Draw colored inner line
                        draw.line([(prev_px, prev_py), (px, py)], fill=path_color_rgb, width=line_width)
                    
                    prev_px, prev_py = px, py
        
        # Draw recorded route points if provided (for backwards compatibility)
        if route_points and not visible_paths:
            draw = ImageDraw.Draw(canvas)
            route_color_rgb = self._color_name_to_rgb(route_color)
            
            # Convert lat/lon points to pixel coordinates and draw lines
            prev_px, prev_py = None, None
            for lat, lon in route_points:
                point_x, point_y = WebMercator.lat_lon_to_world(lat, lon, zoom)
                px = (point_x - center_x) + canvas_width / 2
                py = (point_y - center_y) + canvas_height / 2
                
                if prev_px is not None:
                    draw.line([(prev_px, prev_py), (px, py)], fill=route_color_rgb, width=route_width)
                
                prev_px, prev_py = px, py
        
        # Draw current recording points and lines (if recording is active)
        if recording_points and len(recording_points) > 0:
            draw = ImageDraw.Draw(canvas)
            recording_color_rgb = self._color_name_to_rgb(recording_color)
            
            # Get line width from config (default 3)
            line_width = 3
            try:
                if hasattr(self, 'parent_map_tab') and self.parent_map_tab:
                    line_width = self.parent_map_tab.config.get_int('route_recording', 'line_width', default=3)
            except:
                pass
            
            # Draw lines connecting points with black border
            prev_px, prev_py = None, None
            for lat, lon in recording_points:
                point_x, point_y = WebMercator.lat_lon_to_world(lat, lon, zoom)
                px = (point_x - center_x) + canvas_width / 2
                py = (point_y - center_y) + canvas_height / 2
                
                if prev_px is not None:
                    # Draw black border (outer line)
                    border_width = line_width + 2
                    draw.line([(prev_px, prev_py), (px, py)], fill='#000000', width=border_width)
                    
                    # Draw colored inner line
                    draw.line([(prev_px, prev_py), (px, py)], fill=recording_color_rgb, width=line_width)
                
                prev_px, prev_py = px, py
            
            # Draw filled circles at each point with sequence number
            # Use position_radius from config for circle size
            try:
                if hasattr(self, 'parent_map_tab') and self.parent_map_tab:
                    position_radius = self.parent_map_tab.config.get_int('map', 'position_radius', default=7)
                else:
                    position_radius = 7
            except:
                position_radius = 7
            
            radius = position_radius
            for idx, (lat, lon) in enumerate(recording_points, start=1):
                point_x, point_y = WebMercator.lat_lon_to_world(lat, lon, zoom)
                px = (point_x - center_x) + canvas_width / 2
                py = (point_y - center_y) + canvas_height / 2
                
                # Draw filled circle
                draw.ellipse(
                    [int(px - radius), int(py - radius), int(px + radius), int(py + radius)],
                    fill=recording_color_rgb,
                    outline='#000000',
                    width=1
                )
                
                # Draw sequence number inside the circle
                sequence_text = str(idx)
                # Use default font (PIL's built-in font)
                font = None  # Use default PIL font
                
                # Calculate text position (centered in circle)
                try:
                    text_bbox = draw.textbbox((0, 0), sequence_text, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                except:
                    # Fallback if textbbox fails
                    text_width = len(sequence_text) * 4
                    text_height = 8
                
                text_x = int(px - text_width / 2)
                text_y = int(py - text_height / 2)
                
                # Draw text in white or black depending on circle color
                text_color = '#FFFFFF' if recording_color_rgb[0] < 128 else '#000000'
                try:
                    draw.text((text_x, text_y), sequence_text, fill=text_color, font=font)
                except:
                    # If text rendering fails, just skip the number
                    pass
        
        # Draw GPS marker if we have position
        if gps_lat is not None and gps_lon is not None:
            self._draw_gps_marker(canvas, gps_lat, gps_lon, zoom, center_x, center_y, canvas_width, canvas_height)
        
        return canvas
    
    def _color_name_to_rgb(self, color_name):
        """Convert color name to RGB tuple."""
        colors = {
            'RED': (255, 0, 0),
            'GREEN': (0, 255, 0),
            'BLUE': (0, 0, 255),
            'YELLOW': (255, 255, 0),
            'CYAN': (0, 255, 255),
            'MAGENTA': (255, 0, 255),
            'WHITE': (255, 255, 255),
            'BLACK': (0, 0, 0),
        }
        return colors.get(color_name.upper(), (255, 0, 0))
    
    def _draw_gps_marker(self, canvas, gps_lat, gps_lon, zoom, center_x, center_y, canvas_width, canvas_height):
        """Draw water droplet GPS marker on canvas with bottom point at GPS position."""
        # Convert GPS position to pixel coordinates
        gps_world_x, gps_world_y = WebMercator.lat_lon_to_world(gps_lat, gps_lon, zoom)
        
        px = (gps_world_x - center_x) + canvas_width / 2
        py = (gps_world_y - center_y) + canvas_height / 2
        
        # Only draw if marker is within canvas bounds
        if -50 < px < canvas_width + 50 and -50 < py < canvas_height + 50:
            draw = ImageDraw.Draw(canvas)
            
            px_int = int(px)
            py_int = int(py)
            
            # Professional water droplet based on SVG formula
            # Rotated 180 degrees so it points DOWN (sharp point at bottom)
            # The BOTTOM POINT (sharp end) should be AT the GPS position
            scale = 1.5
            
            # Offset so bottom point aligns with GPS position
            # Bottom point is normally at (0, 12*scale), so we offset upward
            offset_y = -int(12 * scale)
            
            drop_points = [
                # Bottom point (sharp) - at GPS position
                (px_int, py_int),
                # Left side curving up
                (px_int - int(4 * scale), py_int - int(4 * scale)),
                (px_int - int(8 * scale), py_int - int(12 * scale)),
                (px_int - int(10 * scale), py_int - int(18 * scale)),
                # Left curve up (arc top)
                (px_int - int(10 * scale), py_int - int(22 * scale)),
                (px_int - int(8 * scale), py_int - int(26 * scale)),
                (px_int, py_int - int(28 * scale)),  # Top point
                (px_int + int(8 * scale), py_int - int(26 * scale)),
                # Right curve up (arc top)
                (px_int + int(10 * scale), py_int - int(22 * scale)),
                (px_int + int(10 * scale), py_int - int(18 * scale)),
                # Right side curving down
                (px_int + int(8 * scale), py_int - int(12 * scale)),
                (px_int + int(4 * scale), py_int - int(4 * scale)),
            ]
            
            # Draw black outline
            draw.polygon(drop_points, outline='#000000', width=1)
            # Fill with red
            draw.polygon(drop_points, fill='#FF0000')
            # Inner white line
            draw.polygon(drop_points, outline='#FFFFFF', width=1)
            
            # Label positioned INSIDE the droplet TOP, centered horizontally
            # Calculate text dimensions for proper centering
            try:
                text_bbox = draw.textbbox((0, 0), "GPS", font=None)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
            except:
                text_width = len("GPS") * 4
                text_height = 8
            
            # Position in TOP of droplet (above center, in the round bulbous part)
            # Top of droplet is at: py_int - int(16 * scale) = py_int - 24
            # Put text roughly 1/3 down from top
            label_x = int(px_int - text_width / 2)
            label_y = int(py_int - 16 * scale - 5)  # Top area of droplet
            
            # Draw text in white
            draw.text((label_x, label_y), "GPS", fill='#FFFFFF')


# ============================================================================
# TOUCH-ENABLED MAP CANVAS (QGraphicsView)
# ============================================================================



# ============================================================================
# MAIN WINDOW
# ============================================================================

class MapViewerWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self, mbtiles_path):
        super().__init__()
        
        self.setWindowTitle("seeBoard Map Viewer (Test)")
        self.setGeometry(100, 100, 600, 300)  # Height changed to 300
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # No margins
        layout.setSpacing(0)  # No spacing
        central.setLayout(layout)
        
        # Map canvas - takes up all available space
        self.canvas = MapCanvas(mbtiles_path)
        self.canvas.setMinimumSize(600, 400)
        layout.addWidget(self.canvas, 1)  # Stretch factor = 1
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(2, 2, 2, 2)
        
        btn_zoom_in = QPushButton("+ Zoom In")
        btn_zoom_in.clicked.connect(self.canvas.zoom_in)
        button_layout.addWidget(btn_zoom_in)
        
        btn_zoom_out = QPushButton("- Zoom Out")
        btn_zoom_out.clicked.connect(self.canvas.zoom_out)
        button_layout.addWidget(btn_zoom_out)
        
        btn_recenter = QPushButton("⊕ Recenter GPS")
        btn_recenter.clicked.connect(self.canvas.recenter_on_gps)
        button_layout.addWidget(btn_recenter)
        
        # Info label
        self.info_label = QLabel("Pan: drag mouse | Zoom: scroll wheel | Recenter: R key")
        self.info_label.setStyleSheet("background-color: #f0f0f0; padding: 5px;")
        button_layout.addWidget(self.info_label)
        
        layout.addLayout(button_layout)
        
        # GPS receiver thread
        self.gps_receiver = GPSReceiver()
        self.gps_receiver.position_updated.connect(self.on_gps_position_updated)
        self.gps_receiver.start()
        
        # Timer to update info label
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_info)
        self.timer.start(1000)
    
    def on_gps_position_updated(self, data):
        """Handle GPS position update."""
        if data.get('status') == 'fix':
            lat = data.get('lat')
            lon = data.get('lon')
            if lat is not None and lon is not None:
                self.canvas.set_gps_position(lat, lon)
    
    def update_info(self):
        """Update info label with current map state."""
        if self.canvas.gps_lat is not None:
            self.info_label.setText(
                f"Zoom: {self.canvas.zoom} | "
                f"Center: {self.canvas.center_lat:.4f}, {self.canvas.center_lon:.4f} | "
                f"GPS: {self.canvas.gps_lat:.4f}, {self.canvas.gps_lon:.4f}"
            )


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Run the application."""
    # Find MBTiles file
    mbtiles_dir = Path(__file__).parent / "mbtiles"
    mbtiles_files = list(mbtiles_dir.glob("*.mbtiles"))
    
    if not mbtiles_files:
        print("Error: No .mbtiles files found in mbtiles/ directory")
        sys.exit(1)
    
    mbtiles_path = mbtiles_files[0]
    print(f"Using MBTiles: {mbtiles_path}")
    
    app = QApplication(sys.argv)
    window = MapViewerWindow(str(mbtiles_path))
    window.show()
    
    sys.exit(app.exec_())



    def event(self, event):
        """Handle touch events for pan and pinch-zoom."""
        from PyQt5.QtCore import QEvent
        import math
        
        if event.type() in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd):
            touch_points = event.touchPoints()
            if not touch_points:
                return super().event(event)
            
            num_fingers = len(touch_points)
            
            # Pinch zoom (2+ fingers)
            if num_fingers >= 2:
                p1 = touch_points[0].pos()
                p2 = touch_points[1].pos()
                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                current_distance = math.sqrt(dx*dx + dy*dy)
                
                if event.type() == QEvent.TouchBegin:
                    self._pinch_start_distance = current_distance
                    return True
                elif event.type() == QEvent.TouchUpdate:
                    if not hasattr(self, '_pinch_start_distance'):
                        self._pinch_start_distance = current_distance
                    else:
                        distance_change = current_distance - self._pinch_start_distance
                        if distance_change > 15:
                            self.zoom_in()
                            self._pinch_start_distance = current_distance
                        elif distance_change < -15:
                            self.zoom_out()
                            self._pinch_start_distance = current_distance
                    return True
                elif event.type() == QEvent.TouchEnd:
                    self._pinch_start_distance = 0
                    return True
            
            # Single finger pan
            elif num_fingers == 1:
                touch_point = touch_points[0]
                pos = touch_point.pos().toPoint()
                
                if event.type() == QEvent.TouchBegin:
                    self.last_mouse_pos = pos
                    return True
                elif event.type() == QEvent.TouchUpdate:
                    if hasattr(self, 'last_mouse_pos') and self.last_mouse_pos:
                        delta = pos - self.last_mouse_pos
                        self.pan_by_pixels(delta.x(), delta.y())
                        self.last_mouse_pos = pos
                    return True
                elif event.type() == QEvent.TouchEnd:
                    self.last_mouse_pos = None
                    return True
        
        return super().event(event)

class MapTab(QWidget):
    """Map Tab with QGraphicsView, MBTiles, GPS tracking, and recording."""
    
    def __init__(self, config, scale_factor=1.0):
        super().__init__()
        self.config = config
        self.scale_factor = scale_factor
        
        # Current GPS position
        self.current_lat = 56.1612
        self.current_lon = 15.5869
        
        # Map mode
        self.map_mode = "FREE"
        
        # Recording state
        self.is_recording = False
        self.current_recording_path_id = None
        self.current_recording_color = None
        self.current_recording_points = []
        self.recording_time_interval = 15
        self.last_recording_time = None
        self.recording_timer = None
        
        # Initialize route recorder
        try:
            from route_database import PathDatabase
            from route_recorder import RouteRecorder
            self.db = PathDatabase(self.config)
            self.recorder = RouteRecorder(self.db)
        except Exception as e:
            self.db = None
            self.recorder = None
        
        # Find MBTiles
        mbtiles_dir = Path(__file__).parent.parent / "mbtiles"
        if not mbtiles_dir.exists():
            mbtiles_dir = Path.home() / "Projects/seeboard/mbtiles"
        
        mbtiles_files = list(mbtiles_dir.glob("*.mbtiles"))
        if mbtiles_files:
            mbtiles_path = str(mbtiles_files[0])
        else:
            mbtiles_path = None
        
        # Create UI
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Map canvas (QGraphicsView with touch support)
        if mbtiles_path:
            self.canvas = MapCanvas(mbtiles_path)
            self.canvas.parent_map_tab = self  # Reference back to MapTab for recording state
            main_layout.addWidget(self.canvas, 1)
            
            # Control buttons - Top row: pan, recenter, mode toggle
            top_button_layout = QHBoxLayout()
            top_button_layout.setContentsMargins(5, 5, 5, 5)
            top_button_layout.setSpacing(3)
            
            # Pan buttons - wider for touch
            btn_pan_up = QPushButton("Pan ↑")
            btn_pan_up.setMinimumWidth(70)
            btn_pan_up.setMinimumHeight(45)
            btn_pan_up.clicked.connect(self._pan_up)
            top_button_layout.addWidget(btn_pan_up)
            
            btn_pan_down = QPushButton("Pan ↓")
            btn_pan_down.setMinimumWidth(70)
            btn_pan_down.setMinimumHeight(45)
            btn_pan_down.clicked.connect(self._pan_down)
            top_button_layout.addWidget(btn_pan_down)
            
            btn_pan_left = QPushButton("Pan ←")
            btn_pan_left.setMinimumWidth(70)
            btn_pan_left.setMinimumHeight(45)
            btn_pan_left.clicked.connect(self._pan_left)
            top_button_layout.addWidget(btn_pan_left)
            
            btn_pan_right = QPushButton("Pan →")
            btn_pan_right.setMinimumWidth(70)
            btn_pan_right.setMinimumHeight(45)
            btn_pan_right.clicked.connect(self._pan_right)
            top_button_layout.addWidget(btn_pan_right)
            
            btn_recenter = QPushButton("Recenter")
            btn_recenter.setMinimumWidth(80)
            btn_recenter.setMinimumHeight(45)
            btn_recenter.clicked.connect(self.canvas.recenter_on_gps)
            top_button_layout.addWidget(btn_recenter)
            
            # Mode toggle button
            self.mode_toggle_btn = QPushButton(f"Mode: {self.map_mode}")
            self.mode_toggle_btn.setMinimumWidth(100)
            self.mode_toggle_btn.setMinimumHeight(45)
            self.mode_toggle_btn.clicked.connect(self.toggle_map_mode)
            top_button_layout.addWidget(self.mode_toggle_btn)
            
            main_layout.addLayout(top_button_layout)
            
            # Control buttons - Bottom row: Record, Stop (both stretch horizontally)
            bottom_button_layout = QHBoxLayout()
            bottom_button_layout.setContentsMargins(5, 5, 5, 5)
            bottom_button_layout.setSpacing(5)
            
            # Record button - green, stretches
            self.btn_record = QPushButton("● RECORD")
            self.btn_record.setMinimumHeight(45)
            self.btn_record.setStyleSheet("""
                QPushButton {
                    background-color: #00AA00;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    font-size: 16px;
                }
                QPushButton:hover:!disabled {
                    background-color: #00CC00;
                }
                QPushButton:pressed:!disabled {
                    background-color: #008800;
                }
                QPushButton:disabled {
                    background-color: #666666;
                    color: #999999;
                }
            """)
            self.btn_record.clicked.connect(self.start_recording)
            bottom_button_layout.addWidget(self.btn_record, 1)  # Stretch
            
            # Stop button - red, stretches
            self.btn_stop = QPushButton("⏹ STOP")
            self.btn_stop.setMinimumHeight(45)
            self.btn_stop.setEnabled(False)
            self.btn_stop.setStyleSheet("""
                QPushButton {
                    background-color: #AA0000;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    font-size: 16px;
                }
                QPushButton:hover:!disabled {
                    background-color: #CC0000;
                }
                QPushButton:pressed:!disabled {
                    background-color: #880000;
                }
                QPushButton:disabled {
                    background-color: #666666;
                    color: #999999;
                }
            """)
            self.btn_stop.clicked.connect(self.stop_recording)
            bottom_button_layout.addWidget(self.btn_stop, 1)  # Stretch
            
            main_layout.addLayout(bottom_button_layout)
        else:
            label = QLabel("Error: MBTiles file not found!")
            main_layout.addWidget(label)
            self.canvas = None
        
        self.setLayout(main_layout)
        
        # Create mode label as overlay on the map
        # This must be created AFTER the canvas is added to the layout
        if mbtiles_path:
            self.status_label = QLabel(f"Mode: {self.map_mode}")
            self.status_label.setStyleSheet(
                "background-color: rgba(0, 0, 0, 200); "
                "color: white; "
                "padding: 8px 12px; "
                "font-weight: bold; "
                "border-radius: 4px; "
                "min-width: 100px; "
                "text-align: center;"
            )
            self.status_label.setAlignment(Qt.AlignCenter)
            self.status_label.setMaximumHeight(35)
            self.status_label.setMaximumWidth(140)
            
            # Position label at bottom-right of canvas by setting parent
            self.status_label.setParent(self.canvas)
            self.status_label.show()  # Make sure it's visible
            self.status_label.move(self.canvas.width() - 150, self.canvas.height() - 45)
    
    def resizeEvent(self, event):
        """Reposition mode label when widget is resized."""
        super().resizeEvent(event)
        if hasattr(self, 'status_label') and hasattr(self, 'canvas') and self.canvas:
            # Reposition label at bottom-right corner
            self.status_label.move(self.canvas.width() - 150, self.canvas.height() - 45)
    
    def event(self, event):
        """Forward touch events to the canvas so it can handle panning/zooming."""
        if event.type() in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd):
            if hasattr(self, 'canvas') and self.canvas:
                return self.canvas.event(event)
        return super().event(event)
    
    def _pan_up(self):
        """Pan up by 30 pixels."""
        self.canvas.pan_by(0, 30)
    
    def _pan_down(self):
        """Pan down by 30 pixels."""
        self.canvas.pan_by(0, -30)
    
    def _pan_left(self):
        """Pan left by 30 pixels."""
        self.canvas.pan_by(30, 0)
    
    def _pan_right(self):
        """Pan right by 30 pixels."""
        self.canvas.pan_by(-30, 0)
    
    def toggle_map_mode(self):
        """Toggle between FREE and FOLLOW modes."""
        if self.map_mode == "FREE":
            self.map_mode = "FOLLOW"
        else:
            self.map_mode = "FREE"
        self.mode_toggle_btn.setText(f"Mode: {self.map_mode}")
        self.status_label.setText(f"Mode: {self.map_mode}")
    
    def on_tab_shown(self):
        """Called when MapTab is made visible - ensure mode label is visible."""
        if hasattr(self, 'status_label') and hasattr(self, 'canvas') and self.canvas:
            self.status_label.show()
            # Reposition to ensure it's at the right place
            self.status_label.move(self.canvas.width() - 150, self.canvas.height() - 45)
    
    def on_gps_update(self, gps_data):
        """Handle GPS position update from main GPS receiver."""
        if not self.canvas:
            return
        
        if gps_data and gps_data.get('status') == 'fix':
            lat = gps_data.get('lat')
            lon = gps_data.get('lon')
            
            if lat is not None and lon is not None:
                self.current_lat = lat
                self.current_lon = lon
                
                # Update GPS marker on map
                self.canvas.set_gps_position(lat, lon)
                
                # Auto-center on first GPS fix
                if (self.canvas.center_lat == 56.161200 and self.canvas.center_lon == 15.586900 and 
                    (lat != 56.1612 or lon != 15.5869)):
                    self.canvas.recenter_on_gps()
                
                # If in FOLLOW mode, keep centered on GPS
                elif self.map_mode == "FOLLOW":
                    self.canvas.center_lat = lat
                    self.canvas.center_lon = lon
                
                # Re-render to show updated GPS position
                self.canvas.render_map()
                
                # Record GPS point if recording
                if self.is_recording and self.recorder and self.current_recording_path_id:
                    # The timer handles recording points - don't record here
                    pass
    
    def start_recording(self):
        """Start recording route with time-based sampling."""
        if not self.recorder:
            print("[MAP] Recorder not initialized")
            return
        
        try:
            from datetime import datetime
            
            # Generate path name from current time: YYYY-mm-ddTHH:MM:SS
            path_name = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            
            # Get recording settings from config
            line_color = self.config.get_str('route_recording', 'line_color', default='RED')
            line_width = self.config.get_int('route_recording', 'line_width', default=3)
            point_diameter = self.config.get_int('route_recording', 'point_diameter', default=8)
            point_color = self.config.get_str('route_recording', 'point_color', default='red')
            
            # Get time-based sampling interval (e.g., "15s" -> 15 seconds)
            time_sampling_str = self.config.get_str('map', 'time_based_sampling', default='15s')
            time_interval = int(time_sampling_str.rstrip('s'))
            
            # Start recording in the recorder
            path_id = self.recorder.db.start_new_path(path_name, line_color)
            
            if path_id:
                self.is_recording = True
                self.current_recording_path_id = path_id
                self.current_recording_color = line_color
                self.current_recording_points = []
                self.recording_time_interval = time_interval
                self.last_recording_time = None
                
                # Record the first position immediately
                if self.current_lat is not None and self.current_lon is not None:
                    self.recorder.db.add_point_to_path(
                        self.current_recording_path_id,
                        self.current_lat,
                        self.current_lon
                    )
                    self.current_recording_points.append((self.current_lat, self.current_lon))
                    print(f"[MAP] Recorded first position: ({self.current_lat}, {self.current_lon})")
                
                # AUTO-SWITCH TO FOLLOW MODE for recording
                self.map_mode = "FOLLOW"
                self.mode_toggle_btn.setText(f"Mode: {self.map_mode}")
                self.status_label.setText(f"Mode: {self.map_mode}")
                self.status_label.setStyleSheet(
                    "background-color: rgba(255, 0, 0, 200); "
                    "color: white; "
                    "padding: 8px 12px; "
                    "font-weight: bold; "
                    "border-radius: 4px; "
                    "min-width: 100px; "
                    "text-align: center;"
                )
                
                # Update UI - swap button states
                self.btn_record.setEnabled(False)
                self.btn_stop.setEnabled(True)
                
                # Re-render map to show first point
                if hasattr(self, 'canvas'):
                    self.canvas.render_map()
                
                # Start a timer to record GPS points at time intervals
                from PyQt5.QtCore import QTimer
                self.recording_timer = QTimer()
                self.recording_timer.timeout.connect(self._record_gps_point_timed)
                self.recording_timer.start(time_interval * 1000)  # Convert to milliseconds
                
                print(f"[MAP] Started recording: Path {path_id} '{path_name}' ({line_color})")
                print(f"[MAP] Time-based sampling: every {time_interval}s")
                print(f"[MAP] Auto-switched to FOLLOW mode")
                
        except Exception as e:
            print(f"[MAP] Error starting recording: {e}")
            import traceback
            traceback.print_exc()
    
    def stop_recording(self):
        """Stop recording route and save to database."""
        if not self.is_recording or not self.recorder:
            print("[MAP] Not currently recording")
            return
        
        try:
            # Stop the timer
            if hasattr(self, 'recording_timer'):
                self.recording_timer.stop()
            
            # Stop recording in the recorder
            path_id = self.recorder.db.stop_path(self.current_recording_path_id)
            
            self.is_recording = False
            
            # Switch back to FREE mode
            self.map_mode = "FREE"
            self.mode_toggle_btn.setText(f"Mode: {self.map_mode}")
            self.status_label.setText(f"Mode: {self.map_mode}")
            self.status_label.setStyleSheet(
                "background-color: rgba(0, 0, 0, 200); "
                "color: white; "
                "padding: 8px 12px; "
                "font-weight: bold; "
                "border-radius: 4px; "
                "min-width: 100px; "
                "text-align: center;"
            )
            
            # Update UI - swap button states
            self.btn_record.setEnabled(True)
            self.btn_stop.setEnabled(False)
            
            print(f"[MAP] Stopped recording: Path {path_id}")
            print(f"[MAP] Switched back to FREE mode")
            
            self.current_recording_path_id = None
            self.current_recording_color = None
            self.current_recording_points = []
            
            # Re-render map to hide recording overlay
            if hasattr(self, 'canvas'):
                self.canvas.render_map()
            
        except Exception as e:
            print(f"[MAP] Error stopping recording: {e}")
            import traceback
            traceback.print_exc()
    
    def _record_gps_point_timed(self):
        """Record GPS point at time interval (called by timer)."""
        if not self.is_recording or self.current_lat is None or self.current_lon is None:
            return
        
        try:
            # Add point to database
            if self.recorder and self.current_recording_path_id:
                self.recorder.db.add_point_to_path(
                    self.current_recording_path_id,
                    self.current_lat,
                    self.current_lon
                )
                
                # Store point locally for drawing
                self.current_recording_points.append((self.current_lat, self.current_lon))
                
                # Recenter on new recorded position
                if hasattr(self, 'canvas'):
                    self.canvas.recenter_on_gps()
                
        except Exception as e:
            print(f"[MAP] Error recording GPS point: {e}")


class CamTab(QWidget):
    """Camera Display - uses same pattern as tkinter"""
    
    def __init__(self, config, scale_factor=1.0):
        super().__init__()
        self.config = config
        self.scale_factor = scale_factor
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # No margins for fullscreen
        
        self.cam_label = QLabel("Searching for cameras...")
        self.cam_label.setFont(QFont("Arial", 14))
        self.cam_label.setMinimumSize(400, 300)  # Minimum size, will grow with window
        self.cam_label.setScaledContents(True)  # Scale pixmap to fill label
        self.cam_label.setStyleSheet("border: 1px solid black; background: black;")
        self.cam_label.setAlignment(Qt.AlignCenter)
        self.cam_label.setCursor(Qt.PointingHandCursor)  # Show clickable cursor
        layout.addWidget(self.cam_label)
        self.setLayout(layout)
        
        # Track window size for composite generation
        self.current_width = None  # Will be set on first display
        self.current_height = None
        self.first_resize = True  # Flag to defer initial sizing
        
        # Track expired cameras (had frames before, lost signal after grace period)
        self.expired_cameras = {}  # url -> expiry_time
        
        # Fullscreen state: None = grid view, or url string = fullscreen for that camera
        self.fullscreen_url = None
        
        # Camera positions for grid layout (for click detection)
        self.camera_positions = {}  # url -> (x, y, w, h) on composite
        
        # Timer to update camera display every 50ms (same as tkinter)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(50)
    
    def mousePressEvent(self, event):
        """Handle mouse clicks on camera image"""
        if not self.fullscreen_url:
            # In grid view - find which camera was clicked
            click_x = event.pos().x()
            click_y = event.pos().y()
            
            # Scale click position to composite image coordinates
            label_rect = self.cam_label.rect()
            if label_rect.width() > 0 and label_rect.height() > 0:
                scale_x = self.current_width / label_rect.width()
                scale_y = self.current_height / label_rect.height()
                img_x = int(click_x * scale_x)
                img_y = int(click_y * scale_y)
                
                # Find which camera was clicked
                for url, (x, y, w, h) in self.camera_positions.items():
                    if x <= img_x < x + w and y <= img_y < y + h:
                        self.fullscreen_url = url
                        break
        else:
            # In fullscreen - click to go back to grid
            self.fullscreen_url = None
    
    def resizeEvent(self, event):
        """Handle resize to capture actual widget size on first show"""
        super().resizeEvent(event)
        
        # On first resize, set the actual dimensions from the label
        if self.first_resize and self.cam_label.width() > 100:
            self.current_width = self.cam_label.width()
            self.current_height = self.cam_label.height()
            self.first_resize = False
            print(f"[CAM] First resize: set dimensions to {self.current_width}x{self.current_height}")
    
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
            log_msg = f"[DISPLAY] URLs: {len(urls)}, Expired: {len(self.expired_cameras)}, Fullscreen: {self.fullscreen_url}\n"
            
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
            
            # Debug logging (disabled to avoid permission issues when running as root)
            # with open('/tmp/seeboard_display.log', 'a') as f:
            #     f.write(log_msg)
            if not urls:
                self.cam_label.setText("Searching for cameras...")
                return
            
            # Get current label size (will be fullscreen or window size)
            # IMPORTANT: Always use the label's actual size, not minimums
            label_rect = self.cam_label.size()
            w = label_rect.width()
            h = label_rect.height()
            
            # Only use minimum if size is too small (happens during initial layout)
            if w < 200:
                w = 400
            if h < 150:
                h = 300
            
            # Store for click detection scaling
            self.current_width = w
            self.current_height = h
            
            # Cameras to display: all EXCEPT permanently expired ones
            display_urls = [u for u in urls if u not in self.expired_cameras]
            
            if not display_urls:
                self.cam_label.setText("All cameras expired...")
                return
            
            # Clear previous positions
            self.camera_positions.clear()
            
            # If fullscreen mode and camera is no longer available, exit fullscreen
            if self.fullscreen_url and self.fullscreen_url not in display_urls:
                self.fullscreen_url = None
            
            # Setup grid or fullscreen
            if self.fullscreen_url:
                # FULLSCREEN MODE - display only selected camera
                display_urls = [self.fullscreen_url]
                cols = 1
                rows = 1
            else:
                # GRID MODE - normal multi-camera display
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
                
                # Draw label (bottom-left) with red background if in fullscreen, black otherwise
                bbox = draw.textbbox((0, 0), display, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                x = 5
                y = img.height - text_h - 5
                
                # Use red background if this is the fullscreen camera, otherwise black
                label_bg_color = (255, 0, 0, 200) if (self.fullscreen_url and self.fullscreen_url == url) else (0, 0, 0, 200)
                draw.rectangle([(x-3, y-3), (x+text_w+3, y+text_h+3)], fill=label_bg_color)
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
                x_pos = c * cell_w
                y_pos = r * cell_h
                composite.paste(img, (x_pos, y_pos))
                
                # Record camera position for click detection
                self.camera_positions[url] = (x_pos, y_pos, cell_w, cell_h)
            
            # Display
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                composite.save(f.name)
                pixmap = __import__('PyQt5.QtGui', fromlist=['QPixmap']).QPixmap(f.name)
                __import__('os').unlink(f.name)
            
            # Just set the pixmap - QLabel will scale it to fill the label due to setScaledContents(True)
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
    
    def __init__(self, config, main_window=None, scale_factor=1.0):
        super().__init__()
        self.config = config
        self.main_window = main_window
        self.scale_factor = scale_factor
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
    
    def __init__(self, config, main_window=None, scale_factor=1.0):
        super().__init__()
        self.config = config
        self.main_window = main_window  # Reference to parent window for triggering map refresh
        self.scale_factor = scale_factor
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
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Load paths on startup
        self.refresh_paths()
    
    def on_tab_shown(self):
        """Called when PATHS tab becomes visible - auto-refresh the list"""
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
        log("[APP] SeeBoardApp.__init__ starting")
        
        # Load config from ~/.seeboard/see_board.cfg
        log("[APP] Loading config...")
        config_dir = os.path.expanduser("~/.seeboard")
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, "see_board.cfg")
        config = ConfigParser()
        config.read(config_file)
        
        # Create centralized config loader
        log("[APP] Creating ConfigLoader...")
        self.config = ConfigLoader(config)
        self.config.ensure_sections(['gps', 'coords', 'route_recording', 'camera_rotations', 'cam', 'map', 'database'])
        
        # Initialize route recorder BEFORE creating tabs (PathsTab needs it)
        log("[APP] Initializing route recorder...")
        init_route_recorder(self.config)
        
        log("[APP] Setting window title...")
        self.setWindowTitle("seeBoard - GPS & Camera Dashboard")
        
        # Get screen dimensions
        log("[APP] Getting screen dimensions...")
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import QRect
        screen = QApplication.primaryScreen()
        screen_geom = screen.geometry()
        self.screen_width = screen_geom.width()
        self.screen_height = screen_geom.height()
        
        log(f"[APP] Screen: {self.screen_width}x{self.screen_height}")
        
        # Calculate scale factor based on screen height (720 is our base)
        self.scale_factor = self.screen_height / 720.0
        
        # IMPORTANT: Set geometry BEFORE showing - this ensures window starts at correct size
        log("[APP] Setting geometry...")
        self.setGeometry(QRect(0, 0, self.screen_width, self.screen_height))
        
        # Now show fullscreen
        log("[APP] Showing fullscreen...")
        self.showFullScreen()
        
        # Override any window manager attempts to resize
        self.setMinimumSize(self.screen_width, self.screen_height)
        self.setMaximumSize(self.screen_width, self.screen_height)
        
        log("[APP] About to create tabs...")
        
        # Create tabs (pass ConfigLoader and scale factor to all tabs)
        self.tabs = QTabWidget()
        try:
            log(f"[APP] Creating CoordsTab...")
            self.coords_tab = CoordsTab(self.config, self.scale_factor)
            log(f"[APP] Creating MapTab...")
            self.map_tab = MapTab(self.config, self.scale_factor)  # Save reference BEFORE adding to tabs
            log(f"[APP] map_tab saved: {self.map_tab}")
            log(f"[APP] Creating PathsTab...")
            self.paths_tab = PathsTab(self.config, self, self.scale_factor)
            log(f"[APP] Creating CamTab...")
            self.cam_tab = CamTab(self.config, self.scale_factor)
            log(f"[APP] Creating ConfTab...")
            self.conf_tab = ConfTab(self.config, self, self.scale_factor)
            log(f"[APP] All tabs created successfully")
        except Exception as e:
            log(f"[APP] ERROR creating tabs: {e}")
            import traceback
            log(traceback.format_exc())
            raise
        
        self.tabs.addTab(self.coords_tab, self.TAB_NAMES['coords'])
        self.tabs.addTab(self.map_tab, self.TAB_NAMES['map'])
        self.tabs.addTab(self.paths_tab, self.TAB_NAMES['paths'])
        self.tabs.addTab(self.cam_tab, self.TAB_NAMES['cam'])
        self.tabs.addTab(self.conf_tab, self.TAB_NAMES['conf'])
        
        # IMPORTANT: Connect GPS updates from CoordsTab to MapTab
        # CoordsTab creates the GPS worker, so we need to forward updates to MapTab
        log(f"[APP] Linking coords_tab GPS to map_tab...")
        self.coords_tab.map_tab_reference = self.map_tab
        log(f"[APP] coords_tab.map_tab_reference set to {self.map_tab}")
        
        # Style tabs for touchscreen - simple and proper
        tab_padding = int(6 * self.scale_factor)
        tab_font_size = int(12 * self.scale_factor)
        tab_min_height = int(35 * self.scale_factor)
        
        tab_stylesheet = f"""
            QTabBar::tab {{
                background-color: #f5f5f5;
                color: #333;
                padding: {tab_padding}px 20px;
                border: 1px solid #ddd;
                font-size: {tab_font_size}px;
                font-weight: bold;
                min-height: {tab_min_height}px;
            }}
            QTabBar::tab:selected {{
                background-color: #007AFF;
                color: white;
                border: 1px solid #0051d5;
            }}
            QTabBar::tab:hover {{
                background-color: #0051d5;
                color: white;
            }}
        """
        self.tabs.setStyleSheet(tab_stylesheet)
        
        # Enable expanding to fill space
        self.tabs.tabBar().setExpanding(True)
        
        # Force tab bar to take full width
        self.tabs.tabBar().setMinimumWidth(self.screen_width)
        self.tabs.tabBar().setMaximumWidth(self.screen_width)
        
        # Connect tab change signal
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Create a central widget with layout to properly manage space
        central_widget = QWidget()
        central_widget.setStyleSheet("border: 0px; margin: 0px; padding: 0px;")
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        central_layout.setSpacing(0)  # No spacing
        central_layout.addWidget(self.tabs, 1)  # Give tabs all available space
        
        self.setCentralWidget(central_widget)
        
        # Remove all margins and spacing
        self.setContentsMargins(0, 0, 0, 0)
        
        # Ensure tabs expand to fill space
        from PyQt5.QtWidgets import QSizePolicy
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Remove any maximum size restrictions on tabs and their children
        self.tabs.setMaximumSize(16777215, 16777215)  # Qt's maximum size
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            tab.setMaximumSize(16777215, 16777215)
            tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tabs.setStyleSheet(self.tabs.styleSheet() + """
            QTabWidget { border: 0px; margin: 0px; padding: 0px; }
            QTabBar { border: 0px; margin: 0px; padding: 0px; }
        """)
        
        # Schedule backend services to start after UI is shown
        # Use QTimer to defer startup to allow window to render first
        QTimer.singleShot(500, self._start_backend_services)
    
    def _start_backend_services(self):
        """Start backend services after UI is displayed"""
        print("[APP] Starting backend services...")
        try:
            gps_core.start_background_reader()
        except Exception as e:
            print(f"[APP] Error starting GPS: {e}")
        
        try:
            cam_discovery.start()
        except Exception as e:
            print(f"[APP] Error starting cam discovery: {e}")
        
        try:
            start_new_cameras()
        except Exception as e:
            print(f"[APP] Error starting cameras: {e}")
    
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
    log("main() starting")
    try:
        log("Creating QApplication...")
        app = QApplication(sys.argv)
        log("Creating SeeBoardApp window...")
        window = SeeBoardApp()
        log("Showing window...")
        window.show()
        log("Running exec loop...")
        sys.exit(app.exec_())
    except Exception as e:
        log(f"ERROR in main: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    log("Script entry point")
    main()
