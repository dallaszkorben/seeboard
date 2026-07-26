# ESP8266 GPS Unit — WiFi-Enabled Networked GPS Tracker

## Quick Flash Guide (TL;DR)

**Before flashing, disconnect GPS TX/RX cables from D3/D4.** They interfere with boot if connected during upload.

### Step 1: Identify USB Port
```bash
ls /dev/ttyUSB*
# Should show: /dev/ttyUSB0 or /dev/ttyUSB1
```

### Step 2: Update platformio.ini
Replace `/dev/ttyUSB0` with your port if different:
```ini
[env:d1_mini]
upload_port = /dev/ttyUSB0
monitor_port = /dev/ttyUSB0
```

### Step 3: Flash Firmware
```bash
cd /home/akoel/Projects/boat/general/Code/seeboard/esp8266-gps
pio run --target upload
```
**Wait for "SUCCESS" message.**

### Step 4: Connect GPS Cables (CRITICAL WIRING)
```
GPS Module (GY-GPSV3) → ESP8266 D1 Mini
─────────────────────────────────────────
GPS TX (green)  → D3 (GPIO0)
GPS RX (blue)   → D4 (GPIO2)
GPS VCC (red)   → USB 5V
GPS GND (black) → GND
```

### Step 5: Verify on Serial Monitor
```bash
pio device monitor --baud 115200
```
Should show:
```
✓ GPS serial ready.
✓ WiFi connected!
GPS | Waiting for fix | Satellites: X | Wait: Y sec
```

---

## Overview

This document describes how to build a **standalone WiFi-enabled GPS unit** using an ESP8266 D1 Mini microcontroller. The unit works in two modes:

**Standalone Mode (no WiFi):**
- Reads GPS position data from a GY-GPSV3 NEO-7M module via UART
- Displays lat/long coordinates on a 0.96" OLED display (128×64) via I2C
- Works completely independently — no WiFi needed
- Ideal for portable use, testing, or when Raspberry Pi is not available

**Networked Mode (with WiFi):**
- Connects to the Raspberry Pi's WiFi hotspot (GREEN-BEAN)
- Broadcasts itself via mDNS as `_gps._tcp` service
- Serves GPS data as JSON over HTTP for the Raspberry Pi to consume
- Multiple units can be deployed and discovered automatically

## Architecture

### Dual-Mode Operation

```
┌─────────────────────────────────────────────────────────────────┐
│           ESP8266 D1 Mini GPS Unit (Dual Mode)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GPS Module (GY-GPSV3 NEO-7M) ── UART ──► ESP8266 ◄── I2C ──   │
│                                           (WiFi)     OLED Display
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                                                         │  │
│  │  STARTUP LOGIC:                                        │  │
│  │  1. Initialize GPS + OLED immediately                 │  │
│  │  2. Start reading NMEA, display coordinates           │  │
│  │  3. Attempt WiFi connection (non-blocking)            │  │
│  │  4. If WiFi OK → start mDNS + HTTP server             │  │
│  │  5. If WiFi fails → continue standalone mode          │  │
│  │                                                         │  │
│  │  Result: GPS display works ALWAYS                      │  │
│  │          WiFi/HTTP only if connection available       │  │
│  │                                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘


MODE 1: STANDALONE (No WiFi / GREEN-BEAN not available)
───────────────────────────────────────────────────────

GPS Module (GY-GPSV3)
      │
      ├─ NMEA sentences ──► ESP8266 UART
                                │
                                ├─ Parse position
                                │
                                └─► OLED Display (I2C)
                                        ↓
                                   Shows: Lat/Long
                                          Satellites
                                          Time
                                          Quality

WiFi: OFF (not connected, no power consumption)


MODE 2: NETWORKED (WiFi connected to GREEN-BEAN)
─────────────────────────────────────────────────

GPS Module (GY-GPSV3)
      │
      ├─ NMEA sentences ──► ESP8266
                                │
                                ├─ Parse position
                                │
                                ├─► OLED Display (shows coordinates)
                                │
                                └─► WiFi Stack
                                        │
                                        ├─ Connect to GREEN-BEAN
                                        ├─ Broadcast mDNS
                                        └─ HTTP Server on :80

Raspberry Pi (GREEN-BEAN, 10.42.0.1)
      │
      ├─ mDNS discovery ──► finds esp8266-gps-XXYY.local
      │
      └─ HTTP GET /gps ──► reads JSON coordinates
         (when needed)
```

