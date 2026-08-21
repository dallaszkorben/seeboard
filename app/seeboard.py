#!/usr/bin/env python3
"""
seeBoard — Nautical GPS + Camera application.

Touchscreen layout with button panel on the right.
Views: COORDS, MAP, CAM, CONF — each in its own module.

This file is the thin orchestrator: it creates the window, wires up
the views, and runs the main loop. All view logic lives in app/views/.
"""

import tkinter as tk
import configparser
import atexit

# Add app/ directory to Python path so that views/ and gps_core are importable
# without requiring package installation. This lets us run directly with
# "python app/seeboard.py" from the project root.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gps_core import open_serial, close
import gps_core

from views import coords_view
from views import map_view
from views import cam_view
from views import conf_view

from route_database import RouteDatabase
from route_recorder import RouteRecorder

# Ensure serial port is always restored on exit, even on crash.
# Without this, the port can be left in a bad state and `cat /dev/serial0`
# would stop working until a manual `stty sane`.
atexit.register(close)

# Start GPS reading in background thread. Never blocks the main thread.
# If GPS is not connected, the thread retries silently.
open_serial()
gps_core.start_background_reader()

# ─── Configuration ───
# Config file lives at project root (not inside app/) so it's easy to find
# and edit manually if needed. Derived from script location so it works
# regardless of where the project is installed.
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "see_board.cfg")


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    if not cfg.has_section("gps"):
        cfg.add_section("gps")
    return cfg


def save_config(cfg):
    """Save config with comments showing available options."""
    # Ensure all sections and defaults exist before writing
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
    if not cfg.has_option("route_recording", "distance_threshold"):
        cfg.set("route_recording", "distance_threshold", "15.0")
    if not cfg.has_option("route_recording", "time_threshold"):
        cfg.set("route_recording", "time_threshold", "10")
    if not cfg.has_option("route_recording", "line_color"):
        cfg.set("route_recording", "line_color", "RED")
    if not cfg.has_option("route_recording", "line_width"):
        cfg.set("route_recording", "line_width", "3")
    if not cfg.has_option("route_recording", "line_style"):
        cfg.set("route_recording", "line_style", "continuous")
    if not cfg.has_option("route_recording", "point_color"):
        cfg.set("route_recording", "point_color", "red")
    if not cfg.has_option("route_recording", "point_diameter"):
        cfg.set("route_recording", "point_diameter", "8")

    with open(CONFIG_FILE, "w") as f:
        f.write("# seeBoard configuration\n")
        f.write("#\n")
        f.write("# [gps]\n")
        f.write("#   show_dms_decimals: True / False (default: False)\n")
        f.write("#\n")
        f.write("# [cam]\n")
        f.write("#   rotation: 0 / 90 / 180 / 270 (default: 0)\n")
        f.write("#\n")
        f.write("# [coords]\n")
        f.write("#   fix_color:   lime / red / cyan / yellow (default: lime)\n")
        f.write("#   nofix_color: lime / red / cyan / yellow (default: red)\n")
        f.write("#   error_color: red (default: red)\n")
        f.write("#\n")
        f.write("# [route_recording]\n")
        f.write("#   sampling_mode: distance / time (default: distance)\n")
        f.write("#   distance_threshold: meters (default: 15.0)\n")
        f.write("#   time_threshold: seconds (default: 10)\n")
        f.write("#   line_color: RED / BLUE / GREEN / etc or #RRGGBB (default: RED)\n")
        f.write("#   line_width: pixels (default: 3)\n")
        f.write("#   line_style: continuous / dotted / dashed / dashdot (default: continuous)\n")
        f.write("#   point_color: red / blue / green / yellow / etc (default: red)\n")
        f.write("#   point_diameter: pixels (default: 8)\n")
        f.write("\n")
        cfg.write(f)



config = load_config()
save_config(config)  # Initialize/update all config defaults at startup
gps_core.SHOW_DMS_DECIMALS = config.getboolean("gps", "show_dms_decimals", fallback=False)

# ─── Initialize route recording ───
route_db = RouteDatabase()
route_recorder = RouteRecorder(route_db)

# ─── Main window ───
root = tk.Tk()
root.title("seeBoard")
root.configure(bg='black')
root.update_idletasks()
# Fullscreen for touchscreen kiosk use — no window decorations or taskbar
root.attributes('-fullscreen', True)
root.update()
root.bind('<Escape>', lambda e: on_close())

