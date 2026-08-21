"""
Route Recorder

Manages GPS route recording:
- Start/stop recording sessions
- Handle sampling (distance or time based)
- Automatically add GPS points based on sampling criteria
"""

from datetime import datetime
from typing import Optional, Callable, Dict

try:
    from .route_database import RouteDatabase
except ImportError:
    from route_database import RouteDatabase


class RouteRecorder:
    """Manages GPS route recording with configurable sampling"""

    def __init__(self, db: RouteDatabase):
        """
        Initialize route recorder
        
        Args:
            db: RouteDatabase instance
        """
        self.db = db
        self.current_route_id: Optional[int] = None
        self.last_recorded_point: Optional[Dict] = None
        self.recording = False

    def start_recording(self, current_position: Dict, config: Dict) -> int:
        """
        Start a new recording session
        
        Args:
            current_position: Dict with GPS data
            config: Dict with 'line_color', 'line_width', 'line_style', 
                   'sampling_mode', 'sampling_value'
        
        Returns:
            route_id of new recording
        """
        # Stop previous recording if exists
        if self.current_route_id is not None:
            self.stop_recording()
        
        # Create route name from current timestamp (ISO 8601 format)
        route_name = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        
        # Create new route
        self.current_route_id = self.db.create_route(
            name=route_name,
            color=config.get('line_color', 'RED'),
            line_width=config.get('line_width', 3),
            line_style=config.get('line_style', 'continuous'),
            sampling_mode=config.get('sampling_mode', 'distance'),
            sampling_value=config.get('sampling_value', 15.0)
        )
        
        # Set recording BEFORE adding point
        self.recording = True
        
        # Add initial point
        self.add_point(current_position)
        
        return self.current_route_id

    def stop_recording(self) -> Optional[int]:
        """
        Stop the current recording session
        
        Returns:
            route_id that was stopped, or None if no recording active
        """
        if self.current_route_id is None:
            return None
        
        self.db.stop_route(self.current_route_id)
        stopped_id = self.current_route_id
        self.current_route_id = None
        self.last_recorded_point = None
        self.recording = False
        
        return stopped_id

    def should_record_point(self, current_position: Dict) -> bool:
        """
        Check if current position should be recorded based on sampling criteria
        
        Args:
            current_position: Dict with GPS data (can be 'lat'/'lon' or 'lat_raw'/'lon_raw')
        
        Returns:
            True if point should be recorded, False otherwise
        """
        if not self.recording or self.current_route_id is None:
            return False
        
        if self.last_recorded_point is None:
            return True  # Always record first point
        
        # Extract coordinates handling both formats
        current_lat = current_position.get('latitude') or current_position.get('lat_raw') or current_position.get('lat')
        current_lon = current_position.get('longitude') or current_position.get('lon_raw') or current_position.get('lon')
        
        if not current_lat or not current_lon:
            return False
        
        # Get route configuration
        route = self.db.get_route(self.current_route_id)
        if not route:
            return False
        
        sampling_mode = route['sampling_mode']
        sampling_value = route['sampling_value']
        
        if sampling_mode == 'distance':
            # Check if distance threshold met
            distance = self.db._calculate_distance(
                self.last_recorded_point['latitude'],
                self.last_recorded_point['longitude'],
                current_lat,
                current_lon
            )
            return distance >= sampling_value
        
        elif sampling_mode == 'time':
            # Check if time threshold met
            last_time = datetime.fromisoformat(self.last_recorded_point['timestamp'])
            current_time = datetime.now()
            elapsed = (current_time - last_time).total_seconds()
            return elapsed >= sampling_value
        
        return False

    def add_point(self, current_position: Dict) -> Optional[int]:
        """
        Add a GPS point to the current recording
        
        Args:
            current_position: Dict with GPS data
        
        Returns:
            point_id if added, None if not recording or invalid
        """
        if not self.recording or self.current_route_id is None:
            return None
        
        # Extract coordinates handling both GPS data formats
        lat = current_position.get('latitude') or current_position.get('lat_raw') or current_position.get('lat')
        lon = current_position.get('longitude') or current_position.get('lon_raw') or current_position.get('lon')
        alt = current_position.get('altitude') or current_position.get('alt')
        acc = current_position.get('accuracy')
        
        if not lat or not lon:
            return None
        
        point_id = self.db.add_point(
            route_id=self.current_route_id,
            latitude=lat,
            longitude=lon,
            altitude=alt,
            accuracy=acc
        )
        
        # Update last recorded point
        self.last_recorded_point = {
            'latitude': lat,
            'longitude': lon,
            'timestamp': datetime.now().isoformat(),
            'altitude': alt,
            'accuracy': acc
        }
        
        return point_id

    def get_recording_info(self) -> Optional[Dict]:
        """
        Get information about current recording
        
        Returns:
            Dict with route info or None if not recording
        """
        if self.current_route_id is None:
            return None
        
        return self.db.get_route(self.current_route_id)

    def is_recording(self) -> bool:
        """Check if currently recording"""
        return self.recording and self.current_route_id is not None

    def get_current_route_points(self) -> list:
        """
        Get all points for current recording
        
        Returns:
            List of point dictionaries
        """
        if self.current_route_id is None:
            return []
        
        return self.db.get_route_points(self.current_route_id)
