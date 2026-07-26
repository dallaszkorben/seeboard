# ESP8266 GPS Unit Firmware

Networked GPS unit for seeBoard using ESP8266 D1 Mini, NEO-7M GPS module, and 0.96" OLED display.

## Quick Start

### Flash Firmware

**CRITICAL: Disconnect GPS cables (D3/D4) before flashing!**

```bash
cd /home/akoel/Projects/boat/general/Code/seeboard/esp8266-gps

# Check USB port
ls /dev/ttyUSB*

# Update platformio.ini if needed (set correct USB port)
# Then flash:
pio run --target upload

# Watch for: ✓ [SUCCESS] Took XX seconds
```

### Connect Hardware (After Flashing)

- GPS TX (green) → **D3**
- GPS RX (blue) → **D4**
- GPS VCC (red) → USB 5V
- GPS GND (black) → GND

### Verify

```bash
pio device monitor --baud 115200
```

Should show GPS data and WiFi connection status.

## Documentation

- **[GPS_FLASHING_QUICK_REFERENCE.md](../docs/GPS_FLASHING_QUICK_REFERENCE.md)** — Quick flash guide, troubleshooting, pinouts
- **[esp8266_gps_unit.md](../docs/esp8266_gps_unit.md)** — Complete documentation, wiring, architecture, Raspberry Pi integration

## Project Structure

```
esp8266-gps/
├── README.md                  ← This file
├── platformio.ini             ← Build configuration
├── src/
│   └── main.cpp              ← Main firmware (D3/D4 GPS, D1/D2 OLED)
└── .pio/                      ← Build artifacts (auto-generated)
```

## Hardware Wiring

```
ESP8266 D1 Mini (3 connections needed):

GPS Module (GY-GPSV3):
  TX (green)  → D3 (GPIO0)
  RX (blue)   → D4 (GPIO2)
  VCC (red)   → USB 5V
  GND (black) → GND (15)

OLED Display (0.96", 128×64):
  SCL (yellow) → D1 (GPIO5)
  SDA (green)  → D2 (GPIO4)
  VCC (red)    → 3.3V (8)
  GND (black)  → GND (15)

Power:
  USB 5V cable → ESP8266 D1 Mini
```

## Features

- ✅ **Dual-mode operation:**
  - Standalone: GPS + OLED display (no WiFi needed)
  - Networked: Connects to Raspberry Pi GREEN-BEAN hotspot
  
- ✅ **OLED displays:**
  - Latitude/Longitude (when fixed)
  - Satellite count
  - HDOP (dilution of precision)
  - Date/Time (from GPS)
  - WiFi connection status

- ✅ **HTTP API:**
  - `GET /gps` returns JSON: `{lat, lng, satellites, hdop, date, time}`
  - mDNS discovery: `esp8266-gps.local`

- ✅ **Serial debugging:**
  - Real-time GPS data on serial monitor at 115200 baud
  - GPS fix status, satellite count, coordinates

## Dependencies

```ini
[env:d1_mini]
lib_deps =
    TinyGPSPlus
    Adafruit SSD1306
    Adafruit GFX Library
    ESP8266 and ESP32 OLED driver for SSD1306
```

Auto-installed by `pio run`.

## Known Issues

### GPIO0/GPIO2 Conflict

**Problem:** Connecting GPS to D3/D4 during flashing prevents ESP8266 from entering bootloader.

**Solution:** Always disconnect GPS cables before flashing, reconnect after success.

### Cold Start GPS Acquisition

**Normal behavior:** First GPS fix takes 1-5 minutes outdoors (cold start).

**After first fix:** Re-lock takes 1-2 seconds (warm start).

Move antenna outdoors with clear sky view (30° minimum horizon) for faster acquisition.

## Troubleshooting

See [GPS_FLASHING_QUICK_REFERENCE.md](../docs/GPS_FLASHING_QUICK_REFERENCE.md) for:
- Port not found errors
- "Failed to connect" issues
- GPS not acquiring satellites
- OLED display blank
- USB/serial problems

## Building

### PlatformIO (Recommended)

```bash
# Build only
pio run

# Build and upload
pio run --target upload

# Monitor serial output
pio device monitor --baud 115200

# Full rebuild
pio run --target clean
pio run --target upload
```

### Arduino IDE (Alternative)

1. Install ESP8266 board: Preferences → Additional Boards URLs → `http://arduino.esp8266.com/stable/package_esp8266com_index.json`
2. Select Board: **Tools → Board → LOLIN(WEMOS) D1 R1 mini**
3. Install libraries via Sketch → Include Library → Manage Libraries
4. Upload

## Testing Without GPS/OLED

```cpp
// You can test individual components:
// 1. Comment out GPS code, just test OLED
// 2. Comment out OLED code, test GPS via serial monitor
// 3. Upload, check serial output at 115200 baud
```

## Integration with Raspberry Pi

The GPS unit advertises itself via mDNS (`_gps._tcp.local.`) and serves JSON data.

### Discovery on Pi

```bash
avahi-browse -rtp _gps._tcp
```

### Read GPS Data

```python
import requests

response = requests.get('http://esp8266-gps.local/gps', timeout=5)
data = response.json()
print(f"Position: {data['lat']}, {data['lng']}")
print(f"Satellites: {data['satellites']}")
```

## References

- [ESP8266 GPIO Reference](https://github.com/esp8266/Arduino/wiki/Pin-definitions-cheat-sheet)
- [TinyGPSPlus Documentation](http://arduiniana.org/libraries/tinygpsplus/)
- [NEO-7M Datasheet](https://content.u-blox.com/sites/default/files/NEO-7_NEO-8_NEO-9_DataSheet_UBX-13003221.pdf)
- [Adafruit SSD1306](https://github.com/adafruit/Adafruit_SSD1306)

## License

MIT
