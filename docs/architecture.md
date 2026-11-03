# Architecture Specification

## Project Title
**Design and Implementation of a Cloud-Based Smart Healthcare Monitoring and Early Risk Detection System using AWS and IoT**

---

## System Overview

The system is a hybrid cloud-software (80%) and lightweight IoT-hardware (20%) solution designed for continuous patient vital sign monitoring and early clinical risk detection. It extends a traditional Electronic Health Record (EHR) system into an event-driven, serverless intelligent healthcare platform.

```
+---------------------------------------------------------------------------------------------------+
|                                     HARDWARE / SIMULATOR LAYER                                    |
|                                                                                                   |
|  +----------------------------------+            +---------------------------------------------+  |
|  | ESP32 Dev Board + MAX30102 PPG   |            | Synthetic Sensor Simulator (Python Script)  |  |
|  | Heart Rate, SpO2 & Temp Sensors  |            | Simulates Normal, Warning, High Risk Data   |  |
|  +----------------------------------+            +---------------------------------------------+  |
+----------------------------------- \------------------/ ------------------------------------------+
                                      \                /
                                  MQTT (TLS 1.2, Port 8883)
                                Topic: healthcare/vitals/{PatientId}
                                        \            /
                                         v          v
+---------------------------------------------------------------------------------------------------+
|                                         AWS CLOUD BACKEND                                         |
|                                         (ap-south-1 Region)                                       |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | AWS IoT Core (Broker & Rules Engine)                                                        |  |
|  | Topic Rule: SELECT * FROM 'healthcare/vitals/+'                                              |  |
|  +----------------------------------------------+----------------------------------------------+  |
|                                                 |                                                 |
|                                                 v                                                 |
|  +---------------------------------------------------------------------------------------------+  |
|  | AWS Lambda (EHR-IoTIngest & Risk Engine)                                                    |  |
|  | - Validates & normalizes vital telemetry                                                    |  |
|  | - Executes Multi-Parameter Clinical Decision Engine                                         |  |
|  | - Computes Risk Score (0-10) and Risk Level (NORMAL / WARNING / HIGH)                        |  |
|  | - Generates clear medical explanations for abnormalities                                   |  |
|  +--------+--------------------+------------------------------+--------------------------------+  |
|           |                    |                              |                                   |
|           v                    v                              v                                   |
|  +-----------------+  +-----------------+           +--------------------+                        |
|  | DynamoDB        |  | DynamoDB        |           | Amazon SNS Topic   |                        |
|  | VitalReadings   |  | RiskAssessments |           | EHR-HighRiskAlerts |                        |
|  | (Time-Series)   |  | (Risk History)  |           | (Triggered on HIGH)|                        |
|  +-----------------+  +-----------------+           +----------+---------+                        |
|                                                                |                                  |
|                                                                v                                  |
|                                                     +--------------------+                        |
|                                                     | DynamoDB: Alerts   |                        |
|                                                     | (Audit Log)        |                        |
|                                                     +--------------------+                        |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | Amazon API Gateway HTTP API (sf4pw8iev0)                                                    |  |
|  | Secured by Amazon Cognito JWT Authorizer                                                    |  |
|  +----------------------------------------------+----------------------------------------------+  |
|                                                 |                                                 |
|                                                 v                                                 |
|  +---------------------------------------------------------------------------------------------+  |
|  | AWS Lambda Services (EHR-PatientCRUD, EHR-Vitals, EHR-Documents)                            |  |
|  | - Direct DynamoDB queries for patient demographics, time-series vitals & risk assessments   |  |
|  | - S3 Presigned URL generation for secure document uploads/downloads                         |  |
|  +--------+---------------------------------------------------+--------------------------------+  |
|           |                                                   |                                   |
|           v                                                   v                                   |
|  +-----------------+                                 +---------------------------------+          |
|  | DynamoDB        |                                 | Amazon S3                       |          |
|  | Patients        |                                 | sanmugam-ehr-docs-2026          |          |
|  | (EHR Core Data) |                                 | Private Medical Document Vault  |          |
|  +-----------------+                                 +---------------------------------+          |
+---------------------------------------------------------------------------------------------------+
                                                  ^
                                                  | HTTPS / REST API + JWT Bearer Token
                                                  |
+-------------------------------------------------+-------------------------------------------------+
|                                           PRESENTATION LAYER                                      |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | Doctor Monitoring Web Dashboard                                                             |  |
|  | - Patient Demographics & Medical Profile                                                    |  |
|  | - Real-time Vital Sign Monitoring Cards (Color-Coded Status)                                |  |
|  | - Vital Trend Graphs (Heart Rate, SpO2, Temp over time via Chart.js)                        |  |
|  | - Risk Assessment Engine Rationale & Active Abnormalities Badge                              |  |
|  | - High-Risk Alert Notification Banner & Audit Log                                           |  |
|  | - Presigned S3 Medical Document Manager                                                     |  |
|  | - Integrated Sensor Simulator Control Console                                               |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

---

## Core AWS Services & Justifications

| AWS Service | Role in Architecture | Technical Justification |
| :--- | :--- | :--- |
| **AWS IoT Core** | Message Broker & Ingestion | Connects ESP32 securely via MQTT over TLS 1.2; routes sensor messages using SQL rules with zero server maintenance. |
| **AWS Lambda** | Event-Driven Compute | Executes ingestion, clinical risk analysis, and backend API logic synchronously or asynchronously; 100% serverless, zero idle cost. |
| **Amazon DynamoDB** | NoSQL Data Store | Fast, predictable single-digit millisecond latency for patient profiles, time-series vital logs, and risk assessments using PAY_PER_REQUEST billing. |
| **Amazon S3** | Object Storage | Store private medical attachments (PDFs, lab reports) securely with server-side encryption and granular presigned URL time-based access. |
| **Amazon SNS** | Notification Broker | Immediately dispatches SMS/Email notifications to attending physicians when HIGH risk status is detected. |
| **Amazon API Gateway** | HTTP API Management | Secure, low-latency REST endpoints connecting web dashboard to Lambda microservices; handles CORS, route matching, and JWT authorization. |
| **Amazon Cognito** | Authentication & RBAC | Manages user identity pools, issue JWT ID/Access tokens, and enforces role-based access control (Doctor, Staff, Admin). |
| **Amazon CloudWatch** | Monitoring & Logging | Captures Lambda execution logs, system errors, and provides centralized metrics for operational visibility. |

---

## Data Flow Sequences

### Sequence 1: Sensor Ingestion & Risk Evaluation
1. **Sensor Measurement**: ESP32 or Python Simulator measures/generates `HeartRate`, `SpO2`, `Temperature` for `PatientId` (e.g. `P001`).
2. **MQTT Telemetry Publish**: Sensor publishes JSON payload to `healthcare/vitals/P001` on AWS IoT Core endpoint.
3. **IoT Topic Rule Execution**: IoT Rule `EHR_VitalIngestionRule` matches topic pattern `healthcare/vitals/+` and triggers Lambda `EHR-IoTIngest`.
4. **Data Persistence**: `EHR-IoTIngest` saves raw telemetry item to DynamoDB table `VitalReadings`.
5. **Clinical Decision Evaluation**: `EHR-IoTIngest` runs rule engine against medical threshold parameters:
   - Evaluates individual metric deviations (BPM, SpO2 %, Temp °C).
   - Calculates cumulative `RiskScore` (0 to 10).
   - Classifies `RiskLevel` (`NORMAL`, `WARNING`, `HIGH`).
   - Generates human-readable clinical explanation string list.
6. **Risk Persistence**: Saves evaluation output to DynamoDB table `RiskAssessments`.
7. **Alert Dispatch (High Risk Only)**: If `RiskLevel == 'HIGH'`:
   - Formats urgent clinical message.
   - Publishes payload to Amazon SNS Topic `EHR-HighRiskAlerts`.
   - Writes alert audit item to DynamoDB table `Alerts`.

### Sequence 2: Doctor Dashboard Real-Time Monitoring
1. **Authentication**: Doctor enters credentials at `index.html` → Authenticated against Cognito User Pool → Receives signed JWT `idToken`.
2. **Dashboard Fetch**: Web dashboard opens `dashboard.html` → Includes `Authorization: Bearer <idToken>` in request header to API Gateway `sf4pw8iev0`.
3. **API Routing**: API Gateway validates JWT signature and audience → Forwards request to `EHR-Vitals` Lambda.
4. **Data Retrieval**: `EHR-Vitals` queries DynamoDB `Patients`, `VitalReadings`, `RiskAssessments`, and `Alerts`.
5. **UI Rendering**: Dashboard displays color-coded vital sign cards, Chart.js time-series trend line graphs, active risk level badge, abnormality explanation drawer, and high-risk alert log.

---

## Viva Examination Defense Notes

> [!TIP]
> **Key Viva Question: Why choose a Serverless & Event-Driven Architecture over traditional EC2 + RDS?**
> - **Answer**: Healthcare IoT telemetry is inherently event-driven and variable. A serverless architecture (AWS IoT Core + Lambda + DynamoDB) scales automatically from 0 to thousands of sensor messages per second without provisioning or paying for idle servers. It eliminates server maintenance, operating system patching, and provides high availability across multiple Availability Zones natively, making it cost-efficient ($0 idle cost) and enterprise-resilient.

> [!TIP]
> **Key Viva Question: How is Security and Data Privacy ensured?**
> - **Answer**: Security is enforced at 4 distinct layers:
>   1. **In-Transit Encryption**: All IoT messages use TLS 1.2; API requests use HTTPS/TLS 1.3.
>   2. **Identity & Authorization**: API Gateway enforces Cognito JWT validation; microservices verify group claims (`admin`, `doctor`).
>   3. **At-Rest Encryption & Storage Privacy**: S3 bucket is 100% private with Block Public Access enabled; files are accessed strictly via short-lived (300s TTL) presigned S3 URLs generated on demand.
>   4. **Infrastructure Security**: Lambda functions run with strict IAM least-privilege roles, restricting actions to specific DynamoDB table ARNs and SNS topic ARNs.
