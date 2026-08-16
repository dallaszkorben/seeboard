# Reading GPS Values from Desktop Machine

## Overview

The ESP8266 GPS unit broadcasts its data over the local WiFi network as JSON via HTTP. This document explains how to read GPS data from your desktop machine in multiple ways.

## Quick Start (3 Steps)

### 1. Connect to GREEN-BEAN WiFi
Your desktop must be on the same WiFi network as the ESP8266 GPS unit.

**SSID:** GREEN-BEAN  
**Password:** (none - open network)  
**IP Range:** 10.42.0.x

### 2. Open in Browser (Easiest)
Simply open this URL in any web browser:

```
http://esp8266-gps.local/gps
```

Or use the IP directly:

```
http://10.42.0.98/gps
```

You'll see raw JSON like:
```json
{"lat":56.171898,"lng":15.585782,"satellites":6,"hdop":191.00,"date":"2026-08-16","time":"07:37:10","fix":1}
```

### 3. Use the Dashboard (Prettier)
Open the HTML dashboard in your browser:

```
file:///home/akoel/Projects/boat/general/Code/seeboard/gps_dashboard.html
```

Or serve it locally:
```bash
cd ~/Projects/boat/general/Code/seeboard
python3 -m http.server 8000
```

Then visit: `http://localhost:8000/gps_dashboard.html`

---

## Three Ways to Read GPS Data

### Method 1: Web Browser (Direct Access)

**Simplest, no setup required.**

#### Option A: Hostname (mDNS)
```
http://esp8266-gps.local/gps
```

**Requirements:**
- mDNS/Bonjour support (usually built-in on macOS/Linux)
- On Windows: Install Bonjour (comes with iTunes, or standalone)

#### Option B: Direct IP
```
http://10.42.0.98/gps
```

**Requirements:** None (always works if unit has fixed IP)

#### What You See
Raw JSON response:
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

**To make it prettier:**
- Install a browser JSON formatter extension (e.g., "JSON Viewer" for Chrome/Firefox)
- Or use the dashboard (Method 2)

---

### Method 2: Beautiful Dashboard (Recommended)

**Interactive, real-time updates, auto-refresh.**

#### Setup
The dashboard file is already created:
```
~/Projects/boat/general/Code/seeboard/gps_dashboard.html
```

#### Usage Option A: Local File
Simply open in your browser:
```
file:///home/akoel/Projects/boat/general/Code/seeboard/gps_dashboard.html
```

#### Usage Option B: HTTP Server
Serve the file locally and access from any device on your network:

```bash
cd ~/Projects/boat/general/Code/seeboard
python3 -m http.server 8000
```

Then open: `http://localhost:8000/gps_dashboard.html`

Or from another device on GREEN-BEAN WiFi: `http://10.42.0.21:8000/gps_dashboard.html`

#### Dashboard Features
- 🟢 **Live status indicator** — Shows online/offline status with pulsing animation
- 🛰️ **GPS coordinates** — Latitude and longitude with 6 decimal places
- 📡 **Satellite count** — How many satellites in view
- 📊 **Signal quality** — HDOP value and visual quality bar
- ✓ **Fix status** — Whether GPS has lock or still acquiring
- 🗓️ **Date & Time** — UTC date and time from GPS receiver
- 🔄 **Manual refresh** — Click to update immediately
- ⚙️ **Auto-refresh toggle** — Enable continuous updates
- 📍 **Google Maps link** — Click to open position in Google Maps
- ⏱️ **Customizable interval** — 1-30 second update intervals

#### Screenshot
```
┌─────────────────────────────────────┐
│ 🛰️ ESP8266 GPS                     │
│ 🟢 Online                            │
├─────────────────────────────────────┤
│ [🔄 Refresh Now] [Auto: OFF]        │
│                                      │
│ Latitude:  56.171898                │
│ Longitude: 15.585782                │
│                                      │
│ Satellites: 6    Fix Status: ✓ OK   │
│ HDOP: 191.0      Quality: ████▓ 85%│
│ Date: 2026-08-16 Time: 07:37:10    │
│                                      │
│ 📍 Open in Google Maps               │
└─────────────────────────────────────┘
```

---

### Method 3: Python Client Script (Programmable)

