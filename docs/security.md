# Security Architecture & Data Protection

## Security Design Principles

Security in the Smart Healthcare Monitoring System is enforced across all architectural layers in compliance with HIPAA-inspired best practices and AWS Security Pillar guidelines:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Identity & Access: Cognito User Pools & JWT Tokens       │
├─────────────────────────────────────────────────────────────┤
│ 2. API Security: API Gateway JWT Authorizer & CORS           │
├─────────────────────────────────────────────────────────────┤
│ 3. Data Protection: Private S3 Bucket & Presigned URLs      │
├─────────────────────────────────────────────────────────────┤
│ 4. Hardware/IoT Security: TLS 1.2 & X.509 Device Certs      │
├─────────────────────────────────────────────────────────────┤
│ 5. Least Privilege Execution: Fine-grained IAM Policies     │
└─────────────────────────────────────────────────────────────┘
```

---

## Security Implementation Details

### 1. Identity Management & Role-Based Access Control (RBAC)
- **Authentication**: Managed via Amazon Cognito User Pools (`ap-south-1_2uAqFquLU`).
- **Token Verification**: User requests must include a signed JWT ID Token in the `Authorization: Bearer <token>` header.
- **Role Hierarchy**:
  - `doctor`: Access to view patient lists, real-time vitals, trend graphs, risk evaluations, upload medical documents, and delete patient records.
  - `staff`: Access to register patient records and upload clinical files.
  - `admin`: Access to perform destructive operations (`DELETE /patients`, `DELETE /documents`).
- **In-Lambda Role Enforcement**: Backend Lambdas (`patient_crud_lambda.py`, `document_lambda.py`) extract the `cognito:groups` array claim from JWT payloads and reject unauthorized requests with HTTP 403 Forbidden.

### 2. S3 Bucket Privacy & Presigned URL Architecture
- S3 Bucket `sanmugam-ehr-docs-2026` is **100% private**.
- **Block Public Access Enabled**:
  - `BlockPublicAcls = true`
  - `IgnorePublicAcls = true`
  - `BlockPublicPolicy = true`
  - `RestrictPublicBuckets = true`
- **Zero Direct S3 Exposure**: Web dashboard users never receive direct S3 credentials or persistent object URLs.
- **Presigned URLs**: S3 upload (presigned POST) and download (`get_object`) URLs are generated dynamically by `EHR-Documents` Lambda with a short time-to-live (TTL = 300 seconds).

### 3. IoT Edge Security & X.509 Certificates
- Telemetry streams from physical ESP32 devices or simulators use **MQTT over TLS 1.2** (Port 8883).
- Devices authenticate to AWS IoT Core using **X.509 Certificates** signed by Amazon Root CA.
- **Granular IoT Policy**: Policy `EHR_IoTDevicePolicy` restricts MQTT publish privileges specifically to topic pattern `healthcare/vitals/*`.

### 4. IAM Least Privilege Policy
- Execution Role `EHR-Lambda-Execution-Role` restricts DynamoDB access exclusively to explicit table ARNs (`Patients`, `VitalReadings`, `RiskAssessments`, `Alerts`, `Documents`) and SNS publish permissions to topic `EHR-HighRiskAlerts`.
- Zero wildcard (`*`) resource permissions on sensitive data operations.

### 5. Logging Security & Data Hygiene
- Credentials, access keys, passwords, and Cognito tokens are **never printed to logs**.
- Synthetic patient identifiers (e.g. `P001`, `Jane Doe`) are used for college project demonstration; no real Protected Health Information (PHI) is stored.
