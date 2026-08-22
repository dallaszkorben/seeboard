# seeBoard Methods Reference

## Global Utility Functions

### create_styled_button(text, bg_color_hex, text_color, state='active', width=None, height=None)

**Location**: `app/seeboard_pyqt5_direct.py` (module level)

**Purpose**: Create a styled button with consistent appearance across the app with three distinct states.

**Parameters**:
- `text` (str): Button label text
- `bg_color_hex` (str): Background color in hex format (#RRGGBB), e.g., "#00CC00"
- `text_color` (str): Text color (name or hex), e.g., "white" or "#FFFFFF"
- `state` (str): Button state - one of:
  - `'active'`: Enabled, bright color, thin grey border (can be clicked)
  - `'selected'`: Enabled, bright color, thick blue border (highlighted/selected)
  - `'inactive'`: Disabled, grey color, grey border (cannot be clicked)
- `width` (int, optional): Fixed width in pixels
- `height` (int, optional): Fixed height in pixels

**Returns**: `QPushButton` with applied stylesheet

**Example Usage**:
```python
# Create a green active button
rec_btn = create_styled_button("REC", "#00CC00", "white", state='active')

# Create a red selected button
stop_btn = create_styled_button("STOP", "#FF4444", "white", state='selected')

# Create an inactive button
disable_btn = create_styled_button("DISABLED", "#0000FF", "white", state='inactive')
```

**Visual States**:
- **Active**: Thin 2px grey border, responds to hover (blue border), pressable
- **Selected**: Thick 4px blue border, indicates currently selected/active state
- **Inactive**: Grey background, grey border, non-responsive

**Color Helper Functions**:
- `_lighten_color(hex_color, amount)`: Lighten a hex color by given amount
- `_darken_color(hex_color, amount)`: Darken a hex color by given amount

---

## MapTab Class Methods

### MapTab.__init__(config)

**Location**: `app/seeboard_pyqt5_direct.py`, line ~637

**Purpose**: Initialize the MAP tab with map display, GPS marker, and recording controls.

**Key attributes initialized**:
- `self.zoom`: Current zoom level (1-18)
- `self.map_center_lat`, `self.map_center_lon`: Map center coordinates
- `self.is_recording`: Boolean flag for recording state
- `self.current_recording_path_id`: ID of currently recording path
- `self.current_recording_color`: Color of recording path
- `self.map_mode`: "FREE" or "FOLLOW" mode
- `self.recorder`: RouteRecorder instance for path recording
- `self.db`: PathDatabase instance

### MapTab.render_map()

**Location**: `app/seeboard_pyqt5_direct.py`, line ~802

**Purpose**: Render the map at current center with GPS marker, recorded path line, and position circles.

**Process**:
1. Creates map renderer with widget dimensions
2. Retrieves current recording path points from recorder
3. Calls `renderer.render_map()` with path data
4. Scales and displays pixmap on map label

**Parameters used**:
- Map center coordinates (map_center_lat, map_center_lon)
- GPS position (current_lat, current_lon)
- Zoom level
- Route points (if recording)
- Path color from config
- Position radius from config
- Position font size from config
- Path width from config

### MapTab.start_recording()

**Location**: `app/seeboard_pyqt5_direct.py`, line ~970

**Purpose**: Start recording a new GPS path.

**Actions**:
1. Gets recording color from config
2. Creates recording configuration (sampling mode, width, style, color)
3. Calls `self.recorder.start_recording()` to create new path in database
4. Sets `self.is_recording = True` and `self.map_mode = "FOLLOW"`
5. Updates button styles (REC inactive, STOP selected)
6. Triggers map re-render

**State changes**:
- REC button: active → inactive (grey)
- STOP button: inactive → selected (red with blue border)
- Map mode: FREE → FOLLOW (auto-centers on GPS)

### MapTab.stop_recording()

**Location**: `app/seeboard_pyqt5_direct.py`, line ~1008

**Purpose**: Stop the current GPS path recording.

**Actions**:
1. Calls `self.recorder.stop_recording()` to mark path as complete
2. Sets `self.is_recording = False` and `self.map_mode = "FREE"`
3. Updates button styles (REC active, STOP inactive)
4. Triggers map re-render

**State changes**:
- REC button: inactive → active (green)
- STOP button: selected → inactive (grey)
- Map mode: FOLLOW → FREE (stops auto-centering)

### MapTab._update_recording_button_styles()

**Location**: `app/seeboard_pyqt5_direct.py`, line ~1027

**Purpose**: Update REC/STOP button appearances based on recording state.

**Logic**:
- If recording:
  - REC: inactive (grey) - cannot start new recording
  - STOP: selected (red with blue border) - can stop recording
- If not recording:
  - REC: active (green) - can start recording
  - STOP: inactive (grey) - cannot stop

**Uses**: `create_styled_button()` to apply consistent styling

### MapTab.record_gps_point_if_needed()

**Location**: `app/seeboard_pyqt5_direct.py`, line ~1044

**Purpose**: Check if current GPS point should be recorded based on sampling criteria.

**Process**:
1. Only runs if `self.is_recording` is True
2. Calls `self.recorder.should_record_point()` to check sampling criteria
3. If point should be recorded, calls `self.recorder.add_point()`
4. Triggers map re-render if point was added

**Sampling modes**:
- **Time-based**: Records point if elapsed time ≥ configured interval (default 15s)
- **Distance-based**: Records point if distance from last point ≥ threshold

### MapTab.on_gps_update(gps_data)

**Location**: `app/seeboard_pyqt5_direct.py`, line ~788

**Purpose**: Handle GPS position updates from GPS worker thread.

**Actions**:
1. Updates `self.current_lat`, `self.current_lon` from GPS data
2. If in FOLLOW mode, centers map on current GPS position
3. Marks map for re-render if position changed

**Special handling**:
- First GPS update centers map if using default position
- FOLLOW mode keeps map centered on GPS (used during recording)
- FREE mode preserves user's manual map position

---

## RouteRecorder Class Methods

**Location**: `app/route_recorder.py`

### RouteRecorder.start_recording(current_position, config)

**Purpose**: Start a new GPS path recording session.

**Parameters**:
- `current_position`: Dict with GPS data (lat, lon, alt, accuracy)
- `config`: Dict with recording config (line_color, line_width, sampling_mode, sampling_value)

**Returns**: `path_id` of new recording

**Database action**: Creates new row in `paths` table, sets `is_recording = 1`

### RouteRecorder.stop_recording()

**Purpose**: Stop current recording session and mark path as complete.

**Returns**: `path_id` that was stopped (or None if not recording)

**Database action**: Updates `paths` table, sets `stopped_at = NOW()`, `is_recording = 0`

### RouteRecorder.should_record_point(current_position)

**Purpose**: Check if current position meets sampling criteria for recording.

**Logic**:
- Time-based: Check elapsed time since last point
- Distance-based: Check distance from last point
- Always records first point

**Returns**: Boolean

### RouteRecorder.add_point(current_position)

**Purpose**: Add a GPS point to current recording.

**Returns**: `point_id` of inserted point

**Database action**: Inserts row in `path_points` table with sequence number and distance/time from previous point

### RouteRecorder.get_current_route_points()

**Purpose**: Get all points for current recording.

**Returns**: List of point dicts with (latitude, longitude, timestamp, etc.)

---

## MapRenderer Class Methods

**Location**: `app/map_renderer.py`

### MapRenderer.render_map(lat, lon, gps_lat, gps_lon, zoom, route_points, coverage_radius, path_color, position_radius, position_font_size, path_width)

**Purpose**: Render offline map with GPS marker, path line, and position circles.

**Parameters**:
- `lat`, `lon`: Map center coordinates
- `gps_lat`, `gps_lon`: Current GPS position for marker
- `zoom`: Zoom level (1-18)
- `route_points`: List of (lat, lon) tuples for path line
- `path_color`: Color name ('RED', 'BLUE', 'GREEN', etc.)
- `position_radius`: Radius of position circles (1-10 pixels)
- `position_font_size`: Font size for position numbers (6-16pt)
- `path_width`: Width of path line (1-8 pixels)

**Returns**: `QPixmap` with rendered map

**Rendering steps**:
1. Creates map context with OSM tiles
2. Draws path line using py-staticmaps `Line` object
3. Draws GPS marker
4. Calls `_draw_position_markers()` to add circles and numbers
5. Converts PIL Image to QPixmap

### MapRenderer._draw_position_markers(image, ctx, route_points, path_rgb, position_radius, position_font_size, center_lat, center_lon, zoom)

**Purpose**: Draw circles and sequential numbers at each recorded position on the rendered map.

**Process**:
1. For each position in route_points:
   - Converts lat/lon to pixel coordinates using Mercator projection
   - Draws filled circle with path color
   - Draws white number (position order) centered on circle

**Visual output**: Filled circles with white text numbers, making path waypoints clearly visible

---

## Configuration Keys

**File**: `see_board.cfg`

### Map Section `[map]`
- `time_based_sampling`: Recording interval in seconds (default "15s")
- `recording_color`: Color for new paths (default "RED")
- `position_radius`: Circle radius for waypoints, 1-10 (default "2")
- `position_font_size`: Font size for waypoint numbers, 6-16 (default "8")
- `path_width`: Line width for paths, 1-8 pixels (default "1")

---

## Button State Design Pattern

### Three-State Button System

**States**:
1. **Active**: Enabled, can be clicked, thin border
   - Used for: Available actions (REC when not recording)
   - Color: Custom (green, blue, etc.)
   - Border: 2px grey

2. **Selected**: Enabled, currently active, thick blue border
   - Used for: Currently active elements (STOP while recording)
   - Color: Same as active
   - Border: 4px blue (#007AFF)

3. **Inactive**: Disabled, cannot be clicked, grey
   - Used for: Unavailable actions (REC while recording, STOP when not recording)
   - Color: Grey (#999999)
   - Border: 2px grey

**REC/STOP Example**:
- Not recording: REC=active (green), STOP=inactive (grey)
- Recording: REC=inactive (grey), STOP=selected (red with blue border)

This makes the button states immediately clear to the user without needing text labels.

---

## Reusable Methods in ConfTab Class

### ConfTab._create_bordered_section(title)

**Location**: `app/seeboard_pyqt5_direct.py`, ConfTab class, line ~2004

**Purpose**: Create a QGroupBox with minimal styling for section grouping.

**Parameters**:
- `title` (str): Section title

**Returns**: Tuple of `(QGroupBox, QVBoxLayout)`

**Usage**:
```python
section_box, section_layout = self._create_bordered_section("My Section")
section_layout.addWidget(some_widget)
```

**Features**:
- Removes default frame styling (flat appearance)
- Consistent padding and spacing
- 12px font, dark grey text
- Returns both box and layout for convenience

**Used in**: Creating Coordinates, Metadata, Background sections in ConfTab

### ConfTab._create_slider_with_label(label_text, min_val, max_val, default_val, config_section, config_key, layout)

**Location**: Suggested pattern - currently implemented inline multiple times

**Purpose**: Create a slider with label and value display (PATTERN TO IMPLEMENT).

**Current implementation**: Repeated 10+ times with variations like:
```python
# Font size slider (repeated 3 times)
self.font_size_slider = QSlider(Qt.Horizontal)
self.font_size_slider.setMinimum(60)
self.font_size_slider.setMaximum(120)
self.font_size_slider.setStyleSheet(SLIDER_STYLESHEET)
try:
    font_size = int(self.config.get('gps', 'coord_font_size', fallback='65'))
    self.font_size_slider.setValue(font_size)
except:
    self.font_size_slider.setValue(65)
self.font_size_slider.valueChanged.connect(self.save_config)
font_layout.addWidget(self.font_size_slider)

self.font_size_value = QLabel(str(self.font_size_slider.value()))
self.font_size_value.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
self.font_size_slider.valueChanged.connect(lambda v: self.font_size_value.setText(str(v)))
font_layout.addWidget(self.font_size_value)
```

**Recommendation**: Extract to method to reduce code duplication.

---

## Global Stylesheets

### SLIDER_STYLESHEET

**Location**: `app/seeboard_pyqt5_direct.py`, line ~170

**Usage**: Applied to all sliders in the app for consistent appearance.

```python
self.some_slider.setStyleSheet(SLIDER_STYLESHEET)
```

**Includes styling for**:
- Slider groove (background track)
- Handle (draggable thumb)
- Hover states
- Pressed states

---

## Repeated Stylesheet Patterns

### Label StyleSheets (Repeated 15+ times)

**Small label with no border** (used for slider/config labels):
```python
label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
```

**Value display label** (used to show slider/config values):
```python
value_label.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
```

**Recommendation**: Create helper function to eliminate string duplication.

---

## Common Patterns

### Button Creation Pattern
```python
# Instead of creating individual buttons with full stylesheets:
btn = create_styled_button("Label", "#COLOR", "textcolor", state='active')

# Then update state when needed:
btn.setStyleSheet(create_styled_button("Label", "#COLOR", "textcolor", state='selected').styleSheet())
```

### GPS Recording Pattern
```python
# In init: Create recorder
self.recorder = RouteRecorder(self.db)

# Start recording
self.current_recording_path_id = self.recorder.start_recording(gps_data, config)

# During recording timer
if self.recorder.should_record_point(gps_data):
    self.recorder.add_point(gps_data)

# Stop recording
self.recorder.stop_recording()
```

### Config Get/Set Pattern (Repeated 60+ times)
```python
# Load from config with fallback
value = self.config.get('section', 'key', fallback='default_value')

# Save to config
self.config.set('section', 'key', str(value))

# Write config file
with open(config_file, 'w') as f:
    self.config.write(f)
```

### Slider Creation Pattern (Repeated 10+ times)
```python
# Create slider
slider = QSlider(Qt.Horizontal)
slider.setMinimum(min_val)
slider.setMaximum(max_val)
slider.setStyleSheet(SLIDER_STYLESHEET)

# Load value from config
try:
    value = int(self.config.get('section', 'key', fallback='default'))
    slider.setValue(value)
except:
    slider.setValue(default)

# Connect to save
slider.valueChanged.connect(self.save_config)

# Create value label
value_label = QLabel(str(slider.value()))
value_label.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
```

### HLayout Pattern (Repeated 20+ times)
```python
layout = QHBoxLayout()
label = QLabel("Label:")
label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
layout.addWidget(label)
# ... add widget ...
layout.addStretch()
parent_layout.addLayout(layout)
```

---

## Comprehensive Code Duplication Analysis

### 1. Slider Creation Pattern (Repeated 10+ times)

**Current inline implementation:**
```python
slider = QSlider(Qt.Horizontal)
slider.setMinimum(min_val)
slider.setMaximum(max_val)
slider.setStyleSheet(SLIDER_STYLESHEET)
try:
    value = int(self.config.get('section', 'key', fallback='default'))
    slider.setValue(value)
except:
    slider.setValue(default)
slider.valueChanged.connect(self.save_config)
```

**Recommendation**: Extract to `create_slider(min, max, config_section, config_key, default, on_change_callback)`

**Locations**: Lines 1479-1488, 1539-1548, 1627-1632, 1761-1770, 1786-1795, 1809-1818

---

### 2. Slider Label + Value Display Pattern (Repeated 10+ times)

**Current inline implementation:**
```python
slider_layout = QHBoxLayout()
label = QLabel("Label:")
label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
slider_layout.addWidget(label)
slider_layout.addWidget(slider)
value_label = QLabel(str(slider.value()))
value_label.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
slider_layout.addWidget(value_label)
parent_layout.addLayout(slider_layout)
```

**Recommendation**: Extract to `create_slider_with_label(label_text, slider, parent_layout)`

**Locations**: All slider implementations

---

### 3. Color Button Loop Pattern (Repeated 6 times)

**Current inline implementation:**
```python
for color_name, color_hex in colors.items():
    btn = QPushButton(color_name.upper())
    text_color = '#000000' if color_name in ['YELLOW', 'CYAN'] else '#FFFFFF'
    is_selected = saved_color == color_name
    btn.setStyleSheet(get_button_stylesheet(color_hex, text_color, is_selected))
    btn.clicked.connect(lambda checked, c=color_name: self.on_color_selected(c))
    self.color_buttons[color_name] = btn
    layout.addWidget(btn)
```

**Recommendation**: Extract to `create_color_button_grid(colors_dict, saved_color, callback, layout, button_width=None)`

**Locations**: 
- Line 1514 (Coordinate colors)
- Line 1566 (Metadata colors)
- Line 1607 (Background colors)
- Line 1719 (Recording path colors)
- Line 1898 (Camera label colors)
- PathsTab color selection

**Count**: 15+ instances across the app

---

### 4. Label Creation Pattern (Repeated 25+ times)

**Current inline implementation**:
```python
label = QLabel("text")
label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
```

**OR**:
```python
value_label = QLabel(str(value))
value_label.setStyleSheet("font-size: 12px; color: #007AFF; font-weight: bold; min-width: 35px; border: none;")
```

**Recommendation**: Extract to helper functions:
- `create_section_label(text, min_width=80)` - grey label
- `create_value_label(text, min_width=35)` - blue value display label
- `create_generic_label(text, font_size=12, color="#333", min_width=None)` - generic

**Count**: 25+ instances

---

### 5. HBox Layout with Label Pattern (Repeated 20+ times)

**Current inline implementation**:
```python
layout = QHBoxLayout()
label = QLabel("Label:")
label.setStyleSheet("font-size: 12px; color: #333; min-width: 80px; border: none;")
layout.addWidget(label)
# ... add widget(s) ...
layout.addStretch()
parent_layout.addLayout(layout)
```

**Recommendation**: Extract to `create_labelled_row(label_text, widget, parent_layout, stretch=True, label_width=80)`

**Count**: 20+ instances

---

### 6. Button State Update Pattern (Repeated 4+ times)

**Current inline implementation** (in PathsTab):
```python
for c, btn in self.color_buttons.items():
    is_selected = (c == selected_color)
    text_color = '#000000' if c in ['YELLOW', 'CYAN'] else '#FFFFFF'
    btn.setStyleSheet(get_button_stylesheet(color_map[c], text_color, is_selected))
```

**Recommendation**: Extract to `update_button_selection(buttons_dict, selected_key)`

**Locations**: Lines 2123, 2157, 2180, 2218, 2254, 2305

---

### 7. Layout Clear/Refresh Pattern (Repeated 4+ times)

**Current inline implementation**:
```python
while self.layout.count():
    child = self.layout.takeAt(0)
    if child.widget():
        child.widget().deleteLater()
self.data_list.clear()
```

**Recommendation**: Extract to `clear_layout(layout)` utility function

**Locations**: PathsTab refresh paths, CamTab camera updates

---

### 8. Database Query Pattern (Repeated 3+ times in PathsTab)

**Current inline implementation**:
```python
cursor = self.db.connection.cursor()
cursor.execute("SELECT col1, col2 FROM table WHERE condition")
row = cursor.fetchone()
if row:
    value = row['col_name']
```

**Recommendation**: Already have PathDatabase methods, but ensure consistent usage

**Note**: Better to use PathDatabase methods rather than raw SQL

---

### 9. Config Load with Try/Except (Repeated 15+ times)

**Current inline implementation**:
```python
try:
    value = int(self.config.get('section', 'key', fallback='default'))
except:
    value = default_value
```

**Current flow**:
1. App startup (line 2948): `config_file = os.path.expanduser("~/Projects/seeboard/see_board.cfg")`
2. Load config: `self.config.read(config_file)` 
3. Create sections if missing (lines 2950-2951)
4. Pass `self.config` to all tabs in `__init__`
5. Each tab loads values individually with try/except pattern

**Recommendation**: Create centralized config loader utility:
```python
# config_loader.py
class ConfigLoader:
    def __init__(self, config):
        self.config = config
    
    def get_int(self, section, key, default=0):
        """Load integer config value with fallback"""
        try:
            return int(self.config.get(section, key, fallback=str(default)))
        except (ValueError, TypeError):
            return default
    
    def get_str(self, section, key, default=''):
        """Load string config value"""
        return self.config.get(section, key, fallback=default)
    
    def get_bool(self, section, key, default=False):
        """Load boolean config value"""
        return self.config.getboolean(section, key, fallback=default)
    
    def save(self, section, key, value):
        """Save config value to file"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        config_file = os.path.expanduser("~/Projects/seeboard/see_board.cfg")
        with open(config_file, 'w') as f:
            self.config.write(f)
```

**Usage**:
```python
# In tab __init__
self.loader = ConfigLoader(config)
coord_color = self.loader.get_str('gps', 'coord_color', 'lime')
position_radius = self.loader.get_int('map', 'position_radius', 2)
```

**Benefits**:
- Single place to define all config logic
- Consistent error handling
- Easy to add schema validation
- Can add type hints for type safety

**Count**: 15+ instances with similar pattern

---

### 10. Toggle Button Group Pattern (Repeated 2+ times)

**Current inline implementation** (Time buttons, Rotation buttons):
```python
for option_str in options:
    btn = QPushButton(option_str)
    is_selected = option_str == saved_option
    btn.setStyleSheet(get_button_stylesheet("#2196F3", "white", is_selected))
    btn.setCheckable(True)
    btn.setChecked(is_selected)
    btn.clicked.connect(lambda checked, o=option_str: self.on_option_selected(o))
    self.buttons_dict[option_str] = btn
    layout.addWidget(btn)
```

**Recommendation**: Extract to `create_toggle_button_group(options, saved_selection, callback, layout, color="#2196F3")`

**Locations**: Time sampling buttons, Camera rotation buttons

---

## Candidates for Refactoring

### Critical Priority (Repeated 15+ times)
1. **Label creation** - 25+ instances
   - `create_section_label()`, `create_value_label()`, `create_generic_label()`
   
2. **HBox with label** - 20+ instances
   - `create_labelled_row()`

3. **Color button loop** - 15+ instances
   - `create_color_button_grid()`

4. **Config int loading** - 15+ instances
   - `load_config_int()`, `load_config_str()`, `load_config_bool()`

### High Priority (Repeated 10+ times)
1. **Slider creation** - 10+ instances
   - `create_slider()`, `create_slider_with_label()`

2. **Slider + label + value** - 10+ instances
   - `add_slider_to_layout()`

### Medium Priority (Repeated 4-9 times)
1. **Button state update** - 4+ instances
   - `update_button_selection()`

2. **Layout clear/refresh** - 4+ instances
   - `clear_layout()`

3. **Toggle button group** - 2+ instances
   - `create_toggle_button_group()`

### Estimated Code Reduction
- **Labels**: 25 × 5 lines = 125 lines → 1 function call per instance
- **HBox rows**: 20 × 8 lines = 160 lines → 1 function call per instance
- **Color buttons**: 15 × 12 lines = 180 lines → 1 function call per instance
- **Sliders**: 10 × 10 lines = 100 lines → 1 function call per instance
- **Total potential reduction**: ~550 lines of boilerplate code

---

## Last Updated
2026-08-22 11:28 UTC


---

## Implementation Milestones

### ✅ ConfigLoader (2026-08-22 11:42 UTC)
- Centralized config management - eliminated ~30 lines of boilerplate
- Safe integer/string/boolean loading with defaults
- Automatic config file persistence
- **Impact**: All config access now consistent, typesafe, with single source of truth

### ✅ Visible Paths on Map (2026-08-22 11:51 UTC)
- Added `get_visible_paths()` method to MapTab
- Modified MapRenderer to render multiple recorded paths
- Each path displays with stored color and line width
- Visibility state toggleable from PathsTab checkboxes
- Current recording path renders on top of historical paths
- **Impact**: Users can visualize previous paths on map for reference while recording
