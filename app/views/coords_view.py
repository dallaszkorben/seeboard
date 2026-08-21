"""COORDS view — displays GPS coordinates, time, quality, satellites.

This is the primary navigation view showing position in DMS format.
The update loop runs continuously (even when another view is visible)
so that the map marker stays current regardless of which view is active.
"""

import tkinter as tk
from gps_core import get_latest, _dd_to_dms
import gps_core


def create(parent, fonts, config, config_file):
    """Create the COORDS view frame and return (frame, update_func, on_show).

    Args:
        parent: parent tkinter widget
        fonts: dict with FONT_COORD, FONT_INFO, FONT_STATUS
        config: ConfigParser instance
        config_file: absolute path to config file
    Returns:
        frame, update_gps, on_show
    """
    frame = tk.Frame(parent, bg='black')

    # StringVars allow the labels to update without recreating widgets.
    # Initial values show placeholder dashes until GPS data arrives.
    lat_var = tk.StringVar(value="--°--'--\"")
    lon_var = tk.StringVar(value="---°--'--\"")
    time_var = tk.StringVar(value="Time: --:--:--")
    qual_var = tk.StringVar(value="Quality: -")
    sat_var = tk.StringVar(value="Satellites: - used / - visible")
    status_var = tk.StringVar(value="")
    recording_var = tk.StringVar(value="")

    # Large text for coordinates — color changes based on fix status.
    # Color is configurable via CONF menu (stored in see_board.cfg).
    lat_label = tk.Label(frame, textvariable=lat_var, font=fonts["FONT_COORD"],
                         fg='lime', bg='black')
    lat_label.pack(pady=(40, 5))
    lon_label = tk.Label(frame, textvariable=lon_var, font=fonts["FONT_COORD"],
                         fg='lime', bg='black')
    lon_label.pack(pady=5)
    tk.Label(frame, textvariable=time_var, font=fonts["FONT_INFO"],
             fg='white', bg='black').pack(pady=10)
    tk.Label(frame, textvariable=qual_var, font=fonts["FONT_INFO"],
             fg='white', bg='black').pack(pady=5)
    tk.Label(frame, textvariable=sat_var, font=fonts["FONT_INFO"],
             fg='white', bg='black').pack(pady=5)
    
    # Recording status label — RED when recording, invisible when not
    recording_label = tk.Label(frame, textvariable=recording_var, font=fonts["FONT_INFO"],
                               fg='red', bg='black')
    recording_label.pack(pady=5)
    
    # Error/warning label — color read from config each time it's updated
    status_label = tk.Label(frame, textvariable=status_var, font=fonts["FONT_STATUS"],
                            fg='red', bg='black')
    status_label.pack(pady=20)

    # Mutable state in lists so nested functions can modify them.
    # (Python closures can read but not assign to outer variables without nonlocal)
    empty_reads = [0]
    last_pos = [None, None]  # [lat, lon]

    def on_show():
        """Called when switching to COORDS view — re-read config from file.

        The config file is re-read (not just the in-memory object) because
        conf_view writes changes to disk. This ensures the DMS decimal
        and color settings take effect immediately when the user switches views.
        """
        config.read(config_file)
        gps_core.SHOW_DMS_DECIMALS = config.getboolean(
            'gps', 'show_dms_decimals', fallback=False)

    def update_gps(root, get_view_mode, marker, map_widget, route_recorder=None):
        """Display latest GPS data. Non-blocking — reads from background thread."""
        data = get_latest()

        if data is None:
            # GPS disconnected or not responding — show last position in
            # warning color and clear status fields to indicate data is stale.
            nofix_color = config.get("coords", "nofix_color", fallback="red")
            lat_label.config(fg=nofix_color)
            lon_label.config(fg=nofix_color)
            time_var.set("Time: --:--:--")
            qual_var.set("Quality: No GPS")
            sat_var.set("Satellites: - used / - visible")
            error_color = config.get("coords", "error_color", fallback="red")
            status_label.config(fg=error_color)
            status_var.set("⚠ No GPS data")
        elif data["status"] == "no_fix":
            # Show stale coordinates in "no fix" color to indicate position is not current
            nofix_color = config.get("coords", "nofix_color", fallback="red")
            lat_label.config(fg=nofix_color)
            lon_label.config(fg=nofix_color)
            error_color = config.get("coords", "error_color", fallback="red")
            status_label.config(fg=error_color)
            status_var.set("Waiting for fix...")
            qual_var.set("Quality: No fix")
            time_var.set(f"Time: {data['time']}" if data['time'] and str(data['time']) != "None" else "Time: --:--:--")
            sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")
        elif data["status"] == "fix":
            # Show coordinates in "fix" color to indicate position is current
            fix_color = config.get("coords", "fix_color", fallback="lime")
            lat_label.config(fg=fix_color)
            lon_label.config(fg=fix_color)
            status_var.set("")
            lat_var.set(f"{_dd_to_dms(data['lat_raw'])} {data['lat_dir']}")
            lon_var.set(f"{_dd_to_dms(data['lon_raw'])} {data['lon_dir']}")
            time_var.set(f"Time: {data['time']}" if data['time'] and str(data['time']) != "None" else "Time: --:--:--")
            qual_var.set(f"Quality: {data['quality']}")
            sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

            lat = data["lat_raw"]
            lon = data["lon_raw"]
            if lat != last_pos[0] or lon != last_pos[1]:
                marker.set_position(lat, lon)
                if get_view_mode() == "map":
                    map_widget.set_position(lat, lon)
                last_pos[0] = lat
                last_pos[1] = lon

        # Update recording status display
        if route_recorder and route_recorder.is_recording():
            route_info = route_recorder.get_recording_info()
            if route_info:
                point_count = route_info.get('point_count', 0)
                recording_var.set(f"🔴 RECORDING ({point_count} pts)")
        else:
            recording_var.set("")

    return frame, update_gps, on_show
