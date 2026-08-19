#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include <WebServer.h>

// ================================
// MPU6050 PIN CONFIGURATION
// ================================

#define MPU_SDA 21
#define MPU_SCL 22

// ================================
// WIFI & WEBSERVER
// ================================
const char* ssid = "Wokwi-GUEST";
const char* password = "";

WebServer server(80);

// ================================
// MPU6050 OBJECT
// ================================

Adafruit_MPU6050 mpu;

// ================================
// SIMULATED VEHICLE STATE
// ================================
float sim_rpm           = 1200.0;
float sim_coolant_temp  = 85.0;
float sim_voltage       = 13.8;
float sim_engine_load   = 25.0;
float sim_vehicle_speed = 60.0;
float sim_odometer      = 50000.0;

unsigned long lastUpdateMs = 0;

// ================================
// HELPER: Clamp a float value
// ================================
float clampf(float val, float lo, float hi) {
  if (val < lo) return lo;
  if (val > hi) return hi;
  return val;
}

// ================================
// DATA GENERATION
// ================================
void handleData() {
  sensors_event_t accelEvent;
  sensors_event_t gyroEvent;
  sensors_event_t tempEvent;

  // Read MPU6050
  mpu.getEvent(&accelEvent, &gyroEvent, &tempEvent);

  float accel_x = accelEvent.acceleration.x;
  float accel_y = accelEvent.acceleration.y;
  float accel_z = accelEvent.acceleration.z;
  float gyro_x = gyroEvent.gyro.x;
  float gyro_y = gyroEvent.gyro.y;
  float gyro_z = gyroEvent.gyro.z;
  float mpu_temp = tempEvent.temperature;

  float totalAccel = sqrt(accel_x * accel_x + accel_y * accel_y + accel_z * accel_z);
  float vibration = abs(totalAccel - 9.81);
  bool shock = (totalAccel > 15.0 || totalAccel < 5.0);

  unsigned long now = millis();
  float dt = (now - lastUpdateMs) / 1000.0;
  lastUpdateMs = now;
  if (dt > 2.0) dt = 0.5;

  sim_vehicle_speed += (random(-100, 101) / 100.0) * dt;
  sim_vehicle_speed = clampf(sim_vehicle_speed, 0.0, 120.0);

  float target_rpm = 800.0 + (sim_vehicle_speed * 25.0);
  sim_rpm += (target_rpm - sim_rpm) * 0.3 * dt;
  sim_rpm += vibration * (random(-50, 51) / 10.0);
  sim_rpm = clampf(sim_rpm, 600.0, 6500.0);

  float target_load = 20.0 + (sim_vehicle_speed / 4.0);
  sim_engine_load += (target_load - sim_engine_load) * 0.2 * dt;
  sim_engine_load += (random(-150, 151) / 100.0);
  sim_engine_load = clampf(sim_engine_load, 5.0, 100.0);

  float target_coolant = 88.0 + (mpu_temp - 25.0) * 0.5;
  sim_coolant_temp += (target_coolant - sim_coolant_temp) * 0.05 * dt;
  sim_coolant_temp += (random(-20, 21) / 100.0);
  sim_coolant_temp = clampf(sim_coolant_temp, 15.0, 150.0);

  sim_voltage = 13.8 - (vibration * 0.15) + (random(-5, 6) / 100.0);
  sim_voltage = clampf(sim_voltage, 9.0, 15.0);

  sim_odometer += sim_vehicle_speed * (dt / 3600.0);
  float engine_temp = sim_coolant_temp + (random(-100, 101) / 100.0);

  StaticJsonDocument<512> doc;
  doc["engine_temp_c"]      = round(engine_temp * 100.0) / 100.0;
  doc["engine_rpm"]         = round(sim_rpm * 10.0) / 10.0;
  doc["coolant_temp_c"]     = round(sim_coolant_temp * 100.0) / 100.0;
  doc["battery_voltage_v"]  = round(sim_voltage * 100.0) / 100.0;
  doc["vibration_level"]    = round(vibration * 1000.0) / 1000.0;
  doc["odometer_reading"]   = round(sim_odometer * 100.0) / 100.0;
  doc["engine_load"]        = round(sim_engine_load * 10.0) / 10.0;
  doc["vehicle_speed"]      = round(sim_vehicle_speed * 10.0) / 10.0;

  JsonObject raw = doc.createNestedObject("mpu6050_raw");
  raw["accel_x"]     = round(accel_x * 100.0) / 100.0;
  raw["accel_y"]     = round(accel_y * 100.0) / 100.0;
  raw["accel_z"]     = round(accel_z * 100.0) / 100.0;
  raw["gyro_x"]      = round(gyro_x * 100.0) / 100.0;
  raw["gyro_y"]      = round(gyro_y * 100.0) / 100.0;
  raw["gyro_z"]      = round(gyro_z * 100.0) / 100.0;
  raw["temp_c"]      = round(mpu_temp * 10.0) / 10.0;
  raw["total_accel"] = round(totalAccel * 100.0) / 100.0;
  raw["shock"]       = shock;

  String jsonString;
  serializeJson(doc, jsonString);
  server.send(200, "application/json", jsonString);
  
  Serial.println("Sent JSON data to client.");
}

// ================================
// SETUP
// ================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  // Connect to Wi-Fi
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected.");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // Start I2C using ESP32 pins
  Wire.begin(MPU_SDA, MPU_SCL);

  // Start MPU6050
  if (!mpu.begin()) {
    Serial.println("ERROR: MPU6050 not detected");
    while (1) {
      delay(100);
    }
  }

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  // Setup Web Server
  server.on("/data", HTTP_GET, handleData);
  server.begin();
  Serial.println("HTTP server started. Access /data for telemetry.");

  delay(500);
  lastUpdateMs = millis();
}

// ================================
// LOOP
// ================================

void loop() {
  server.handleClient();
  delay(2);
}