**For automation, integration, or command-line usage.**

#### The Script
A Python client script is provided:
```
~/Projects/boat/general/Code/seeboard/gps_client.py
```

#### Setup (One-time)
Install required libraries:
```bash
pip install requests zeroconf
```

#### Usage

**Option A: Auto-discover GPS unit (simplest)**
```bash
cd ~/Projects/boat/general/Code/seeboard
python3 gps_client.py
```

Output:
```
Scanning for GPS units (3s)...

✓ Found GPS unit: esp8266-gps._gps._tcp.local.
  URL: http://10.42.0.98:80/gps
Found 1 GPS unit(s)

╔═══════════════════════════════════════╗
║ GPS Data from: 10.42.0.98              ║
╠═══════════════════════════════════════╣
║ Latitude:  56.171898                  ║
║ Longitude: 15.585782                  ║
║ Satellites: 6                         ║
║ HDOP: 191.0                           ║
║ Date: 2026-08-16                      ║
║ Time: 07:37:10                        ║
║ Fix: 1                                ║
╚═══════════════════════════════════════╝
```

**Option B: Direct connection (no discovery)**
```bash
python3 gps_client.py --host esp8266-gps.local
```

Or by IP:
```bash
python3 gps_client.py --host 10.42.0.98
```

**Option C: Continuous monitoring (watch mode)**
```bash
python3 gps_client.py --host esp8266-gps.local --watch
```

Updates every 10 seconds (press Ctrl+C to stop).

**Option D: Custom interval**
```bash
python3 gps_client.py --host esp8266-gps.local --watch --interval 2
```

Updates every 2 seconds.

**Option E: Change discovery timeout**
```bash
python3 gps_client.py --timeout 5
```

Scans for 5 seconds before giving up.

#### Usage in Your Code
Import the client into your own Python scripts:

```python
from gps_client import read_gps_direct
import json

# Read GPS data once
data = read_gps_direct('esp8266-gps.local')

# Print coordinates
if data:
    print(f"Latitude: {data['lat']}")
    print(f"Longitude: {data['lng']}")
    print(f"Satellites: {data['satellites']}")
    print(f"Date/Time: {data['date']} {data['time']}")
    print(f"Full data: {json.dumps(data, indent=2)}")
```

Or in a loop:

```python
import time
from gps_client import read_gps_direct

for i in range(10):
    print(f"\n=== Read {i+1} ===")
    data = read_gps_direct('esp8266-gps.local')
    time.sleep(2)  # Wait 2 seconds
```

#### Command-line Examples
```bash
# Show help
python3 gps_client.py --help

# Read once, auto-discover
python3 gps_client.py

# Read once, direct connection
python3 gps_client.py --host esp8266-gps.local

# Continuous reading, 5-second intervals
python3 gps_client.py --host 10.42.0.98 --watch --interval 5

# Auto-discover, then watch
python3 gps_client.py --watch
```

---

## GPS Data Format (JSON Response)

The HTTP endpoint returns this JSON structure:

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

### Field Definitions

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `lat` | float | -90 to 90 | Latitude in decimal degrees (positive = North) |
| `lng` | float | -180 to 180 | Longitude in decimal degrees (positive = East) |
| `satellites` | int | 0-32 | Number of satellites in view (higher is better) |
| `hdop` | float | 0.5-999 | Horizontal Dilution of Precision (lower is better) |
| `date` | string | YYYY-MM-DD | UTC date from GPS receiver |
| `time` | string | HH:MM:SS | UTC time from GPS receiver (24-hour) |
| `fix` | int | 0 or 1 | 0 = No fix, 1 = Fix acquired |

### Quality Indicators

**Satellites count:**
- 0-3: Acquiring, no fix yet
- 4-6: Weak fix (accuracy ~30-50m)
- 7-10: Good fix (accuracy ~5-15m)
- 10+: Excellent fix (accuracy ~1-5m)

**HDOP (Horizontal Dilution of Precision):**
- < 1: Excellent (±0.5-1.5m error)
- 1-2: Very good (±1.5-3m error)
- 2-5: Good (±3-8m error)
- 5-10: Moderate (±8-20m error)
- \> 10: Poor (±20m+ error)

