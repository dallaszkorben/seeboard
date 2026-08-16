#include <Arduino.h>
#include <SoftwareSerial.h>
#include <TinyGPSPlus.h>

// ===== GPS PINS (SoftwareSerial) =====
const int GPS_RX_PIN = D3;   // GPIO0 - receives from GPS TX
const int GPS_TX_PIN = D4;   // GPIO2 - sends to GPS RX

// ===== GLOBAL OBJECTS =====
SoftwareSerial gpsSerial(GPS_RX_PIN, GPS_TX_PIN);  // RX, TX
TinyGPSPlus gps;

// ===== DIAGNOSTIC STATE =====
unsigned long lastReport = 0;
const unsigned long REPORT_INTERVAL = 2000;  // Report every 2 seconds
int bytesReceived = 0;
int sentencesProcessed = 0;
int sentencesWithFix = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n=== ESP8266 GPS DIAGNOSTIC ===\n");
  Serial.print("Initializing GPS on D3/D4 at 9600 baud...");
  
  gpsSerial.begin(9600);
  
  Serial.println(" READY\n");
  Serial.println("Waiting for GPS data...\n");
}

void loop() {
  // Read ALL available bytes
  while (gpsSerial.available()) {
    int c = gpsSerial.read();
    bytesReceived++;
    
    // Encode into GPS parser
    if (gps.encode(c)) {
      sentencesProcessed++;
      
      // Check what we got
      if (gps.location.isUpdated()) {
        sentencesWithFix++;
      }
    }
  }
  
  // Report diagnostics every 2 seconds
  unsigned long now = millis();
  if (now - lastReport >= REPORT_INTERVAL) {
    lastReport = now;
    
    Serial.println("=== DIAGNOSTIC REPORT ===");
    Serial.print("Bytes received: ");
    Serial.println(bytesReceived);
    Serial.print("Sentences decoded: ");
    Serial.println(sentencesProcessed);
    Serial.print("Sentences with valid location: ");
    Serial.println(sentencesWithFix);
    
    // GPS parser state
    Serial.print("Satellites: ");
    Serial.println(gps.satellites.value());
    
    Serial.print("Location valid: ");
    Serial.println(gps.location.isValid() ? "YES" : "NO");
    
    Serial.print("Date valid: ");
    Serial.println(gps.date.isValid() ? "YES" : "NO");
    
    Serial.print("Time valid: ");
    Serial.println(gps.time.isValid() ? "YES" : "NO");
    
    // If we have data, show it
    if (gps.date.isValid()) {
      Serial.print("  Date: ");
      Serial.print(gps.date.year());
      Serial.print("-");
      Serial.print(gps.date.month());
      Serial.print("-");
      Serial.println(gps.date.day());
    }
    
    if (gps.time.isValid()) {
      Serial.print("  Time: ");
      Serial.print(gps.time.hour());
      Serial.print(":");
      Serial.print(gps.time.minute());
      Serial.print(":");
      Serial.println(gps.time.second());
    }
    
    if (gps.location.isValid()) {
      Serial.print("  Location: ");
      Serial.print(gps.location.lat(), 6);
      Serial.print(", ");
      Serial.println(gps.location.lng(), 6);
    }
    
    Serial.print("HDOP: ");
    Serial.println(gps.hdop.value());
    
    Serial.println("");
    
    // Reset counters for next interval
    bytesReceived = 0;
    sentencesProcessed = 0;
    sentencesWithFix = 0;
  }
  
  delay(10);
}
