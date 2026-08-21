"""
Route Database Management

Handles all database operations for GPS route recording:
- Route CRUD operations
- GPS point insertion and retrieval
- Route metadata management
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict


class RouteDatabase:
    """SQLite database manager for GPS route recording"""

    def __init__(self):
        """Initialize database connection and create schema if needed"""
        # Database path: ~/.seeboard/routes.db
        self.db_path = Path.home() / ".seeboard" / "routes.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.connection = None
        self.connect()
        self.create_schema()

    def connect(self) -> None:
        """Establish database connection"""
        try:
            self.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=5.0
            )
            self.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self.connection.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            raise

    def create_schema(self) -> None:
        """Create database tables if they don't exist"""
        cursor = self.connection.cursor()
        
        # Routes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS routes (
                route_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name              TEXT NOT NULL UNIQUE,
                created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                stopped_at        DATETIME,
                is_recording      BOOLEAN NOT NULL DEFAULT 1,
                color             TEXT NOT NULL DEFAULT 'RED',
                line_width        INTEGER NOT NULL DEFAULT 3,
                line_style        TEXT NOT NULL DEFAULT 'continuous',
                sampling_mode     TEXT NOT NULL DEFAULT 'distance',
                sampling_value    REAL NOT NULL DEFAULT 15.0,
                total_distance    REAL,
                total_duration    REAL,
                point_count       INTEGER DEFAULT 0,
                created_date      DATE GENERATED ALWAYS AS (DATE(created_at)) STORED
            )
        """)
        
        # Route points table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS route_points (
                point_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                route_id          INTEGER NOT NULL,
                latitude          REAL NOT NULL,
                longitude         REAL NOT NULL,
                altitude          REAL,
                accuracy          REAL,
                timestamp         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                sequence          INTEGER NOT NULL,
                distance_from_prev REAL,
                time_from_prev    REAL,
                FOREIGN KEY (route_id) REFERENCES routes(route_id) ON DELETE CASCADE
            )
        """)
        
        # Route segments table (for future optimization)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS route_segments (
                segment_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                route_id          INTEGER NOT NULL,
                point_from_id     INTEGER NOT NULL,
                point_to_id       INTEGER NOT NULL,
                distance          REAL NOT NULL,
                bearing           REAL,
                FOREIGN KEY (route_id) REFERENCES routes(route_id),
                FOREIGN KEY (point_from_id) REFERENCES route_points(point_id),
                FOREIGN KEY (point_to_id) REFERENCES route_points(point_id)
            )
        """)
        
        self.connection.commit()

    def create_route(self, name: str, color: str, line_width: int, line_style: str,
                     sampling_mode: str, sampling_value: float) -> int:
        """
        Create a new route record
        
        Args:
            name: Route name (typically timestamp: yyyy-MM-dd'T'HH:mm:ss)
            color: Line color (e.g., 'RED', '#FF0000')
            line_width: Line width in pixels
            line_style: Line style (continuous, dotted, dashed, dashdot)
            sampling_mode: 'distance' or 'time'
            sampling_value: Distance in meters or time in seconds
            
        Returns:
            route_id of created route
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO routes 
                (name, color, line_width, line_style, sampling_mode, sampling_value)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, color, line_width, line_style, sampling_mode, sampling_value))
            self.connection.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            print(f"Error creating route: {e}")
            raise

    def stop_route(self, route_id: int) -> None:
        """
        Stop recording a route
        
        Args:
            route_id: ID of route to stop
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            UPDATE routes 
            SET is_recording = 0, stopped_at = CURRENT_TIMESTAMP
            WHERE route_id = ?
        """, (route_id,))
        self.connection.commit()

    def add_point(self, route_id: int, latitude: float, longitude: float,
                  altitude: Optional[float] = None, accuracy: Optional[float] = None) -> int:
        """
        Add a GPS point to a route
        
        Args:
            route_id: ID of the route
            latitude: GPS latitude
            longitude: GPS longitude
            altitude: Optional altitude
            accuracy: Optional GPS accuracy
            
        Returns:
            point_id of inserted point
        """
        cursor = self.connection.cursor()
        
        # Get the sequence number (next point number)
        cursor.execute("SELECT COUNT(*) FROM route_points WHERE route_id = ?", (route_id,))
        sequence = cursor.fetchone()[0] + 1
        
        # Get previous point for distance/time calculation
        prev_distance = None
        prev_time = None
        cursor.execute("""
            SELECT latitude, longitude, timestamp FROM route_points
            WHERE route_id = ? ORDER BY sequence DESC LIMIT 1
        """, (route_id,))
        prev_point = cursor.fetchone()
        
        if prev_point:
            prev_distance = self._calculate_distance(
                prev_point['latitude'], prev_point['longitude'],
                latitude, longitude
            )
            prev_timestamp = datetime.fromisoformat(prev_point['timestamp'])
            prev_time = (datetime.now() - prev_timestamp).total_seconds()
        
        # Insert new point
        cursor.execute("""
            INSERT INTO route_points
            (route_id, latitude, longitude, altitude, accuracy, sequence, 
             distance_from_prev, time_from_prev)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (route_id, latitude, longitude, altitude, accuracy, sequence, 
              prev_distance, prev_time))
        
        # Update route point count
        cursor.execute("""
            UPDATE routes SET point_count = point_count + 1 WHERE route_id = ?
        """, (route_id,))
        
        self.connection.commit()
        return cursor.lastrowid

    def get_active_route(self) -> Optional[Dict]:
        """
        Get the currently active (recording) route
        
        Returns:
            Dictionary with route data or None if no active route
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM routes WHERE is_recording = 1
            ORDER BY created_at DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_route_points(self, route_id: int) -> List[Dict]:
        """
        Get all points for a route in order
        
        Args:
            route_id: ID of the route
            
        Returns:
            List of point dictionaries
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM route_points 
            WHERE route_id = ?
            ORDER BY sequence ASC
        """, (route_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_route(self, route_id: int) -> Optional[Dict]:
        """
        Get route metadata
        
        Args:
            route_id: ID of the route
            
        Returns:
            Dictionary with route data or None
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM routes WHERE route_id = ?", (route_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_route_metadata(self, route_id: int, **kwargs) -> None:
        """
        Update route metadata (color, line_width, line_style, etc.)
        
        Args:
            route_id: ID of the route
            **kwargs: Fields to update (e.g., color='BLUE', line_width=2)
        """
        if not kwargs:
            return
        
        cursor = self.connection.cursor()
        fields = ", ".join(f"{key} = ?" for key in kwargs.keys())
        values = list(kwargs.values()) + [route_id]
        
        cursor.execute(f"UPDATE routes SET {fields} WHERE route_id = ?", values)
        self.connection.commit()

    def calculate_route_stats(self, route_id: int) -> Dict:
        """
        Calculate statistics for a route
        
        Args:
            route_id: ID of the route
            
        Returns:
            Dictionary with total_distance, total_duration, point_count
        """
        cursor = self.connection.cursor()
        
        # Total distance
        cursor.execute("""
            SELECT SUM(distance_from_prev) as total_distance
            FROM route_points
            WHERE route_id = ? AND distance_from_prev IS NOT NULL
        """, (route_id,))
        total_distance = cursor.fetchone()['total_distance'] or 0.0
        
        # Point count
        cursor.execute("SELECT COUNT(*) as point_count FROM route_points WHERE route_id = ?",
                      (route_id,))
        point_count = cursor.fetchone()['point_count']
        
        # Duration
        cursor.execute("""
            SELECT MIN(timestamp) as first, MAX(timestamp) as last
            FROM route_points WHERE route_id = ?
        """, (route_id,))
        result = cursor.fetchone()
        total_duration = 0
        if result['first'] and result['last']:
            first = datetime.fromisoformat(result['first'])
            last = datetime.fromisoformat(result['last'])
            total_duration = (last - first).total_seconds()
        
        return {
            'total_distance': total_distance,
            'total_duration': total_duration,
            'point_count': point_count
        }

    @staticmethod
    def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two GPS points using Haversine formula
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        from math import radians, cos, sin, asin, sqrt
        
        # Convert to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371000  # Earth radius in meters
        return c * r

    def get_routes_by_date(self, date_str: str) -> List[Dict]:
        """
        Get all routes created on a specific date
        
        Args:
            date_str: Date string (YYYY-MM-DD)
            
        Returns:
            List of route dictionaries
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM routes WHERE created_date = ?
            ORDER BY created_at DESC
        """, (date_str,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_route(self, route_id: int) -> None:
        """
        Delete a route and all its points
        
        Args:
            route_id: ID of the route to delete
        """
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM routes WHERE route_id = ?", (route_id,))
        self.connection.commit()

    def close(self) -> None:
        """Close database connection"""
        if self.connection:
            self.connection.close()

    def __del__(self):
        """Cleanup on deletion"""
        self.close()
