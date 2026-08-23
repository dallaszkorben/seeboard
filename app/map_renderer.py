"""Map rendering using MBTiles for offline map display with route drawing"""

import os
import io
import sqlite3
import struct
import zlib
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QSize
import math


class MapCache:
    """Simple cache for rendered maps"""
    def __init__(self):
        self.cache = {}
    
    def get(self, key):
        return self.cache.get(key)
    
    def set(self, key, value):
        self.cache[key] = value
    
    def clear(self):
        self.cache.clear()


class MapRenderer:
    """Render offline maps using MBTiles with routes and markers"""
    
    TILE_SIZE = 256  # Standard tile size in pixels
    
    def __init__(self, charts_dir=None, mbtiles_file=None, width=800, height=600):
        """
        Initialize map renderer with MBTiles
        
        Args:
            charts_dir: Path to charts folder with offline map tiles (legacy)
            mbtiles_file: Path to MBTiles file. If None, searches in mbtiles folder
            width: Map width in pixels
            height: Map height in pixels
        """
        self.width = width
        self.height = height
        
        # Find MBTiles file
        if mbtiles_file is None:
            app_dir = os.path.dirname(os.path.abspath(__file__))
            mbtiles_dir = os.path.join(os.path.dirname(app_dir), "mbtiles")
            
            # Find first .mbtiles file in directory
            if os.path.exists(mbtiles_dir):
                for f in os.listdir(mbtiles_dir):
                    if f.endswith('.mbtiles'):
                        mbtiles_file = os.path.join(mbtiles_dir, f)
                        break
        
        self.mbtiles_path = mbtiles_file
        self.mbtiles_conn = None
        self.tile_cache = {}
        self.available_zooms = []
        self.last_rendered_zoom = 12  # Track the actual zoom level used in last render
        
        # Try to open MBTiles file
        if self.mbtiles_path and os.path.exists(self.mbtiles_path):
            try:
                self.mbtiles_conn = sqlite3.connect(self.mbtiles_path)
                print(f"Loaded MBTiles: {self.mbtiles_path}")
                
                # Get available zoom levels
                cursor = self.mbtiles_conn.cursor()
                cursor.execute("SELECT DISTINCT zoom_level FROM tiles ORDER BY zoom_level")
                self.available_zooms = [row[0] for row in cursor.fetchall()]
                print(f"[MAP] Available zoom levels: {self.available_zooms}")
            except Exception as e:
                print(f"Failed to open MBTiles: {e}")
                self.mbtiles_conn = None
        else:
            print(f"MBTiles file not found: {self.mbtiles_path}")
        
        # Default center (Karlskrona, Sweden)
        self.default_lat = 56.1612
        self.default_lon = 15.5869
    
    def get_tile(self, z, x, y):
        """
        Get a tile from MBTiles database
        
        Args:
            z: Zoom level (assumed to be available)
            x: Tile X coordinate
            y: Tile Y coordinate
        
        Returns:
            PIL Image or None if tile not found
        """
        if not self.mbtiles_conn:
            return None
        
        # Check cache first
        cache_key = (z, x, y)
        if cache_key in self.tile_cache:
            return self.tile_cache[cache_key]
        
        try:
            # MBTiles stores tiles inverted on Y axis
            y_inv = (2 ** z) - 1 - y
            
            cursor = self.mbtiles_conn.cursor()
            cursor.execute(
                "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                (z, x, y_inv)
            )
            row = cursor.fetchone()
            
            if row:
                tile_data = row[0]
                try:
                    tile_image = Image.open(io.BytesIO(tile_data))
                    self.tile_cache[cache_key] = tile_image
                    return tile_image
                except Exception as e:
                    print(f"Failed to decode tile {z}/{x}/{y}: {e}")
            
            return None
        except Exception as e:
            print(f"Error fetching tile {z}/{x}/{y}: {e}")
            return None
    
    def latlon_to_tile(self, lat, lon, zoom):
        """Convert lat/lon to tile coordinates"""
        n = 2.0 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n)
        return x, y
    
    def tile_to_latlon(self, x, y, zoom):
        """Convert tile coordinates to lat/lon (top-left corner)"""
        n = 2.0 ** zoom
        lon = x / n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        return lat, lon
        
    def render_map(self, lat, lon, gps_lat=None, gps_lon=None, zoom=13, route_points=None, 
                   path_color='RED', position_radius=2, position_font_size=8, path_width=1, visible_paths=None, coverage_radius=None):
        """
        Render a map with GPS position marker and routes
        
        Args:
            lat: Map center latitude
            lon: Map center longitude
            gps_lat: GPS marker latitude
            gps_lon: GPS marker longitude
            zoom: Zoom level (for tile selection)
            route_points: List of (lat, lon) tuples for current recording
            path_color: Color name for current recording path
            position_radius: Radius of position circles
            position_font_size: Font size for position numbers
            path_width: Width of the current recording path line
            visible_paths: List of dicts with recorded path data
            
        Returns:
            QPixmap with rendered map
        """
        try:
            # Create map from tiles or blank image
            # _render_from_tiles returns (image, actual_zoom_used)
            if self.mbtiles_conn:
                map_image, actual_zoom = self._render_from_tiles(lat, lon, zoom)
            else:
                # Fallback to blank map
                map_image = Image.new('RGB', (self.width, self.height), color='lightblue')
                draw = ImageDraw.Draw(map_image)
                self._draw_map_background(map_image, draw, lat, lon)
                actual_zoom = zoom
            
            draw = ImageDraw.Draw(map_image)
            
            # Draw visible recorded paths first
            if visible_paths:
                for path_info in visible_paths:
                    self._draw_path(map_image, draw, path_info['points'], 
                                   path_info.get('color', 'BLUE'),
                                   path_info.get('width', 1),
                                   lat, lon, actual_zoom)
            
            # Draw current recording route
            if route_points and len(route_points) > 1:
                self._draw_path(map_image, draw, route_points, path_color, path_width, lat, lon, actual_zoom)
            
            # Draw GPS position marker using ACTUAL zoom level used for tiles
            if gps_lat is not None and gps_lon is not None:
                self._draw_gps_marker(map_image, draw, gps_lat, gps_lon, lat, lon, actual_zoom)
            else:
                self._draw_gps_marker(map_image, draw, lat, lon, lat, lon, actual_zoom)
            
            # Draw title/info at top
            self._draw_map_title(map_image, draw, lat, lon, actual_zoom)
            
            # Convert PIL Image to QPixmap
            img_bytes = io.BytesIO()
            map_image.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes.read())
            
            return pixmap
            
        except Exception as e:
            print(f"Error rendering map: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _render_from_tiles(self, lat, lon, zoom):
        """Render map from MBTiles tiles, centered on (lat, lon)"""
        # Find closest available zoom level
        actual_zoom = zoom
        if zoom not in self.available_zooms:
            actual_zoom = min(self.available_zooms, key=lambda az: abs(az - zoom))
        
        # Calculate tile coordinates at the ACTUAL zoom level
        center_tile_x, center_tile_y = self.latlon_to_tile(lat, lon, actual_zoom)
        
        # How many tiles do we need in each direction?
        tiles_h = (self.width + self.TILE_SIZE - 1) // self.TILE_SIZE
        tiles_v = (self.height + self.TILE_SIZE - 1) // self.TILE_SIZE
        
        # Create output image
        map_image = Image.new('RGB', (self.width, self.height), color='#c8c8c8')
        
        # Draw tiles centered on (center_tile_x, center_tile_y)
        for ty in range(-tiles_v//2, tiles_v//2 + 1):
            for tx in range(-tiles_h//2, tiles_h//2 + 1):
                tile_x = center_tile_x + tx
                tile_y = center_tile_y + ty
                
                # Get tile
                tile = self.get_tile(actual_zoom, tile_x, tile_y)
                
                if tile:
                    # Convert palette mode to RGBA if needed
                    if tile.mode == 'P':
                        tile = tile.convert('RGBA')
                    
                    # Calculate position on output image
                    px = self.width // 2 + tx * self.TILE_SIZE
                    py = self.height // 2 + ty * self.TILE_SIZE
                    
                    # Paste tile
                    map_image.paste(tile, (px, py))
                else:
                    # Draw placeholder for missing tile
                    px = self.width // 2 + tx * self.TILE_SIZE
                    py = self.height // 2 + ty * self.TILE_SIZE
                    draw = ImageDraw.Draw(map_image)
                    draw.rectangle(
                        [(px, py), (px + self.TILE_SIZE - 1, py + self.TILE_SIZE - 1)],
                        outline='#999999'
                    )
        
        return map_image, actual_zoom
    
    def _draw_map_background(self, image, draw, center_lat, center_lon):
        """Draw map background with grid"""
        # Draw a simple grid
        grid_spacing = 50  # pixels
        for x in range(0, self.width, grid_spacing):
            draw.line([(x, 0), (x, self.height)], fill='#cccccc', width=1)
        for y in range(0, self.height, grid_spacing):
            draw.line([(0, y), (self.width, y)], fill='#cccccc', width=1)
        
        # Draw center crosshair
        cx, cy = self.width // 2, self.height // 2
        draw.line([(cx - 10, cy), (cx + 10, cy)], fill='green', width=2)
        draw.line([(cx, cy - 10), (cx, cy + 10)], fill='green', width=2)
    
    def _draw_path(self, image, draw, points, color, width, center_lat, center_lon, zoom=13):
        """Draw a path (route) on the map"""
        if len(points) < 2:
            return
        
        # Color map
        color_map = {
            'RED': (255, 0, 0),
            'BLUE': (0, 0, 255),
            'GREEN': (0, 255, 0),
            'YELLOW': (255, 255, 0),
            'CYAN': (0, 255, 255),
            'MAGENTA': (255, 0, 255),
            'ORANGE': (255, 165, 0),
            'PURPLE': (128, 0, 128),
            'WHITE': (255, 255, 255),
            'BLACK': (0, 0, 0),
        }
        
        rgb_color = color_map.get(color, (255, 0, 0))
        
        # Convert lat/lon to pixel coordinates
        pixel_points = []
        for lat, lon in points:
            px, py = self._latlon_to_pixel(lat, lon, center_lat, center_lon, zoom)
            pixel_points.append((px, py))
        
        # Draw path line
        if len(pixel_points) > 1:
            draw.line(pixel_points, fill=rgb_color, width=max(1, width))
        
        # Draw points as circles
        for i, (px, py) in enumerate(pixel_points):
            r = max(2, 3)  # radius
            draw.ellipse([(px - r, py - r), (px + r, py + r)], 
                        fill=rgb_color, outline='white', width=1)
            
            # Draw point number
            try:
                font = ImageFont.load_default()
                text = str(i + 1)
                draw.text((px + 5, py - 5), text, fill='white', font=font)
            except:
                pass
    
    def _draw_gps_marker(self, image, draw, marker_lat, marker_lon, center_lat, center_lon, zoom=13):
        """Draw GPS position marker as a water droplet"""
        # In FOLLOW mode, GPS position == map center, so marker is always at screen center
        # Only calculate offset if GPS is different from map center (manual pan)
        px = self.width // 2
        py = self.height // 2
        
        # If GPS is not at map center, calculate the offset
        if abs(marker_lat - center_lat) > 0.0001 or abs(marker_lon - center_lon) > 0.0001:
            # Only then do the complex calculation
            px, py = self._latlon_to_pixel(marker_lat, marker_lon, center_lat, center_lon, zoom)
        
        print(f"[MAP_MARKER] zoom={zoom}, center=({center_lat:.6f},{center_lon:.6f}), marker=({marker_lat:.6f},{marker_lon:.6f}), pixel=({px},{py})")
        
        # Draw water droplet shape
        r = 8  # radius of rounded top
        h = 12  # height of point
        
        # Draw rounded top (semicircle)
        draw.ellipse([(px - r, py - r), (px + r, py + r)], 
                    fill='red', outline='white', width=2)
        
        # Draw point (triangle bottom)
        point_coords = [
            (px - r, py),      # left side of circle
            (px + r, py),      # right side of circle
            (px, py + h)       # point at bottom
        ]
        draw.polygon(point_coords, fill='red', outline='white')
        
        # Draw "GPS" label
        try:
            font = ImageFont.load_default()
            draw.text((px + 12, py - 10), "GPS", fill='red', font=font)
        except:
            pass
    
    def _draw_map_title(self, image, draw, lat, lon, zoom=13):
        """Draw map title with coordinates"""
        try:
            font = ImageFont.load_default()
            title = f"Map: {lat:.4f}, {lon:.4f} Z{zoom} (OFFLINE)"
            draw.text((5, 5), title, fill='black', font=font)
        except:
            pass
    
    def _latlon_to_pixel(self, lat, lon, center_lat, center_lon, zoom=13):
        """
        Convert lat/lon to pixel position using standard Web Mercator
        Based on: https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
        """
        # Convert GPS coordinates to Web Mercator unit square (0-1 range)
        def lat_lon_to_unit(latitude, longitude):
            # Web Mercator projection
            x_unit = 0.5 + longitude / 360.0
            y_webm = math.asinh(math.tan(math.radians(latitude)))
            y_unit = 0.5 - y_webm / (2 * math.pi)
            return x_unit, y_unit
        
        # Get unit coordinates for both map center and GPS marker
        center_x, center_y = lat_lon_to_unit(center_lat, center_lon)
        point_x, point_y = lat_lon_to_unit(lat, lon)
        
        # Convert to tile space (multiply by 2^zoom)
        n = 2.0 ** zoom
        center_tile_x = center_x * n
        center_tile_y = center_y * n
        point_tile_x = point_x * n
        point_tile_y = point_y * n
        
        # Difference in tiles
        tile_diff_x = point_tile_x - center_tile_x
        tile_diff_y = point_tile_y - center_tile_y
        
        # Convert to pixels (256 pixels per tile)
        pixel_diff_x = tile_diff_x * self.TILE_SIZE
        pixel_diff_y = tile_diff_y * self.TILE_SIZE
        
        # Screen center
        cx = self.width // 2
        cy = self.height // 2
        
        # Final pixel position
        px = int(cx + pixel_diff_x)
        py = int(cy + pixel_diff_y)
        
        # Clamp to screen
        px = max(0, min(self.width - 1, px))
        py = max(0, min(self.height - 1, py))
        
        return px, py
