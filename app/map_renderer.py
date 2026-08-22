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
        
    def render_map(self, lat, lon, gps_lat=None, gps_lon=None, zoom=13, route_points=None, coverage_radius=None, path_color='RED', position_radius=2, position_font_size=8, path_width=1, visible_paths=None):
        """
        Render a map with GPS position marker, current recording route, and visible recorded paths
        
        Args:
            lat: Map center latitude
            lon: Map center longitude
            gps_lat: GPS marker latitude (if different from center)
            gps_lon: GPS marker longitude (if different from center)
            zoom: Zoom level (1-18)
            route_points: List of (lat, lon) tuples for current recording (if recording)
            coverage_radius: (unused for now)
            path_color: Color name for current recording path ('RED', 'BLUE', etc.)
            position_radius: Radius of position circles (1-5)
            position_font_size: Font size for position numbers (6-16)
            path_width: Width of the current recording path line (1-6)
            visible_paths: List of dicts with recorded path data:
                [{
                    'path_id': int,
                    'name': str,
                    'color': str,
                    'points': [(lat, lon), ...],
                    'width': int
                }, ...]
            
        Returns:
            QPixmap with rendered map
        """
        try:
            from staticmaps import create_latlng, Line
            
            # Map color names to RGB tuples
            color_map = {
                'RED': (255, 0, 0),
                'BLUE': (0, 0, 255),
                'GREEN': (0, 255, 0),
                'YELLOW': (255, 255, 0),
                'CYAN': (0, 255, 255),
                'MAGENTA': (255, 0, 255),
                'ORANGE': (255, 165, 0),
                'PURPLE': (128, 0, 128),
            }
            
            # Get RGB color for the path
            path_rgb = color_map.get(path_color, (255, 0, 0))  # Default to RED
            
            # Create context (map object)
            ctx = Context()
            ctx.set_center(create_latlng(lat, lon))
            ctx.set_zoom(zoom)
            
            # Draw visible recorded paths first (so they appear behind current recording)
            drawn_visible_paths = []  # Track which paths we drew, for markers
            if visible_paths:
                try:
                    from staticmaps import Color
                    for path_data in visible_paths:
                        path_points = path_data.get('points', [])
                        path_color_name = path_data.get('color', 'RED')
                        path_line_width = path_data.get('width', 1)
                        
                        if len(path_points) > 1:
                            line_coords = [create_latlng(pt[0], pt[1]) for pt in path_points]
                            path_rgb = color_map.get(path_color_name, (255, 0, 0))
                            line_color = Color(*path_rgb)
                            line = Line(line_coords, color=line_color, width=path_line_width)
                            ctx.add_object(line)
                            drawn_visible_paths.append({
                                'points': path_points,
                                'color_rgb': path_rgb,
                                'width': path_line_width
                            })
                except Exception as e:
                    print(f"[MAP] Error drawing visible paths: {e}")
            
            # Get RGB color for current recording path
            path_rgb = color_map.get(path_color, (255, 0, 0))  # Default to RED
            
            # Draw current recording route line if provided
            if route_points and len(route_points) > 1:
                try:
                    from staticmaps import Color
                    line_coords = [create_latlng(lat, lon) for lat, lon in route_points]
                    # Use Color object with RGB values
                    line_color = Color(*path_rgb)
                    line = Line(line_coords, color=line_color, width=path_width)
                    ctx.add_object(line)
                except Exception as e:
                    print(f"Error drawing route line: {e}")
            
            # Draw GPS position marker at the actual GPS position, not at center
            if gps_lat is not None and gps_lon is not None:
                self._add_position_marker(ctx, gps_lat, gps_lon)
            else:
                # Fallback: draw at center if GPS not provided
                self._add_position_marker(ctx, lat, lon)
            
            # Render using PillowRenderer
            image = ctx.render_pillow(self.width, self.height)
            
            # Draw position circles and numbers if we have route points
            if route_points and len(route_points) > 0:
                image = self._draw_position_markers(image, ctx, route_points, path_rgb, position_radius, position_font_size, lat, lon, zoom)
            
            # Convert PIL Image to QPixmap
            img_bytes = io.BytesIO()
            image.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes.read())
            
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
        except Exception as e:
            print(f"Error adding position marker: {e}")
    
    def _draw_position_markers(self, image, ctx, route_points, path_rgb, position_radius, position_font_size, center_lat, center_lon, zoom):
        """
        Draw circles and numbers at each position on the rendered map
        
        Args:
            image: PIL Image from ctx.render_pillow()
            ctx: staticmaps Context object (for coordinate conversion)
            route_points: List of (lat, lon) tuples
            path_rgb: RGB tuple for the color
            position_radius: Radius of circles (pixels)
            position_font_size: Font size for numbers
            center_lat, center_lon: Map center coordinates
            zoom: Zoom level
            
        Returns:
            PIL Image with markers drawn
        """
        try:
            from PIL import ImageDraw, ImageFont
            import math
            
            draw = ImageDraw.Draw(image)
            
            # For each position, calculate its pixel position and draw circle + number
            for idx, (pt_lat, pt_lon) in enumerate(route_points, 1):
                # Convert lat/lon to pixel coordinates
                # This is approximate - we need to calculate based on mercator projection
                
                # Get map bounds (approximate)
                # At zoom level z, the world is 256*2^z pixels wide
                pixels_per_degree_lon = (256 * (2 ** zoom)) / 360
                pixels_per_degree_lat = (256 * (2 ** zoom)) / 180
                
                # Calculate pixel offset from center
                delta_lon = pt_lon - center_lon
                delta_lat = pt_lat - center_lat
                
                px = self.width / 2 + (delta_lon * pixels_per_degree_lon)
                py = self.height / 2 - (delta_lat * pixels_per_degree_lat)
                
                # Only draw if within image bounds
                if 0 <= px < self.width and 0 <= py < self.height:
                    # Draw filled circle
                    circle_radius = position_radius
                    draw.ellipse(
                        [(px - circle_radius, py - circle_radius), 
                         (px + circle_radius, py + circle_radius)],
                        fill=path_rgb,
                        outline=path_rgb
                    )
                    
                    # Draw number text
                    try:
                        # Try to use a nice font, fall back to default
                        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", position_font_size)
                    except:
                        font = ImageFont.load_default()
                    
                    # Draw white text with the position number
                    text = str(idx)
                    # Get text bounding box to center it
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    text_x = px - text_width / 2
                    text_y = py - text_height / 2
                    
                    draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)
            
            return image
        except Exception as e:
            print(f"Error drawing position markers: {e}")
            import traceback
            traceback.print_exc()
            return image


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
