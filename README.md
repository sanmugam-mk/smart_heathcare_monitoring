# Smart Healthcare Monitoring and Early Risk Detection System (AWS + IoT)

> **College Project Title**: Design and Implementation of a Cloud-Based Smart Healthcare Monitoring and Early Risk Detection System using AWS and IoT

---

## 🏥 Project Overview

This project is an advanced, enterprise-grade cloud + IoT healthcare solution. It upgrades a traditional Electronic Health Record (EHR) database into an event-driven, intelligent patient monitoring platform.

The system combines:
1. **IoT Edge Telemetry Ingestion**: ESP32 microcontroller with MAX30102 sensor publishing measured heart rate via MQTT over TLS 1.2. SpO2 and body temperature are stored only when provided by a sensor that actually measures them.
2. **Serverless Cloud Stream Processing**: AWS IoT Core broker + IoT Topic Rules executing AWS Lambda ingestion pipelines (`EHR-IoTIngest`).
3. **Clinical Decision Support Engine**: Multi-metric physiological rule engine calculating clinical risk scores (0–10) and classifying patient risk state (`NORMAL`, `WARNING`, `HIGH RISK`) with human-readable rationale.
4. **Automated Emergency Alerting**: Amazon SNS topic `EHR-HighRiskAlerts` dispatching urgent notifications when critical health conditions are detected.
5. **NoSQL Healthcare Database Architecture**: 5 DynamoDB tables (`Patients`, `VitalReadings`, `RiskAssessments`, `Alerts`, `Documents`) operating under `PAY_PER_REQUEST` billing.
6. **Presigned S3 Medical Document Vault**: Private S3 storage (`sanmugam-ehr-docs-2026`) with 100% Block Public Access and short-lived presigned upload/download URLs.
7. **Doctor Monitoring Web Dashboard**: MediChart UI with live vital cards, DynamoDB-backed Chart.js trends, risk badges, and emergency alert logs. Synthetic dashboard uploads are disabled to prevent replacing real patient readings.
8. **Cognito Role-Based Access Control**: Amazon Cognito User Pool (`ap-south-1_2uAqFquLU`) with JWT token authorization enforcing `doctor`, `staff`, and `admin` permissions.

---

## 📐 Architecture Diagram

```
ESP32 / Python Simulator ──> MQTT (TLS 1.2) ──> AWS IoT Core ──> IoT Topic Rule
                                                                      │
                                                                      ▼
                                                            AWS Lambda (EHR-IoTIngest)
                                                                      │
                         ┌────────────────────────────────────────────┼────────────────────────────────────────────┐
                         ▼                                            ▼                                            ▼
               DynamoDB: VitalReadings                     DynamoDB: RiskAssessments                       Amazon SNS (EHR-HighRiskAlerts)
           (Time-Series Sensor Logs)                     (Clinical Score & Rationale)                               (Triggered on HIGH Risk)
                         │                                            │                                            │
                         └────────────────────────────────────────────┼────────────────────────────────────────────┘
                                                                      ▼
                                                            Amazon API Gateway (sf4pw8iev0)
                                                                      │
                                                           Amazon Cognito JWT Auth
                                                                      │
                                                                      ▼
                                                       Doctor Monitoring Web Dashboard
                                                 (Vital Cards, Trend Charts, EHR, Presigned S3)
```

---

## 📁 Repository Directory Structure

