# ESP8266 GPS Unit — Quick Flashing Reference Card

## CRITICAL: GPIO0/GPIO2 Conflict During Boot

**GPS cables MUST be disconnected during flashing!**

Connecting GPS TX/RX (D3/D4, GPIO0/GPIO2) during boot prevents the ESP8266 from entering bootloader mode.

```
Timeline:
┌─────────────────────────────────────────────────────────────────┐
│ Flash Sequence (GPS cables DISCONNECTED)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Disconnect GPS TX and RX cables from D3 and D4             │
│  2. Unplug USB cable (5 seconds)                               │
│  3. Plug USB back in                                           │
│  4. Run: pio run --target upload                               │
│  5. Watch for: "Writing..." then "SUCCESS"                     │
│  6. Wait 5 seconds after SUCCESS message                       │
│  7. NOW: Connect GPS TX (green) to D3                          │
│  8. NOW: Connect GPS RX (blue) to D4                           │
│  9. Device is ready (OLED and serial show "Waiting for fix")  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## One-Command Flash & Verify

```bash
# 1. Change to project directory
cd /home/akoel/Projects/boat/general/Code/seeboard/esp8266-gps

# 2. Check USB port availability
ls /dev/ttyUSB*

# 3. If not /dev/ttyUSB0, update platformio.ini (see step 4)

# 4. Flash firmware (GPS cables disconnected!)
pio run --target upload

# 5. After SUCCESS, connect GPS cables to D3/D4

# 6. Verify (opens serial monitor at 115200 baud)
pio device monitor --baud 115200
```

Expected output:
```
=== ESP8266 GPS Unit ===
✓ OLED initialized.
✓ GPS serial ready.
✓ WiFi connected!
IP Address: 10.42.0.98
✓ mDNS started: esp8266-gps.local
Setup complete.

GPS | Waiting for fix | Satellites: 0 | Wait: 1 sec | WiFi: OK
GPS | Waiting for fix | Satellites: 3 | Wait: 5 sec | WiFi: OK
GPS | Waiting for fix | Satellites: 8 | Wait: 23 sec | WiFi: OK
=== GPS FIX OK ===
Latitude:  55.123456
Longitude: 15.654321
...
```

## Wiring Checklist (After Flashing)

- [ ] GPS TX (green) connected to D3 (GPIO0)
- [ ] GPS RX (blue) connected to D4 (GPIO2)
- [ ] GPS VCC (red) connected to USB 5V
- [ ] GPS GND (black) connected to GND (pin 15)
- [ ] OLED SCL (yellow) connected to D1 (GPIO5)
- [ ] OLED SDA (green) connected to D2 (GPIO4)
- [ ] OLED VCC (red) connected to 3.3V (pin 8)
- [ ] OLED GND (black) connected to GND (pin 15)

## Port Configuration

Edit `/home/akoel/Projects/boat/general/Code/seeboard/esp8266-gps/platformio.ini`:

```ini
[env:d1_mini]
platform = espressif8266
board = d1_mini
framework = arduino
monitor_speed = 115200
upload_port = /dev/ttyUSB0    # ← Change if needed (USB1, USB2, etc.)
monitor_port = /dev/ttyUSB0   # ← Must match upload_port
upload_speed = 74880
upload_resetmethod = nodemcu
```

## Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| `/dev/ttyUSB0` not found | Check `ls /dev/ttyUSB*`, update `platformio.ini` |
| "Failed to connect" | Disconnect GPS cables, unplug USB 5sec, retry |
| "Timed out waiting for packet" | GPS cables connected → disconnect them, retry |
| Stuck on "Connecting......" | Kill process: `killall pio`, disconnect GPS, retry |
| GPS shows 0 satellites | Antenna outdoor, wait 1-5 min for cold start |
| OLED blank | Check I2C wiring (SCL→D1, SDA→D2) |
| No serial output on monitor | Device might be running fine, check OLED display |

## Firmware PIN Map (After Flashing)

```
ESP8266 D1 Mini
────────────────────────────────────

