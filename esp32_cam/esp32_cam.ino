// ESP32-CAM CODE (Camera + Command Server)
#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

// WiFi credentials
const char* ssid = "YOUR_SSID";
const char* password = "YOUR_PASSWORD";

WebServer server(80);

// ===== COMMAND HANDLER =====
void handleCmd() {
  String cmd = server.arg("move");

  if (cmd.length() > 0) {
    Serial.write(cmd[0]);   // Send to Arduino
  }

  server.send(200, "text/plain", "OK");
}

void setup() {
  Serial.begin(115200);

  // Connect WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }

  Serial.println(WiFi.localIP());

  // Add command endpoint
  server.on("/cmd", handleCmd);

  // Start server
  server.begin();

  // ⚠️ Your existing camera init + stream code stays here
  
}

void loop() {
  server.handleClient();
}
