#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>
#include <SoftwareSerial.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_GFX.h>
#include <TinyGPSPlus.h>

// ===== CONFIGURATION =====
const char* SSID = "GREEN-BEAN";
const char* PASSWORD = "";
const int GPS_BAUD = 9600;
const int OLED_ADDR = 0x3C;
const int OLED_WIDTH = 128;
const int OLED_HEIGHT = 64;

// ===== GPS PINS (SoftwareSerial) =====
// GPS TX -> D3 (GPIO0) - we read from this
// GPS RX -> D4 (GPIO2) - we write to this
const int GPS_RX_PIN = D3;   // GPIO0 - receives from GPS TX
const int GPS_TX_PIN = D4;   // GPIO2 - sends to GPS RX

// ===== GLOBAL OBJECTS =====
SoftwareSerial gpsSerial(GPS_RX_PIN, GPS_TX_PIN);  // RX, TX
TinyGPSPlus gps;
Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);
ESP8266WebServer server(80);

// ===== GLOBAL STATE =====
bool wifi_connected = false;
bool gps_has_fix = false;
unsigned long last_display_update = 0;
const unsigned long DISPLAY_UPDATE_INTERVAL = 500;
unsigned long gps_wait_start = 0;
unsigned long last_wifi_attempt = 0;
const unsigned long WIFI_RETRY_INTERVAL = 30000;  // Retry every 30 seconds

// ===== GPS DATA CACHE =====
float cached_lat = 0;
float cached_lng = 0;
int cached_sats = 0;
float cached_hdop = 0;
String cached_date = "";
String cached_time = "";

// ===== FUNCTION DECLARATIONS =====
void initOLED();
void initGPS();
void initWiFi();
void setupWiFiServer();
void attemptWiFiReconnect();
void handleGPS();
void readGPSData();
void updateDisplay();
void displayWaitingForFix();
void displayGPSFix();

// ===== SETUP =====
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n=== ESP8266 GPS Unit (SoftwareSerial D3/D4) ===\n");
  
  // Initialize I2C (GPIO4 = SDA/D2, GPIO5 = SCL/D1)
  Wire.begin(4, 5);
  
  // Initialize OLED
  initOLED();
  
  // Initialize GPS on SoftwareSerial D3/D4
  initGPS();
  
  // Display initializing message
  display.clearDisplay();
  display.setTextSize(2);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("ESP8266");
  display.println("GPS");
  display.setTextSize(1);
  display.println("");
  display.println("Initializing...");
  display.display();
  
  // Attempt WiFi connection
  initWiFi();
  
  gps_wait_start = millis();
  Serial.println("Setup complete. Entering main loop.\n");
}

// ===== OLED INITIALIZATION =====
void initOLED() {
  Serial.println("Initializing OLED...");
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("ERROR: OLED not found");
  } else {
    Serial.println("✓ OLED initialized.");
  }
}

// ===== GPS INITIALIZATION (SoftwareSerial on D3/D4) =====
void initGPS() {
  Serial.print("Initializing GPS on SoftwareSerial (D3=RX, D4=TX, ");
  Serial.print(GPS_BAUD);
  Serial.println(" baud)...");
  gpsSerial.begin(GPS_BAUD);
  Serial.println("✓ GPS serial ready.");
}