### Startup Flowchart

```
ESP8266 Power On
      │
      ├─► Initialize UART (GPS)
      │
      ├─► Initialize I2C (OLED)
      │
      ├─► Display "Initializing..." on OLED
      │
      ├─► Start GPS reading thread
      │       │
      │       └─► NMEA parsing begins
      │
      ├─► Attempt WiFi connection (async, non-blocking)
      │       │
      │       ├─ YES: WiFi connected
      │       │        │
      │       │        ├─ Initialize mDNS
      │       │        ├─ Start HTTP server
      │       │        ├─ Broadcast _gps._tcp service
      │       │        └─ Update OLED: "Connected"
      │       │
      │       └─ NO: WiFi failed
      │                │
      │                └─ Update OLED: "Offline"
      │
      └─► Enter main loop (infinite)
           ├─ Keep reading GPS
           ├─ Keep updating OLED
           ├─ Keep serving HTTP (if connected)
           └─ GPS display ALWAYS works
```

## Use Cases

### Use Case 1: Standalone Portable GPS

**Scenario:** You're on a boat trip without the Raspberry Pi. You take just the GPS unit.

**What happens:**
1. Power on the ESP8266 GPS unit
2. OLED shows "GPS Unit Starting..."
3. WiFi attempt times out (no GREEN-BEAN available)
4. OLED shows "WiFi: Offline (Standalone mode)"
5. GPS reading continues, OLED displays your position
6. **Result:** Fully functional portable GPS with OLED display, no Raspberry Pi needed

### Use Case 2: Networked GPS (with Raspberry Pi)

**Scenario:** You want to display GPS data on the seeBoard touchscreen.

**What happens:**
1. Raspberry Pi creates GREEN-BEAN hotspot
2. Power on ESP8266 GPS unit
3. ESP8266 connects to GREEN-BEAN
4. OLED shows "WiFi: Connected" + IP address
5. Broadcasts itself via mDNS as `esp8266-gps-XXYY`
6. Raspberry Pi discovers it and can read GPS data
7. **Result:** seeBoard shows your position from the networked unit, with OLED also showing coordinates

### Use Case 3: Multiple GPS Units (Mixed Mode)

**Scenario:** You have the Raspberry Pi + local GPS, plus 2 portable GPS units.

**What happens:**
1. Local GPS on Raspberry Pi (wired to /dev/serial0) — always priority
2. Unit #1 powers on without WiFi → standalone OLED display
3. Unit #2 powers on, finds GREEN-BEAN → networked to Pi
4. Raspberry Pi's seeBoard shows local GPS (highest priority)
5. Unit #1 OLED shows its own position (standalone)
6. Unit #2 OLED shows its own position (networked, also available to Pi)
7. **Result:** Flexible system with local, standalone, and networked options

| Component | Model | Purpose |
|-----------|-------|---------|
| Microcontroller | ESP8266 D1 Mini | WiFi + UART + I2C |
| GPS Module | GY-GPSV3 NEO-7M | NMEA sentence generation |
| Display | 0.96" OLED (128×64) | Local coordinate display |
| Power Supply | USB 5V or external | Powers all components |

## Wiring Diagram

### ESP8266 D1 Mini Pinout Reference

```
ESP8266 D1 Mini (Top View)

        ┌─────────────────────────────────────┐
        │ D1 Mini Board (with pin labels)     │
        │                                     │
    RST │ RST                             GND │ GND (15)
    A0  │ A0                              D0  │ D0
   D5   │ D5    ╔═════════════════════╗  D1  │ D1
   D6   │ D6    ║  8 Pin Antenna      ║  D2  │ D2
   D7   │ D7    ║  Connector          ║  D3  │ D3
   D8   │ D8    ╚═════════════════════╝  D4  │ D4
   3V3  │ 3.3V                           D5  │ D5
   GND  │ GND                            GND │ GND (15)
        │                                    │
        │    USB Micro           GPIO Map   │
        │    (5V in)            (internal)  │
        │                                    │
        └─────────────────────────────────────┘

GPIO Internal Mappings (for reference):
  D0 = GPIO16
  D1 = GPIO5  (SCL for I2C)
  D2 = GPIO4  (SDA for I2C)
  D3 = GPIO0
  D4 = GPIO2
  D5 = GPIO14
  D6 = GPIO12
  D7 = GPIO13
  D8 = GPIO15
  RX = GPIO3  (RXD0 - Serial RX)
  TX = GPIO1  (TXD0 - Serial TX)
```

