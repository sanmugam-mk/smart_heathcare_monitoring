#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>

#include "credentials.h"

static const char WIFI_SSID_VALUE[] = WIFI_SSID;
static const char WIFI_PASSWORD_VALUE[] = WIFI_PASSWORD;
static const char AWS_IOT_ENDPOINT[] = "a1uyfass1g887i-ats.iot.ap-south-1.amazonaws.com";
static const char AWS_IOT_TOPIC[] = "smart-healthcare/P001/vitals";
static const char PATIENT_ID[] = "P001";
static const char DEVICE_ID[] = "ESP32_SIMULATOR";
static const uint32_t READING_INTERVAL_MS = 5000;

enum SimulationMode { NORMAL_MODE, WARNING_MODE, HIGH_RISK_MODE };
static SimulationMode simulationMode = NORMAL_MODE;

struct Vitals {
  float heartRate;
  float spo2;
  float temperature;
};

static Vitals currentVitals = {78.0f, 98.0f, 36.8f};
static WiFiClientSecure secureClient;
static PubSubClient mqttClient(secureClient);
static uint32_t lastReadingAt = 0;
static uint32_t lastWifiAttemptAt = 0;
static uint32_t lastMqttAttemptAt = 0;
static bool clockSynchronized = false;

const char *modeName() {
  switch (simulationMode) {
    case WARNING_MODE: return "WARNING";
    case HIGH_RISK_MODE: return "HIGH_RISK";
    default: return "NORMAL";
  }
}

void modeRanges(float &hrLow, float &hrHigh, float &spo2Low, float &spo2High,
                float &tempLow, float &tempHigh) {
  if (simulationMode == WARNING_MODE) {
    hrLow = 100; hrHigh = 115; spo2Low = 92; spo2High = 95;
    tempLow = 37.6f; tempHigh = 38.2f;
  } else if (simulationMode == HIGH_RISK_MODE) {
    hrLow = 120; hrHigh = 140; spo2Low = 85; spo2High = 91;
    tempLow = 38.5f; tempHigh = 39.5f;
  } else {
    hrLow = 65; hrHigh = 95; spo2Low = 96; spo2High = 100;
    tempLow = 36.3f; tempHigh = 37.4f;
  }
}

float moveToward(float current, float target, float maxStep) {
  const float difference = target - current;
  if (fabsf(difference) <= maxStep) return target;
  return current + (difference > 0 ? maxStep : -maxStep);
}

void generateReading() {
  float hrLow, hrHigh, spo2Low, spo2High, tempLow, tempHigh;
  modeRanges(hrLow, hrHigh, spo2Low, spo2High, tempLow, tempHigh);

  const float hrTarget = random((long)hrLow, (long)hrHigh + 1);
  const float spo2Target = random((long)spo2Low, (long)spo2High + 1);
  const float tempTarget = random((long)(tempLow * 10), (long)(tempHigh * 10) + 1) / 10.0f;
  currentVitals.heartRate = moveToward(currentVitals.heartRate, hrTarget, 3.0f);
  currentVitals.spo2 = moveToward(currentVitals.spo2, spo2Target, 1.0f);
  currentVitals.temperature = moveToward(currentVitals.temperature, tempTarget, 0.1f);

  currentVitals.heartRate = constrain(currentVitals.heartRate, hrLow, hrHigh);
  currentVitals.spo2 = constrain(currentVitals.spo2, spo2Low, spo2High);
  currentVitals.temperature = constrain(currentVitals.temperature, tempLow, tempHigh);
}

bool getIsoTimestamp(char *output, size_t outputSize) {
  time_t now = time(nullptr);
  if (now < 1700000000) return false;
  struct tm utcTime;
  gmtime_r(&now, &utcTime);
  strftime(output, outputSize, "%Y-%m-%dT%H:%M:%SZ", &utcTime);
  return true;
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  const uint32_t now = millis();
  if (now - lastWifiAttemptAt < 10000) return;
  lastWifiAttemptAt = now;
  Serial.println("Connecting to WiFi...");
  WiFi.begin(WIFI_SSID_VALUE, WIFI_PASSWORD_VALUE);
}

