# Architecture and data flow

## Telemetry flow

```text
ESP32 simulator
  -> MQTT over TLS 1.2/1.3, client certificate authentication
  -> AWS IoT Core topic smart-healthcare/P001/vitals
  -> SmartHealthcareProcessVitals IoT rule
  -> ProcessVitals Lambda
  -> VitalReadings DynamoDB
  -> RiskAssessment Lambda -> RiskAssessments DynamoDB
  -> Alerts DynamoDB; SNS publish only for HIGH category
  -> Cognito JWT-protected API Gateway HTTP API
  -> MediChart frontend
```

The dashboard does not synthesize telemetry. A blank state means no stored AWS reading was returned. The browser polls the protected API every five seconds and charts API response data.

## Components and table keys

| Resource | Primary key / role |
|---|---|
| Patients | `PatientId` |
| VitalReadings | `PatientId` / `Timestamp` |
| RiskAssessments | `PatientId` / `Timestamp` |
| Alerts | `AlertId`; `PatientAlertsIndex` partitions by PatientId and sorts by Timestamp |
| Documents | `PatientId` / `DocumentId` |
| Cognito `doctor` group | Authenticated monitoring and patient/document use |
| Cognito `admin` group | Additional permission to delete patient records and resolve alerts |
| S3 | Private encrypted bucket; only short-lived signed form uploads/downloads |

All stored timestamps are UTC ISO 8601 strings. Vital timestamp order is lexicographically sortable. An exact repeated patient/timestamp telemetry record is rejected rather than overwritten.

## Lambda responsibilities

- `process_vitals.py`: validate JSON, patient/topic identity and simulation-mode bounds; store readings; synchronously invoke risk assessment; store abnormal alerts; publish high-category notifications.
- `patient_crud.py`: authenticated patient listing, registration, retrieval and update; Cognito group enforcement for delete.
- `get_vitals.py`: bounded latest/history queries.
- `risk_assessment.py`: rule-only scoring from received numeric vitals, stores assessments, and serves latest/history. `SimulationMode` is never used to determine risk.
- `document_management.py`: issue 5-minute constrained S3 POST policies, record metadata, verify completed uploads, and issue 5-minute downloads.
- `alert_management.py`: query the patient GSI and update alert status.

Functions use Python 3.12 and Lambda-provided boto3; there are no runtime third-party packages.

## Illustrative risk rules

Default configurable scoring parameters are exposed as CloudFormation template parameters. Elevated heart rate and temperature, reduced SpO2, or more extreme values add points. Score is capped at 10. Internal levels are NORMAL (0), LOW (1–2), MODERATE (3–5), HIGH (6–10). Dashboard categories map 0 to NORMAL, 1–5 to WARNING, and 6–10 to HIGH. Alerts are recorded for WARNING/HIGH, while SNS publishes only for HIGH to reduce notification noise.

The scores and thresholds are for a software demonstration only; they are not medical guidance.

## Authentication and security boundaries

- Cognito Hosted UI uses OAuth authorization-code flow with PKCE and a public client (no client secret).
- API Gateway HTTP API validates JWT issuer/audience before invoking handlers.
- Browser access tokens remain in sessionStorage and are sent only as Bearer authorization headers.
- S3 has public access blocks and server-side encryption. URLs expire after five minutes. Upload policy restricts MIME type and maximum size to 10 MiB.
- IoT policy allows only the configured device client ID and P001 publish topic.
- No AWS account keys, Wi-Fi secrets, or device private keys belong in the repository.

This project is not a production healthcare system. Before any real patient use, perform a formal privacy, threat, safety, reliability, and regulatory review.
