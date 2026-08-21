"""
Pure SVG-based map generation (no external dependencies)
Generates OpenStreetMap-compatible SVG map with circles, line, and numbers
"""

import json
import math

# Default map center
DEFAULT_LAT = 56.1612
DEFAULT_LON = 15.5869
DEFAULT_ZOOM = 17

# Mercator projection
EARTH_RADIUS = 6378137  # meters


def lat_lon_to_mercator(lat, lon, zoom):
    """Convert lat/lon to pixel coordinates in Mercator projection"""
    # Standard Web Mercator projection
    lat_rad = math.radians(lat)
    mercator_lat = math.log(math.tan(math.pi / 4 + lat_rad / 2))
    
    # Pixel coordinates
    # At zoom 0, 1 tile (256 pixels) covers the whole world
    # At zoom z, we have 2^z tiles
    tiles_at_zoom = 2 ** zoom
    pixels_per_tile = 256
    world_width_pixels = tiles_at_zoom * pixels_per_tile
    
    x = ((lon + 180) / 360) * world_width_pixels
    y = ((math.pi - mercator_lat) / (2 * math.pi)) * world_width_pixels
    
    return x, y


def mercator_to_lat_lon(x, y, zoom):
    """Convert pixel coordinates back to lat/lon"""
    tiles_at_zoom = 2 ** zoom
    pixels_per_tile = 256
    world_width_pixels = tiles_at_zoom * pixels_per_tile
    
    lon = (x / world_width_pixels) * 360 - 180
    mercator_lat = (y / world_width_pixels) * (2 * math.pi) - math.pi
    mercator_lat = math.pi - mercator_lat
    lat = math.degrees(2 * math.atan(math.exp(mercator_lat)) - math.pi / 2)
    
    return lat, lon


def generate_map_html(coordinates, route_info=None, config=None):
    """
    Generate pure SVG map HTML (no external dependencies)
    
    Args:
        coordinates: list of (lat, lon) tuples
        route_info: dict with route metadata (color, line_width, etc.)
        config: configparser Config object for styling
    
    Returns:
        HTML string of the map
    """
    
    zoom = DEFAULT_ZOOM
    map_width = 800
    map_height = 600
    
    # Determine map center
    if coordinates and len(coordinates) > 0:
        center_lat, center_lon = coordinates[-1]  # Center on latest
    else:
        center_lat, center_lon = DEFAULT_LAT, DEFAULT_LON
    
    # Parse styling from config
    point_color = 'red'
    point_diameter = 8
    line_color = '#FF0000'
    line_width = 2
    
    if config:
        try:
            # Try route_recording section first, then fall back to general settings
            try:
                point_color = config.get('route_recording', 'point_color', fallback='red').lower()
                point_diameter = config.getint('route_recording', 'point_diameter', fallback=8)
            except:
                # Fall back to checking other sections if available
                pass
        except:
            pass
    
    if route_info:
        color_name = route_info.get('color', 'RED')
        if color_name == 'RED':
            line_color = '#FF0000'
        elif color_name == 'BLUE':
            line_color = '#0000FF'
        elif color_name == 'GREEN':
            line_color = '#00FF00'
        elif color_name == 'YELLOW':
            line_color = '#FFFF00'
        line_width = route_info.get('line_width', 3)
    
    # Convert point color name to hex
    color_map = {
        'red': '#FF0000',
        'blue': '#0000FF',
        'green': '#00FF00',
        'yellow': '#FFFF00',
        'cyan': '#00FFFF',
        'orange': '#FFA500',
    }
    point_color_hex = color_map.get(point_color, '#FF0000')
    
    # Get center pixel coordinates
    center_x, center_y = lat_lon_to_mercator(center_lat, center_lon, zoom)
    
    # Calculate SVG viewport (center of map = center_x, center_y)
    svg_min_x = center_x - map_width / 2
    svg_min_y = center_y - map_height / 2
    
    # Start building SVG
    svg_lines = []
    svg_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg_lines.append(f'<svg viewBox="0 0 {map_width} {map_height}" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" style="background-color: #e0e0e0;">')
    
    # Add OSM tile background (simplified - just a grid pattern)
    svg_lines.append(f'  <rect width="{map_width}" height="{map_height}" fill="#d0d0d0"/>')
    svg_lines.append(f'  <g stroke="#999" stroke-width="0.5" opacity="0.3">')
    for i in range(-5, 6):
        svg_lines.append(f'    <line x1="0" y1="{map_height/2 + i*50}" x2="{map_width}" y2="{map_height/2 + i*50}"/>')
        svg_lines.append(f'    <line x1="{map_width/2 + i*50}" y1="0" x2="{map_width/2 + i*50}" y2="{map_height}"/>')
    svg_lines.append('  </g>')
    
    # Draw polyline if we have coordinates
    if len(coordinates) >= 2:
        path_points = []
        for lat, lon in coordinates:
            px, py = lat_lon_to_mercator(lat, lon, zoom)
            svg_x = px - svg_min_x
            svg_y = py - svg_min_y
            path_points.append(f"{svg_x},{svg_y}")
        
        path_data = " ".join(path_points)
        svg_lines.append(f'  <polyline points="{path_data}" stroke="{line_color}" stroke-width="{line_width}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    
    # Draw circles and numbers at each point
    # point_diameter is in pixels, convert to radius
    radius_px = max(2, point_diameter / 2.0)  # Minimum 2px radius for visibility
    
    for idx, (lat, lon) in enumerate(coordinates, 1):
        px, py = lat_lon_to_mercator(lat, lon, zoom)
        svg_x = px - svg_min_x
        svg_y = py - svg_min_y
        
        # Draw solid filled circle
        svg_lines.append(f'  <circle cx="{svg_x}" cy="{svg_y}" r="{radius_px}" fill="{point_color_hex}" stroke="{point_color_hex}" stroke-width="1"/>')
        
        # Draw number text
        svg_lines.append(f'  <text x="{svg_x}" y="{svg_y + 3}" text-anchor="middle" font-size="10" font-weight="bold" fill="white" pointer-events="none">{idx}</text>')
    
    svg_lines.append('</svg>')
    
    # Wrap in HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>SeeBOARD Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background: #000;
        }}
        
        #map {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 100%;
            height: 100%;
        }}
        
        #status {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.7);
            color: #FFF;
            padding: 10px 15px;
            border-radius: 5px;
            font-size: 14px;
            z-index: 1000;
        }}
        
        .point-count {{
            font-weight: bold;
            color: #FF0000;
        }}
    </style>
</head>
<body>
    <div id="map">
        {''.join(svg_lines)}
    </div>
    <div id="status">
        <div>SeeBOARD Map</div>
        <div>Points: <span class="point-count">{len(coordinates)}</span></div>
    </div>
</body>
</html>"""
    
    return html


def generate_map_file(coordinates, route_info=None, config=None, output_file='/tmp/seeboard_map.html'):
    """
    Generate and save map to HTML file
    
    Args:
        coordinates: list of (lat, lon) tuples
        route_info: dict with route metadata
        config: configparser Config object
        output_file: where to save the HTML
    
    Returns:
        path to saved file
    """
    html = generate_map_html(coordinates, route_info, config)
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    return output_file
