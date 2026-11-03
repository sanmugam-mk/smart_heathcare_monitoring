# Viva Examination Preparation & Q&A Defense Guide

## Quick Project Elevator Pitch

> "Our project is a serverless, event-driven Smart Healthcare Monitoring and Early Risk Detection System built on AWS and IoT. It combines real-time vital telemetry collection (Heart Rate, SpO2, Body Temperature via ESP32 hardware and synthetic simulators), cloud-native stream processing via AWS IoT Core and Lambda, an automated Clinical Decision Support Engine for early health risk classification (NORMAL, WARNING, HIGH RISK), automated physician alerts via Amazon SNS, and an interactive Doctor Dashboard displaying patient EHR records, presigned S3 medical documents, and real-time Chart.js vital trend line graphs."

---

## Key Technical Questions & Answers

### Q1: What makes this project an "Advanced Cloud & IoT System" rather than a basic CRUD application?
**Answer**:
A basic CRUD app simply stores data when a user manually clicks save. Our system implements an **event-driven, near-real-time streaming processing architecture**. Telemetry flows asynchronously from IoT edge sensors over MQTT TLS 1.2 to AWS IoT Core, triggering AWS Lambda instantly. The backend continuously computes multi-metric clinical risk scores, identifies physiological abnormalities, and automatically triggers high-risk alerts via Amazon SNS without human intervention.

### Q2: Why choose AWS IoT Core instead of sending HTTP POST requests directly from ESP32 to API Gateway?
**Answer**:
1. **Protocol Efficiency**: MQTT is an extremely lightweight pub/sub protocol with minimal header overhead compared to HTTP/REST, making it ideal for battery-constrained ESP32 microcontrollers.
2. **Persistent Connection & Security**: AWS IoT Core provides mutual authentication via X.509 certificates and TLS 1.2.
3. **Decoupled Rules Engine**: AWS IoT Topic Rules allow routing incoming telemetry to multiple destinations (e.g. Lambda, S3, Kinesis) without modifying firmware code.

### Q3: Explain how the Clinical Decision Support Engine calculates Risk Level.
**Answer**:
The rule engine evaluates 3 core metrics against medical clinical thresholds:
- **Heart Rate**: Normal 60-100 BPM | Warning 50-59 or 101-120 | Critical <50 or >120 (+4 points).
- **SpO2 (Oxygen Saturation)**: Normal ≥95% | Mild Hypoxia 92-94% (+2 pts) | Critical Hypoxia <92% (+4 pts).
- **Body Temperature**: Normal 36.5-37.5°C | Elevated 37.6-38.2°C (+1 pt) | High Fever >38.2°C (+3 pts).

Cumulative Risk Score:
- **NORMAL**: Score 0–1.
- **WARNING**: Score 2–4 (Single mild metric deviation).
- **HIGH**: Score ≥ 5 OR any critical threshold breach (e.g. SpO2 < 92%). Triggers Amazon SNS alert.

### Q4: How is data privacy and security handled for medical files in S3?
**Answer**:
1. The S3 bucket `sanmugam-ehr-docs-2026` has **Block Public Access enabled on all 4 settings** (100% private).
2. Direct access to S3 objects is blocked.
3. The frontend requests short-lived (300-second TTL) presigned `PUT` and `GET` URLs generated dynamically by `EHR-Documents` Lambda after validating the user's Cognito JWT ID Token.

### Q5: How do you justify the database design for `VitalReadings` in DynamoDB?
**Answer**:
`VitalReadings` uses a composite primary key:
- **Partition Key**: `PatientId` (co-locates all telemetry for a specific patient on the same physical partition).
- **Sort Key**: `Timestamp` (ISO-8601 UTC string).
Because DynamoDB maintains items sorted by the RANGE key, we can execute single-digit millisecond time-range queries (`BETWEEN :t1 AND :t2`) for trend graphs or fetch the latest reading instantly using `ScanIndexForward=False, Limit=1`.

### Q6: What is the total operational cost of this project?
**Answer**:
$0.00 / month under the AWS Free Tier. The architecture is 100% serverless with PAY_PER_REQUEST billing for DynamoDB, 1 Million free requests/month for Lambda & API Gateway, 2.25 Million free messages for IoT Core, and a 7-day CloudWatch log retention policy preventing log accumulation.
