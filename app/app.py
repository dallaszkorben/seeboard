#!/usr/bin/env python3
"""
seeBoard Web Application - Flask backend

Replaces tkinter desktop app with web-based UI.
All views run in the browser, all logic exposed via REST API.
"""

import sys
import os
import configparser
import atexit
import json
from datetime import datetime
from flask import Flask, render_template, jsonify, request

# Add app/ directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import core modules (unchanged from tkinter version)
from gps_core import open_serial, close, get_latest, _dd_to_dms
import gps_core
from route_database import RouteDatabase
from route_recorder import RouteRecorder
from map_generator import generate_map_html
import cam_discovery

# Configuration
CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "..", 
    "see_board.cfg"
)

# Ensure serial port is restored on exit
atexit.register(close)
atexit.register(cam_discovery.stop)

# Start GPS reading in background
open_serial()
gps_core.start_background_reader()

# Start camera discovery in background
cam_discovery.start()

# Initialize Flask app
app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), '..', 'static')
)

# ─── Helper Functions ───

def get_gps_position():
    """Get current GPS position with DMS formatting"""
    pos_dict = get_latest()
    print(f"[GPS] get_latest() = {pos_dict}")
    
    if pos_dict is None:
        print(f"[GPS] pos_dict is None")
        return None
    
    if pos_dict.get('status') not in ('fix', 'no_fix'):
        print(f"[GPS] status not fix/no_fix: {pos_dict.get('status')}")
        return None
    
    # Extract lat/lon from the GPS data dictionary
    lat = pos_dict.get('lat')
    lon = pos_dict.get('lon')
    print(f"[GPS] lat={lat}, lon={lon}")
    
    result = {
        'lat': lat,
        'lon': lon,
        'lat_dms': _dd_to_dms(lat) if lat else '--°--\'--"',
        'lon_dms': _dd_to_dms(lon) if lon else '--°--\'--"',
        'timestamp': None,
        'satellites': int(pos_dict.get('sats_used', 0)) if pos_dict.get('sats_used') else 0,
        'hdop': float(pos_dict.get('hdop', 0)) if pos_dict.get('hdop') else None,
        'speed': None,
        'fix_quality': 1 if pos_dict.get('status') == 'fix' else 0,
    }
    print(f"[GPS] returning: {result}")
    return result

# Initialize route recording
route_db = RouteDatabase()
route_recorder = RouteRecorder(route_db)

# Global state
recording_state = {
    'active': False,
    'route_id': None,
    'start_time': None
}

# ─── Configuration Management ───

def load_config():
    """Load configuration from file"""
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    if not cfg.has_section("gps"):
        cfg.add_section("gps")
    return cfg


def save_config(cfg):
    """Save configuration with comments"""
    if not cfg.has_section("gps"):
        cfg.add_section("gps")
    if not cfg.has_option("gps", "show_dms_decimals"):
        cfg.set("gps", "show_dms_decimals", "False")

    if not cfg.has_section("cam"):
        cfg.add_section("cam")
    if not cfg.has_option("cam", "rotation"):
        cfg.set("cam", "rotation", "0")

    if not cfg.has_section("coords"):
        cfg.add_section("coords")
    if not cfg.has_option("coords", "fix_color"):
        cfg.set("coords", "fix_color", "lime")
    if not cfg.has_option("coords", "nofix_color"):
        cfg.set("coords", "nofix_color", "red")
    if not cfg.has_option("coords", "error_color"):
        cfg.set("coords", "error_color", "red")

    if not cfg.has_section("route_recording"):
        cfg.add_section("route_recording")
    if not cfg.has_option("route_recording", "sampling_mode"):
        cfg.set("route_recording", "sampling_mode", "distance")
    if not cfg.has_option("route_recording", "line_color"):
        cfg.set("route_recording", "line_color", "RED")
    if not cfg.has_option("route_recording", "point_color"):
        cfg.set("route_recording", "point_color", "red")
    if not cfg.has_option("route_recording", "point_diameter"):
        cfg.set("route_recording", "point_diameter", "8")

    with open(CONFIG_FILE, "w") as f:
        f.write("# seeBoard configuration\n")
        cfg.write(f)


