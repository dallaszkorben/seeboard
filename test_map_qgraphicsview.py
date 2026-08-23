#!/usr/bin/env python3
"""
Map Viewer - PyQt5 QGraphicsView Implementation (Proven Architecture)

Based on proven PyQtImageViewer pattern with integrated MBTiles rendering.
Uses QGraphicsView for built-in pan/zoom - eliminates race conditions.

Features:
- Pan: Middle mouse button drag (or left button with Ctrl)
- Zoom: Mouse wheel or buttons
- Recenter: R key or button
- GPS marker: Water droplet at current position
"""

import sys
import sqlite3
import io
import math
from pathlib import Path

from PyQt5.QtCore import Qt, QRectF, QPoint, QPointF, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
)
from PIL import Image, ImageDraw


# ============================================================================
# WEB MERCATOR PROJECTION & COORDINATE CONVERSION
# ============================================================================

class WebMercator:
    """Web Mercator coordinate conversion utilities."""
    
    TILE_SIZE = 256
    MAX_LAT = 85.05112878
    
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
            
            # Water droplet: circle with point
            radius = 8
            
            # Circle (red fill, white outline)
            draw.ellipse(
                [int(px - radius), int(py - radius), int(px + radius), int(py)],
                fill='#FF0000', outline='#FFFFFF', width=2
            )
            
            # Point (triangle at bottom)
            draw.polygon(
                [(int(px - radius), int(py)), (int(px + radius), int(py)), (int(px), int(py + radius + 3))],
                fill='#FF0000', outline='#FFFFFF'
            )
            
            # Label
            draw.text((int(px - 15), int(py - 25)), "GPS", fill='#FFFFFF')


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
        
        # Initial render
        self.render_map()
    
    def render_map(self):
        """Render map and apply pan offset, loading extra tiles for coverage."""
        # Skip if already rendering to prevent race conditions
        if self._is_zooming:
            return
        
        self._is_zooming = True
        
        try:
            # Create a larger canvas to accommodate pan offset
            expanded_width = self.canvas_width + abs(self.pan_offset_x) + 512
            expanded_height = self.canvas_height + abs(self.pan_offset_y) + 512
            
            # Render tiles to PIL Image at current zoom level (larger area)
            canvas = self.renderer.render_map_canvas(
                self.zoom, self.center_lat, self.center_lon,
                expanded_width, expanded_height,
                self.gps_lat, self.gps_lon
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
        print(f"[PAN] pan_by({pixel_dx}, {pixel_dy}), current offset=({self.pan_offset_x}, {self.pan_offset_y})")
        # Accumulate pan offset
        self.pan_offset_x += pixel_dx
        self.pan_offset_y += pixel_dy
        print(f"[PAN] new offset=({self.pan_offset_x}, {self.pan_offset_y})")
        
        # Re-render with the new offset (renderer will load appropriate tiles)
        self.render_map()
    
    def zoom_in(self):
        """Zoom in to next available zoom level, keeping window center position fixed."""
        # Available zoom levels in MBTiles: 8, 10, 12, 14, 16
        available_zooms = [8, 10, 12, 14, 16]
        
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
        # Available zoom levels in MBTiles: 8, 10, 12, 14, 16
        available_zooms = [8, 10, 12, 14, 16]
        
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
        # Available zoom levels in MBTiles: 8, 10, 12, 14, 16 (NOT consecutive!)
        available_zooms = [8, 10, 12, 14, 16]
        
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
            print(f"[PAN SPEED] Increased to {self.pan_speed_multiplier:.1f}x")
        elif event.key() == Qt.Key_BracketLeft:  # [ key - decrease pan speed
            self.pan_speed_multiplier -= 0.1
            self.pan_speed_multiplier = max(self.pan_speed_multiplier, 0.5)  # Min 0.5x
            print(f"[PAN SPEED] Decreased to {self.pan_speed_multiplier:.1f}x")
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
            print(f"[TOUCH] {num_fingers} fingers - Event type: {event.type()}")
            
            # ──── PINCH-TO-ZOOM (2+ fingers) ────
            if num_fingers >= 2:
                print(f"[ZOOM] {num_fingers} fingers detected - processing pinch")
                point1 = touch_event.touchPoints()[0].pos()
                point2 = touch_event.touchPoints()[1].pos()
                
                # Calculate distance between two touch points
                dx = point2.x() - point1.x()
                dy = point2.y() - point1.y()
                current_distance = math.sqrt(dx*dx + dy*dy)
                print(f"[ZOOM] Distance: {current_distance:.1f}")
                
                if event.type() == QEvent.TouchBegin:
                    print(f"[ZOOM] Pinch BEGIN: distance={current_distance:.1f}")
                    self._pinch_start_distance = current_distance
                    self._is_panning = False  # Disable pan during pinch
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchUpdate:
                    print(f"[ZOOM] Pinch UPDATE")
                    # On first 2-finger contact, TouchUpdate arrives instead of TouchBegin
                    # So initialize pinch_start_distance here if not already set
                    if not hasattr(self, '_pinch_start_distance') or self._pinch_start_distance == 0:
                        print(f"[ZOOM] First 2-finger event - initializing pinch distance")
                        self._pinch_start_distance = current_distance
                        event.accept()
                        return True
                    
                    distance_change = current_distance - self._pinch_start_distance
                    print(f"[ZOOM] current={current_distance:.1f}, start={self._pinch_start_distance:.1f}, change={distance_change:.1f}")
                    
                    # Pinch threshold: require 15+ pixels change to zoom
                    if distance_change > 15:
                        print(f"[ZOOM] *** ZOOMING IN (change={distance_change:.1f} > 15) ***")
                        self.zoom_in()
                        self._pinch_start_distance = current_distance  # Reset for next zoom
                    elif distance_change < -15:
                        print(f"[ZOOM] *** ZOOMING OUT (change={distance_change:.1f} < -15) ***")
                        self.zoom_out()
                        self._pinch_start_distance = current_distance  # Reset for next zoom
                    
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchEnd:
                    print(f"[ZOOM] Pinch END")
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
                    print(f"[TOUCH] Single finger pan start at {pos}")
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
                        print(f"[TOUCH] Pan delta: dx={pan_dx}, dy={pan_dy}")
                        # Pan by OPPOSITE amount (invert delta so dragging left pans the map left)
                        self.pan_by(pan_dx, pan_dy)
                        self._last_pan_pos = pos
                    event.accept()
                    return True
                
                elif event.type() == QEvent.TouchEnd:
                    # Stop pan when finger lifted
                    print(f"[TOUCH] Single finger pan end")
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

class MapViewerWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self, mbtiles_path):
        super().__init__()
        
        self.setWindowTitle("seeBoard Map Viewer (QGraphicsView)")
        self.setFixedSize(600, 300)  # Fixed size for testing
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        central.setLayout(layout)
        
        # Map canvas
        self.canvas = MapCanvas(mbtiles_path)
        layout.addWidget(self.canvas, 1)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(2, 2, 2, 2)
        
        # Pan buttons (UP, DOWN, LEFT, RIGHT)
        # Each click = 20 visual pixels
        btn_pan_up = QPushButton("↑ Pan Up")
        btn_pan_up.clicked.connect(lambda: self.canvas.pan_by(0, -20))
        button_layout.addWidget(btn_pan_up)
        
        btn_pan_down = QPushButton("↓ Pan Down")
        btn_pan_down.clicked.connect(lambda: self.canvas.pan_by(0, 20))
        button_layout.addWidget(btn_pan_down)
        
        btn_pan_left = QPushButton("← Pan Left")
        btn_pan_left.clicked.connect(lambda: self.canvas.pan_by(-20, 0))
        button_layout.addWidget(btn_pan_left)
        
        btn_pan_right = QPushButton("→ Pan Right")
        btn_pan_right.clicked.connect(lambda: self.canvas.pan_by(20, 0))
        button_layout.addWidget(btn_pan_right)
        
        # Zoom buttons
        btn_zoom_in = QPushButton("+ Zoom In")
        btn_zoom_in.clicked.connect(self.canvas.zoom_in)
        button_layout.addWidget(btn_zoom_in)
        
        btn_zoom_out = QPushButton("- Zoom Out")
        btn_zoom_out.clicked.connect(self.canvas.zoom_out)
        button_layout.addWidget(btn_zoom_out)
        
        btn_recenter = QPushButton("⊕ Recenter GPS")
        btn_recenter.clicked.connect(self.canvas.recenter_on_gps)
        button_layout.addWidget(btn_recenter)
        
        self.info_label = QLabel("Pan: 1 finger drag | Zoom: 2 finger pinch | Speed: [ ] keys | Recenter: R")
        self.info_label.setStyleSheet("background-color: #f0f0f0; padding: 3px;")
        button_layout.addWidget(self.info_label)
        
        layout.addLayout(button_layout)
        
        # GPS receiver
        self.gps_receiver = GPSReceiver()
        self.gps_receiver.position_updated.connect(self.on_gps_update)
        self.gps_receiver.start()
        
        # Track if we've auto-centered on first GPS fix
        self._gps_auto_centered = False
        
        # Info update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_info)
        self.timer.start(1000)
    
    def on_gps_update(self, data):
        """Handle GPS update."""
        if data.get('status') == 'fix':
            lat = data.get('lat')
            lon = data.get('lon')
            if lat is not None and lon is not None:
                print(f"[GPS] Update received: lat={lat}, lon={lon}, auto_centered={self._gps_auto_centered}")
                self.canvas.set_gps_position(lat, lon)
                
                # Auto-center on first GPS fix ONLY
                if not self._gps_auto_centered:
                    print(f"[GPS] Auto-centering on first fix")
                    self.canvas.recenter_on_gps()
                    self._gps_auto_centered = True
                else:
                    print(f"[GPS] Skipping auto-center (already done)")
    
    def update_info(self):
        """Update info label."""
        if self.canvas.gps_lat is not None:
            self.info_label.setText(
                f"Z{self.canvas.zoom} | Pan speed: {self.canvas.pan_speed_multiplier:.1f}x | "
                f"Center: {self.canvas.center_lat:.4f}, {self.canvas.center_lon:.4f}"
            )


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Run the application."""
    # Redirect stdout/stderr to log file for debugging
    import sys
    log_file = open('/home/pi/Projects/seeboard/touch_debug.log', 'w')
    sys.stdout = log_file
    sys.stderr = log_file
    
    # Find MBTiles file
    mbtiles_dir = Path(__file__).parent / "mbtiles"
    mbtiles_files = list(mbtiles_dir.glob("*.mbtiles"))
    
    if not mbtiles_files:
        print("Error: No .mbtiles files found in mbtiles/ directory")
        sys.exit(1)
    
    mbtiles_path = mbtiles_files[0]
    print(f"Using MBTiles: {mbtiles_path}")
    
    app = QApplication(sys.argv)
    
    # Enable touch support
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    
    window = MapViewerWindow(str(mbtiles_path))
    
    # Enable touch events on window and canvas
    window.setAttribute(Qt.WA_AcceptTouchEvents)
    window.canvas.setAttribute(Qt.WA_AcceptTouchEvents)
    
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