### Wiring Table

| Component | ESP8266 Pin | Pin Name | Function |
|-----------|-------------|----------|----------|
| **GPS Module (GY-GPSV3)** |
| GY-GPSV3 VCC | USB 5V | Power | +5V (via USB or external) |
| GY-GPSV3 GND | GND (15) | Ground | Ground reference |
| GY-GPSV3 TX | RX (21) | GPIO3-RXD0 | GPS data → ESP8266 |
| GY-GPSV3 RX | TX (22) | GPIO1-TXD0 | ESP8266 command → GPS |
| **OLED Display (0.96", 128×64)** |
| OLED GND | GND (15) | Ground | Ground reference |
| OLED VCC | 3.3V (8) | Power | +3.3V |
| OLED SCL | D1 (20) | GPIO5-SCL | I2C Clock |
| OLED SDA | D2 (19) | GPIO4-SDA | I2C Data |

### ASCII Wiring Diagram (Aligned)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ESP8266 D1 Mini Wiring                             │
└─────────────────────────────────────────────────────────────────────────────┘

POWER INPUT (USB or External)
├─ 5V ──────────────────────────────────────────► GY-GPSV3 NEO-7M VCC
└─ GND ─────┬──────────────────────────────────► GY-GPSV3 NEO-7M GND
            │
            ├──────────────────────────────────► OLED GND (pin -)
            └──────────────────────────────────► ESP8266 GND (15)


ESP8266 PIN ASSIGNMENTS
│
├─ RX (21) GPIO3-RXD0
│  └──────────────────────────────────────────► GY-GPSV3 NEO-7M TX
│
├─ TX (22) GPIO1-TXD0
│  └──────────────────────────────────────────► GY-GPSV3 NEO-7M RX
│
├─ D1 (20) GPIO5-SCL (I2C Clock)
│  └──────────────────────────────────────────► OLED SCL (pin ⊞)
│
├─ D2 (19) GPIO4-SDA (I2C Data)
│  └──────────────────────────────────────────► OLED SDA (pin ⊕)
│
└─ 3.3V (8)
   └──────────────────────────────────────────► OLED VCC (pin +)


COMPLETE CONNECTION LIST:
─────────────────────────

GY-GPSV3 NEO-7M GPS Module (4 pins):
  Pin 1 (VCC)    ─ Red wire ─ USB 5V input
  Pin 2 (RX)     ─ Blue wire ─ ESP8266 TX (22)
  Pin 3 (TX)     ─ Green wire ─ ESP8266 RX (21)
  Pin 4 (GND)    ─ Black wire ─ GND (15)

0.96" OLED Display 128×64 (4 pins):
  Pin 1 (GND)    ─ Black wire ─ GND (15)
  Pin 2 (VCC)    ─ Red wire ─ 3.3V (8)
  Pin 3 (SCL)    ─ Yellow wire ─ ESP8266 D1 (20) GPIO5
  Pin 4 (SDA)    ─ Green wire ─ ESP8266 D2 (19) GPIO4

Power & Ground Bus:
  USB 5V ─────────► GY-GPSV3 VCC
  3.3V (8) ─────► OLED VCC
  GND (15) ─────► GY-GPSV3 GND, OLED GND (common ground)
```

### Physical Layout Guide

```
┌──────────────────────────────────────────────────────────────────┐
│                    Suggested Physical Layout                     │
└──────────────────────────────────────────────────────────────────┘

Top of Enclosure:
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  [OLED Display]              [GPS Antenna]                      │
│  (0.96" OLED mounted)        (NEO-7M unit)                      │
│   on clear plastic overlay    mounted on side                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Interior (ESP8266 + connections):
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ┌──────────────┐         ┌────────────────┐                 │
│   │ ESP8266      │         │ GY-GPSV3       │                 │
│   │ D1 Mini      │         │ NEO-7M Module  │                 │
│   │              │◄────────►│                │                 │
│   │ UART (RX/TX) │         │ (GPS)          │                 │
│   │              │         │                │                 │
│   │ I2C (SDA/SCL)│         └────────────────┘                 │
│   │      ▲       │                                             │
│   │      │       │                                             │
│   └──────┼───────┘                                             │
│          │ (I2C ribbon)                                        │
│          │                                                     │
│      ┌───▼──────┐                                              │
│      │   OLED   │  (mounted in cover or bracket)              │
│      │ Display  │                                              │
│      └──────────┘                                              │
│                                                                 │
│   ┌─────────────────────────────────┐                         │
│   │ USB Power Input                 │                         │
│   │ (5V to all components)          │                         │
│   └─────────────────────────────────┘                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Tips:
- Use short, twisted I2C wires (SDA/SCL together) to reduce noise
- Keep power wires separate from signal wires
- Use labels on all wires for easy troubleshooting
- Consider using a breadboard or perfboard to organize connections
```

## Firmware Overview

### ESP8266 Firmware Tasks

The firmware must handle three concurrent operations, with a fallback if WiFi is unavailable:

1. **GPS Reading (UART) — ALWAYS ACTIVE**
   - Read NMEA sentences from serial port (UART1 on ESP8266)
   - Parse GGA sentences (position, quality, satellites)
   - Update local variables with latest position
   - Continues working even if WiFi fails

2. **OLED Display (I2C) — ALWAYS ACTIVE**
   - Display lat/long in real-time
   - Update coordinates every 1-2 seconds
   - Show GPS quality and satellite count
   - Show WiFi connection status (Connected/Offline)
   - Works in both standalone and networked modes

3. **WiFi + HTTP Server — OPTIONAL (graceful degradation)**
   - Attempt connection to GREEN-BEAN hotspot (non-blocking)
   - If successful: Advertise via mDNS, serve JSON on HTTP port 80
   - If failed: Continue running GPS + OLED in standalone mode
   - Display shows "Offline" status but GPS still works

### Key Design: Fault Tolerance

```
WiFi status:            GPS Display:      HTTP Server:
─────────────────      ──────────────     ──────────────
NOT CONNECTED          ✓ Works            ✗ Off
CONNECTED              ✓ Works            ✓ On
FAILED                 ✓ Works            ✗ Off
CONNECTION LOST        ✓ Works            ✗ Off (auto-reconnect)
```

### Firmware Structure (Pseudocode)

```cpp
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>
#include <SoftwareSerial.h>
#include <Adafruit_SSD1306.h>
#include <TinyGPSPlus.h>

// Configuration
const char* SSID = "GREEN-BEAN";
const char* PASSWORD = "";  // No password
const int GPS_BAUD = 9600;
const int OLED_ADDR = 0x3C;

// Global state
TinyGPSPlus gps;
SoftwareSerial gpsSerial(D7, D8);  // RX on D7, TX on D8 (or hardware UART)
Adafruit_SSD1306 display(128, 64, &Wire, -1);
ESP8266WebServer server(80);
bool wifi_connected = false;

void setup() {
  Serial.begin(115200);
  
  // Initialize OLED FIRST (independent of WiFi)
  display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 0);
  display.println("GPS Unit Starting...");
  display.display();
  
  // Initialize GPS serial IMMEDIATELY (independent of WiFi)
  gpsSerial.begin(GPS_BAUD);
  
  // ===== WIFI ATTEMPT (non-blocking, optional) =====
  // This is NON-BLOCKING so GPS continues if WiFi fails
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);
  
  // Set timeout (will retry in background)
  // Don't wait forever — if WiFi fails, standalone mode still works
  int wifi_attempt = 0;
  while (WiFi.status() != WL_CONNECTED && wifi_attempt < 20) {
    delay(500);
    wifi_attempt++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    // WiFi SUCCESS
    wifi_connected = true;
    
    // Start mDNS
    MDNS.begin("esp8266-gps");
    MDNS.addService("gps", "tcp", 80);
    
    // Setup HTTP endpoints
    server.on("/gps", handleGPS);
    server.begin();
    
    display.clearDisplay();
    display.println("WiFi: Connected");
    display.println(WiFi.localIP().toString().c_str());
  } else {
    // WiFi FAILED — Continue in STANDALONE mode
    wifi_connected = false;
    display.clearDisplay();
    display.println("WiFi: Offline");
    display.println("(Standalone mode)");
  }
  
  display.display();
}

