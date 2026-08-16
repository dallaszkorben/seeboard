# seeBoard Documentation

Complete documentation for the seeBoard GPS + multi-camera system for Raspberry Pi.

## Quick Navigation

### For First-Time Users

1. **Start here**: [`seeboard.md`](seeboard.md) — Main project overview, hardware setup, and architecture
2. **GPS Setup**: [`GPS_FLASHING_QUICK_REFERENCE.md`](GPS_FLASHING_QUICK_REFERENCE.md) — Flash the ESP8266 GPS unit
3. **Read GPS from Desktop**: [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) — Access GPS data from your machine
4. **ESP32-CAM Setup**: [`esp32-cam.md`](esp32-cam.md) — Flash and configure cameras

### Documentation by Topic

#### GPS System

| Document | Purpose |
|----------|---------|
| [`esp8266_gps_unit.md`](esp8266_gps_unit.md) | Complete GPS unit documentation (hardware, firmware, architecture, troubleshooting) |
| [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) | **NEW:** How to read GPS values from your desktop (browser, Python, dashboard) |
| [`GPS_FLASHING_QUICK_REFERENCE.md`](GPS_FLASHING_QUICK_REFERENCE.md) | Quick reference for flashing ESP8266 firmware |
| [`GPS_CONSOLE.md`](gps_console.md) | Legacy: Console-based GPS testing (POC) |

#### Camera System

| Document | Purpose |
|----------|---------|
| [`esp32-cam.md`](esp32-cam.md) | ESP32-CAM firmware, WiFi, MJPEG streaming |
| [`camera.md`](camera.md) | Legacy: Camera stream viewer POC |

#### Main Application

| Document | Purpose |
|----------|---------|
| [`seeboard.md`](seeboard.md) | Main seeBoard app: overview, UI, hardware wiring, features |

#### Other

| Document | Purpose |
|----------|---------|
| [`esp8266_gps_unit.md`](esp8266_gps_unit.md) | Detailed GPS unit documentation |
| [`gps_gui.md`](gps_gui.md) | Legacy: GPS GUI POC |
| [`old_gps_gui.md`](old_gps_gui.md) | Legacy: Old GPS GUI reference |

## What You Can Do With seeBoard

### View GPS Position
- **Browser:** Open `http://esp8266-gps.local/gps` in your browser
- **Dashboard:** Open `gps_dashboard.html` for a beautiful UI with auto-refresh
- **Command-line:** Use `gps_client.py` to read GPS data programmatically

### View Live Camera Streams
- Open CAM view in seeBoard app (shows multi-camera grid)
- Connect directly to camera: `http://esp32-cam.local:81/stream`

### Display on Offline Map
- MAP view in seeBoard shows your position on pre-downloaded OpenStreetMap tiles
- No internet required (tiles stored locally in 148 MB SQLite database)

### Record Routes & Waypoints
- Future feature: Save GPS tracks to SQLite database

## File Structure

```
seeboard/
├── docs/                          ← You are here
│   ├── README.md                  ← Navigation guide (this file)
│   ├── seeboard.md                ← Main app documentation
│   ├── esp8266_gps_unit.md        ← GPS unit details
│   ├── GPS_READING_FROM_DESKTOP.md ← How to read GPS values ⭐ NEW
│   ├── GPS_FLASHING_QUICK_REFERENCE.md
│   ├── esp32-cam.md
│   ├── esp8266_gps_unit.md
│   └── ... (other docs)
│
├── app/                           ← Main Python app
│   ├── seeboard.py
│   ├── gps_core.py
│   ├── cam_discovery.py
│   └── views/
│
├── firmware/                      ← ESP32-CAM firmware
│   └── esp32-cam/
│
├── esp8266-gps/                   ← ESP8266 GPS unit firmware
│   └── src/main.cpp
│
├── gps_client.py                  ← Read GPS from desktop (CLI tool)
├── gps_dashboard.html             ← Read GPS from desktop (Web UI)
└── see_board.cfg                  ← Configuration file
```

## Common Tasks

### "I want to see GPS coordinates on my desktop"

**3 options (pick one):**

1. **Browser (easiest):**
   ```
   http://esp8266-gps.local/gps
   ```

2. **Beautiful dashboard (recommended):**
   ```
   file:///home/akoel/Projects/boat/general/Code/seeboard/gps_dashboard.html
   ```

3. **Command-line tool:**
   ```bash
   python3 gps_client.py --host esp8266-gps.local --watch
   ```

👉 See [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) for details

### "I want to flash the GPS unit"

1. Read: [`GPS_FLASHING_QUICK_REFERENCE.md`](GPS_FLASHING_QUICK_REFERENCE.md)
2. For details: [`esp8266_gps_unit.md`](esp8266_gps_unit.md) → Setup Instructions section

### "The GPS unit won't connect to WiFi"