# Font sizes are relative to screen height so the UI scales correctly
# on different displays (5" vs 7" touchscreen) without hardcoded pixel values.
_sh = root.winfo_screenheight()
fonts = {
    "FONT_COORD": ("Helvetica", _sh // 7, "bold"),
    "FONT_INFO": ("Helvetica", _sh // 20),
    "FONT_STATUS": ("Helvetica", _sh // 27),
    "FONT_BTN": ("Helvetica", _sh // 34, "bold"),
}

# ─── Right panel: buttons ───
# Fixed 120px width so the content area gets all remaining space.
# pack_propagate(False) prevents child widgets from shrinking the panel.
btn_panel = tk.Frame(root, bg='#222222', width=120)
btn_panel.pack(side='right', fill='y')
btn_panel.pack_propagate(False)

# ─── Left panel: content area ───
content = tk.Frame(root, bg='black')
content.pack(side='left', fill='both', expand=True)

# ─── Create views ───
# Each view module returns its frame + any callbacks needed by the orchestrator.
# Views are created once at startup and shown/hidden via pack/pack_forget
# (not destroyed/recreated) to preserve state and avoid flicker.
coords_frame, update_gps, coords_on_show = coords_view.create(
    content, fonts, config, CONFIG_FILE)
map_frame, map_widget, marker, route_lines = map_view.create(content)
cam_frame, cam_label = cam_view.create(content, fonts)
conf_frame = conf_view.create(content, fonts, config, save_config, CONFIG_FILE)

# Show COORDS by default — most important view for navigation
coords_frame.pack(fill='both', expand=True)

# ─── View switching ───
view_mode = 'coords'
# Using a list so the closure in update_cam can see mutations
running = [True]


def get_view_mode():
    return view_mode


def show_view(mode):
    """Switch to the specified view. Hides all others."""
    global view_mode
    coords_frame.pack_forget()
    map_frame.pack_forget()
    cam_frame.pack_forget()
    conf_frame.pack_forget()

    # Always stop camera streams when leaving CAM view to free network
    # bandwidth and CPU. Streams are cheap to restart.
    cam_view.stop_all()

    if mode == 'coords':
        # Re-read config on every switch to COORDS so that settings changed
        # in CONF (like DMS decimals) take effect immediately.
        coords_on_show()
        coords_frame.pack(fill='both', expand=True)
    elif mode == 'map':
        map_frame.pack(fill='both', expand=True)
    elif mode == 'conf':
        conf_frame.pack(fill='both', expand=True)
    elif mode == 'cam':
        # Reset discovery and rebuild: ensures dead cameras are dropped
        # and newly connected cameras are found fresh.
        cam_view.on_show(root)
        cam_frame.pack(fill='both', expand=True)

    view_mode = mode
    # Highlight active button green, others white
    for btn, m in [(coords_btn, 'coords'), (map_btn, 'map'),
                   (cam_btn, 'cam'), (conf_btn, 'conf')]:
        if mode == m:
            btn.config(fg='lime', bg='#666666',
                       activeforeground='lime', activebackground='#777777')
        else:
            btn.config(fg='white', bg='#444444',
                       activeforeground='white', activebackground='#555555')


# ─── Buttons ───
# Large touch targets (ipady=12) for reliable touchscreen taps.
coords_btn = tk.Button(btn_panel, text="COORDS", font=fonts["FONT_BTN"],
                       bg="#666666", fg='lime', activebackground='#666666',
                       command=lambda: show_view('coords'))
coords_btn.pack(fill='x', padx=5, pady=(20, 5), ipady=12)

map_btn = tk.Button(btn_panel, text="MAP", font=fonts["FONT_BTN"],
                    bg='#444444', fg='white', activebackground='#666666',
                    command=lambda: show_view('map'))
map_btn.pack(fill='x', padx=5, pady=5, ipady=12)

cam_btn = tk.Button(btn_panel, text="CAM", font=fonts["FONT_BTN"],
                    bg='#444444', fg='white', activebackground='#666666',
                    command=lambda: show_view('cam'))
cam_btn.pack(fill='x', padx=5, pady=5, ipady=12)

conf_btn = tk.Button(btn_panel, text="CONF", font=fonts["FONT_BTN"],
                     bg='#444444', fg='white',
                     activeforeground='white', activebackground='#555555',
                     command=lambda: show_view('conf'))
conf_btn.pack(fill='x', padx=5, pady=5, ipady=12)

# ─── REC/STOP buttons for route recording ───
def on_rec_pressed():
    """Start or auto-restart route recording"""
    gps_data = gps_core.get_latest()
    
    if gps_data and gps_data.get('status') == 'fix':
        config_fresh = load_config()
        sampling_mode = config_fresh.get('route_recording', 'sampling_mode', fallback='distance')
        rec_config = {
            'line_color': config_fresh.get('route_recording', 'line_color', fallback='RED'),
            'line_width': config_fresh.getint('route_recording', 'line_width', fallback=3),
            'line_style': config_fresh.get('route_recording', 'line_style', fallback='continuous'),
            'sampling_mode': sampling_mode,
            'sampling_value': config_fresh.getfloat(
                'route_recording', 
                'distance_threshold' if sampling_mode == 'distance' 
                else 'time_threshold',
                fallback=15.0 if sampling_mode == 'distance' else 10.0
            )
        }
        route_recorder.start_recording(gps_data, rec_config)
        update_button_states()


def on_stop_pressed():
    """Stop route recording"""
    route_recorder.stop_recording()
    update_button_states()


def update_button_states():
    """Update button appearance based on recording state"""
    if route_recorder.is_recording():
        # Recording active: REC is RED, STOP is active (LIME)
        rec_btn.config(bg='#666666', fg='red', state='normal')
        stop_btn.config(bg='#666666', fg='lime', state='normal')
    else:
        # Not recording: REC is WHITE, STOP is inactive (GRAY)
        rec_btn.config(bg='#444444', fg='white', state='normal')
        stop_btn.config(bg='#444444', fg='gray', state='disabled')


rec_btn = tk.Button(btn_panel, text="REC", font=fonts["FONT_BTN"],
                    bg='#444444', fg='white', activebackground='#666666',
                    command=on_rec_pressed)
rec_btn.pack(fill='x', padx=5, pady=5, ipady=12)

stop_btn = tk.Button(btn_panel, text="STOP", font=fonts["FONT_BTN"],
                     bg='#444444', fg='gray', activebackground='#666666',
                     state='disabled', command=on_stop_pressed)
stop_btn.pack(fill='x', padx=5, pady=5, ipady=12)

# TODO: SAVE button — will store current position as waypoint in SQLite
tk.Button(btn_panel, text="SAVE", font=fonts["FONT_BTN"],
          bg='#444444', fg='gray', state='disabled'
          ).pack(fill='x', padx=5, pady=5, ipady=12)

# EXIT button at the bottom — separated from nav buttons to avoid accidental taps.
# Uses side='bottom' on a sub-frame to pin it to the panel's bottom edge.
exit_frame = tk.Frame(btn_panel, bg='#222222')
exit_frame.pack(side='bottom', fill='x')
tk.Button(exit_frame, text="EXIT", font=fonts["FONT_BTN"],
          bg='#444444', fg='red', activeforeground='red', activebackground='#555555',
          command=lambda: on_close()).pack(fill='x', padx=5, pady=(5, 20), ipady=12)


# ─── Cleanup ───
def on_close():
    running[0] = False
    cam_view.stop_all()
    gps_core.stop_background_reader()
    route_db.close()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)

# ─── Start update loops ───
# GPS updates every 1s (matches NMEA sentence rate from NEO-7M).
# Includes route recording point capture based on sampling threshold.
def gps_update_with_recording(root, get_view_mode, marker, map_widget, config):
    """Update GPS display and route recording"""
    gps_data = gps_core.get_latest()
    
    # If recording and we have GPS data, check if we should record a point
    if route_recorder.is_recording() and gps_data and gps_data.get('status') == 'fix':
        if route_recorder.should_record_point(gps_data):
            route_recorder.add_point(gps_data)
        
        # Always redraw route while recording (not just when adding new points)
        # This ensures route stays visible even if sampling threshold hasn't been met
        from views import map_view
        map_view.draw_route(map_widget, route_lines, route_db, route_recorder, config)
        
        # Redraw circles to ensure they're visible after any map pans/zooms
        map_view.redraw_route_circles_on_view_change(map_widget)
    
    # Continue with normal GPS update (passing route_recorder for status display)
    update_gps(root, get_view_mode, marker, map_widget, route_recorder)
    
    # Reschedule for next update
    root.after(1000, lambda: gps_update_with_recording(root, get_view_mode, marker, map_widget, config))


# Camera updates every 50ms (~20fps) for smooth video.
root.after(1000, lambda: gps_update_with_recording(root, get_view_mode, marker, map_widget, config))
cam_view.update_cam(root, cam_label, config, get_view_mode, running)
root.mainloop()
close()
route_db.close()