void loop() {
  // ===== ALWAYS DO THIS (GPS + OLED) =====
  
  // Read GPS data continuously
  while (gpsSerial.available()) {
    gps.encode(gpsSerial.read());
  }
  
  // Update OLED display continuously
  if (gps.location.isUpdated()) {
    display.clearDisplay();
    display.setTextSize(2);
    display.setCursor(0, 0);
    display.print("Lat: ");
    display.println(gps.location.lat(), 6);
    display.print("Lon: ");
    display.println(gps.location.lng(), 6);
    
    display.setTextSize(1);
    display.print("Sats: ");
    display.println(gps.satellites.value());
    display.print("HDOP: ");
    display.println(gps.hdop.value());
    
    // Show WiFi status
    if (wifi_connected) {
      display.print("WiFi: Connected");
    } else {
      display.print("WiFi: Offline");
    }
    
    display.display();
  }
  
  // ===== ONLY DO THIS IF WIFI IS CONNECTED =====
  
  if (wifi_connected) {
    // Handle HTTP requests (only if WiFi enabled)
    server.handleClient();
    MDNS.update();
    
    // Try to reconnect if connection lost
    if (WiFi.status() != WL_CONNECTED) {
      wifi_connected = false;
      WiFi.reconnect();  // Background reconnect attempt
    }
  }
}