**Fix status:**
- `"fix": 0` = GPS is searching for satellites (no data is valid)
- `"fix": 1` = GPS has lock (lat/lng/satellites/time are valid)

---

## Finding the GPS Unit

### Auto-Discovery (Recommended)

The GPS unit broadcasts itself via mDNS (multicast DNS), so your computer can find it automatically.

#### List all GPS units on network:
```bash
avahi-browse -rtp _gps._tcp
```

Output:
```
+;wlp4s0;IPv4;esp8266-gps;_gps._tcp;local
=;wlp4s0;IPv4;esp8266-gps;_gps._tcp;local;esp8266-gps.local;10.42.0.98;80;
```

This tells you:
- **Hostname:** `esp8266-gps.local`
- **IP:** `10.42.0.98`
- **Port:** `80`

#### Verify connectivity:
```bash
ping esp8266-gps.local
```

Output (if online):
```
PING esp8266-gps.local (10.42.0.98) 56(84) bytes of data.
64 bytes from esp8266-gps.local (10.42.0.98): icmp_seq=1 ttl=128 time=12.3 ms
```

### Manual Discovery

If auto-discovery doesn't work, find the unit by IP scan:

```bash
# Scan the GREEN-BEAN subnet (10.42.0.x)
nmap -sn 10.42.0.0/24 | grep esp

# Or check ARP table
arp -a | grep esp

# Or list DHCP leases on the Pi
cat /var/lib/misc/dnsmasq.leases
```

### Known Fixed Address

The ESP8266 GPS unit typically gets IP `10.42.0.98` from the Pi's DHCP when connected to GREEN-BEAN hotspot. This is relatively stable, but can change if:
- Another device boots first
- The unit is power-cycled
- The Pi's DHCP lease pool runs out

For reliable access, use the **hostname** (`esp8266-gps.local`) instead of IP.

---

## Troubleshooting

### "Connection refused" or "Cannot reach host"

**Problem:** Your browser/script can't connect to the GPS unit.

**Diagnosis Checklist:**

1. **Is desktop on GREEN-BEAN WiFi?**
   ```bash
   iwconfig  # or ip link show
   ```
   Should show connection to GREEN-BEAN AP. Your IP should be 10.42.0.x

2. **Is GPS unit powered on?**
   - Check for power light on ESP8266
   - Check for activity on OLED display

3. **Is GPS unit connected to WiFi?**
   - On Pi, check: `arp -a` (should show esp8266-gps or 10.42.0.98)
   - Or: `avahi-browse -rtp _gps._tcp` (should find the unit)

4. **Can you ping it?**
   ```bash
   ping esp8266-gps.local
   # or
   ping 10.42.0.98
   ```
   If timeout, unit isn't on network. Check WiFi/power.

5. **Is the HTTP server running?**
   ```bash
   curl http://esp8266-gps.local/gps
   ```
   Should return JSON. If error, try:
   - Restart GPS unit (unplug USB for 5 sec)
   - Check serial monitor on Pi for firmware errors

**Solutions:**
```bash
# Restart GPS unit completely
# (Unplug USB power, wait 5 seconds, plug back in)

# Clear WiFi cache on GPS unit
# (This usually requires re-flashing firmware)

# Force reconnection from Pi side
sudo nmcli connection down Hotspot
sudo nmcli connection up Hotspot

# Restart mDNS on desktop
sudo systemctl restart avahi-daemon  # Linux
sudo launchctl restart mdnsresponder  # macOS
```

### "No GPS fix" or coordinates show 0.000000

**Problem:** GPS is running but hasn't acquired satellite lock yet.

**This is normal behavior:**
- First-time startup (cold start): 1-5 minutes to acquire fix
- After fix already acquired (warm start): 1-2 seconds to re-lock
- Moved indoors: May not acquire at all (needs sky view)

**Fix:**
1. Move antenna outdoors or near a window
2. Wait 2-5 minutes for satellite acquisition
3. Check HDOP and satellite count (should be increasing)
4. Verify antenna is not blocked
5. Try different location (some places have worse reception)

### mDNS not resolving (hostname doesn't work)

**Problem:** `esp8266-gps.local` doesn't resolve, but direct IP `10.42.0.98` works.

