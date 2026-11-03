# AWS Infrastructure & Resource Inventory

## Region: `ap-south-1` (Asia Pacific - Mumbai)

---

## 1. Amazon DynamoDB Tables

| Table Name | Partition Key | Sort Key | Secondary Indexes | Billing Mode | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`Patients`** | `PatientId` (S) | *None* | *None* | PAY_PER_REQUEST | EHR Core Demographic Profiles |
| **`VitalReadings`** | `PatientId` (S) | `Timestamp` (S) | *None* | PAY_PER_REQUEST | Time-series health sensor telemetry (HR, SpO2, Temp) |
| **`RiskAssessments`** | `PatientId` (S) | `Timestamp` (S) | *None* | PAY_PER_REQUEST | Clinical Decision Support Engine output & score logs |
| **`Alerts`** | `PatientId` (S) | `Timestamp` (S) | *None* | PAY_PER_REQUEST | Emergency high-risk alert notification audit history |
| **`Documents`** | `DocumentId` (S) | *None* | `PatientIdIndex` (PK: PatientId) | PAY_PER_REQUEST | Presigned S3 medical attachment metadata index |

---

## 2. AWS Lambda Functions

| Function Name | Runtime | Handler | Timeout | Role | Trigger / Event Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`EHR-IoTIngest`** | Python 3.12 | `iot_ingest_lambda.lambda_handler` | 15s | `EHR-Lambda-Execution-Role` | AWS IoT Core Rule `EHR_VitalIngestionRule` |
| **`EHR-Vitals`** | Python 3.12 | `vitals_lambda.lambda_handler` | 10s (deployed) | `EHR-Lambda-Execution-Role` | API Gateway HTTP API (`/vitals/*`, `/patients/{PatientId}/vitals`, `/patients/{PatientId}/alerts`) |
| **`EHR-PatientCRUD`**| Python 3.12 | `patient_crud_lambda.lambda_handler` | 10s (deployed) | `EHR-Lambda-Execution-Role` | API Gateway HTTP API (`/patients/*`) |
| **`EHR-Documents`** | Python 3.12 | `document_lambda.lambda_handler` | 15s | `EHR-Lambda-Execution-Role` | API Gateway HTTP API (`/documents`) |

---

## 3. Amazon API Gateway (HTTP API)

- **API Name**: `EHR-API`
- **API ID**: `sf4pw8iev0`
- **Endpoint**: `https://sf4pw8iev0.execute-api.ap-south-1.amazonaws.com`
- **Authorizer**: `EHR-CognitoAuthorizer` (JWT Authorizer linked to Cognito User Pool `ap-south-1_2uAqFquLU`)

### Active Routes

| Method | Route Key | Target Integration | Authorization |
| :--- | :--- | :--- | :--- |
| `GET` | `/vitals/latest` | `EHR-Vitals` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `GET` | `/vitals/history` | `EHR-Vitals` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `GET` | `/vitals/alerts` | `EHR-Vitals` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `GET` | `/patients/{PatientId}/vitals` | `EHR-Vitals` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `GET` | `/patients/{PatientId}/alerts` | `EHR-Vitals` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `GET` | `/patients` | `EHR-PatientCRUD` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `POST` | `/patients` | `EHR-PatientCRUD` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `PUT` | `/patients/{PatientId}` | `EHR-PatientCRUD` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `DELETE`| `/patients` | `EHR-PatientCRUD` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `DELETE`| `/patients/{PatientId}` | `EHR-PatientCRUD` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `GET` | `/patients/{PatientId}` | `EHR-PatientCRUD` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `GET` | `/documents` | `EHR-Documents` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |
| `DELETE`| `/documents` | `EHR-Documents` Lambda | Cognito JWT (`EHR-CognitoAuthorizer`) |

---

## 4. AWS IoT Core Components

- **ATS Data Endpoint**: `a1uyfass1g887i-ats.iot.ap-south-1.amazonaws.com`
- **IoT Policy**: `EHR_IoTDevicePolicy` (deployed publish resource currently allows `healthcare/vitals/*`)
- **IoT Thing**: `SmartHealth_ESP32_P001`
- **X.509 Certificate**: `arn:aws:iot:ap-south-1:798645002694:cert/9155e6a98e402fb5f5a3344df8201fc72b38b5726dbc6738e8815343a119f3f0`
- **IoT Topic Rule**: `EHR_VitalIngestionRule`
  - **SQL Filter**: `SELECT * FROM 'smart-healthcare/+/vitals'`
  - **Action**: Invokes `EHR-IoTIngest` AWS Lambda function.
  - **Observed status (2026-11-02)**: Disabled. The Lambda invoke permission is present.

The deployed IoT policy currently allows a different topic prefix (`healthcare/vitals/*`) than the firmware's `smart-healthcare/P001/vitals`. Update the policy resource to match the firmware topic before connecting the device.

---

## 5. Amazon SNS Topic

- **Topic Name**: `EHR-HighRiskAlerts`
- **Topic ARN**: `arn:aws:sns:ap-south-1:798645002694:EHR-HighRiskAlerts`
- **Function**: Dispatches urgent SMS/Email notifications to medical staff when `RiskLevel == 'HIGH'`.

---

## 6. Amazon Cognito User Pool

- **User Pool Name**: `EHR-UserPool`
- **User Pool ID**: `ap-south-1_2uAqFquLU`
- **App Client ID**: `5ok9ten25r2dgh9u5q2omuihml`
- **Configured Groups**: `doctor`, `staff`, `admin`
- **Verified Active Users**: `doctor1@ehr.com` (Doctor role), `admin1@ehr.com` (Admin role).

---

## 7. Amazon S3 Storage

- **Bucket Name**: `sanmugam-ehr-docs-2026`
- **Public Access**: 100% Block Public Access (`BlockPublicAcls=true`, `IgnorePublicAcls=true`, `BlockPublicPolicy=true`, `RestrictPublicBuckets=true`).
- **CORS Configuration**: Enabled for `POST`, `PUT`, and `GET` requests via presigned URLs.