// HTTP endpoint: /gps returns JSON
// (only called if WiFi connected)
void handleGPS() {
  String json = "{";
  json += "\"lat\":" + String(gps.location.lat(), 6) + ",";
  json += "\"lng\":" + String(gps.location.lng(), 6) + ",";
  json += "\"satellites\":" + String(gps.satellites.value()) + ",";
  json += "\"hdop\":" + String(gps.hdop.value()) + ",";
  json += "\"time\":\"" + String(gps.time.hour()) + ":";
  json += String(gps.time.minute()) + ":";
  json += String(gps.time.second()) + "\"";
  json += "}";
  server.send(200, "application/json", json);
}
```

### Key Points

1. **OLED initialized first** — appears immediately on power
2. **GPS reading starts immediately** — no dependency on WiFi
3. **WiFi attempt is non-blocking** — times out after 10 seconds, continues anyway
4. **Standalone mode automatic** — if WiFi fails, display shows "Offline" and GPS still works
5. **Main loop always updates GPS + OLED** — HTTP/mDNS only if WiFi connected
6. **Graceful reconnection** — if WiFi drops after initial connection, auto-reconnect in background

### Required Libraries

Install via PlatformIO or Arduino IDE:

```
TinyGPSPlus       (Mikal Hart) - GPS NMEA parsing
Adafruit_SSD1306  (Adafruit) - OLED display driver
Adafruit_GFX      (Adafruit) - Graphics primitives for OLED
ESP8266WiFi       (built-in) - WiFi connectivity
ESP8266WebServer  (built-in) - HTTP server
ESP8266mDNS       (built-in) - mDNS service broadcasting
```

## Raspberry Pi Integration

### Discovery (Same as Cameras)

The Raspberry Pi discovers GPS units using the existing mDNS mechanism:

```python
# In cam_discovery.py or new gps_discovery.py
SERVICE_TYPE = "_gps._tcp.local."

def _on_service_state_change(zeroconf, service_type, name, state_change):
    """Called when a GPS unit appears or disappears."""
    if state_change == ServiceStateChange.Added:
        info = zeroconf.get_service_info(service_type, name)
        if info:
            ip = socket.inet_ntoa(info.addresses[0])
            url = f"http://{ip}:80/gps"
            _gps_units[name] = url