**Likely causes:**
- Avahi/Bonjour not installed
- mDNS daemon not running
- Firewall blocking mDNS traffic (port 5353)

**Solutions:**

**Linux (Ubuntu/Debian):**
```bash
# Install Avahi
sudo apt update
sudo apt install avahi-daemon avahi-utils

# Restart Avahi
sudo systemctl restart avahi-daemon

# Verify it's running
sudo systemctl status avahi-daemon

# Test discovery
avahi-browse -rtp _gps._tcp
```

**macOS:**
```bash
# Should be built-in, but if not:
# Restart Bonjour
sudo launchctl stop com.apple.mDNSResponder
sudo launchctl start com.apple.mDNSResponder

# Verify discovery
dns-sd -B _gps._tcp local
```

**Windows:**
```
1. Install Bonjour from Apple (search "Bonjour Print Services")
2. Or install from: https://support.apple.com/downloads/bonjour
3. Restart computer after installation
4. Open Command Prompt
5. Try: nslookup esp8266-gps.local
```

### Dashboard shows "Offline"

**Problem:** Dashboard can't connect to GPS unit.

**Diagnosis:**
1. Dashboard can load but shows "Offline" → Connection issue
2. Dashboard won't load at all → File/server issue

**Solutions:**

If dashboard can load:
```bash
# Check if GPS endpoint is accessible
curl http://esp8266-gps.local/gps

# If times out or connection refused, see "Connection refused" section above
```

If dashboard won't load:
```bash
# If opening as file (file://...)
# Make sure file exists:
ls -la ~/Projects/boat/general/Code/seeboard/gps_dashboard.html

# If serving from Python HTTP server:
cd ~/Projects/boat/general/Code/seeboard
python3 -m http.server 8000

# Then try: http://localhost:8000/gps_dashboard.html
```

### Python script fails: "No GPS units found"

**Problem:** `gps_client.py` says no GPS units found on network.

**Diagnosis:**
```bash
# 1. Are you on GREEN-BEAN WiFi?
iwconfig

# 2. Can you find it with avahi?
avahi-browse -rtp _gps._tcp

# 3. Can you reach it directly?
ping esp8266-gps.local

# 4. Are zeroconf tools installed?
which avahi-browse
```

**Solutions:**

If `avahi-browse` doesn't work:
```bash
# Install avahi tools
sudo apt install avahi-utils

# Start daemon
sudo systemctl restart avahi-daemon
```

If you know the IP, use direct mode:
```bash
python3 gps_client.py --host 10.42.0.98
```

If you know the hostname, try direct mode:
```bash
python3 gps_client.py --host esp8266-gps.local
```

Increase discovery timeout:
```bash
python3 gps_client.py --timeout 10
```

### Browser shows raw JSON but I want it formatted

**Solution 1: Browser extension (easiest)**
- Chrome: Install "JSON Viewer" extension
- Firefox: Install "JSONView" extension
- Once installed, the JSON will automatically format

**Solution 2: Use the dashboard**
```bash
# Open the HTML dashboard:
http://localhost:8000/gps_dashboard.html
```

**Solution 3: Command line**
```bash
# Using curl + jq (pretty JSON formatter)
pip install jq
curl http://esp8266-gps.local/gps | jq .

# Or if jq not available, use Python
curl http://esp8266-gps.local/gps | python3 -m json.tool
```

---

## Integration Examples

### Shell Script: Monitor GPS Position

Create a script to continuously check GPS position:

```bash
#!/bin/bash
# File: gps_monitor.sh

echo "Continuous GPS monitoring (Ctrl+C to stop)"
echo ""

while true; do
  curl -s http://esp8266-gps.local/gps | python3 -m json.tool
  echo ""
  echo "---"
  sleep 5
done
```

Run it:
```bash
chmod +x gps_monitor.sh
./gps_monitor.sh
```

### Python: Get latest GPS coordinates

```python
#!/usr/bin/env python3
# File: get_gps.py

import json
import requests

url = "http://esp8266-gps.local/gps"

try:
    response = requests.get(url, timeout=5)
    data = response.json()
    
    if data.get('fix') == 1:
        print(f"Position: {data['lat']}, {data['lng']}")
        print(f"Accuracy: {data['hdop']} (HDOP)")
        print(f"Satellites: {data['satellites']}")
    else:
        print("No GPS fix yet")
        
except Exception as e:
    print(f"Error: {e}")
```

