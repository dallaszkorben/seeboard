# seeBoard Development Notes

## ⚠️ CRITICAL: GIT WORKFLOW POLICY

**DO NOT TOUCH THE GIT REPOSITORY.** 

You should not make any `git` commands including:
- `git add`
- `git commit`
- `git push`
- `git mv`
- Any other git operations

**Why:** This is YOUR repository. Only YOU should manage git history and remote pushes. Automated git operations can cause:
- Unwanted commits in your history
- Accidental pushes that you didn't review
- Loss of control over what gets committed
- Conflicts with your own git workflow

**What to do instead:**
1. Make code/documentation changes
2. You manually review the changes
3. You manually run `git add`, `git commit`, `git push`

This ensures you maintain full control over your repository and commit history.

---

## Critical Implementation Solutions

### 1. Collapsible Sections with Instant Layout Updates

**Problem:** When collapsing sections in CONF tab, the layout would show empty space for several seconds before recalculating. The header would jump to the middle of the empty space.

**Root Cause:** 
- `setVisible(False)` doesn't immediately recalculate layout - Qt keeps the space reserved
- Scroll area has cached size calculations that don't update automatically
- Simple `layout().update()` calls are insufficient

**Solution:** Use `setMaximumHeight()` combined with aggressive parent chain updates
```python
def toggle_collapse(self):
    self.is_collapsed = not self.is_collapsed
    
    # Force content to collapse
    if self.is_collapsed:
        self.content_widget.setMaximumHeight(0)
    else:
        self.content_widget.setMaximumHeight(16777215)  # Qt max height
    
    # Propagate updates up entire parent chain
    self.layout().update()
    self.updateGeometry()
    
    parent = self.parent()
    while parent:
        if hasattr(parent, 'layout') and parent.layout():
            parent.layout().update()
        if hasattr(parent, 'updateGeometry'):
            parent.updateGeometry()
        if hasattr(parent, 'update'):
            parent.update()
        parent = parent.parent()
```

**Key Points:**
- `setMaximumHeight(0)` hides and removes from layout space immediately
- `updateGeometry()` forces size recalculation
- Parent chain propagation ensures scroll area knows about changes
- Must call both `update()` and `updateGeometry()` on parents

---

### 2. QSlider Handle Styling on Framebuffer

**Problem:** Framebuffer rendering doesn't support CSS `border-radius` on slider handles, leaving them square instead of round.

**Attempted Solutions (FAILED):**
- `border-radius: 10px` - ignored by framebuffer
- `border-radius: 50%` - ignored
- `qradialgradient()` - ignored
- Custom paintEvent with `drawEllipse()` - requires non-existent API methods

**Working Solution:** Use default native Qt slider handles
- Remove ALL custom stylesheet from QSlider
- Let Qt render native handles (which are round by default)
- Don't try to customize slider handles on framebuffer

**Code:**
```python
self.slider = QSlider(Qt.Horizontal)
# NO stylesheets for the handle itself
# Qt will render native round handles
```

**Lesson:** Framebuffer has severe stylesheet limitations. When visual customization fails, accept native rendering instead.

---

### 3. Tab Names Configuration

**Pattern:** Store tab names in a class-level dictionary instead of hardcoding them throughout the code.

**Implementation:**
```python
class SeeBoardApp(QMainWindow):
    TAB_NAMES = {
        'coords': 'GPS',
        'map': 'MAP',
        'cam': 'CAM',
        'conf': 'CONF'
    }
    
    def __init__(self):
        # Use via:
        self.tabs.addTab(self.coords_tab, self.TAB_NAMES['coords'])
```

**Benefit:** Single location to change all tab names - no grepping/replacing needed.

---

### 4. Collapsible Section Structure (GPS = Parent Section)

**Design Decision:** GPS section contains all GPS-related subsections
- GPS (collapsible parent)
  - Show DMS Decimals
  - Coordinates (Font Size, Color)
  - Metadata (Font Size, Color)
  - Background (Color, Brightness)
- Map (collapsible)
- Camera (collapsible)

**Why:** Logical grouping. Collapsing GPS collapses all display-related settings together. Makes mobile UI cleaner.

**Implementation:** Use `CollapsibleSection` class with nested `add_to_layout()` and `add_layout()` methods.

---

### 5. CollapsibleSection Class Design