```

### GPS Data Reading

```python
import requests

def read_gps_from_remote(url):
    """Read GPS data from remote ESP8266 unit."""
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        return {
            'status': 'fix',
            'latitude': data['lat'],
            'longitude': data['lng'],
            'satellites': data['satellites'],
            'hdop': data['hdop'],
            'time': data['time']
        }
    except Exception as e:
        return {'status': 'no_data', 'error': str(e)}
```

### Priority Logic (Raspberry Pi)

```python
def get_gps_data():
    """
    Get GPS data with priority:
    1. Local GPS (/dev/serial0) if available
    2. Randomly selected remote GPS unit
    3. No data if neither available
    """
    
    # Try local GPS first
    local_data = read_local_gps()
    if local_data['status'] == 'fix':
        return local_data  # Use local, ignore remote
    
    # No local GPS, try remote units
    gps_units = get_gps_units()
    if gps_units:
        selected_unit = random.choice(list(gps_units.values()))
        return read_gps_from_remote(selected_unit)
    
    # No GPS available
    return {'status': 'no_data'}
```

## Setup Instructions

### 1. Hardware Assembly

1. **Connect GY-GPSV3 NEO-7M GPS module:**
   - VCC (red) → USB 5V
   - RX (blue) → ESP8266 TX (22)
   - TX (green) → ESP8266 RX (21)
   - GND (black) → GND (15)

2. **Connect 0.96" OLED display:**
   - GND (black) → GND (15)
   - VCC (red) → 3.3V (8)
   - SCL (yellow) → ESP8266 D1 (20) GPIO5
   - SDA (green) → ESP8266 D2 (19) GPIO4

3. **Power supply:**
   - Connect USB 5V cable to ESP8266 D1 Mini
   - Alternatively, use external power (5V regulated)

### 2. Firmware Installation

#### Option A: Using PlatformIO (Recommended)

```bash
# Create new PlatformIO project for ESP8266
mkdir esp8266-gps-unit
cd esp8266-gps-unit
pio init --board d1_mini

# Install dependencies in platformio.ini
[env:d1_mini]
platform = espressif8266
board = d1_mini
framework = arduino
lib_deps =
    TinyGPSPlus
    Adafruit SSD1306
    Adafruit GFX Library
    
# Create src/main.cpp with firmware code (see above)
# Build and upload
pio run -t upload
```

#### Option B: Using Arduino IDE

1. Install ESP8266 board support: **File → Preferences → Additional Board Manager URLs** → add `http://arduino.esp8266.com/stable/package_esp8266com_index.json`
2. **Tools → Board → ESP8266 Boards → WeMos D1 R1 mini**
3. Sketch → Include Library → Manage Libraries → search and install:
   - TinyGPSPlus
   - Adafruit SSD1306
   - Adafruit GFX
4. Paste firmware code into Arduino IDE
5. **Upload** (select correct COM port)

### 3. WiFi Configuration

Edit the firmware to match your Raspberry Pi's hotspot:

```cpp
const char* SSID = "GREEN-BEAN";
const char* PASSWORD = "";  // No password (as configured on Pi)
```

Ensure the Raspberry Pi hotspot is active:
```bash
sudo nmcli connection up Hotspot
```

### 4. Verification

1. **Power on ESP8266**
   - OLED should show "Initializing..." then "Connected!"
   - GPS antenna should be outdoors (needs 1-5 minutes for first fix)

2. **Check mDNS discovery from Pi:**
   ```bash
   avahi-browse -rtp _gps._tcp
   ```
   Should show: `esp8266-gps-XXYY` with IP address

3. **Test HTTP endpoint from Pi:**
   ```bash
   curl http://esp8266-gps-XXYY.local/gps
   ```
   Should return JSON:
   ```json
   {
     "lat": 55.1234567,
     "lng": 15.5678901,
     "satellites": 12,
     "hdop": 1.2,
     "time": "14:32:45"
   }
   ```

## Troubleshooting

### FLASHING ISSUES

#### Port not found: "No such file or directory: /dev/ttyUSB0"
**Cause:** ESP8266 disconnected or wrong port

