/*
 * ESP32-CAM MJPEG Streaming Firmware
 *
 * This firmware runs on a Freenove ESP32-WROVER-CAM board.
 * It connects to the Raspberry Pi's WiFi access point (GREEN-BEAN)
 * and serves a live MJPEG video stream over HTTP.
 *
 * Architecture:
 *   - ESP32 connects to Pi's AP as a WiFi client (station mode)
 *   - Two HTTP servers run on different ports:
 *     Port 80: serves an HTML page with embedded stream
 *     Port 81: serves the raw MJPEG stream (supports multiple clients)
 *   - mDNS advertises the device as "esp32-cam.local"
 *
 * Access:
 *   http://esp32-cam.local      — HTML page with embedded video
 *   http://esp32-cam.local:81/stream — direct MJPEG stream
 *
 * LED behavior (GPIO 2):
 *   Blinking = trying to connect to WiFi
 *   Rapid blink = camera init failed (halted)
 *   Off = running normally
 */

#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <esp_http_server.h>
#include "esp_camera.h"

// WiFi SSID defined in platformio.ini build_flags (-DWIFI_SSID)

// LED_PIN defined in platformio.ini build_flags (-DLED_PIN)

// ─── Camera pin mapping for Freenove ESP32-WROVER-CAM ───
// These are fixed by the board's PCB layout — do not change
#define PWDN_GPIO_NUM    -1   // Not used (no power-down pin)
#define RESET_GPIO_NUM   -1   // Not used (no hardware reset pin)
#define XCLK_GPIO_NUM    21   // Camera clock input
#define SIOD_GPIO_NUM    26   // I2C data (camera config)
#define SIOC_GPIO_NUM    27   // I2C clock (camera config)
#define Y9_GPIO_NUM      35   // Data bit 7
#define Y8_GPIO_NUM      34   // Data bit 6
#define Y7_GPIO_NUM      39   // Data bit 5
#define Y6_GPIO_NUM      36   // Data bit 4
#define Y5_GPIO_NUM      19   // Data bit 3
#define Y4_GPIO_NUM      18   // Data bit 2
#define Y3_GPIO_NUM       5   // Data bit 1
#define Y2_GPIO_NUM       4   // Data bit 0
#define VSYNC_GPIO_NUM   25   // Vertical sync
#define HREF_GPIO_NUM    23   // Horizontal reference
#define PCLK_GPIO_NUM    22   // Pixel clock

// ─── MJPEG stream constants ───
// These define the HTTP multipart boundary used to separate JPEG frames
#define PART_BOUNDARY "frame"
static const char* STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// HTTP server handles (two separate servers on different ports)
httpd_handle_t stream_httpd = NULL;
httpd_handle_t web_httpd = NULL;

// ─── Camera initialization ───
bool initCamera() {
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;       // 20MHz clock to camera
    config.pixel_format = PIXFORMAT_JPEG;  // Hardware JPEG encoding
    config.frame_size = FRAMESIZE_VGA;     // 640x480 resolution
    config.jpeg_quality = 12;              // 0-63, lower = better quality
    config.fb_count = 2;                   // Double buffer for smoother streaming
    config.grab_mode = CAMERA_GRAB_LATEST; // Always get the newest frame

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed: 0x%x\n", err);
        return false;
    }
    Serial.println("Camera initialized OK");
    return true;
}

// ─── MJPEG stream handler ───
// Each connected client gets its own instance of this handler.
// It continuously captures frames and sends them as multipart JPEG.
// The connection stays open until the client disconnects.
static esp_err_t stream_handler(httpd_req_t *req) {
    esp_err_t res = ESP_OK;
    char part_buf[64];

    res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
    if (res != ESP_OK) return res;

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("Camera capture failed");
            res = ESP_FAIL;
            break;
        }

        // Send boundary, then content-type/length header, then JPEG data
        size_t hlen = snprintf(part_buf, 64, STREAM_PART, fb->len);
        res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
        if (res == ESP_OK)
            res = httpd_resp_send_chunk(req, part_buf, hlen);
        if (res == ESP_OK)
            res = httpd_resp_send_chunk(req, (const char*)fb->buf, fb->len);

        esp_camera_fb_return(fb);
        if (res != ESP_OK) break;  // Client disconnected
    }
    return res;
}