Run it:
```bash
python3 get_gps.py
```

### Node.js: Read GPS every 10 seconds

```javascript
// File: gps_monitor.js

const http = require('http');

function getGPS() {
    http.get('http://esp8266-gps.local/gps', (res) => {
        let data = '';
        
        res.on('data', (chunk) => {
            data += chunk;
        });
        
        res.on('end', () => {
            const gps = JSON.parse(data);
            console.log(`[${new Date().toISOString()}]`);
            console.log(`  Lat: ${gps.lat}, Lng: ${gps.lng}`);
            console.log(`  Sats: ${gps.satellites}, HDOP: ${gps.hdop}`);
            console.log(`  Status: ${gps.fix ? 'OK' : 'No fix'}`);
        });
    });
}

// Read every 10 seconds
setInterval(getGPS, 10000);
getGPS(); // Read immediately
```

Run it:
```bash
node gps_monitor.js
```

### IFTTT / Automation: Send alert if out of range

```python
#!/usr/bin/env python3
# File: gps_geofence.py

import requests
import json
from datetime import datetime

GPS_URL = "http://esp8266-gps.local/gps"

# Define safe zone (e.g., around Karlskrona harbor)
SAFE_ZONE = {
    'lat_min': 55.15,
    'lat_max': 55.20,
    'lng_min': 15.50,
    'lng_max': 15.65,
}

def check_geofence():
    try:
        response = requests.get(GPS_URL, timeout=5)
        data = response.json()
        
        if data.get('fix') != 1:
            print("No GPS fix")
            return
            
        lat = data['lat']
        lng = data['lng']
        
        in_zone = (
            SAFE_ZONE['lat_min'] <= lat <= SAFE_ZONE['lat_max'] and
            SAFE_ZONE['lng_min'] <= lng <= SAFE_ZONE['lng_max']
        )
        
        if in_zone:
            print(f"✓ In safe zone: {lat}, {lng}")
        else:
            print(f"⚠ OUT OF ZONE: {lat}, {lng}")
            # Send alert email/SMS/webhook here
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_geofence()
```

Run periodically:
```bash
# Run every minute via cron
* * * * * python3 /path/to/gps_geofence.py >> /tmp/gps.log
```

---

## Performance & Limitations

### HTTP Endpoint Specifications

| Property | Value |
|----------|-------|
| **Protocol** | HTTP 1.1 |
| **Port** | 80 (standard HTTP) |
| **URL** | `/gps` |
| **Method** | GET |
| **Response format** | JSON |
| **Response size** | ~110 bytes |
| **Update frequency** | ~1-2 updates per second |
| **Max concurrent clients** | 1 simultaneous stream (due to WiFi bandwidth) |

### Update Rate

GPS data updates typically every 1-2 seconds as new satellite fixes arrive. However:
- Browser refresh adds latency (DNS + TCP + HTTP overhead)
- Consider polling every 5-10 seconds for dashboard
- For real-time tracking, use WebSocket (not currently implemented)

### Accuracy

GPS accuracy depends on several factors:

| Factor | Impact |
|--------|--------|
| **Satellite count** | 4-6 sats = ±30-50m, 10+ sats = ±1-5m |
| **HDOP value** | Lower is better; <2 is excellent |
| **Antenna quality** | Consumer antenna = typical |
| **Sky view** | 30° minimum horizon clearance needed |
| **Multipath** | Reflections off buildings reduce accuracy |

Typical accuracy: **5-15 meters** with good sky view and 8+ satellites.

### Network Considerations

- **WiFi range:** ~50-100m from Pi (depends on environment)
- **Latency:** ~10-50ms typical (WiFi + LAN)
- **Bandwidth:** Minimal (~1 KB per request)
- **Concurrent clients:** Limited by WiFi interference (1-2 simultaneous connections recommended)

---

