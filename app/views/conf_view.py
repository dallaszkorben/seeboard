"""CONF view — configuration settings with persistent storage and vertical scrolling.

Settings are saved to disk immediately on change (not on app exit) so that
values survive crashes. The COORDS and CAM views re-read the config file
each time they're shown, ensuring changes take effect without restart.

Uses radio buttons and checkboxes instead of dropdowns because tkinter's
OptionMenu doesn't respond well to touchscreen taps (requires precise
press-hold-release gesture that's difficult on a 5" resistive screen).
"""

import tkinter as tk
from tkinter import ttk


def create(parent, fonts, config, save_config, config_file):
    """Create the CONF view frame with scrollable content.

    Args:
        parent: parent tkinter widget
        fonts: dict with keys FONT_INFO, FONT_STATUS
        config: ConfigParser instance (shared with other views)
        save_config: callable to persist config to disk
        config_file: absolute path to config file
    Returns:
        frame: the conf_frame widget (scrollable)
    """
    frame = tk.Frame(parent, bg='black')
    
    # Create a canvas with scrollbar for scrollable content
    canvas = tk.Canvas(frame, bg='black', highlightthickness=0, height=400)
    scrollbar = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg='black')
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Pack canvas and scrollbar
    canvas.pack(side='left', fill='both', expand=True, padx=0, pady=0)
    scrollbar.pack(side='right', fill='y', padx=0, pady=0)
    
    # Enable mouse wheel scrolling on Linux and Windows
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def _on_mousewheel_linux(event):
        if event.num == 5:
            canvas.yview_scroll(3, "units")
        elif event.num == 4:
            canvas.yview_scroll(-3, "units")
    
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    canvas.bind_all("<Button-4>", _on_mousewheel_linux)
    canvas.bind_all("<Button-5>", _on_mousewheel_linux)

    tk.Label(scrollable_frame, text="Configuration", font=fonts["FONT_INFO"],
             fg='white', bg='black').pack(pady=(20, 20))

    # ─── DMS decimals checkbox ───
    dms_decimal_var = tk.BooleanVar(
        value=config.getboolean("gps", "show_dms_decimals", fallback=False))

    def on_dms_toggle():
        val = dms_decimal_var.get()
        config.set("gps", "show_dms_decimals", str(val))
        save_config(config)

    tk.Checkbutton(scrollable_frame, text="Show decimal seconds in GPS coordinates",
                   variable=dms_decimal_var, command=on_dms_toggle,
                   font=fonts["FONT_STATUS"], fg='white', bg='black',
                   selectcolor='#333333',
                   activebackground='black',
                   activeforeground='white').pack(pady=10, padx=20, anchor='w')

    # ─── Camera rotation radio buttons ───
    tk.Label(scrollable_frame, text="Camera rotation:", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(20, 5), padx=20, anchor='w')

    cam_rotation_var = tk.StringVar(
        value=str(config.getint("cam", "rotation", fallback=0)))

    def on_rotation_change():
        if not config.has_section("cam"):
            config.add_section("cam")
        config.set("cam", "rotation", cam_rotation_var.get())
        save_config(config)

    rot_frame = tk.Frame(scrollable_frame, bg='black')
    rot_frame.pack(padx=20, anchor='w')
    for val in ("0", "90", "180", "270"):
        tk.Radiobutton(rot_frame, text=f"{val}\u00b0",
                       variable=cam_rotation_var, value=val,
                       command=on_rotation_change, font=fonts["FONT_STATUS"],
                       fg='white', bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground='white',
                       indicatoron=1).pack(side='left', padx=10)

    # ─── Coordinate colors ───
    if not config.has_section("coords"):
        config.add_section("coords")

    COLORS = [("green", "lime"), ("red", "red"), ("blue", "cyan"), ("yellow", "yellow")]

    # Fix color (when GPS has a valid position)
    tk.Label(scrollable_frame, text="Position color (GPS fix):", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(20, 5), padx=20, anchor='w')
    fix_color_var = tk.StringVar(value=config.get("coords", "fix_color", fallback="lime"))

    def on_fix_color():
        config.set("coords", "fix_color", fix_color_var.get())
        save_config(config)

    fix_color_frame = tk.Frame(scrollable_frame, bg='black')
    fix_color_frame.pack(padx=20, anchor='w')
    for label, value in COLORS:
        tk.Radiobutton(fix_color_frame, text=label, variable=fix_color_var, value=value,
                       command=on_fix_color, font=fonts["FONT_STATUS"],
                       fg=value, bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground=value,
                       indicatoron=1).pack(side='left', padx=10)

    # No-fix color (when GPS lost fix, showing stale position)
    tk.Label(scrollable_frame, text="Position color (no fix):", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(20, 5), padx=20, anchor='w')
    nofix_color_var = tk.StringVar(value=config.get("coords", "nofix_color", fallback="red"))

    def on_nofix_color():
        config.set("coords", "nofix_color", nofix_color_var.get())
        save_config(config)

    nofix_color_frame = tk.Frame(scrollable_frame, bg='black')
    nofix_color_frame.pack(padx=20, anchor='w')
    for label, value in COLORS:
        tk.Radiobutton(nofix_color_frame, text=label, variable=nofix_color_var, value=value,
                       command=on_nofix_color, font=fonts["FONT_STATUS"],
                       fg=value, bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground=value,
                       indicatoron=1).pack(side='left', padx=10)

    # ─── Error/warning message color ───
    tk.Label(scrollable_frame, text="Error message color:", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(20, 5), padx=20, anchor='w')

    error_color_var = tk.StringVar(value=config.get("coords", "error_color", fallback="red"))

    def on_error_color():
        config.set("coords", "error_color", error_color_var.get())
        save_config(config)

    error_color_frame = tk.Frame(scrollable_frame, bg='black')
    error_color_frame.pack(padx=20, anchor='w')
    for label_text, value in [("red", "red")]:
        tk.Radiobutton(error_color_frame, text=label_text, variable=error_color_var, value=value,
                       command=on_error_color, font=fonts["FONT_STATUS"],
                       fg=value, bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground=value,
                       indicatoron=1).pack(side='left', padx=10)

    # ─── Route Recording Settings ───
    tk.Label(scrollable_frame, text="Route Recording:", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(20, 5), padx=20, anchor='w')

    # Sampling mode (distance vs time)
    if not config.has_section("route_recording"):
        config.add_section("route_recording")

    sampling_mode_var = tk.StringVar(
        value=config.get("route_recording", "sampling_mode", fallback="distance"))

    def on_sampling_mode_change():
        config.set("route_recording", "sampling_mode", sampling_mode_var.get())
        save_config(config)

    sampling_frame = tk.Frame(scrollable_frame, bg='black')
    sampling_frame.pack(padx=20, anchor='w', pady=5)
    tk.Radiobutton(sampling_frame, text="Distance-based (15m)",
                   variable=sampling_mode_var, value="distance",
                   command=on_sampling_mode_change, font=fonts["FONT_STATUS"],
                   fg='white', bg='black', selectcolor='#333333',
                   activebackground='black', activeforeground='white',
                   indicatoron=1).pack(side='left', padx=10)
    tk.Radiobutton(sampling_frame, text="Time-based (10s)",
                   variable=sampling_mode_var, value="time",
                   command=on_sampling_mode_change, font=fonts["FONT_STATUS"],
                   fg='white', bg='black', selectcolor='#333333',
                   activebackground='black', activeforeground='white',
                   indicatoron=1).pack(side='left', padx=10)

    # Line color for routes
    tk.Label(scrollable_frame, text="Route line color:", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(10, 5), padx=20, anchor='w')
    line_color_var = tk.StringVar(
        value=config.get("route_recording", "line_color", fallback="RED"))

    def on_line_color():
        config.set("route_recording", "line_color", line_color_var.get())
        save_config(config)

    line_color_frame = tk.Frame(scrollable_frame, bg='black')
    line_color_frame.pack(padx=20, anchor='w', pady=5)
    for color in ["RED", "BLUE", "GREEN", "YELLOW"]:
        color_hex = {"RED": "#FF0000", "BLUE": "#0000FF", "GREEN": "#00FF00", "YELLOW": "#FFFF00"}.get(color, "white")
        tk.Radiobutton(line_color_frame, text=color, variable=line_color_var, value=color,
                       command=on_line_color, font=fonts["FONT_STATUS"],
                       fg=color_hex, bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground=color_hex,
                       indicatoron=1).pack(side='left', padx=5)

    # ─── Route Point Circle Color (NEW - SCROLLABLE) ───
    tk.Label(scrollable_frame, text="Route point circle color:", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(15, 5), padx=20, anchor='w')
    
    point_color_value = config.get("route_recording", "point_color", fallback="red")
    point_color_var = tk.StringVar(value=point_color_value)

    def on_point_color():
        config.set("route_recording", "point_color", point_color_var.get())
        save_config(config)

    point_color_frame = tk.Frame(scrollable_frame, bg='black')
    point_color_frame.pack(padx=20, anchor='w', pady=5)
    for color in ["red", "blue", "green", "yellow", "cyan", "orange"]:
        color_hex = {
            "red": "#FF0000", "blue": "#0000FF", "green": "#00FF00",
            "yellow": "#FFFF00", "cyan": "#00FFFF", "orange": "#FFA500"
        }.get(color, "white")
        tk.Radiobutton(point_color_frame, text=color.capitalize(), variable=point_color_var, value=color,
                       command=on_point_color, font=fonts["FONT_STATUS"],
                       fg=color_hex, bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground=color_hex,
                       indicatoron=1).pack(side='left', padx=5)

    # ─── Route Point Circle Diameter (NEW - SCROLLABLE) ───
    tk.Label(scrollable_frame, text="Route point circle diameter (pixels):", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(15, 5), padx=20, anchor='w')
    
    diameter_value = config.get("route_recording", "point_diameter", fallback="8")
    diameter_var = tk.StringVar(value=diameter_value)

    def on_diameter_change():
        config.set("route_recording", "point_diameter", diameter_var.get())
        save_config(config)

    diameter_frame = tk.Frame(scrollable_frame, bg='black')
    diameter_frame.pack(padx=20, anchor='w', pady=5)
    
    for size in ["5", "8", "12", "15"]:
        tk.Radiobutton(diameter_frame, text=f"{size}px",
                       variable=diameter_var, value=size,
                       command=on_diameter_change, font=fonts["FONT_STATUS"],
                       fg='white', bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground='white',
                       indicatoron=1).pack(side='left', padx=5)

    # Add padding at bottom for scrolling room
    tk.Frame(scrollable_frame, bg='black', height=100).pack()

    return frame