1. Check: [`GPS_FLASHING_QUICK_REFERENCE.md`](GPS_FLASHING_QUICK_REFERENCE.md) → Troubleshooting
2. Full troubleshooting: [`esp8266_gps_unit.md`](esp8266_gps_unit.md) → Troubleshooting section
3. Connection issues: [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Troubleshooting

### "I can't find the GPS unit on the network"

👉 See [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Finding the GPS Unit section

### "I want to integrate GPS data into my own app"

1. Python: See [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Method 3: Python Client
2. Shell script example: See [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Integration Examples
3. Node.js example: Same section

### "I want to set up the seeBoard app on the Pi"

1. Start: [`seeboard.md`](seeboard.md) → Running section
2. Full setup: [`seeboard.md`](seeboard.md) → Raspberry Pi Setup section

### "I want to understand the whole system"

1. Architecture: [`seeboard.md`](seeboard.md) → Overview section
2. GPS details: [`esp8266_gps_unit.md`](esp8266_gps_unit.md) → Architecture section
3. Camera system: [`esp32-cam.md`](esp32-cam.md) → Architecture section

## Key Concepts

### GPS Data Format
All GPS endpoints return JSON with this structure:
```json
{
  "lat": 56.171898,
  "lng": 15.585782,
  "satellites": 6,
  "hdop": 191.00,
  "date": "2026-08-16",
  "time": "07:37:10",
  "fix": 1
}
```

See [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → GPS Data Format for field definitions

### Network Architecture
```
Raspberry Pi (10.42.0.1, GREEN-BEAN hotspot)
    ├── GPS Unit (10.42.0.98, mDNS: esp8266-gps.local)
    ├── Camera #1 (10.42.0.x, mDNS: esp32-cam-XXYY.local)
    ├── Camera #2 (10.42.0.x, mDNS: esp32-cam-AABB.local)
    └── Your Desktop (10.42.0.x, can read all services)
```

### GPS Quality

| Satellites | Status | Accuracy |
|------------|--------|----------|
| 0-3 | Acquiring | No lock yet |
| 4-6 | Weak | ~30-50m error |
| 7-10 | Good | ~5-15m error |
| 10+ | Excellent | ~1-5m error |

For more detail, see [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Quality Indicators

## Tools & Scripts

### GPS Client (`gps_client.py`)
Command-line tool to discover and read GPS data.

**Quick start:**
```bash
cd ~/Projects/boat/general/Code/seeboard
python3 gps_client.py --host esp8266-gps.local --watch
```

See [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Method 3 for full usage

### GPS Dashboard (`gps_dashboard.html`)
Beautiful web UI to view GPS data in real-time.

**Quick start:**
```bash
file:///home/akoel/Projects/boat/general/Code/seeboard/gps_dashboard.html
```

See [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Method 2 for full details

## Troubleshooting Quick Links

**GPS not found?** → [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Troubleshooting → "No GPS units found"

**Connection refused?** → [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Troubleshooting → "Connection refused"

**No GPS fix yet?** → [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Troubleshooting → "No GPS fix"

**mDNS not resolving?** → [`GPS_READING_FROM_DESKTOP.md`](GPS_READING_FROM_DESKTOP.md) → Troubleshooting → "mDNS not resolving"

**Flashing failed?** → [`GPS_FLASHING_QUICK_REFERENCE.md`](GPS_FLASHING_QUICK_REFERENCE.md) → Troubleshooting

**General GPS issues?** → [`esp8266_gps_unit.md`](esp8266_gps_unit.md) → Troubleshooting

## New Features (Recently Added)

### 🆕 GPS_READING_FROM_DESKTOP.md
Comprehensive guide on how to read GPS values from your desktop machine in three ways:
1. **Browser** — Direct HTTP access (simplest)
2. **Dashboard** — Beautiful web UI with auto-refresh (recommended)
3. **Python client** — Command-line tool for automation

This is the main document if you're trying to access GPS data from outside the Raspberry Pi.

### 🆕 gps_client.py
Python CLI tool to discover and read GPS data from the network. Supports:
- Auto-discovery via mDNS
- Direct IP/hostname connection
- Continuous monitoring
- Custom polling intervals
- Integration into other scripts

### 🆕 gps_dashboard.html
HTML5 dashboard with:
- Real-time GPS display
- Live status indicator
- Signal quality visualization
- Google Maps integration
- Auto-refresh with configurable intervals

## Document History

| Document | Version | Last Updated | Status |
|----------|---------|--------------|--------|
| seeboard.md | Latest | 2026-07-26 | Complete |
| esp8266_gps_unit.md | Latest | 2026-07-26 | Complete |
| GPS_FLASHING_QUICK_REFERENCE.md | 1.0 | 2026-07-26 | Complete |
| **GPS_READING_FROM_DESKTOP.md** | **1.0** | **2026-08-16** | **🆕 NEW** |
| esp32-cam.md | Latest | 2026-07-26 | Complete |

## Getting Help

1. **Quick answer?** → Check this README or the relevant document in the Quick Navigation section
2. **Detailed help?** → Use the "Troubleshooting" section of the relevant document
3. **General question?** → Check the FAQ at the end of the relevant document
4. **Not documented?** → Create an issue or check the project repository

## Contributing

To improve documentation:
1. Check the relevant document in `docs/` folder
2. Make updates or additions
3. Test your changes
4. Update the table of contents if needed
5. Commit with clear message: "docs: improve X documentation"

---

**Happy sailing!** ⛵

*Last updated: 2026-08-16*
