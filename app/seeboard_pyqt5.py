#!/usr/bin/env python3
"""
seeBoard PyQt5 Application
GPS + Multi-camera maritime dashboard for Raspberry Pi with touchscreen
"""

import sys
import os
import threading
import time
from datetime import datetime
from configparser import ConfigParser

# PyQt5 imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QGridLayout, QComboBox, QCheckBox,
    QSpinBox, QSlider, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont, QColor, QPixmap

# Add app directory to path
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

import gps_core
import cam_discovery

# ─── GLOBAL SLIDER STYLESHEET ───
SLIDER_STYLESHEET = """
    QSlider {
        border: none;
        outline: none;
    }
    QSlider::groove:horizontal {
        border: none;
        outline: none;
        background: #e0e0e0;
        height: 5px;
        margin: 5px 0;
    }
    QSlider::sub-page:horizontal {
        background: #007AFF;
    }
    QSlider::handle:horizontal {
        background: #007AFF;
        border: none;
        outline: none;
        width: 18px;
        margin: -7px 0;
        border-radius: 9px;
    }
"""
import map_generator
import route_recorder
from route_database import RouteDatabase


class GPSWorker(QObject):
    """Worker thread for GPS updates"""
    gps_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.running = True
        
    def run(self):
        while self.running:
            try:
                data = gps_core.get_latest()
                if data:
                    self.gps_updated.emit(data)
            except Exception as e:
                print(f"[GPS] Error: {e}")
            time.sleep(0.5)
    
    def stop(self):
        self.running = False


class CameraWorker(QObject):
    """Worker thread for camera discovery"""
    cameras_updated = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.running = True
    
    def run(self):
        while self.running:
            try:
                cameras = cam_discovery.get_cameras()
                camera_list = [{'name': name, 'url': url} for name, url in cameras.items()]
                self.cameras_updated.emit(camera_list)
            except Exception as e:
                print(f"[CAM] Error: {e}")
            time.sleep(2)
    
    def stop(self):
        self.running = False


class CoordsTab(QWidget):
    """GPS Coordinates Display Tab"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.recording = False
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # Status indicator
        self.status_light = QLabel("●")
        self.status_light.setFont(QFont("Arial", 48))
        self.status_light.setStyleSheet("color: red;")
        layout.addWidget(self.status_light)
        
        # Coordinates display
        self.coords_label = QLabel("No GPS Fix")
        self.coords_label.setFont(QFont("Courier", 14))
        layout.addWidget(self.coords_label)
        
        # Status info
        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Courier", 10))
        layout.addWidget(self.info_label)
        
        # Recording buttons
        button_layout = QHBoxLayout()
        self.rec_button = QPushButton("REC")
        self.rec_button.setStyleSheet("background-color: red; color: white; font-weight: bold; font-size: 16px; padding: 10px;")
        self.rec_button.clicked.connect(self.start_recording)
        button_layout.addWidget(self.rec_button)
        
        self.stop_button = QPushButton("STOP")
        self.stop_button.setStyleSheet("background-color: green; color: white; font-weight: bold; font-size: 16px; padding: 10px;")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_recording)
        button_layout.addWidget(self.stop_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        self.setLayout(layout)
    
    def update_gps(self, data):
        """Update GPS display"""
        if data['status'] == 'fix':
            self.status_light.setStyleSheet("color: lime;")
            lat = data.get('lat_dms', data.get('lat', ''))
            lon = data.get('lon_dms', data.get('lon', ''))
            self.coords_label.setText(f"LAT: {lat}\nLON: {lon}")
            
            info = f"Satellites: {data.get('sats_used', 0)} | HDOP: {data.get('hdop', 'N/A')}"
            self.info_label.setText(info)
        else:
            self.status_light.setStyleSheet("color: red;")
            self.coords_label.setText("No GPS Fix")
            self.info_label.setText("")
    
    def start_recording(self):
        self.recording = True
        self.rec_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        print("[REC] Recording started")
    
    def stop_recording(self):
        self.recording = False
        self.rec_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        print("[REC] Recording stopped")


class MapTab(QWidget):
    """Map Display Tab with SVG"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        self.map_label = QLabel("Map - Route Visualization")
        self.map_label.setFont(QFont("Arial", 12))
        self.map_label.setMinimumHeight(400)
        self.map_label.setStyleSheet("border: 1px solid black; background: white;")
        layout.addWidget(self.map_label)
        
        self.setLayout(layout)
    
    def update_map(self, points):
        """Update map with route points"""
        if not points:
            self.map_label.setText("Map - No route recorded yet")
            return
        
        html = map_generator.generate_map_html(points)
        # For now, just show a placeholder
        self.map_label.setText(f"Map - {len(points)} points recorded")