```
smart-healthcare-ehr/
├── docs/                             # Complete Technical Documentation Suite
│   ├── architecture.md               # System Architecture Specification & Component Diagrams
│   ├── aws-resources.md              # Detailed AWS Resource Inventory & Region Configurations
│   ├── data-model.md                 # DynamoDB Schema Specifications & Access Pattern Matrix
│   ├── api-documentation.md          # REST API Specification (Endpoints, Headers, JSON payloads)
│   ├── security.md                   # Security Architecture, RBAC, Presigned S3 & IoT Encryption
│   ├── cost-optimization.md          # Serverless Cost Analysis & CloudWatch Retention Policy
│   ├── testing.md                    # End-to-End Test Matrix & Verification Commands
│   └── viva-notes.md                 # Project Defense Q&A & Viva Examination Guide
├── frontend/                         # Modern Healthcare Web Dashboard
│   ├── index.html                    # Cognito Sign-in Page (USER_PASSWORD_AUTH)
│   ├── dashboard.html                # Doctor Monitoring Dashboard (Vitals, Charts, Risk, Simulator)
│   └── documents.html                # Presigned S3 Medical Attachment Manager
├── lambda/                           # AWS Lambda Microservices
│   ├── iot_ingest_lambda.py          # Telemetry Ingestion & Clinical Risk Analysis Engine
│   ├── vitals_lambda.py              # GET API handler for Vitals, Trends & Alerts
│   ├── patient_crud_lambda.py        # EHR Patient Profile CRUD & Role Enforcement
│   └── document_lambda.py           # S3 Presigned URL Generator & Document Metadata Index
├── infrastructure/                   # Infrastructure Policies & ESP32 Code
│   ├── ehr-permissions-policy.json   # IAM Execution Policy
│   ├── iot-policy.json               # AWS IoT Device Security Policy
│   ├── iot-rule.json                 # AWS IoT Topic Rule SQL Mapping
│   └── esp32_smart_health.ino        # ESP32 C++ Arduino Firmware Sketch
└── scripts/                          # Sensor Simulation Tools
    └── sensor_simulator.py           # Synthetic Telemetry Generator Script
```

---

## 🚀 Quick Start Guide

### 1. Host the Web Dashboard locally
From the repository root, start a local static web server:

```bash
python -m http.server 8000 --directory frontend
```

Then open `http://localhost:8000` in a browser. Keep the terminal running while you use the site. This hosts the dashboard on your computer; it does not publish it to the public internet.
- **Doctor Credentials**: `doctor1@ehr.com`
- **Admin Credentials**: `admin1@ehr.com`

The dashboard uses the configured AWS Cognito and API Gateway endpoints, so those AWS resources must be active and configured for browser access for sign-in and live data features to work.

### 2. Build and upload the ESP32 firmware with PlatformIO
Install the PlatformIO IDE extension in VS Code, connect the ESP32 over USB, and open this repository as the PlatformIO project. Copy `infrastructure/wifi_secrets.example.h` to `infrastructure/wifi_secrets.h`, then set your Wi-Fi SSID and password in the local copy. The local secrets file is excluded from version control.

In the PlatformIO terminal, run:

```bash
py -m platformio run
py -m platformio run --target upload
py -m platformio device monitor
```

Alternatively, use PlatformIO's **Build**, **Upload**, and **Monitor** actions in VS Code. If the board is not detected, select its serial port and update the `board` value in `platformio.ini` if your ESP32 model is not the standard `esp32dev`.
The ESP32 requires a 2.4 GHz Wi-Fi network; set the phone hotspot to 2.4 GHz if it is configurable.

Before building, copy `infrastructure/aws_iot_secrets.example.h` to the ignored local file `infrastructure/aws_iot_secrets.h`, then insert a newly issued Amazon Root CA, device certificate, and private key. The sketch cannot connect until these credentials are installed. Never commit the local secrets file. The device certificate previously embedded in the sketch must be rotated before reuse.

### 3. Optional Synthetic Test Data
The standalone simulator writes synthetic records to DynamoDB through the ingestion Lambda. Never target a patient with live hardware readings; simulated records can become that patient's latest displayed reading. Prefer a separate test patient ID and do not run it against production patient records.

```bash
# Send isolated normal test data (use only in a non-production AWS environment)
python scripts/sensor_simulator.py --patient SIM-TEST --mode normal --count 5 --interval 1.0 --confirm-cloud-write
```

---

## 🔒 Security & Privacy
- **100% Private S3 Storage**: All 4 Block Public Access settings are `true`.
- **Short-Lived Presigned URLs**: 300s TTL for document operations.
- **Cognito JWT Validation**: Enforced at API Gateway for all REST endpoints.
- **Zero Fixed Cost**: 100% Serverless Pay-Per-Use architecture.