**Fix:**
1. Check available ports: `ls /dev/ttyUSB*`
2. Update `platformio.ini` with correct port
3. Unplug USB 5 seconds, plug back in
4. Retry upload

#### "Failed to connect to ESP8266: Timed out"
**Cause:** GPS cables connected during flash (GPIO0/GPIO2 conflict)

**Fix:**
1. **Disconnect GPS TX/RX cables immediately**
2. Unplug ESP8266 USB
3. Wait 5 seconds
4. Plug back in
5. Flash again: `pio run --target upload`
6. Wait for SUCCESS
7. **Then connect GPS cables**

#### "Protocol error" during DTR/RTS operations
**Cause:** Serial port locked or in bad state

**Fix:**
```bash
# Kill any lingering serial processes
killall pio
killall esptool.py

# Reset USB device (replace X with your port number)
echo "Resetting USB..."
sudo sh -c 'echo 0 > /sys/bus/usb/devices/1-1/authorized'
sleep 1
sudo sh -c 'echo 1 > /sys/bus/usb/devices/1-1/authorized'
sleep 2

# Try again
pio run --target upload
```

#### Stuck on "Connecting......" (hangs for 30+ seconds)
**Cause:** GPIO0 held low (GPS cable connected, preventing boot)

**Fix:**
1. **Disconnect GPS cables from D3/D4**
2. Unplug USB
3. Wait 10 seconds
4. Plug back in
5. Immediately run: `pio run --target upload` (within 5 seconds)
6. If still hanging, try power cycling with different USB port

#### "Protocol error" or "No serial data received"
**Cause:** CH340 USB-to-serial chip in bad state

**Fix:**
1. Try different USB port on computer
2. Try different USB cable
3. If still failing, device may need hardware reset

### GPS RECEPTION ISSUES

#### OLED shows "0.000000" coordinates
**Cause:** GPS has no satellite fix yet

**Fix:**
1. Move antenna outdoors or near window (needs sky view)
2. Wait 1-5 minutes (cold start acquisition time)
3. Verify GPS module has power (red LED should blink)
4. Check TX/RX wiring: TX→D3, RX→D4

#### "Received 0 bytes" in serial monitor
**Cause:** GPS not sending NMEA data (no communication)

**Fix:**
1. Verify GPS cables connected: TX→D3, RX→D4
2. Test GPS independently with Arduino sketch (see test firmware)
3. Check GPS module power (red LED on)
4. Try moving antenna outdoors

#### GPS shows satellites but coordinates won't lock
**Cause:** GPS module working but needs more acquisition time or better sky view

**Fix:**
1. Keep antenna outdoors with clear sky view (30° horizon minimum)
2. Wait 5-10 minutes (open sky cold start)
3. Check antenna: should be slightly elevated, not blocked
4. Verify GPS module has power and is not overheating

### OLED DISPLAY ISSUES

**Symptoms:** OLED shows initialization message but coordinates don't update

**Diagnosis:**
- GPS has no satellites (cold start or no sky visibility)
- Serial wiring incorrect (GPS not sending NMEA)
- UART baud rate mismatch

**Fix:**
1. Move antenna outdoors, wait 1-5 minutes (cold start time)
2. Check serial wiring: RX on GPIO3 (pin 21), TX on GPIO1 (pin 22)
3. Verify GPS module is powered (red LED should be blinking)
4. Test with serial monitor: Upload test sketch, check for NMEA sentences at 9600 baud

### GPS not showing coordinates on OLED

**Symptoms:** OLED shows "0.000000" for lat/long

**Diagnosis:**
- Move antenna outdoors or near window (GPS needs sky view)
- Wait 1-5 minutes for cold start (initial satellite acquisition)
- Check GY-GPSV3 wiring: TX↔RX are crossed

**Fix:**
1. Verify wiring (RX on pin 21, TX on pin 22)
2. Test GPS directly: Open serial monitor at 9600 baud, should see NMEA sentences
3. If no NMEA output, check power (GY-GPSV3 red LED should blink when powered)

### OLED display not showing anything

**Symptoms:** Blank OLED or garbled text

**Diagnosis:**
- I2C address mismatch
- Wiring loose or incorrect
- SDA/SCL swapped

