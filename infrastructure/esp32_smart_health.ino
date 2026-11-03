/*
 * Smart Healthcare Monitoring System
 * ESP32 + MAX30102 + AWS IoT Core
 *
 * Connections:
 * MAX30102 VCC -> ESP32 3.3V
 * MAX30102 GND -> ESP32 GND
 * MAX30102 SDA -> GPIO 21
 * MAX30102 SCL -> GPIO 22
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <time.h>
#include <string.h>
#include <MAX30105.h>
#include "heartRate.h"
#include "spo2_algorithm.h"
#include "wifi_secrets.h"
#include "aws_iot_secrets.h"

const char* AWS_IOT_ENDPOINT = "a1uyfass1g887i-ats.iot.ap-south-1.amazonaws.com";
const char* AWS_IOT_TOPIC = "smart-healthcare/P001/vitals";
const char* PATIENT_ID = "P001";

const uint16_t spo2BufferLength = 100;
const uint8_t spo2RecalculateSamples = 25;
const long fingerIrThreshold = 50000;

WiFiClientSecure net;
PubSubClient client(net);
MAX30105 particleSensor;

uint32_t irBuffer[spo2BufferLength];
uint32_t redBuffer[spo2BufferLength];
uint16_t spo2SampleCount = 0;
uint8_t samplesSinceSpo2Calculation = 0;
int32_t measuredSpO2 = 0;
int8_t validSpO2 = 0;
bool spo2BufferInitialized = false;
bool sensorReady = false;
bool fingerDetected = false;
unsigned long lastMsg = 0;
unsigned long lastReconnect = 0;
unsigned long lastSensorLog = 0;
unsigned long lastSensorSample = 0;
unsigned long lastBeat = 0;
unsigned long lastValidBeat = 0;
float averageBPM = 0;

const unsigned long publishInterval = 3000;
const unsigned long reconnectInterval = 5000;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
}

void connectAWS() {
  if (WiFi.status() != WL_CONNECTED) return;

  net.setCACert(AWS_CERT_CA);
  net.setCertificate(AWS_CERT_CRT);
  net.setPrivateKey(AWS_CERT_PRIVATE);
  client.setServer(AWS_IOT_ENDPOINT, 8883);
  client.setKeepAlive(60);
  client.setBufferSize(512);

  Serial.println("Connecting to AWS IoT Core...");
  if (client.connect("SmartHealth_ESP32_P001")) {
    Serial.println("AWS IoT Core connected");
  } else {
    Serial.printf("AWS connection failed. MQTT state: %d\n", client.state());
  }
}

void initializeSensor() {
  Wire.begin(21, 22);
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 not found");
    sensorReady = false;
    return;
  }

  particleSensor.setup(60, 4, 2, 100, 411, 4096);
  particleSensor.setPulseAmplitudeRed(0x1F);
  particleSensor.setPulseAmplitudeIR(0x1F);
  particleSensor.setPulseAmplitudeGreen(0);
  sensorReady = true;
  Serial.println("MAX30102 initialized");
}

void resetFingerMeasurements() {
  fingerDetected = false;
  averageBPM = 0;
  lastBeat = 0;
  lastValidBeat = 0;
  measuredSpO2 = 0;
  validSpO2 = 0;
  spo2SampleCount = 0;
  samplesSinceSpo2Calculation = 0;
  spo2BufferInitialized = false;
}

void processSensorSample(uint32_t irValue, uint32_t redValue) {
  if (irValue < fingerIrThreshold) {
    resetFingerMeasurements();
    return;
  }

  fingerDetected = true;
  if (checkForBeat(irValue)) {
    const unsigned long currentTime = millis();
    if (lastBeat > 0) {
      const unsigned long delta = currentTime - lastBeat;
      if (delta > 0) {
        const float bpm = 60000.0f / delta;
        if (bpm >= 40 && bpm <= 180) {
          averageBPM = averageBPM == 0 ? bpm : (averageBPM * 0.7f) + (bpm * 0.3f);
          lastValidBeat = currentTime;
          Serial.printf("Heart Rate: %.1f BPM\n", averageBPM);
        }
      }
    }
    lastBeat = currentTime;
  }

  if (spo2SampleCount < spo2BufferLength) {
    irBuffer[spo2SampleCount] = irValue;
    redBuffer[spo2SampleCount] = redValue;
    spo2SampleCount++;
  } else {
    memmove(irBuffer, irBuffer + 1, (spo2BufferLength - 1) * sizeof(irBuffer[0]));
    memmove(redBuffer, redBuffer + 1, (spo2BufferLength - 1) * sizeof(redBuffer[0]));
    irBuffer[spo2BufferLength - 1] = irValue;
    redBuffer[spo2BufferLength - 1] = redValue;
  }

  if (spo2SampleCount == spo2BufferLength) {
    samplesSinceSpo2Calculation++;
    if (!spo2BufferInitialized || samplesSinceSpo2Calculation >= spo2RecalculateSamples) {
      int32_t calculatedHeartRate = 0;
      int8_t validHeartRate = 0;
      maxim_heart_rate_and_oxygen_saturation(
        irBuffer,
        spo2BufferLength,
        redBuffer,
        &measuredSpO2,
        &validSpO2,
        &calculatedHeartRate,
        &validHeartRate
      );
      spo2BufferInitialized = true;
      samplesSinceSpo2Calculation = 0;
      if (validSpO2 && measuredSpO2 >= 70 && measuredSpO2 <= 100) {
        Serial.printf("SpO2: %ld%%\n", static_cast<long>(measuredSpO2));
      } else {
        validSpO2 = 0;
      }
    }
  }
}

void readSensorSamples() {
  if (!sensorReady) return;

  particleSensor.check();
  while (particleSensor.available()) {
    const uint32_t irValue = particleSensor.getIR();
    const uint32_t redValue = particleSensor.getRed();
    particleSensor.nextSample();

    const unsigned long sampleTime = millis();
    if (lastSensorSample > 0 && sampleTime - lastSensorSample > 1000) {
      resetFingerMeasurements();
    }
    lastSensorSample = sampleTime;

    if (sampleTime - lastSensorLog >= 1000) {
      lastSensorLog = sampleTime;
      Serial.printf("IR signal: %lu\n", static_cast<unsigned long>(irValue));
    }
    processSensorSample(irValue, redValue);
  }
}

void publishVitals() {
  if (!client.connected()) {
    Serial.println("AWS MQTT not connected");
    return;
  }
  StaticJsonDocument<256> doc;
  const bool sensorActive = sensorReady && lastSensorSample > 0 &&
    millis() - lastSensorSample <= 2000;
  doc["PatientId"] = PATIENT_ID;
  doc["SensorReady"] = sensorActive;
  doc["FingerDetected"] = sensorActive && fingerDetected;
  doc["DeviceID"] = "ESP32_MAX30102";
  doc["Source"] = "ESP32";
  if (sensorActive && fingerDetected && averageBPM > 0 && lastValidBeat > 0 &&
      millis() - lastValidBeat <= 10000) {
    doc["HeartRate"] = averageBPM;
  }
  if (sensorActive && fingerDetected && validSpO2) {
    doc["SpO2"] = measuredSpO2;
  }

  const time_t now = time(nullptr);
  if (now > 1700000000) {
    struct tm utcTime;
    char timestamp[25];
    if (gmtime_r(&now, &utcTime) &&
        strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &utcTime)) {
      doc["Timestamp"] = timestamp;
    }
  }

  char jsonBuffer[256];
  const size_t payloadLength = serializeJson(doc, jsonBuffer, sizeof(jsonBuffer));
  if (payloadLength == 0) {
    Serial.println("Could not serialize telemetry");
    return;
  }

  if (client.publish(AWS_IOT_TOPIC, jsonBuffer)) {
    Serial.printf("MQTT sensor status published (%u bytes, finger %s)\n",
      static_cast<unsigned>(payloadLength), sensorActive && fingerDetected ? "detected" : "not detected");
  } else {
    Serial.println("MQTT publish failed");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\nSmart Healthcare System Starting...");
  initializeSensor();
  connectWiFi();
  connectAWS();
  Serial.println("System setup completed");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (!client.connected()) {
    if (millis() - lastReconnect >= reconnectInterval) {
      lastReconnect = millis();
      connectAWS();
    }
  } else {
    client.loop();
  }

  readSensorSamples();
  if (millis() - lastMsg >= publishInterval) {
    lastMsg = millis();
    publishVitals();
  }
}
