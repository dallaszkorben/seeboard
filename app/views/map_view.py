"""MAP view — displays GPS position on an OpenStreetMap.

Uses pre-downloaded offline tiles (SQLite database) so the map works
without internet connection. Tiles cover the Karlskrona area at zoom 8-17.
To download tiles for a different area, use tools/download_tiles.py.
"""

import tkinter as tk
import os
import tkintermapview


# Default map center (Karlskrona, Sweden) shown before GPS fix.
# This ensures the user sees a meaningful map immediately on startup,
# rather than a zoomed-out world view or empty area.
DEFAULT_LAT = 56.1612
DEFAULT_LON = 15.5869
DEFAULT_ZOOM = 13

# Pre-downloaded OSM tiles (148 MB, zoom 8-17, Karlskrona area).
# Stored as SQLite because tkintermapview's OfflineLoader uses this format.
# The database must be generated beforehand using tools/download_tiles.py.
# Derived from script location so it works regardless of install path.
TILES_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "maps", "tiles", "osm_tiles.db")


def create(parent):
    """Create the MAP view frame with an interactive map and GPS marker.

    The map uses offline tiles from a local SQLite database. If the database
    is missing, it falls back to fetching tiles from the internet.

    Args:
        parent: parent tkinter widget
    Returns:
        tuple: (frame, map_widget, marker, route_lines)
            - frame: the view's tk.Frame
            - map_widget: TkinterMapView instance (for position updates)
            - marker: map marker (for GPS position updates)
            - route_lines: list to hold polylines for recorded routes
    """
    frame = tk.Frame(parent, bg='black')

    # database_path and use_database_only are passed in the constructor
    # (not set afterwards) because set_tile_server() triggers immediate
    # tile fetching. If we set them after construction, the widget would
    # attempt internet requests before knowing it should use local tiles only.
    if os.path.exists(TILES_DB):
        map_widget = tkintermapview.TkinterMapView(
            frame, corner_radius=0,
            database_path=TILES_DB, use_database_only=True, max_zoom=17)
    else:
        # Fallback: fetch tiles from OpenStreetMap (requires internet).
        # This path only runs during development when tiles haven't been
        # downloaded yet — in production the Pi has no internet in AP mode.
        map_widget = tkintermapview.TkinterMapView(frame, corner_radius=0)
        map_widget.set_tile_server(
            "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=17)
    map_widget.pack(fill='both', expand=True)

    # Set initial view to default position until GPS provides a fix.
    # The coords_view update loop will call marker.set_position() and
    # map_widget.set_position() once a GPS fix is acquired.
    map_widget.set_position(DEFAULT_LAT, DEFAULT_LON)
    map_widget.set_zoom(DEFAULT_ZOOM)
    marker = map_widget.set_marker(DEFAULT_LAT, DEFAULT_LON, text="GPS")

    # Route lines storage for visualization
    # Store both the path and metadata for redrawing
    route_lines = []
    
    # Store redraw callback on map_widget so it can be called on view changes
    map_widget._route_lines = route_lines
    map_widget._route_redraw_callback = None

    return frame, map_widget, marker, route_lines


def draw_route(map_widget, route_lines, route_db, route_recorder, config=None):
    """
    Draw the currently recording route on the map with:
    - RED LINE path connecting all points
    - SOLID RED FILLED CIRCLES at each position (8px diameter)
    - WHITE NUMBERS showing sequence (1, 2, 3, etc.)
    
    Circles are drawn on the canvas and automatically repositioned when map view changes.
    
    Args:
        map_widget: TkinterMapView instance
        route_lines: list to store drawn objects (path line and circle data)
        route_db: RouteDatabase instance
        route_recorder: RouteRecorder instance
        config: configparser Config object for styling
    """
    # Get currently recording route
    if not route_recorder.is_recording():
        return
    
    route_info = route_recorder.get_recording_info()
    if not route_info:
        return
    
    # Get all points for this route
    points = route_recorder.get_current_route_points()
    if len(points) < 1:
        return
    
    # Extract coordinates
    coordinates = [(p['latitude'], p['longitude']) for p in points]
    
    # Parse route line color and circle color from config
    point_color = 'red'  # Default
    point_diameter = 8    # Default
    
    if config:
        try:
            point_color = config.get('route_recording', 'point_color', fallback='red').lower()
            point_diameter = config.getint('route_recording', 'point_diameter', fallback=8)
        except:
            pass
    
    # Convert color name to hex
    color_hex = _color_name_to_hex(point_color)
    
    # Parse route line color
    line_color = route_info.get('color', 'RED')
    if line_color == 'RED':
        line_color = '#FF0000'
    elif line_color == 'BLUE':
        line_color = '#0000FF'
    elif line_color == 'GREEN':
        line_color = '#00FF00'
    elif line_color == 'YELLOW':
        line_color = '#FFFF00'
    elif line_color == 'WHITE':
        line_color = '#FFFFFF'
    
    line_width = route_info.get('line_width', 3)
    
    # Check if point count changed - if not, skip redraw
    if len(route_lines) > 0 and hasattr(route_lines[0], '_point_count'):
        if route_lines[0]._point_count == len(coordinates):
            # Point count hasn't changed, but map might have panned/zoomed
            # Redraw circles in case they moved on canvas
            _redraw_route_circles(map_widget, route_lines, coordinates, point_color, point_diameter)
            return
    
    # Delete old path and circles
    if len(route_lines) > 0:
        try:
            if hasattr(route_lines[0], 'delete'):
                route_lines[0].delete()  # Delete path
        except:
            pass
        route_lines.clear()
    
    try:
        # Draw path connecting all points
        if len(coordinates) >= 2:
            path = map_widget.set_path(
                coordinates,
                color=line_color,
                width=line_width
            )
            path._point_count = len(coordinates)
            path._coordinates = coordinates  # Store for circle redraw
            path._color = point_color
            path._diameter = point_diameter
            path._line_color = line_color
            path._line_width = line_width
            route_lines.append(path)
        
        # Draw circles and numbers on canvas
        _draw_route_circles(map_widget, route_lines, coordinates, point_color, point_diameter)
        
        # Center map on latest position
        if len(coordinates) > 0:
            latest_lat, latest_lon = coordinates[-1]
            map_widget.set_position(latest_lat, latest_lon)
        
    except Exception as e:
        print(f"Route drawing error: {e}")


def _draw_route_circles(map_widget, route_lines, coordinates, point_color, point_diameter):
    """
    Draw solid filled circles at each route point on the canvas.
    Called when a new point is added to the route.
    
    Args:
        map_widget: TkinterMapView instance
        route_lines: list where path object is stored (used to access canvas)
        coordinates: list of (lat, lon) tuples
        point_color: color name (e.g., 'red', 'blue')
        point_diameter: circle diameter in pixels
    """
    try:
        canvas = map_widget.canvas
        color_hex = _color_name_to_hex(point_color)
        radius_px = point_diameter / 2.0
        
        # Store canvas items on the path object for later cleanup
        if len(route_lines) > 0 and hasattr(route_lines[0], '_canvas_items'):
            # Delete old canvas items
            for item_id in route_lines[0]._canvas_items:
                try:
                    canvas.delete(item_id)
                except:
                    pass
            route_lines[0]._canvas_items = []
        elif len(route_lines) > 0:
            route_lines[0]._canvas_items = []
        
        # Draw circle and number for each point
        for idx, (lat, lon) in enumerate(coordinates, 1):
            try:
                # Create temp marker to get canvas position
                temp_marker = map_widget.set_marker(lat, lon, text="")
                canvas_pos = temp_marker.get_canvas_pos((lat, lon))
                temp_marker.delete()
                
                if canvas_pos is None:
                    continue
                
                x, y = canvas_pos
                
                # Draw solid filled circle
                circle = canvas.create_oval(
                    x - radius_px, y - radius_px,
                    x + radius_px, y + radius_px,
                    fill=color_hex,
                    outline=color_hex,
                    width=0
                )
                route_lines[0]._canvas_items.append(circle)
                
                # Draw white number
                text = canvas.create_text(
                    x, y,
                    text=str(idx),
                    fill="white",
                    font=("Arial", 6, "bold"),
                    anchor="center"
                )
                canvas.tag_raise(text)
                route_lines[0]._canvas_items.append(text)
                
            except Exception as e:
                print(f"Error drawing circle at point {idx}: {e}")
    
    except Exception as e:
        print(f"Error in _draw_route_circles: {e}")


def _redraw_route_circles(map_widget, route_lines, coordinates, point_color, point_diameter):
    """
    Redraw circles when map view changes (pan, zoom, resize) without changing points.
    Used when canvas coordinates change but GPS coordinates stay the same.
    
    Args:
        map_widget: TkinterMapView instance
        route_lines: list where path object is stored
        coordinates: list of (lat, lon) tuples
        point_color: color name
        point_diameter: circle diameter in pixels
    """
    _draw_route_circles(map_widget, route_lines, coordinates, point_color, point_diameter)


def redraw_route_circles_on_view_change(map_widget):
    """
    Called whenever the map view changes (pan, zoom, resize).
    Redraws all route circles at their correct canvas positions.
    
    This keeps circles synchronized with the path when the user pans/zooms.
    
    Args:
        map_widget: TkinterMapView instance
    """
    if not hasattr(map_widget, '_route_lines') or len(map_widget._route_lines) == 0:
        return
    
    route_lines = map_widget._route_lines
    path = route_lines[0]
    
    # Check if path has stored metadata
    if not hasattr(path, '_coordinates'):
        return
    
    # Redraw circles at current canvas positions
    try:
        _draw_route_circles(
            map_widget,
            route_lines,
            path._coordinates,
            path._color,
            path._diameter
        )
    except Exception as e:
        print(f"Error redrawing circles on view change: {e}")


def _color_name_to_hex(color_name):
    """Convert color name to hex code
    
    Args:
        color_name: Color name (lowercase) or hex code
        
    Returns:
        Hex color code (e.g., #FF0000)
    """
    colors = {
        'red': '#FF0000',
        'blue': '#0000FF',
        'green': '#00FF00',
        'yellow': '#FFFF00',
        'white': '#FFFFFF',
        'black': '#000000',
        'cyan': '#00FFFF',
        'magenta': '#FF00FF',
        'gray': '#808080',
        'orange': '#FFA500',
        'purple': '#800080',
        'pink': '#FFC0CB',
        'lime': '#00FF00',
        'navy': '#000080',
        'teal': '#008080',
    }
    
    color_lower = color_name.lower() if isinstance(color_name, str) else str(color_name)
    return colors.get(color_lower, '#FF0000')  # Default to red
