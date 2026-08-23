# seeBoard Path Recording Rules

## 1. BUTTON LAYOUT & STATES

- Both RECORD and STOP buttons stretch horizontally (fill available width)
- RECORD button: starts active (green), becomes inactive (grayed out) when clicked
- STOP button: starts inactive (grayed out), becomes active (red) when RECORD clicked
- Toggle behavior: clicking one activates the other and deactivates itself
- Button styling: RECORD = green (#00AA00), STOP = red (#AA0000)
- Buttons are located at the bottom of the map view
- Minimum height: 45 pixels for touch screen usability

## 2. RECORDING MECHANISM

- Recording is TIME-BASED (not distance-based)
- Time interval configured in `[map]` section: `time_based_sampling` (default: 15s)
- When RECORD clicked:
  - Start recording GPS points at configured time intervals
  - Record the FIRST position IMMEDIATELY (don't wait for first interval)
  - Path name auto-generated as: `YYYY-mm-ddTHH:MM:SS` (exact timestamp)
  - Each recording stored in database as a new path
  - Timer triggers at regular intervals to record subsequent points
- When STOP clicked or app closes: save the recording to database
- Recording state: `is_recording = True` during recording, `False` when stopped
- Timer precision: use QTimer with interval in milliseconds

## 3. MAP DISPLAY DURING RECORDING

- Each recorded GPS point shown as FILLED CIRCLE
- Circle radius: from config `[map]` > `position_radius` (default: 7 pixels)
- Circle color: from config `[route_recording]` > `point_color` (default: red)
- Circle outline: BLACK with 1-pixel width
- Circles connected by LINES between consecutive points:
  - Inner line width: from config `[route_recording]` > `line_width` (default: 3)
  - Inner line color: from config `[route_recording]` > `line_color` (default: RED)
  - Outer border: BLACK line (width = inner_width + 2 for bordered effect)
  - Border creates outline effect around the colored line
- Each circle displays SEQUENCE NUMBER inside:
  - Numbering starts at 1 for first recorded position
  - Numbers increment (2, 3, 4, etc.) with each new recorded point
  - Font: default PIL font (small enough to fit in circle)
  - Text color: WHITE for dark circles, BLACK for light circles (auto-selected)
- Points update in REAL-TIME as GPS data arrives (not after STOP)
- Recording points stored locally: `current_recording_points = [(lat, lon), ...]`

## 4. AFTER RECORDING STOPS

- Recorded path is SAVED to database:
  - `paths` table: `path_id`, `name` (timestamp), `color`, `is_recording=0`, `stopped_at`
  - `path_points` table: all recorded GPS points with sequence numbers
- Path is NOT shown on map by default (`is_visible = 0` in database)
- Path only appears on map if user checks it in PATHS tab to make it visible
- Recording circles and lines DISAPPEAR from map when STOP is clicked
- Map re-renders to show only visible paths (those checked in PATHS tab)
- If app closes/crashes: current recording is saved (not lost)
- Button states reset: RECORD active (green), STOP inactive (grayed out)

## 5. WATER DROPLET GPS MARKER

- GPS marker is a water droplet shape (professional SVG-based)
- Rotated 180 degrees so sharp POINT is at BOTTOM
- Bottom point coordinates EXACTLY at GPS position
- Droplet scale: 1.5 (relative to base size)
- Color: RED (#FF0000) with BLACK outline (#000000)
- Inner line: WHITE (#FFFFFF) for visual definition
- Label: "GPS" text displayed above the droplet
- Position accuracy: sharp point points directly to actual GPS location

## 6. SAVED PATHS DISPLAY (from PATHS Tab)

- Saved paths drawn ONLY when checked in PATHS tab (`is_visible = 1`)
- Each path uses its STORED COLOR from database (not hardcoded)
- Line width for saved paths: 2 pixels (fixed, separate from recording)
- Line style: bordered effect (black outer line + colored inner line)
- Saved paths do NOT show sequence numbers (only recording does)
- Multiple paths can be visible simultaneously, each with different color
- Path colors configured per recording, not globally

## 7. DATABASE STRUCTURE

### paths table
- `path_id`: unique identifier (auto-increment)
- `name`: `YYYY-mm-ddTHH:MM:SS` (timestamp, unique)
- `color`: path color (e.g., RED, BLUE, YELLOW, MAGENTA)
- `is_visible`: 0 (hidden by default) or 1 (shown when checked)
- `is_recording`: 0 (stopped) or 1 (currently recording)
- `created_at`: auto-timestamp when recording starts
- `stopped_at`: timestamp when recording stops

### path_points table
- `point_id`: unique identifier
- `path_id`: foreign key to paths
- `latitude`, `longitude`: GPS coordinates
- `timestamp`: when point was recorded
- `sequence`: point order number (1, 2, 3, ...)

## 8. CONFIGURATION SETTINGS

```ini
[map]
time_based_sampling = 15s          # Recording interval (e.g., "15s", "10s")
position_radius = 7                # Recorded point circle radius (pixels)

[route_recording]
line_color = RED                   # Recording line color
line_width = 3                     # Recording line width (pixels)
point_color = red                  # Recording point circle color
point_diameter = 8                 # Recording point circle diameter (pixels)
```

## 9. ERROR HANDLING

- Timer starts only if database initialized successfully
- Invalid GPS positions ignored (None, 0, or invalid coordinates)
- Recording continues even if GPS signal lost (last known position preserved)
- Database errors logged but don't stop recording
- Circle drawing errors caught and skipped (app continues)
- Text rendering fallback if font unavailable

## 10. USER WORKFLOW

### Step 1: User clicks RECORD button
- Path starts recording with first GPS position immediately
- Buttons toggle (RECORD disabled, STOP enabled)
- Circle #1 appears on map at current location

### Step 2: GPS points recorded at time intervals (e.g., every 15 seconds)
- New circle appears with next sequence number
- Circle connected to previous with bordered line
- All changes visible in real-time on map

### Step 3: User clicks STOP button
- Recording stops, recording circles disappear
- Path saved to database with `is_visible = 0`
- Buttons toggle back (RECORD enabled, STOP disabled)
- Map re-renders without recording overlay

### Step 4: User opens PATHS tab
- New recording appears in the list
- User checks checkbox to make path visible
- Path appears on map with stored color and 2px width
- User can change path color or rename from PATHS tab
