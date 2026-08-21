"""
Flask web application for SeeBOARD map visualization
Serves a Folium-based interactive map with route circles and line
"""

from flask import Flask, render_template, jsonify
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from route_database import RouteDatabase
from route_recorder import RouteRecorder
import gps_core

app = Flask(__name__, 
    template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'))

# Global instances (will be set by seeboard.py)
route_db = None
route_recorder = None
config = None


def set_context(db, recorder, cfg):
    """Set global context from seeboard.py"""
    global route_db, route_recorder, config
    route_db = db
    route_recorder = recorder
    config = cfg


@app.route('/')
def index():
    """Serve the map page"""
    return render_template('map.html', timestamp=datetime.now().timestamp())


@app.route('/api/map')
def get_map():
    """Generate and return map HTML"""
    from map_generator import generate_map_html
    
    if not route_recorder or not route_recorder.is_recording():
        # Return empty map centered on default position
        html = generate_map_html([], None)
    else:
        # Get current route points
        points = route_recorder.get_current_route_points()
        coordinates = [(p['latitude'], p['longitude']) for p in points]
        route_info = route_recorder.get_recording_info()
        
        html = generate_map_html(coordinates, route_info, config)
    
    return html


@app.route('/api/status')
def get_status():
    """Return route recording status"""
    if not route_recorder:
        return jsonify({'recording': False, 'points': 0})
    
    points = route_recorder.get_current_route_points()
    return jsonify({
        'recording': route_recorder.is_recording(),
        'points': len(points),
        'latest': points[-1] if points else None
    })


def run_server(port=5000, debug=False):
    """Start Flask development server"""
    app.run(host='127.0.0.1', port=port, debug=debug, use_reloader=False)


if __name__ == '__main__':
    # For testing/development
    run_server(debug=True)
