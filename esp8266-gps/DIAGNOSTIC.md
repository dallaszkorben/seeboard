# GPS Diagnostic Firmware

## Location
`src/main_diagnostic_gps.cpp`

## Purpose
Diagnose GPS module communication without OLED, WiFi, or other components. Shows raw NMEA parsing data every 2 seconds.

## When to Use
- GPS not acquiring satellites
- GPS showing 0 satellites when it should have signal
- Verifying GPS module is receiving data from antenna
- Troubleshooting wiring issues
- Testing after hardware changes

## How to Use

### 1. Swap firmware
```bash
cd /home/akoel/Projects/boat/general/Code/seeboard/esp8266-gps
cp src/main.cpp src/main_working.cpp
cp src/main_diagnostic_gps.cpp src/main.cpp
```

### 2. Flash
```bash
pio run --target upload
```

### 3. Monitor serial output
```bash
pio device monitor --baud 115200
```

### 4. Interpret output

**Example output when working:**
```
=== DIAGNOSTIC REPORT ===
Bytes received: 546
Sentences decoded: 14
Sentences with valid location: 0
Satellites: 3
Location valid: NO
Date valid: YES
Time valid: YES
  Date: 2026-7-26
  Time: 9:3:54
HDOP: 1088
```

**Key indicators:**

| Field | Meaning |
|-------|---------|
| `Bytes received: 546` | ✓ GPS talking to ESP8266 |
| `Sentences decoded: 14` | ✓ NMEA parser working |
| `Satellites: 3+` | ✓ Getting signal (needs 4+ for fix) |
| `Date valid: YES` | ✓ Time data available |
| `Time valid: YES` | ✓ Date data available |
| `Location valid: NO` | ⏳ Still acquiring (normal) |

**Problem indicators:**

| Symptom | Cause |
|---------|-------|
| `Bytes received: 0` | GPS not connected, wrong baud, or wiring issue |
| `Sentences decoded: 0` | GPS sending garbage data (baud mismatch?) |
| `Satellites: 0` | No antenna signal (move outside or wait longer) |
| `Date valid: NO` | Cold start (wait 1-5 minutes) |

### 5. Restore working firmware
```bash
cp src/main_working.cpp src/main.cpp
pio run --target upload
```

## Technical Details

- Reads GPS on **D3/D4** (SoftwareSerial)
- **9600 baud** (NEO-7M standard)
- Reports every **2 seconds**
- No OLED, WiFi, or HTTP overhead
- Minimal code = maximum GPS focus

## Files
- **main_diagnostic_gps.cpp** - Diagnostic firmware (this file)
- **main.cpp** - Working firmware (swap when diagnosing)
- **main_working.cpp** - Backup of working firmware