## Network Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     WiFi Network                            │
│                    GREEN-BEAN 2.4GHz                        │
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │  Raspberry Pi    │         │   ESP8266 GPS    │          │
│  │  (Access Point)  │         │   Unit           │          │
│  │  10.42.0.1       │◄───────►│   10.42.0.98     │          │
│  │                  │   WiFi  │                  │          │
│  │  nmcli: GREEN-   │         │   mDNS: esp8266- │          │
│  │  BEAN hotspot    │         │   gps.local      │          │
│  └──────────────────┘         │                  │          │
│       ▲                        │   HTTP Server    │          │
│       │                        │   Port 80        │          │
│       │ WiFi                   │   /gps endpoint  │          │
│       │                        │                  │          │
│       │                        └──────────────────┘          │
│       │                                                       │
│       │         ┌──────────────────┐                         │
│       └────────►│  Your Desktop    │                         │
│                 │  Machine         │                         │
│                 │  10.42.0.21      │                         │
│                 │                  │                         │
│                 │  Browser:        │                         │
│                 │  Firefox/Chrome  │                         │
│                 │  Python client   │                         │
│                 └──────────────────┘                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Reference Links

### GPS Unit Documentation
- **Main**: `docs/esp8266_gps_unit.md`
- **Flashing**: `docs/GPS_FLASHING_QUICK_REFERENCE.md`
- **This guide**: `docs/GPS_READING_FROM_DESKTOP.md`

### Python Scripts
- **GPS Client**: `gps_client.py` (command-line tool)
- **GPS Dashboard**: `gps_dashboard.html` (web UI)

### Useful Commands

**Discover GPS unit:**
```bash
avahi-browse -rtp _gps._tcp
```

**Test connectivity:**
```bash
ping esp8266-gps.local
curl http://esp8266-gps.local/gps
```

**Monitor in real-time:**
```bash
watch -n 1 'curl -s http://esp8266-gps.local/gps | python3 -m json.tool'
```

**Kill HTTP server:**
```bash
pkill -f "python3 -m http.server"
```

### External Resources
- **NEO-7M GPS Module:** https://www.u-blox.com/en/product/neo-7-series
- **ESP8266 Documentation:** https://esp8266.com/
- **HDOP Explanation:** https://en.wikipedia.org/wiki/Dilution_of_precision
- **mDNS/Bonjour:** https://en.wikipedia.org/wiki/Multicast_DNS

---

## Frequently Asked Questions

**Q: Does the GPS unit work without the Raspberry Pi?**  
A: Yes, in standalone mode. It displays coordinates on the OLED screen and doesn't need WiFi. However, you won't be able to access it from your desktop.

**Q: Can I use the GPS unit over the internet (outside my WiFi network)?**  
A: Not directly. The HTTP endpoint is only available on the local GREEN-BEAN network. For remote access, you'd need to:
- Set up port forwarding on the Pi (security risk)
- Use a VPN to connect back to the Pi
- Use a cloud service to relay GPS data

**Q: What's the difference between HDOP and satellite count?**  
A: Satellite count = how many satellites you see. HDOP = how well they're positioned. You want both: many satellites (10+) AND good geometry (HDOP < 2).

**Q: Why does coordinates sometimes jump around?**  
A: GPS receivers have inherent noise. ~1-3 meter jumps are normal even with good signal. Kalman filtering can reduce this, but isn't currently implemented.

**Q: Can I change the update frequency?**  
A: The ESP8266 updates its cached GPS data ~1-2 times per second. The HTTP endpoint always returns the latest data. Polling faster than every 1 second won't help (you'll just get duplicates).

**Q: How do I log GPS data to a file?**  
A: Use the Python script or cron job:
```bash
# Append GPS data to file every 10 seconds
*/10 * * * * curl -s http://esp8266-gps.local/gps >> ~/gps_log.json && echo "" >> ~/gps_log.json
```

**Q: Can multiple devices read GPS simultaneously?**  
A: Yes, but ESP8266 WiFi can get saturated. Recommended: 1-2 concurrent connections. More than that may cause slowdowns.

**Q: What if the GPS unit loses WiFi connection?**  
A: GPS will continue working (reading satellites, updating OLED). It will auto-reconnect to WiFi when available. HTTP endpoint will be unavailable during disconnection.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-08-16 | Initial documentation: Browser access, dashboard, Python client, troubleshooting |

---

**Document Status:** Complete  
**Last Updated:** 2026-08-16  
**Maintainer:** GPS Unit Project Team