void connectMqtt() {
  if (mqttClient.connected() || WiFi.status() != WL_CONNECTED) return;
  const uint32_t now = millis();
  if (now - lastMqttAttemptAt < 5000) return;
  lastMqttAttemptAt = now;
  Serial.println("Connecting to AWS IoT Core...");
  if (mqttClient.connect(DEVICE_ID)) {
    Serial.println("AWS IoT Core Connected!");
  } else {
    Serial.printf("AWS IoT Core connection failed (state %d); retrying.\n", mqttClient.state());
  }
}

void publishReading() {
  if (!clockSynchronized) {
    Serial.println("Waiting for synchronized UTC clock; reading not published.");
    return;
  }
  char timestamp[25];
  if (!getIsoTimestamp(timestamp, sizeof(timestamp))) {
    Serial.println("UTC timestamp unavailable; reading not published.");
    return;
  }

  StaticJsonDocument<256> payload;
  payload["PatientId"] = PATIENT_ID;
  payload["HeartRate"] = (int)lroundf(currentVitals.heartRate);
  payload["SpO2"] = (int)lroundf(currentVitals.spo2);
  payload["Temperature"] = roundf(currentVitals.temperature * 10.0f) / 10.0f;
  payload["DeviceID"] = DEVICE_ID;
  payload["Source"] = "ESP32_SIMULATED";
  payload["Timestamp"] = timestamp;
  payload["SimulationMode"] = modeName();

  char message[256];
  const size_t length = serializeJson(payload, message, sizeof(message));
  if (length == 0 || !mqttClient.publish(AWS_IOT_TOPIC, message, false)) {
    Serial.println("MQTT publish failed.");
    return;
  }

  Serial.printf("\nSimulation Mode: %s\nPatient ID: %s\n", modeName(), PATIENT_ID);
  Serial.printf("Heart Rate: %d BPM\nSpO2: %d%%\nTemperature: %.1f C\n",
                (int)lroundf(currentVitals.heartRate), (int)lroundf(currentVitals.spo2),
                currentVitals.temperature);
  Serial.println("MQTT Data Published Successfully!");
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nSmart Healthcare System Starting...");
  Serial.println("SIMULATED VITAL DATA - FOR DEMONSTRATION ONLY.");
  Serial.printf("Simulation Mode: %s\nPatient ID: %s\n", modeName(), PATIENT_ID);
  randomSeed((uint32_t)esp_random());

  WiFi.mode(WIFI_STA);
  secureClient.setCACert(AWS_ROOT_CA);
  secureClient.setCertificate(AWS_DEVICE_CERT);
  secureClient.setPrivateKey(AWS_DEVICE_PRIVATE_KEY);
  mqttClient.setServer(AWS_IOT_ENDPOINT, 8883);
  mqttClient.setBufferSize(512);
  mqttClient.setKeepAlive(60);

  configTime(0, 0, "pool.ntp.org", "time.google.com");
  connectWifi();
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    if (lastWifiAttemptAt != 0 && !clockSynchronized) {
      struct tm timeInfo;
      clockSynchronized = getLocalTime(&timeInfo, 100);
    }
    if (lastWifiAttemptAt != 0 && WiFi.localIP() != IPAddress(0, 0, 0, 0)) {
      static bool reportedWifi = false;
      if (!reportedWifi) {
        Serial.println("WiFi Connected!");
        reportedWifi = true;
      }
    }
    connectMqtt();
    mqttClient.loop();
  } else {
    connectWifi();
  }

  const uint32_t now = millis();
  if (now - lastReadingAt >= READING_INTERVAL_MS) {
    lastReadingAt = now;
    generateReading();
    if (mqttClient.connected()) publishReading();
    else Serial.println("Not connected to AWS IoT Core; reading not published.");
  }
  delay(10);
}
