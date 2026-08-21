#!/usr/bin/env python3
"""
seeBoard PyQt5 Minimal Application
Uses only system-installed PyQt5, no external dependencies
"""

import sys
import os
import json
import urllib.request
import urllib.error
import threading
import time
from configparser import ConfigParser

# PyQt5 imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QGridLayout, QCheckBox,
    QSlider, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont, QColor

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

class GPSSignals(QObject):
    """Signal emitter for GPS updates"""
    updated = pyqtSignal(dict)


class CameraSignals(QObject):
    """Signal emitter for camera updates"""
    updated = pyqtSignal(list)


class GPSWorker(QThread):
    """Background thread for GPS updates"""
    signals = GPSSignals()
    
    def run(self):
        while True:
            try:
                response = urllib.request.urlopen('http://localhost:5000/api/gps', timeout=2)
                data = json.loads(response.read())
                self.signals.updated.emit(data)
            except:
                pass
            time.sleep(0.5)


class CameraWorker(QThread):
    """Background thread for camera discovery"""
    signals = CameraSignals()
    
    def run(self):
        while True:
            try:
                response = urllib.request.urlopen('http://localhost:5000/api/cameras', timeout=2)
                data = json.loads(response.read())
                self.signals.updated.emit(data)
            except:
                pass
            time.sleep(2)


class CoordsTab(QWidget):
    """GPS Coordinates Display"""
    
    def __init__(self):
        super().__init__()
        self.recording = False
        self.initUI()
        
        # Connect GPS updates
        self.gps_worker = GPSWorker()
        self.gps_worker.signals.updated.connect(self.update_gps)
        self.gps_worker.start()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Status light
        self.status_label = QLabel("●")
        self.status_label.setFont(QFont("Arial", 48))
        self.status_label.setStyleSheet("color: red;")
        layout.addWidget(self.status_label)
        
        # Coordinates
        self.coords_label = QLabel("No GPS Fix")
        self.coords_label.setFont(QFont("Courier", 14))
        layout.addWidget(self.coords_label)
        
        # Info
        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Courier", 10))
        layout.addWidget(self.info_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.rec_button = QPushButton("REC")
        self.rec_button.setStyleSheet("background-color: red; color: white; font-weight: bold; font-size: 16px; padding: 10px;")
        self.rec_button.clicked.connect(self.start_recording)
        btn_layout.addWidget(self.rec_button)
        
        self.stop_button = QPushButton("STOP")
        self.stop_button.setStyleSheet("background-color: green; color: white; font-weight: bold; font-size: 16px; padding: 10px;")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_recording)
        btn_layout.addWidget(self.stop_button)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        self.setLayout(layout)
    
    def update_gps(self, data):
        if data.get('status') == 'fix':
            self.status_label.setStyleSheet("color: lime;")
            lat = data.get('lat_dms', str(data.get('lat', '')))
            lon = data.get('lon_dms', str(data.get('lon', '')))
            self.coords_label.setText(f"LAT: {lat}\nLON: {lon}")
            self.info_label.setText(f"Sats: {data.get('sats_used', 0)}")
        else:
            self.status_label.setStyleSheet("color: red;")
            self.coords_label.setText("No GPS Fix")
    
    def start_recording(self):
        self.recording = True
        self.rec_button.setEnabled(False)
        self.stop_button.setEnabled(True)
    
    def stop_recording(self):
        self.recording = False
        self.rec_button.setEnabled(True)
        self.stop_button.setEnabled(False)


class MapTab(QWidget):
    """Map Display"""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        
        self.map_label = QLabel("Map View - Route Recording")
        self.map_label.setFont(QFont("Arial", 14))
        self.map_label.setMinimumHeight(400)
        self.map_label.setStyleSheet("border: 1px solid black; background: white; padding: 20px;")
        
        layout.addWidget(self.map_label)
        self.setLayout(layout)


class CamTab(QWidget):
    """Camera Display"""
    
    def __init__(self):
        super().__init__()
        self.camera_labels = {}
        self.initUI()
        
        # Connect camera updates
        self.camera_worker = CameraWorker()
        self.camera_worker.signals.updated.connect(self.update_cameras)
        self.camera_worker.start()
    
    def initUI(self):
        self.grid_layout = QGridLayout()
        self.setLayout(self.grid_layout)
    
    def update_cameras(self, cameras):
        # Clear old
        for label in self.camera_labels.values():
            label.deleteLater()
        self.camera_labels.clear()
        
        # Add new
        row = 0
        col = 0
        for cam in cameras:
            label = QLabel(cam['name'])
            label.setMinimumSize(300, 200)
            label.setStyleSheet("border: 1px solid #ccc; background: #f0f0f0; padding: 20px;")
            label.setAlignment(Qt.AlignCenter)
            self.grid_layout.addWidget(label, row, col)
            self.camera_labels[cam['name']] = label
            
            col += 1
            if col >= 2:
                col = 0
                row += 1


class ConfTab(QWidget):
    """Configuration"""
    
    def __init__(self):
        super().__init__()
        self.initUI()
        self.load_config()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # GPS settings
        self.dms_checkbox = QCheckBox("Show DMS Decimals")
        layout.addWidget(self.dms_checkbox)
        
        # Point diameter
        layout.addWidget(QLabel("Point Diameter:"))
        self.diameter_slider = QSlider(Qt.Horizontal)
        self.diameter_slider.setMinimum(5)
        self.diameter_slider.setMaximum(20)
        self.diameter_slider.setStyleSheet(SLIDER_STYLESHEET)
        self.diameter_slider.setValue(8)
        layout.addWidget(self.diameter_slider)
        
        # Save button
        save_button = QPushButton("Save Configuration")
        save_button.clicked.connect(self.save_config)
        layout.addWidget(save_button)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def load_config(self):
        try:
            response = urllib.request.urlopen('http://localhost:5000/api/config', timeout=2)
            data = json.loads(response.read())
            self.dms_checkbox.setChecked(data.get('gps', {}).get('show_dms_decimals', False))
            self.diameter_slider.setValue(data.get('route_recording', {}).get('point_diameter', 8))
        except:
            pass
    
    def save_config(self):
        try:
            data = {
                'gps': {'show_dms_decimals': self.dms_checkbox.isChecked()},
                'route_recording': {'point_diameter': self.diameter_slider.value()},
                'camera_rotations': {}
            }
            
            req = urllib.request.Request(
                'http://localhost:5000/api/config',
                data=json.dumps(data).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=2)
            print("Configuration saved")
        except Exception as e:
            print(f"Error saving config: {e}")


class SeeBoardApp(QMainWindow):
    """Main Application Window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("seeBoard - GPS & Camera Dashboard")
        self.setGeometry(0, 0, 800, 600)
        
        # Create tabs
        self.tabs = QTabWidget()
        
        self.coords_tab = CoordsTab()
        self.map_tab = MapTab()
        self.cam_tab = CamTab()
        self.conf_tab = ConfTab()
        
        self.tabs.addTab(self.coords_tab, "COORDS")
        self.tabs.addTab(self.map_tab, "MAP")
        self.tabs.addTab(self.cam_tab, "CAM")
        self.tabs.addTab(self.conf_tab, "CONF")
        
        self.setCentralWidget(self.tabs)


def main():
    app = QApplication(sys.argv)
    window = SeeBoardApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
