# MediChart Smart Healthcare Monitoring

**Project title:** Design and Implementation of a Cloud-Based Smart Healthcare Monitoring and Early Risk Detection System Using AWS and IoT

This is a new, separate project. It uses ESP32 firmware to generate simulated heart rate, SpO2, and temperature readings, sends them over MQTT/TLS to AWS IoT Core, processes and stores them with Lambda and DynamoDB, and displays only API-returned readings in the MediChart dashboard.

> **SIMULATED VITAL DATA – FOR DEMONSTRATION ONLY.** The rules and scores are illustrative, are not medically validated, and must not be used for diagnosis, treatment, triage, or emergencies.

## What is included

- `infrastructure/`: AWS SAM/CloudFormation stack, minimal IoT publish policy, PlatformIO project config, and ESP32 simulator.
- `lambda/`: six Python 3.12 Lambda handlers for ingestion, patient CRUD, vitals, risk, documents, and alerts.
- `frontend/`: Cognito Hosted UI sign-in, patient directory, live API-backed dashboard/charts, and private S3 document vault.
- `scripts/`: setup, approval-gated deployment, non-destructive checks, and safe cleanup guidance.
- `tests/`: local unit tests for input validation, patient operations, risk calculation, and API response shape.

The deployment stack creates PAY_PER_REQUEST DynamoDB tables (`Patients`, `VitalReadings`, `RiskAssessments`, `Alerts`, and `Documents`), an encrypted private S3 bucket, an SNS topic, a Cognito user pool and groups, a JWT-protected API Gateway HTTP API, six Lambda functions, an IoT Thing/policy, and an IoT topic rule. CloudFormation-generated Lambda execution roles only receive the table, bucket, topic, and invoke permissions their handlers need.

## Prerequisites

- Windows 10/11, VS Code, and PlatformIO IDE extension.
- Python 3.12+, AWS CLI v2, AWS SAM CLI, and an AWS account configured for `ap-south-1`.
- ESP32 DevKit/ESP32-WROOM and USB data cable.
- A 2.4 GHz Wi-Fi network.

No AWS deployment is performed by preparing these files. Deployment is a separate, cost-incurring action that requires running `scripts\deploy.ps1` and typing `DEPLOY` after reviewing its resource/cost notice.

## Local setup and tests

From this directory in PowerShell:

```powershell
.\scripts\setup.ps1
.\.venv\Scripts\python.exe -m pytest
sam validate --lint --template-file infrastructure\template.yaml
```

`setup.ps1` checks required commands and prepares a local Python virtual environment. SAM validation is local and does not create AWS resources.

## Deploy AWS resources (only after review)

1. Review [docs/aws-setup.md](docs/aws-setup.md), especially resource creation and possible charges.
2. Set AWS CLI credentials for a non-root deployment identity with the needed CloudFormation, SAM, Lambda, IoT, Cognito, API Gateway, DynamoDB, S3, SNS, IAM, and CloudWatch permissions.
3. Choose a unique Cognito domain prefix.
4. Run `.\scripts\deploy.ps1`. It describes the resources, asks for the literal confirmation `DEPLOY`, builds the stack, then runs SAM deployment. It does not create a certificate or delete existing resources.
5. Create doctor/admin accounts through Cognito as documented in [docs/aws-setup.md](docs/aws-setup.md). User passwords are never placed in source.

The CloudFormation IoT rule name is `SmartHealthcareProcessVitals`; deployment fails if that name is already in use in the selected account/region. Resolve any conflict deliberately; do not delete an existing rule blindly.

## Configure the frontend

Run:

```powershell
aws cloudformation describe-stacks --stack-name smart-healthcare-monitoring --region ap-south-1 --query "Stacks[0].Outputs" --output table
```

Copy the returned UserPoolId, AppClientId, CognitoHostedUi, and ApiBaseUrl into `frontend\js\config.js`. Set `redirectUri` and `logoutUri` to the exact deployed `FrontendRedirectUri` (default `http://localhost:8000/`).

Start a local static server from this folder:

```powershell
python -m http.server 8000 --directory frontend
```

Open `http://localhost:8000/`, then sign in through Cognito. The browser stores short-lived tokens only in `sessionStorage`; no credentials or private client secret are in the frontend.

Register patient `P001` through the directory if it is not already present. The dashboard reads patients, vitals, risks, and alerts through the authenticated API; it never creates sample readings. If there are no readings it displays “Waiting for incoming readings...”.

## ESP32 setup and exact PlatformIO commands

See [docs/hardware-setup.md](docs/hardware-setup.md) for Wi-Fi, certificate, and IoT policy setup. Copy `infrastructure\credentials.example.h` to `infrastructure\credentials.h` and insert the Wi-Fi SSID/password and the Root CA, device certificate, and private key. `credentials.h` and key files are ignored by Git.

From the project directory, with PlatformIO installed:

```powershell
platformio run -e esp32dev
platformio run -e esp32dev -t upload --upload-port COM5
platformio device monitor -e esp32dev --port COM5 --baud 115200
```

The sketch defaults to `NORMAL_MODE`. Change `simulationMode` near the top of `infrastructure\esp32_smart_health.ino` to `WARNING_MODE` or `HIGH_RISK_MODE` to demonstrate those ranges. The backend validates values against the selected mode. A deliberate mode switch can shift values to the new permitted range; normal consecutive readings vary gradually.

## API endpoints

All endpoints below require a Cognito JWT in `Authorization: Bearer <access-token>`.

| Method | Path | Purpose |
|---|---|---|
| GET, POST | `/patients` | List/register patients |
| GET, PUT, DELETE | `/patients/{patientId}` | Read/update; delete is admin-only |
| GET | `/patients/{patientId}/vitals` | Read bounded vital history |
| GET | `/patients/{patientId}/vitals/latest` | Latest vital |
| GET | `/patients/{patientId}/vitals/history` | Historical vital readings |
| GET | `/patients/{patientId}/risk` | Latest value-based risk assessment |
| GET | `/patients/{patientId}/risk/history` | Historical risk scores |
| GET | `/patients/{patientId}/alerts` | Patient alerts |
| PATCH | `/alerts/{alertId}` | Set OPEN/ACKNOWLEDGED/RESOLVED; resolve is admin-only |
| POST | `/documents/upload-url` | Create a short-lived size-limited S3 upload |
| POST | `/documents/{documentId}/complete` | Verify upload exists and publish document metadata |
| GET | `/documents?patientId=...` | List available patient documents |
| GET | `/documents/{documentId}/download-url?patientId=...` | Create short-lived download URL |

## Tests and operational flow

Follow the 17-step checklist in [docs/testing.md](docs/testing.md). Local tests do not require AWS. Cloud tests require a deployed stack, an authenticated doctor, an active ESP32 certificate, and real AWS data. Do not mark an end-to-end step complete until it has actually been observed.

## Cost and data cautions

AWS charges can apply for IoT messages/connections, Lambda invocations and logs, API Gateway requests, DynamoDB read/write/storage, S3 requests/storage/transfer, SNS notifications, and Cognito usage. PAY_PER_REQUEST and low Lambda memory reduce idle cost but do not guarantee free use. Review current AWS regional pricing and budgets before deployment. Medical documents and patient identifiers are sensitive: use only synthetic demonstration records and follow applicable privacy policies.

To see non-destructive verification commands, run `.\scripts\test.ps1 -RunAwsChecks`. `.\scripts\cleanup.ps1` only prints explicit cleanup guidance; it never deletes AWS resources.