GPS Module (GY-GPSV3):
  TX (green)  ←──→ D3 (GPIO0)  ✓ Correct
  RX (blue)   ←──→ D4 (GPIO2)  ✓ Correct
  VCC (red)   ←──→ USB 5V
  GND (black) ←──→ GND (15)

OLED Display:
  SCL (yellow) ←──→ D1 (GPIO5)
  SDA (green)  ←──→ D2 (GPIO4)
  VCC (red)    ←──→ 3.3V (8)
  GND (black)  ←──→ GND (15)
```

## Serial Monitor Output During Normal Operation

```
=== GPS FIX OK ===                          ← GPS locked, coordinates valid
Latitude:  55.123456                        ← Your latitude
Longitude: 15.654321                        ← Your longitude
Satellites: 12 | HDOP: 1.2                  ← 12 satellites, quality 1.2
Date: 2026-07-26                            ← UTC date from GPS
Time: 10:38:55                              ← UTC time from GPS
WiFi: OK                                    ← Connected to GREEN-BEAN

(repeats every ~0.5 seconds while OLED updating)
```

## If GPS Not Acquiring Fix

**Wait times (normal behavior):**
- **First 30 seconds:** 0-3 satellites (acquisition starting)
- **1-3 minutes:** 5-8 satellites (approaching fix)
- **3-5 minutes:** 10+ satellites, FIXED (initial cold start)
- **After initial fix:** 1-2 seconds to re-lock (warm start)

**If still 0 satellites after 5 minutes outdoors:**
1. Check GPS module power (red LED should blink)
2. Verify GPS TX/RX wired correctly
3. Test with serial monitor (should see NMEA sentences)
4. Try different antenna location (elevated, clear sky)

## Testing Without OLED

If OLED not yet connected, use serial monitor to verify operation:

```bash
pio device monitor --baud 115200
```

The firmware outputs all data to serial, so you can diagnose without OLED.

## Reset/Recovery Procedures

### Full USB Reset (if hung)
```bash
sudo sh -c 'echo 0 > /sys/bus/usb/devices/1-1/authorized'
sleep 1
sudo sh -c 'echo 1 > /sys/bus/usb/devices/1-1/authorized'
sleep 2
pio run --target upload
```

### Clean Build (if compilation fails)
```bash
cd /home/akoel/Projects/boat/general/Code/seeboard/esp8266-gps
pio run --target clean
pio run --target upload
```

### Factory Reset (nuclear option)
```bash
# Erase entire chip (this wipes firmware)
esptool.py -p /dev/ttyUSB0 --baud 74880 erase_flash

# Then re-flash
pio run --target upload
```

## Pinout Reference Card

```
ESP8266 D1 Mini (Top View)

              ╔═══════════════════════════╗
       RST ───║ RST             GND   GND ║ (15)
        A0 ───║ A0              D0        ║ D0
        D5 ───║ D5              D1        ║ D1 (SCL, GPIO5)
        D6 ───║ D6              D2        ║ D2 (SDA, GPIO4)
        D7 ───║ D7              D3        ║ D3 (GPIO0, GPS RX) ← IMPORTANT
        D8 ───║ D8              D4        ║ D4 (GPIO2, GPS TX) ← IMPORTANT
       3V3 ───║ 3.3V (8)        D5        ║ D5
       GND ───║ GND (15)        GND       ║ GND (15)
              ║                           ║
              ║  USB Micro        Antenna ║
              ║  (5V Input)      Connector║
              ╚═══════════════════════════╝
```

## Verification Checklist

After flashing and connecting GPS:

- [ ] USB cable connected to ESP8266
- [ ] GPS antenna outdoors (or near window)
- [ ] OLED showing something (not blank)
- [ ] Serial monitor shows "Setup complete"
- [ ] Satellite count increasing (not stuck at 0)
- [ ] After 1-5 minutes: coordinates displayed
- [ ] WiFi connected to GREEN-BEAN (if in range)
- [ ] HTTP endpoint works: `curl http://esp8266-gps.local/gps`

---

**Document Version:** 1.0 | **Last Updated:** 2026-07-26 | **Device:** ESP8266 D1 Mini
