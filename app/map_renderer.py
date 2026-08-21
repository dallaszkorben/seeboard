"""Map rendering using py-staticmaps with Cairo for offline map display with route drawing"""

import os
import io
from PIL import Image
from staticmaps import Context, Marker, Line, Circle, ImageMarker, BLUE, RED, ORANGE
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QSize


class MapRenderer:
    """Render offline maps with routes and markers using py-staticmaps"""
    
    def __init__(self, tiles_db=None, width=800, height=600):
        """
        Initialize map renderer
        
        Args:
            tiles_db: Path to SQLite tiles database (optional, uses online tiles if not provided)
            width: Map width in pixels
            height: Map height in pixels
        """
        self.width = width
        self.height = height
        self.tiles_db = tiles_db
        
    def render_map(self, lat, lon, gps_lat=None, gps_lon=None, zoom=13, route_points=None, coverage_radius=None):
        """
        Render a map with GPS position marker
        
        Args:
            lat: Map center latitude
            lon: Map center longitude
            gps_lat: GPS marker latitude (if different from center)
            gps_lon: GPS marker longitude (if different from center)
            zoom: Zoom level (1-18)
            route_points: (unused for now)
            coverage_radius: (unused for now)
            
        Returns:
            QPixmap with rendered map
        """
        try:
            from staticmaps import create_latlng
            
            print(f"[MAP-RENDERER] Rendering {self.width}x{self.height} map at center {lat},{lon} zoom={zoom} with GPS marker at {gps_lat},{gps_lon}")
            
            # Create context (map object)
            ctx = Context()
            ctx.set_center(create_latlng(lat, lon))
            ctx.set_zoom(zoom)
            
            # Draw GPS position marker at the actual GPS position, not at center
            if gps_lat is not None and gps_lon is not None:
                self._add_position_marker(ctx, gps_lat, gps_lon)
            else:
                # Fallback: draw at center if GPS not provided
                self._add_position_marker(ctx, lat, lon)
            
            # Render using PillowRenderer
            image = ctx.render_pillow(self.width, self.height)
            
            print(f"[MAP-RENDERER] Rendered image size: {image.size}")
            
            # Convert PIL Image to QPixmap
            img_bytes = io.BytesIO()
            image.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes.read())
            
            print(f"[MAP-RENDERER] QPixmap size: {pixmap.width()}x{pixmap.height()}")
            
            return pixmap
            
        except Exception as e:
            print(f"Error rendering map: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    
    def _add_position_marker(self, ctx, lat, lon):
        """Add current GPS position marker"""
        try:
            from staticmaps import Marker, create_latlng
            
            # Create a marker at current position
            # Note: create_latlng expects (lat, lon)
            marker = Marker(create_latlng(lat, lon), color=RED)
            ctx.add_object(marker)
            print(f"[MAP] Added marker at lat={lat}, lon={lon}")
        except Exception as e:
            print(f"Error adding position marker: {e}")


class MapCache:
    """Cache rendered maps to reduce rendering load"""
    
    def __init__(self, max_cache_size=5):
        self.cache = {}
        self.max_size = max_cache_size
    
    def get_key(self, lat, lon, zoom, route_hash, coverage_radius):
        """Generate cache key from parameters"""
        return f"{lat:.4f}_{lon:.4f}_{zoom}_{route_hash}_{coverage_radius}"
    
    def get(self, key):
        """Get cached pixmap"""
        return self.cache.get(key)
    
    def set(self, key, pixmap):
        """Cache pixmap, evicting oldest if necessary"""
        if len(self.cache) >= self.max_size:
            # Remove oldest (first) entry
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        self.cache[key] = pixmap
    
    def clear(self):
        """Clear cache"""
        self.cache.clear()