class CamTab(QWidget):
    """Camera Grid Display Tab"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.camera_labels = {}
        self.initUI()
    
    def initUI(self):
        self.grid_layout = QGridLayout()
        scroll_widget = QScrollArea()
        scroll_widget.setWidget(QWidget())
        scroll_widget.widget().setLayout(self.grid_layout)
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll_widget)
        self.setLayout(main_layout)
    
    def update_cameras(self, cameras):
        """Update camera grid"""
        # Clear old labels
        for label in self.camera_labels.values():
            label.deleteLater()
        self.camera_labels.clear()
        
        # Add cameras
        row = 0
        col = 0
        for cam in cameras:
            label = QLabel()
            label.setMinimumSize(400, 300)
            
            # Load MJPEG stream
            pixmap = QPixmap()
            try:
                # This is simplified - real implementation would need streaming
                label.setText(cam['name'])
            except:
                label.setText(f"Loading: {cam['name']}")
            
            self.grid_layout.addWidget(label, row, col)
            self.camera_labels[cam['name']] = label
            
            col += 1
            if col >= 2:
                col = 0
                row += 1


class ConfTab(QWidget):
    """Configuration Tab"""
    
    def __init__(self, config, save_callback):
        super().__init__()
        self.config = config
        self.save_callback = save_callback
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # GPS settings
        gps_frame = QFrame()
        gps_layout = QVBoxLayout()
        
        self.dms_checkbox = QCheckBox("Show DMS Decimals")
        self.dms_checkbox.setChecked(self.config.getboolean('gps', 'show_dms_decimals', fallback=False))
        gps_layout.addWidget(self.dms_checkbox)
        
        gps_frame.setLayout(gps_layout)
        layout.addWidget(gps_frame)
        
        # Route recording settings
        route_frame = QFrame()
        route_layout = QVBoxLayout()
        
        route_layout.addWidget(QLabel("Point Diameter:"))
        self.diameter_slider = QSlider(Qt.Horizontal)
        self.diameter_slider.setMinimum(5)
        self.diameter_slider.setMaximum(20)
        self.diameter_slider.setStyleSheet(SLIDER_STYLESHEET)
        self.diameter_slider.setValue(self.config.getint('route_recording', 'point_diameter', fallback=8))
        route_layout.addWidget(self.diameter_slider)
        
        route_frame.setLayout(route_layout)
        layout.addWidget(route_frame)
        
        # Save button
        save_button = QPushButton("Save Configuration")
        save_button.clicked.connect(self.save_config)
        layout.addWidget(save_button)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def save_config(self):
        self.config.set('gps', 'show_dms_decimals', str(self.dms_checkbox.isChecked()))
        self.config.set('route_recording', 'point_diameter', str(self.diameter_slider.value()))
        self.save_callback()
        print("[CONF] Configuration saved")


class SeeBoardApp(QMainWindow):
    """Main Application Window"""
    
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.initUI()
        self.start_workers()
    
    def load_config(self):
        """Load configuration from file"""
        config = ConfigParser()
        config_path = os.path.expanduser('~/Projects/seeboard/see_board.cfg')
        if os.path.exists(config_path):
            config.read(config_path)
        return config
    
    def save_config(self):
        """Save configuration to file"""
        config_path = os.path.expanduser('~/Projects/seeboard/see_board.cfg')
        with open(config_path, 'w') as f:
            self.config.write(f)
    
    def initUI(self):
        """Initialize UI"""
        self.setWindowTitle("seeBoard - GPS & Camera Dashboard")
        self.setGeometry(0, 0, 800, 600)
        
        # Create tabs
        self.tabs = QTabWidget()
        
        self.coords_tab = CoordsTab(self.config)
        self.map_tab = MapTab(self.config)
        self.cam_tab = CamTab(self.config)
        self.conf_tab = ConfTab(self.config, self.save_config)
        
        self.tabs.addTab(self.coords_tab, "COORDS")
        self.tabs.addTab(self.map_tab, "MAP")
        self.tabs.addTab(self.cam_tab, "CAM")
        self.tabs.addTab(self.conf_tab, "CONF")
        
        self.setCentralWidget(self.tabs)
        
        # Start camera discovery
        cam_discovery.start()
    
    def start_workers(self):
        """Start background worker threads"""
        # GPS worker
        self.gps_thread = QThread()
        self.gps_worker = GPSWorker()
        self.gps_worker.moveToThread(self.gps_thread)
        self.gps_thread.started.connect(self.gps_worker.run)
        self.gps_worker.gps_updated.connect(self.coords_tab.update_gps)
        self.gps_thread.start()
        
        # Camera worker
        self.cam_thread = QThread()
        self.cam_worker = CameraWorker()
        self.cam_worker.moveToThread(self.cam_thread)
        self.cam_thread.started.connect(self.cam_worker.run)
        self.cam_worker.cameras_updated.connect(self.cam_tab.update_cameras)
        self.cam_thread.start()
    
    def closeEvent(self, event):
        """Clean up on close"""
        cam_discovery.stop()
        self.gps_worker.stop()
        self.cam_worker.stop()
        self.gps_thread.quit()
        self.cam_thread.quit()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = SeeBoardApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