**Fix:**
1. Verify I2C wiring: SCL to D1 (20), SDA to D2 (19)
2. Scan I2C addresses: Upload Arduino I2C scanner sketch, check output
3. Common address: 0x3C (most 128×64 OLED displays)
4. If address different, update firmware: `display.begin(SSD1306_SWITCHCAPVCC, 0x3D);`

### ESP8266 not connecting to GREEN-BEAN

**Symptoms:** OLED shows "Initializing..." forever, no connection

**Diagnosis:**
- Wrong SSID or password in firmware
- Raspberry Pi hotspot not active
- WiFi interference or range issue

**Fix:**
1. Verify Pi hotspot is active: `sudo nmcli connection up Hotspot`
2. Check SSID matches exactly: `sudo nmcli connection show Hotspot | grep ssid`
3. Ensure password is correct (GREEN-BEAN has no password by default)
4. If still failing, check WiFi logs on ESP8266: Open serial monitor at 115200 baud

### GPS units not discovered on Raspberry Pi

**Symptoms:** `avahi-browse -rtp _gps._tcp` shows nothing

**Diagnosis:**
- ESP8266 connected but mDNS not broadcasting
- Zeroconf library not installed on Pi
- mDNS service not registered in firmware

**Fix:**
1. Install zeroconf on Pi: `pip install zeroconf`
2. Verify mDNS is advertising: Check serial output for "mDNS started"
3. Manually test IP connectivity: `ping esp8266-gps-XXYY.local`
4. If ping works but avahi doesn't find it, restart avahi daemon: `sudo systemctl restart avahi-daemon`

### HTTP endpoint returns 404

**Symptoms:** `curl http://esp8266-gps-XXYY.local/gps` → 404 error

**Diagnosis:**
- Endpoint not registered in firmware
- Web server not started

**Fix:**
1. Verify firmware has `server.on("/gps", handleGPS);`
2. Verify `server.begin();` called in setup()
3. Check serial monitor for "Server started"

### Bluetooth/WiFi interference (OLED and GPS both using 2.4GHz)

**Note:** Both ESP8266 WiFi and GPS use 2.4GHz band, but GPS is spread-spectrum (low power). Minimal interference expected.

**If interference occurs:**
1. Move GPS antenna away from WiFi antenna
2. Use ferrite clamps on GPS wires
3. Separate power supply for GPS module (isolated from WiFi)

## Integration with seeBoard Application

### Modify seeboard.py to support GPS units

```python
# In seeboard.py, initialize both discovery systems
from cam_discovery import start as start_cam_discovery
from gps_discovery import start as start_gps_discovery

# At app startup
start_cam_discovery()
start_gps_discovery()

# In GPS reading logic, add priority check
def get_gps_data(local_gps_reader, gps_units_discovery):
    """Get GPS with priority: local > random remote"""
    
    # Try local GPS
    local_data = local_gps_reader.read()
    if local_data['status'] == 'fix':
        return local_data
    
    # Try remote GPS units
    gps_units = gps_units_discovery.get_units()
    if gps_units:
        selected_url = random.choice(list(gps_units.values()))
        return requests.get(selected_url, timeout=5).json()
    
    return None
```

## Future Enhancements

1. **Multiple GPS units with failover** — rotate through units if one fails
2. **GPS accuracy comparison** — display HDOP from all units, let user select best
3. **Logging** — store GPS tracks from remote units to SQLite
4. **Configuration UI** — OLED menu to show WiFi status, IP, fix quality
5. **Battery mode** — low-power sleep when no clients connected
6. **Sensor fusion** — combine data from multiple GPS units for improved accuracy

## References

- **TinyGPSPlus library:** http://arduiniana.org/libraries/tinygpsplus/
- **Adafruit SSD1306:** https://github.com/adafruit/Adafruit_SSD1306
- **ESP8266 mDNS:** https://github.com/esp8266/Arduino/tree/master/libraries/ESP8266mDNS
- **NEO-7M datasheet:** https://content.u-blox.com/sites/default/files/NEO-7_NEO-8_NEO-9_DataSheet_UBX-13003221.pdf