# Load config at startup
config = load_config()
save_config(config)
gps_core.SHOW_DMS_DECIMALS = config.getboolean("gps", "show_dms_decimals", fallback=False)

# ─── Page Routes ───

@app.route('/')
def index():
    """Main page with navigation"""
    return render_template('index.html')


@app.route('/coords')
def coords_page():
    """COORDS view"""
    return render_template('coords.html')


@app.route('/map')
def map_page():
    """MAP view"""
    return render_template('map.html')


@app.route('/cam')
def cam_page():
    """CAM view"""
    return render_template('cam.html')


@app.route('/conf')
def conf_page():
    """CONF view"""
    return render_template('conf.html')


# ─── API Routes: GPS ───

@app.route('/api/gps', methods=['GET'])
def api_gps():
    """Current GPS position and status"""
    pos_dict = get_gps_position()
    
    # Debug
    print(f"[GPS DEBUG] get_gps_position() returned: {pos_dict}")
    
    if pos_dict is None or pos_dict['lat'] is None:
        return jsonify({
            'status': 'no_fix',
            'lat': None,
            'lon': None,
            'lat_dms': '--°--\'--"',
            'lon_dms': '--°--\'--"',
            'timestamp': None,
            'satellites': 0,
            'hdop': None,
            'speed': None,
        })
    
    return jsonify({
        'status': 'fix' if pos_dict['fix_quality'] >= 1 else 'no_fix',
        'lat': pos_dict['lat'],
        'lon': pos_dict['lon'],
        'lat_dms': pos_dict['lat_dms'],
        'lon_dms': pos_dict['lon_dms'],
        'timestamp': pos_dict['timestamp'].isoformat() if pos_dict['timestamp'] else None,
        'satellites': pos_dict['satellites'],
        'hdop': pos_dict['hdop'],
        'speed': pos_dict['speed'],
        'fix_quality': pos_dict['fix_quality'],
    })


@app.route('/api/gps/history', methods=['GET'])
def api_gps_history():
    """Route history (recorded GPS points)"""
    if recording_state['active'] and recording_state['route_id']:
        # Get points from current recording
        points = route_recorder.get_route_points(recording_state['route_id'])
        return jsonify([
            {
                'lat': p[0],
                'lon': p[1],
                'timestamp': p[2] if len(p) > 2 else None
            }
            for p in points
        ])
    
    return jsonify([])


# ─── API Routes: Recording ───

@app.route('/api/recording/start', methods=['POST'])
def api_recording_start():
    """Start recording route"""
    global recording_state
    
    if recording_state['active']:
        return jsonify({'error': 'Already recording'}), 400
    
    # Start new route recording
    route_id = route_recorder.start_recording()
    recording_state['active'] = True
    recording_state['route_id'] = route_id
    recording_state['start_time'] = datetime.now().isoformat()
    
    return jsonify({
        'status': 'recording',
        'route_id': route_id,
        'start_time': recording_state['start_time']
    })


@app.route('/api/recording/stop', methods=['POST'])
def api_recording_stop():
    """Stop recording route"""
    global recording_state
    
    if not recording_state['active']:
        return jsonify({'error': 'Not recording'}), 400
    
    route_id = recording_state['route_id']
    route_recorder.stop_recording()
    
    recording_state['active'] = False
    recording_state['route_id'] = None
    recording_state['start_time'] = None
    
    # Get final route info
    route = route_db.get_route(route_id)
    
    return jsonify({
        'status': 'stopped',
        'route_id': route_id,
        'point_count': len(route['points']) if route else 0,
        'distance_m': route['distance'] if route else 0
    })


@app.route('/api/recording/status', methods=['GET'])
def api_recording_status():
    """Get current recording status"""
    return jsonify({
        'active': recording_state['active'],
        'route_id': recording_state['route_id'],
        'start_time': recording_state['start_time']
    })


# ─── API Routes: Map ───

