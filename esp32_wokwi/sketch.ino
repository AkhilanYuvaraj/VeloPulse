#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>

// ================================
// MPU6050 PIN CONFIGURATION
// ================================

#define MPU_SDA 21
#define MPU_SCL 22

// ================================
// MPU6050 OBJECT
// ================================

Adafruit_MPU6050 mpu;

// ================================
// SIMULATED VEHICLE STATE
// ================================
// These values simulate realistic OBD-II parameters.
// The MPU6050 accelerometer drives vibration_level and
// influences the simulated engine behavior (e.g., rougher
// vibration → higher simulated RPM load).

float sim_rpm           = 1200.0;
float sim_coolant_temp  = 85.0;
float sim_voltage       = 13.8;
float sim_engine_load   = 25.0;
float sim_vehicle_speed = 60.0;
float sim_odometer      = 50000.0;

unsigned long lastUpdateMs = 0;

// ================================
// SETUP
// ================================

void setup() {

  Serial.begin(115200);
  delay(1000);

  // Start I2C using ESP32 pins
  Wire.begin(MPU_SDA, MPU_SCL);

  // Start MPU6050
  if (!mpu.begin()) {
    // Output error as JSON so Python side can detect it
    Serial.println("{\"error\":\"MPU6050 not detected\"}");
    while (1) {
      delay(100);
    }
  }

  // Set accelerometer range
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);

  // Set gyroscope range
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);

  // Set filter bandwidth
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  delay(500);
  lastUpdateMs = millis();
}

// ================================
// HELPER: Clamp a float value
// ================================

float clampf(float val, float lo, float hi) {
  if (val < lo) return lo;
  if (val > hi) return hi;
  return val;
}

// ================================
// LOOP
// ================================

void loop() {

  sensors_event_t accelEvent;
  sensors_event_t gyroEvent;
  sensors_event_t tempEvent;

  // Read MPU6050
  mpu.getEvent(&accelEvent, &gyroEvent, &tempEvent);

  // --- Real sensor data ---

  float accel_x = accelEvent.acceleration.x;
  float accel_y = accelEvent.acceleration.y;
  float accel_z = accelEvent.acceleration.z;

  float gyro_x = gyroEvent.gyro.x;
  float gyro_y = gyroEvent.gyro.y;
  float gyro_z = gyroEvent.gyro.z;

  float mpu_temp = tempEvent.temperature;

  // Total acceleration magnitude
  float totalAccel = sqrt(
    accel_x * accel_x +
    accel_y * accel_y +
    accel_z * accel_z
  );

  // Vibration = deviation from gravity (9.81 m/s²)
  // At rest this should be near 0, shaking increases it
  float vibration = abs(totalAccel - 9.81);

  // Shock detection
  bool shock = (totalAccel > 15.0 || totalAccel < 5.0);

  // --- Simulated OBD-II parameters ---
  // These evolve over time with small random drift,
  // influenced by real MPU6050 vibration readings.

  unsigned long now = millis();
  float dt = (now - lastUpdateMs) / 1000.0;
  lastUpdateMs = now;

  // Clamp dt to prevent jumps on first frame
  if (dt > 2.0) dt = 0.5;

  // Speed drifts randomly
  sim_vehicle_speed += (random(-100, 101) / 100.0) * dt;
  sim_vehicle_speed = clampf(sim_vehicle_speed, 0.0, 120.0);

  // RPM tracks speed, vibration adds noise (rougher = higher RPM variance)
  float target_rpm = 800.0 + (sim_vehicle_speed * 25.0);
  sim_rpm += (target_rpm - sim_rpm) * 0.3 * dt;
  sim_rpm += vibration * (random(-50, 51) / 10.0);  // vibration-driven jitter
  sim_rpm = clampf(sim_rpm, 600.0, 6500.0);

  // Engine load tracks speed
  float target_load = 20.0 + (sim_vehicle_speed / 4.0);
  sim_engine_load += (target_load - sim_engine_load) * 0.2 * dt;
  sim_engine_load += (random(-150, 151) / 100.0);
  sim_engine_load = clampf(sim_engine_load, 5.0, 100.0);

  // Coolant temp: use MPU temp as base offset, slowly drifts toward ~90°C
  float target_coolant = 88.0 + (mpu_temp - 25.0) * 0.5;  // MPU temp influences
  sim_coolant_temp += (target_coolant - sim_coolant_temp) * 0.05 * dt;
  sim_coolant_temp += (random(-20, 21) / 100.0);
  sim_coolant_temp = clampf(sim_coolant_temp, 15.0, 150.0);

  // Battery voltage: stable with small noise, drops under high vibration
  sim_voltage = 13.8 - (vibration * 0.15) + (random(-5, 6) / 100.0);
  sim_voltage = clampf(sim_voltage, 9.0, 15.0);

  // Odometer increments based on speed
  sim_odometer += sim_vehicle_speed * (dt / 3600.0);

  // Engine temp = coolant + small offset
  float engine_temp = sim_coolant_temp + (random(-100, 101) / 100.0);

  // ================================
  // BUILD JSON OUTPUT
  // ================================
  // Matches VeloPulseAI canonical ML feature schema exactly:
  //   engine_temp_c, engine_rpm, coolant_temp_c,
  //   battery_voltage_v, vibration_level,
  //   odometer_reading, engine_load, vehicle_speed
  //
  // Plus raw MPU6050 data for diagnostics.

  StaticJsonDocument<512> doc;

  // --- Canonical ML features (what the model needs) ---
  doc["engine_temp_c"]      = round(engine_temp * 100.0) / 100.0;
  doc["engine_rpm"]         = round(sim_rpm * 10.0) / 10.0;
  doc["coolant_temp_c"]     = round(sim_coolant_temp * 100.0) / 100.0;
  doc["battery_voltage_v"]  = round(sim_voltage * 100.0) / 100.0;
  doc["vibration_level"]    = round(vibration * 1000.0) / 1000.0;
  doc["odometer_reading"]   = round(sim_odometer * 100.0) / 100.0;
  doc["engine_load"]        = round(sim_engine_load * 10.0) / 10.0;
  doc["vehicle_speed"]      = round(sim_vehicle_speed * 10.0) / 10.0;

  // --- Raw MPU6050 diagnostics (extra, not required by ML) ---
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

  // Serialize and send
  serializeJson(doc, Serial);
  Serial.println();  // newline delimiter for Python readline()

  // 2 Hz update rate (matches VeloPulseAI pipeline)
  delay(500);
}
