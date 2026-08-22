"""
Centralized configuration loading and management for seeBoard
Handles all config file I/O with consistent error handling and type conversion
"""

import os
from configparser import ConfigParser


class ConfigLoader:
    """Centralized config access with consistent error handling"""
    
    CONFIG_PATH = os.path.expanduser("~/.seeboard/see_board.cfg")
    
    def __init__(self, config):
        """
        Initialize config loader with existing ConfigParser instance
        
        Args:
            config: ConfigParser instance already loaded from file
        """
        self.config = config
        
        # Ensure database section and set default database path if not present
        if not self.config.has_section('database'):
            self.config.add_section('database')
        
        if not self.config.has_option('database', 'path'):
            default_db_path = os.path.expanduser("~/.seeboard/seeboard.db")
            self.config.set('database', 'path', default_db_path)
    
    def get_int(self, section, key, default=0):
        """
        Load integer config value with fallback to default
        
        Args:
            section: Config section name
            key: Config key name
            default: Default value if key missing or invalid
        
        Returns:
            Integer value or default
        """
        try:
            value = self.config.get(section, key, fallback=None)
            if value is None:
                return default
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_str(self, section, key, default=''):
        """
        Load string config value with fallback to default
        
        Args:
            section: Config section name
            key: Config key name
            default: Default value if key missing
        
        Returns:
            String value or default
        """
        return self.config.get(section, key, fallback=default)
    
    def get_bool(self, section, key, default=False):
        """
        Load boolean config value with fallback to default
        
        Args:
            section: Config section name
            key: Config key name
            default: Default value if key missing
        
        Returns:
            Boolean value or default
        """
        return self.config.getboolean(section, key, fallback=default)
    
    def set_value(self, section, key, value):
        """
        Set config value and save to file
        
        Args:
            section: Config section name
            key: Config key name
            value: Value to set (will be converted to string)
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        
        self.config.set(section, key, str(value))
        self._save_to_file()
    
    def ensure_section(self, section):
        """Ensure a config section exists"""
        if not self.config.has_section(section):
            self.config.add_section(section)
    
    def ensure_sections(self, sections):
        """Ensure multiple config sections exist"""
        for section in sections:
            self.ensure_section(section)
    
    def _save_to_file(self):
        """Save config to file"""
        try:
            with open(self.CONFIG_PATH, 'w') as f:
                self.config.write(f)
        except Exception as e:
            print(f"[CONFIG] Error saving to {self.CONFIG_PATH}: {e}")