@app.route('/api/map', methods=['GET'])
def api_map():
    """Generate and return SVG map"""
    # Get route points
    if recording_state['active'] and recording_state['route_id']:
        route = route_db.get_route(recording_state['route_id'])
        if route:
            coordinates = [(p[0], p[1]) for p in route['points']]
        else:
            coordinates = []
    else:
        coordinates = []
    
    # Generate SVG HTML
    html = generate_map_html(coordinates, config=config)
    
    # Return as response with content-type text/html
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


# ─── API Routes: Configuration ───

@app.route('/api/config', methods=['GET'])
def api_config_get():
    """Get current configuration"""
    cfg = load_config()
    
    # Load camera rotations from config file
    camera_rotations = {}
    if cfg.has_section('camera_rotations'):
        camera_rotations = dict(cfg.items('camera_rotations'))
    
    return jsonify({
        'gps': {
            'show_dms_decimals': cfg.getboolean('gps', 'show_dms_decimals', fallback=False)
        },
        'coords': {
            'fix_color': cfg.get('coords', 'fix_color', fallback='lime'),
            'nofix_color': cfg.get('coords', 'nofix_color', fallback='red'),
            'error_color': cfg.get('coords', 'error_color', fallback='red')
        },
        'route_recording': {
            'sampling_mode': cfg.get('route_recording', 'sampling_mode', fallback='distance'),
            'line_color': cfg.get('route_recording', 'line_color', fallback='RED'),
            'point_color': cfg.get('route_recording', 'point_color', fallback='red'),
            'point_diameter': cfg.getint('route_recording', 'point_diameter', fallback=8)
        },
        'camera_rotations': camera_rotations
    })


@app.route('/api/config', methods=['POST'])
def api_config_set():
    """Update configuration"""
    data = request.json
    print(f"[CONFIG] Received POST data: {data}")
    cfg = load_config()
    
    # Update GPS settings
    if 'gps' in data:
        if 'show_dms_decimals' in data['gps']:
            cfg.set('gps', 'show_dms_decimals', 
                   str(data['gps']['show_dms_decimals']))
            gps_core.SHOW_DMS_DECIMALS = data['gps']['show_dms_decimals']
    
    # Update camera settings
    if 'cam' in data:
        if 'rotation' in data['cam']:
            cfg.set('cam', 'rotation', str(data['cam']['rotation']))
    
    # Update coordinates display colors
    if 'coords' in data:
        for key in ['fix_color', 'nofix_color', 'error_color']:
            if key in data['coords']:
                cfg.set('coords', key, data['coords'][key])
    
    # Update route recording settings
    if 'route_recording' in data:
        for key in ['sampling_mode', 'line_color', 'point_color', 'point_diameter']:
            if key in data['route_recording']:
                cfg.set('route_recording', key, str(data['route_recording'][key]))
    
    # Update camera rotations (per-camera)
    if 'camera_rotations' in data:
        print(f"[CONFIG] Updating camera rotations: {data['camera_rotations']}")
        if not cfg.has_section('camera_rotations'):
            cfg.add_section('camera_rotations')
        for camera_name, rotation in data['camera_rotations'].items():
            print(f"[CONFIG]   {camera_name} = {rotation}")
            cfg.set('camera_rotations', camera_name, str(rotation))
    
    save_config(cfg)
    print(f"[CONFIG] Config saved")
    
    return jsonify({'status': 'updated'})


# ─── API Routes: Cameras ───

@app.route('/api/cameras', methods=['GET'])
def api_cameras():
    """Get list of discovered cameras"""
    cameras = cam_discovery.get_cameras()
    
    # cameras is a dict: {name: url}
    # Convert to list format for API
    camera_list = []
    for name, url in cameras.items():
        camera_list.append({
            'name': name,
            'url': url,
            'available': True
        })
    
    return jsonify(camera_list)


# ─── Error Handlers ───

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ─── Main ───

if __name__ == '__main__':
    # Run Flask development server
    # In production, use gunicorn or similar
    print("Starting seeBoard web server...")
    print("Open http://localhost:5000 in your browser")
    
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=5000,
        debug=False,  # Disable debug mode in production
        threaded=True  # Allow concurrent requests
    )