// ===== WIFI INITIALIZATION (NON-BLOCKING) =====
void initWiFi() {
  Serial.println("Attempting WiFi connection to GREEN-BEAN...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);
  
  int attempt = 0;
  while (WiFi.status() != WL_CONNECTED && attempt < 20) {
    delay(500);
    Serial.print(".");
    attempt++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    setupWiFiServer();
  } else {
    wifi_connected = false;
    Serial.println("\n✗ WiFi connection failed - Will retry every 30 seconds");
    Serial.println("  Standalone mode active (GPS display works)");
  }
}

// ===== SETUP WIFI SERVER (mDNS + HTTP) =====
void setupWiFiServer() {
  wifi_connected = true;
  Serial.println("\n✓ WiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  
  if (!MDNS.begin("esp8266-gps")) {
    Serial.println("ERROR: mDNS setup failed");
  } else {
    MDNS.addService("gps", "tcp", 80);
    Serial.println("✓ mDNS started: esp8266-gps.local");
  }
  
  server.on("/gps", handleGPS);
  server.begin();
  Serial.println("✓ HTTP server started on port 80");
}

// ===== ATTEMPT WIFI RECONNECTION (CALLED FROM LOOP) =====
void attemptWiFiReconnect() {
  unsigned long now = millis();
  
  if (WiFi.status() == WL_CONNECTED) {
    // WiFi is connected
    if (!wifi_connected) {
      // Was previously disconnected, now reconnected - setup server
      setupWiFiServer();
    }
  } else {
    // WiFi is disconnected
    wifi_connected = false;
    
    // Attempt reconnection every 30 seconds
    if (now - last_wifi_attempt >= WIFI_RETRY_INTERVAL) {
      last_wifi_attempt = now;
      Serial.println("\nRetrying WiFi connection...");
      WiFi.reconnect();
    }
  }
}

// ===== MAIN LOOP =====
void loop() {
  // Read GPS data
  readGPSData();
  
  // Update display
  unsigned long now = millis();
  if (now - last_display_update >= DISPLAY_UPDATE_INTERVAL) {
    updateDisplay();
    last_display_update = now;
  }
  
  // Attempt WiFi reconnection (with 30-second retry interval)
  attemptWiFiReconnect();
  
  // Handle WiFi server if connected
  if (wifi_connected) {
    server.handleClient();
    MDNS.update();
  }
  
  delay(10);
}

// ===== READ GPS DATA FROM SOFTWARESERIAL =====
void readGPSData() {
  while (gpsSerial.available() > 0) {
    char c = gpsSerial.read();
    gps.encode(c);
  }
  
  // Update cached values if location is valid
  if (gps.location.isValid()) {
    gps_has_fix = true;
    cached_lat = gps.location.lat();
    cached_lng = gps.location.lng();
  } else {
    gps_has_fix = false;
  }
  
  // Always update these (they become valid before location)
  cached_sats = gps.satellites.value();
  cached_hdop = gps.hdop.value();
  
  // Extract date if valid
  if (gps.date.isValid()) {
    cached_date = "";
    int year = gps.date.year();
    int month = gps.date.month();
    int day = gps.date.day();
    
    if (year < 10) cached_date += '0';
    cached_date += String(year);
    cached_date += "-";
    if (month < 10) cached_date += '0';
    cached_date += String(month);
    cached_date += "-";
    if (day < 10) cached_date += '0';
    cached_date += String(day);
  }
  
  // Extract time if valid
  if (gps.time.isValid()) {
    cached_time = "";
    int hour = gps.time.hour();
    int minute = gps.time.minute();
    int second = gps.time.second();
    
    if (hour < 10) cached_time += '0';
    cached_time += String(hour);
    cached_time += ":";
    if (minute < 10) cached_time += '0';
    cached_time += String(minute);
    cached_time += ":";
    if (second < 10) cached_time += '0';
    cached_time += String(second);
  }
}

// ===== DISPLAY: WAITING FOR GPS FIX =====
void displayWaitingForFix() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  
  display.println("GPS Acquiring...");
  display.println("");
  
  display.print("Satellites: ");
  display.println(cached_sats);
  
  display.print("HDOP: ");
  display.println(String(cached_hdop, 1));
  
  // Show date/time if available (even without location fix)
  if (!cached_date.isEmpty()) {
    display.print("Date: ");
    display.println(cached_date);
  }
  if (!cached_time.isEmpty()) {
    display.print("Time: ");
    display.println(cached_time);
  }
  
  unsigned long elapsed = (millis() - gps_wait_start) / 1000;
  display.print("Wait: ");
  display.print(elapsed);
  display.println("s");
  
  display.display();
  
  // Mirror to Serial Monitor
  Serial.print("GPS | Acquiring | Sats: ");
  Serial.print(cached_sats);
  Serial.print(" | HDOP: ");
  Serial.print(String(cached_hdop, 1));
  if (!cached_date.isEmpty()) {
    Serial.print(" | ");
    Serial.print(cached_date);
  }
  if (!cached_time.isEmpty()) {
    Serial.print(" ");
    Serial.print(cached_time);
  }
  Serial.println();
}

// ===== DISPLAY: GPS FIX ACQUIRED =====
void displayGPSFix() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  
  // Coordinates in yellow area (top 16 pixels)
  // Yellow area: pixels 0-15, Blue area starts at pixel 16
  display.setTextSize(1);
  
  display.setCursor(0, 0);
  display.print("Lat:");
  display.println(String(cached_lat, 6));
  
  // Position Lng at pixel 8 to fit completely in yellow area
  display.setCursor(0, 8);
  display.print("Long:");
  display.println(String(cached_lng, 6));
  
  // Small info in blue area
  display.setCursor(0, 20);
  display.print("Sats: ");
  display.print(cached_sats);
  display.print("  HDOP: ");
  display.println(String(cached_hdop, 1));
  
  // Date and time
  display.setCursor(0, 30);
  if (!cached_date.isEmpty()) {
    display.print(cached_date);
    if (!cached_time.isEmpty()) {
      display.print("  ");
      display.print(cached_time);
    }
  } else if (!cached_time.isEmpty()) {
    display.print(cached_time);
  }
  display.println("");
  
  // WiFi status moved up (was at 58, now at 48 to stay visible)
  display.setCursor(0, 48);
  display.print("WiFi: ");
  display.println(wifi_connected ? "OK" : "Offline");
  
  display.display();
  
  // Mirror to Serial Monitor
  Serial.println("=== GPS FIX OK ===");
  Serial.print("Latitude:  ");
  Serial.println(String(cached_lat, 6));
  Serial.print("Longitude: ");
  Serial.println(String(cached_lng, 6));
  Serial.print("Satellites: ");
  Serial.print(cached_sats);
  Serial.print(" | HDOP: ");
  Serial.println(String(cached_hdop, 1));
  if (!cached_date.isEmpty()) {
    Serial.print("Date: ");
    Serial.println(cached_date);
  }
  if (!cached_time.isEmpty()) {
    Serial.print("Time: ");
    Serial.println(cached_time);
  }
  Serial.println("");
}

// ===== UPDATE OLED DISPLAY =====
void updateDisplay() {
  if (gps_has_fix) {
    displayGPSFix();
  } else {
    displayWaitingForFix();
  }
}

// ===== HTTP HANDLER: /gps endpoint =====
void handleGPS() {
  if (!gps_has_fix) {
    server.send(503, "application/json", "{\"error\": \"No GPS fix\"}");
    return;
  }
  
  String json = "{";
  json += "\"lat\":" + String(cached_lat, 6) + ",";
  json += "\"lng\":" + String(cached_lng, 6) + ",";
  json += "\"satellites\":" + String(cached_sats) + ",";
  json += "\"hdop\":" + String(cached_hdop, 2) + ",";
  json += "\"date\":\"" + cached_date + "\",";
  json += "\"time\":\"" + cached_time + "\",";
  json += "\"fix\":" + String(gps_has_fix ? 1 : 0);
  json += "}";
  
  server.send(200, "application/json", json);
}