**Requirements:**
- Entire header clickable (not just icon) - important for boat use where finger coordination is difficult
- Arrow indicator shows state (▼ expanded, ▶ collapsed)
- Content area clearly separated (white background, border)
- Large touch targets (12px padding on header)

**Key Features:**
- No animation (instant collapse for responsiveness)
- Header uses blue (#007AFF) to match Apple-style UI
- Content widget styling separate from header
- Methods: `add_to_layout(layout)` and `add_to_layout(widget)` for flexible content

---

### 6. PyQt5 Layout Rebuilding - Element Ordering is Critical

**Problem:** When you rebuild a collapsible section or layout dynamically (e.g., in `on_tab_shown()`), elements get deleted via `takeAt()` and must be re-added. If you forget permanent elements during rebuild, they disappear (not "covered").

**The Mistake:**
```python
# initUI() - builds layout once
def initUI(self):
    camera_section = CollapsibleSection("Camera")
    camera_section.add_layout(grace_period_layout)      # Add FIRST
    camera_section.add_layout(camera_buttons_layout)    # Add SECOND

# on_tab_shown() - rebuilds layout every tab switch
def on_tab_shown(self):
    # Clear everything
    while camera_section.content_layout.count():
        item = camera_section.content_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    
    # Re-add cameras - BUT FORGET GRACE PERIOD!
    for camera in cameras:
        camera_section.add_layout(camera_buttons_layout)
    # ❌ Grace period disappeared! (not covered, just deleted)
```

**The Solution:**
Maintain identical element ordering in both `initUI()` and `on_tab_shown()`. Always re-add permanent/static elements FIRST:

```python
def on_tab_shown(self):
    # Clear everything
    while camera_section.content_layout.count():
        item = camera_section.content_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    
    # Re-add grace period FIRST (matching initUI order)
    camera_section.add_layout(grace_period_layout)
    
    # Then add dynamic cameras
    for camera in cameras:
        camera_section.add_layout(camera_buttons_layout)
    # ✅ Grace period visible at top, cameras below
```

**Key Insights:**
- QVBoxLayout renders items top-to-bottom in the exact order they're added
- Missing elements don't get "covered" - they simply don't exist
- Element ordering MUST be identical in `initUI()` and rebuild methods
- Layout manager handles all spacing automatically - don't use tricks like `setMinimumHeight()`
- Always add permanent elements first, then dynamic/changing elements

**Debugging Tip:** If an element "disappears" after tab switch, check if `on_tab_shown()` is forgetting to re-add it.

---

## UI Design Standards

### Colors
- Primary Blue: `#007AFF` (Apple iOS style)
- Hover Blue: `#0051d5` (darker)
- Pressed Blue: `#003d9e` (even darker)
- Background: `#f5f5f5` (light gray)
- Text: `#333` (dark gray)
- Label: `#555` (medium gray)
- Border: `#ddd` (light gray)

### Button Styling (Apple Style)
```python
QPushButton {
    background-color: [color];
    color: [text_color];
    font-size: 10px;
    font-weight: bold;
    padding: 8px 12px;
    border: 4px solid #007AFF;      # Selected
    border-radius: 6px;
    min-width: 50px;
}
QPushButton:hover {
    border: 3px solid #007AFF;
}
QPushButton:pressed {
    border: 4px solid #0051d5;
}
```

### Section Headers (Collapsible)
- Blue background (#007AFF)
- White text, bold, 12px
- 12px padding
- 6px border-radius
- Full-width clickable area
- Arrow indicator

---

## Important Framebuffer Limitations

1. **CSS border-radius:** Doesn't work on most widgets. Workaround: Use native rendering or accept square appearance.

2. **Stylesheet animations:** Not supported. All changes must be instant.

3. **Complex gradients:** `qradialgradient()` may not render. Use solid colors instead.

4. **SVG/Icons:** Limited support. Use Unicode arrows (▼, ▶, etc.) instead.

5. **Layout performance:** Heavy reliance on explicit `update()`, `updateGeometry()`, and parent chain propagation.

---

## Config File Structure

**Location:** `~/Projects/seeboard/see_board.cfg`

**Sections:**
```ini
[gps]
show_dms_decimals = False
coord_font_size = 65
coord_color = lime
meta_font_size = 12
meta_color = white

[coords]
bg_color = black
bg_brightness = 0

[camera_rotations]
esp32-cam-a1b2.local = 0
esp32-cam-c3d4.local = 90

[route_recording]
enabled = False
```

**Auto-save:** All changes to CONF tab immediately write to config file via `save_config()` method.

---

## Performance Optimization Tips

1. **Slider styling:** Never use custom handles on framebuffer. Use native.

2. **Layout updates:** Always propagate up parent chain when visibility changes.

3. **Scroll areas:** Force `updateGeometry()` on scroll widget itself, not just children.

4. **Collapsing content:** Use `setMaximumHeight(0)` instead of `setVisible(False)`.

5. **Background colors:** Use palette method (`setPalette()`) instead of stylesheet for main tab backgrounds.

---

## Future Enhancements

- [ ] Route visualization on MAP tab
- [ ] Performance optimization for 3 MJPEG streams
- [ ] Outdoor brightness testing
- [ ] Additional GPS data fields
- [ ] Gesture support for mobile usability

---

## Running the Application on Raspberry Pi

### Installation

The application is installed at `/home/pi/Projects/seeboard` on the Raspberry Pi. For complete installation instructions, see `INSTALLATION_PYQT5.md`.

**Quick setup (if not already done):**
```bash
# Deploy code to RP
rsync -avz --delete ~/Projects/boat/general/Code/seeboard/ pi@10.42.0.1:~/Projects/seeboard/ \
  --exclude=.git --exclude=__pycache__ --exclude=*.pyc

# Create virtual environment
ssh pi@10.42.0.1
cd /home/pi/Projects/seeboard
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
sudo apt-get install -y python3-pyqt5
pip install pyserial==3.5 pynmea2==1.19.0 zeroconf==0.132.0 py-staticmaps==0.5.0
```

### Running the Application

**Via launcher script (recommended):**
```bash
ssh pi@10.42.0.1
cd /home/pi/Projects/seeboard
./seeboard_pyqt5.sh
```

**Manually (for debugging):**
```bash
ssh pi@10.42.0.1
cd /home/pi/Projects/seeboard
source venv/bin/activate
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/lib/python3.11/dist-packages:$PYTHONPATH"
python3 app/seeboard_pyqt5.py
```

**On the Raspberry Pi touchscreen directly:**
1. Connect to the Pi's display/touchscreen
2. Open a terminal
3. Run: `cd /home/pi/Projects/seeboard && ./seeboard_pyqt5.sh`

### Configuration

Configuration file: `~/.seeboard/see_board.cfg`

Copy from development machine if needed:
```bash
scp ~/Projects/boat/general/Code/seeboard/home/pi/.seeboard/see_board.cfg \
  pi@10.42.0.1:~/.seeboard/see_board.cfg
```

### Architecture on RP

```
Raspberry Pi (WiFi AP: GREEN-BEAN at 10.42.0.1)
├── seeBoard PyQt5 app (seeboard_pyqt5.py)
├── GPS module (NEO-7M via /dev/serial0)
├── Camera discovery (mDNS auto-discovery)
└── WiFi clients:
    ├── ESP32-CAM #1 (esp32-cam-*.local)
    ├── ESP32-CAM #2 (esp32-cam-*.local)
    └── ...
```

### Views Available

| Tab    | Function                                      |
|--------|-----------------------------------------------|
| COORDS | GPS coordinates (DMS), time, satellite count  |
| MAP    | Offline map with position and recorded route  |
| CAM    | Multi-camera grid (MJPEG streaming)           |
| CONF   | Settings (DMS format, rotations, etc.)        |

### Troubleshooting

- **PyQt5 not found:** Ensure `PYTHONPATH` is set (launcher script handles this)
- **GPS not detecting:** Check UART enabled: `ls -la /dev/serial0`
- **Cameras not appearing:** Verify they're on GREEN-BEAN hotspot and mDNS discoverable
- **App crashes/hangs:** Check disk space (`df -h`) and review system logs

See `INSTALLATION_PYQT5.md` for detailed troubleshooting.

---

**Last Updated:** 2026-08-22
**Framebuffer Platform:** Raspberry Pi 5" touchscreen (linuxfb)
**PyQt5 Version:** 5.15+
**Application Status:** Active (PyQt5-based)
**Launcher:** `seeboard_pyqt5.sh`
