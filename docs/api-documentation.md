# REST API Documentation

## Base URL
`https://sf4pw8iev0.execute-api.ap-south-1.amazonaws.com`

---

## Authentication Header
All endpoints (except OPTIONS preflight) require an HTTP Authorization header containing a valid Cognito JWT ID Token:
```
Authorization: Bearer <Cognito ID token>
```

---

## Endpoints Summary

### 1. Health Monitoring & Vitals

#### `GET /patients/{PatientId}/vitals`
- **Description**: Returns the latest stored telemetry reading, up to 30 chronological readings, and the latest risk assessment.
- **Response `200 OK`**:
```json
{
  "PatientId": "P001",
  "Latest": {
    "PatientId": "P001",
    "Timestamp": "2026-11-02T10:30:00Z",
    "HeartRate": 74.2,
    "DeviceID": "ESP32_MAX30102",
    "Source": "ESP32"
  },
  "History": [],
  "LatestRisk": null
}
```
SpO2 and Temperature are omitted when not measured. `Latest` and `LatestRisk` are `null` when no record exists.
The ESP32 sends `SensorReady` and `FingerDetected` status every 3 seconds. When a finger is detected it publishes measured heart rate and, when valid, SpO2. A status-only record can contain those booleans without vital metrics; it is not included in risk assessment or alerting. The dashboard displays stored measurements only and retains the most recent measurement when no finger is detected. The MAX30102 does not measure body temperature, so Temperature is shown only if supplied by a separate temperature sensor.

#### `GET /patients/{PatientId}/alerts`
- **Description**: Returns high-risk alert records for the specified patient.

#### Legacy routes
The existing `GET /vitals/latest?PatientId={PatientId}`, `GET /vitals/history?PatientId={PatientId}`, and `GET /vitals/alerts?PatientId={PatientId}` routes remain supported.

#### `GET /vitals/history?PatientId={PatientId}`
- **Description**: Returns chronological time-series telemetry data for plotting trend line charts.
- **Response `200 OK`**:
```json
{
  "PatientId": "P001",
  "History": [ ... ],
  "Count": 30
}
```

#### `GET /vitals/alerts?PatientId={PatientId}`
- **Description**: Returns high-risk emergency alert logs for the specified patient.
- **Response `200 OK`**:
```json
{
  "PatientId": "P001",
  "Alerts": [
    {
      "PatientId": "P001",
      "Timestamp": "2026-09-14T07:50:03.808573+00:00",
      "RiskLevel": "HIGH",
      "VitalsSnapshot": { "HeartRate": 118, "SpO2": 91, "Temperature": 38.4 },
      "SNSMessageId": "a1b2c3d4-e5f6-7890",
      "Status": "SENT"
    }
  ],
  "Count": 1
}
```

---

### 2. Patient EHR Management

#### `GET /patients/{PatientId}`
- **Description**: Retrieves one patient record.

#### `GET /patients`
- **Description**: Retrieves all patient records or filters by name search.
- **Query Parameters**: `search` (Optional)
- **Response `200 OK`**:
```json
{
  "patients": [
    { "PatientId": "P001", "Name": "Jane Doe", "Age": 42, "Gender": "Female" }
  ]
}
```

#### `POST /patients`
- **Description**: Registers a new patient record.
- **Validation**: `PatientId` and `Name` are required. If provided, `Age` must be a whole number from 0 to 130. Duplicate patient IDs return `409 Conflict`; existing records are not overwritten.
- **Request Body**:
```json
{
  "PatientId": "P003",
  "Name": "Robert Chen",
  "Age": 55,
  "Gender": "Male"
}
```

#### `DELETE /patients`
- **Description**: Deletes a patient record (Doctor or Admin role required).
- **Request Body**: `{"PatientId": "P003"}`

`PUT /patients/{PatientId}` updates supplied fields without removing fields omitted from the request. Both patient delete routes require the Cognito `doctor` or `admin` group.

The dashboard's local showcase samples are explicitly labeled synthetic. They are displayed only in the browser and are not written to this API, used in clinical risk assessments, or sent as alerts.

---

### 3. Medical Documents Vault (Presigned S3 URLs)

#### `GET /documents?action=upload-url&PatientId={PatientId}&filename={filename}&contentType={mimeType}`
- **Description**: Generates a temporary (300s) S3 presigned POST URL and form fields. Submit the returned fields and the file as `multipart/form-data`; do not set the multipart `Content-Type` header manually.

#### `GET /documents?action=download-url&key={key}`
- **Description**: Generates a temporary (300s) S3 presigned `GET` URL for downloading files securely from private S3 bucket.