// ─── HTML page handler ───
// Serves a simple page that embeds the stream in an <img> tag.
// The browser handles MJPEG natively in <img src="...">.
static esp_err_t index_handler(httpd_req_t *req) {
    char html[256];
    snprintf(html, sizeof(html),
        "<html><head><title>ESP32-CAM</title></head>"
        "<body style='margin:0;background:#000;'>"
        "<img src='http://%s:81/stream' style='width:100%%;height:100vh;object-fit:contain;'>"
        "</body></html>",
        WiFi.localIP().toString().c_str());
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, html, strlen(html));
}

// ─── Start both HTTP servers ───
// Port 80: HTML page (lightweight, quick response)
// Port 81: MJPEG stream (long-lived connections, handles multiple clients)
// Using esp_http_server instead of Arduino WebServer because it supports
// concurrent connections — multiple devices can view the stream simultaneously.
void startWebServer() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = WEB_PORT;

    if (httpd_start(&web_httpd, &config) == ESP_OK) {
        httpd_uri_t index_uri = {
            .uri = "/",
            .method = HTTP_GET,
            .handler = index_handler,
            .user_ctx = NULL
        };
        httpd_register_uri_handler(web_httpd, &index_uri);
        Serial.printf("Web server on port %d\n", WEB_PORT);
    }

    // Separate server on port 81 for streaming
    config.server_port = STREAM_PORT;
    config.ctrl_port = 32769;  // Must differ from port 80's control port

    if (httpd_start(&stream_httpd, &config) == ESP_OK) {
        httpd_uri_t stream_uri = {
            .uri = "/stream",
            .method = HTTP_GET,
            .handler = stream_handler,
            .user_ctx = NULL
        };
        httpd_register_uri_handler(stream_httpd, &stream_uri);
        Serial.printf("Stream server on port %d\n", STREAM_PORT);
    }
}

// ─── WiFi connection with infinite retry ───
// The Pi's AP might not be running yet when the ESP32 boots,
// so we retry forever until connected. LED blinks during attempts.
void connectWiFi() {
    while (true) {
        // Full WiFi reset on each attempt — ensures clean state
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
        delay(1000);
        WiFi.mode(WIFI_STA);
        #ifdef WIFI_PASS
        WiFi.begin(WIFI_SSID, WIFI_PASS);
        #else
        WiFi.begin(WIFI_SSID);
        #endif

        Serial.printf("Connecting to '%s'...\n", WIFI_SSID);
        int attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < 20) {
            delay(500);
            Serial.print(".");
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            attempts++;
        }

        if (WiFi.status() == WL_CONNECTED) {
            Serial.printf("\nConnected! IP: %s\n", WiFi.localIP().toString().c_str());
            digitalWrite(LED_PIN, LOW);  // LED off = connected
            return;
        }

        // AP not available yet — wait and retry
        Serial.println("\nFailed. Retrying in 5s...");
        delay(5000);
    }
}

void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(1000);
    Serial.println("\n\nESP32-CAM Starting...");

    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, HIGH);  // LED on during init

    // Camera init with 3 retries (sometimes first attempt fails after cold boot)
    bool cam_ok = false;
    for (int i = 0; i < 3; i++) {
        cam_ok = initCamera();
        if (cam_ok) break;
        Serial.printf("Camera retry %d/3...\n", i + 1);
        delay(1000);
    }

    if (!cam_ok) {
        // Rapid blink = camera hardware error, halted
        Serial.println("Camera failed. Halting.");
        while (true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(200);
        }
    }

    connectWiFi();
    startWebServer();

    // mDNS: unique hostname based on last 4 chars of MAC address
    // e.g., "esp32-cam-a1b2.local" — each camera gets a unique name
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char hostname[20];
    snprintf(hostname, sizeof(hostname), "esp32-cam-%02x%02x", mac[4], mac[5]);

    if (MDNS.begin(hostname)) {
        // Advertise _mjpeg._tcp service so Pi can auto-discover all cameras
        MDNS.addService("mjpeg", "tcp", STREAM_PORT);
        Serial.printf("mDNS: %s.local\n", hostname);
    }

    Serial.printf("Ready! http://%s.local:81/stream\n", hostname);
}

void loop() {
    // Monitor WiFi — reconnect if connection drops
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi lost. Reconnecting...");
        connectWiFi();
    }
    delay(1000);
}
