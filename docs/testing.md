# End-to-End System Testing & Verification

## Test Execution Matrix

The source code and deployed AWS configuration were inspected read-only on 2026-11-02. The full end-to-end flow has not yet been executed because the deployed IoT rule is disabled, the deployed IoT policy uses a mismatched topic, and the device certificate must be rotated. Do not treat the statuses below as completed tests.

| Test Case | Description | Verification Method | Status |
| :--- | :--- | :--- | :--- |
| **1. Cognito Login** | Authenticate user & issue signed JWT | Deployed pool/client IDs and user-password/refresh flows inspected | Config inspected; login not exercised |
| **2. Unauthorized API Access** | Require JWT bearer header | API Gateway patient route is configured with the Cognito JWT authorizer | Config inspected; runtime not exercised |
| **3. Authorized API Access** | Request API with valid JWT | Requires a signed-in doctor session | Pending |
| **4. Patient CRUD** | Create, Query, Update, Delete patient | Local Lambda changes must be deployed before testing | Pending |
| **5-6. S3 Documents** | Presigned upload/download | Not exercised to avoid writing files to the existing bucket | Pending |
| **7. IoT Ingestion** | Publish telemetry from ESP32 | Deployed rule disabled; deployed topic policy mismatched | Blocked on AWS configuration and certificate rotation |
| **8. Vital Telemetry Storage** | Verify `VitalReadings` write | Requires an actual device publish after the rule is enabled | Pending |
| **9-11. Risk and Alerts** | Assess measured values and dispatch alerts | Not exercised; synthetic high-risk records could notify staff | Pending |
| **12. Dashboard** | Display actual readings and chart | Local changes require hosting and a valid doctor login | Pending |
| **13. Role-Based Access** | Restrict deletion to admins | Local Lambda changes must be deployed before testing | Pending |
| **14. Error Handling** | Reject malformed telemetry/API requests | Local Lambda changes must be deployed before testing | Pending |
| **15. End-to-End Workflow** | Telemetry -> IoT -> Lambda -> DynamoDB -> API -> Dashboard | Blocked on AWS configuration and certificate rotation | Pending |

---

## Repeatable Command Examples

### Optional isolated synthetic test (non-production only)
```bash
python scripts/sensor_simulator.py --patient SIM-TEST --mode normal --count 3 --interval 1.0 --confirm-cloud-write
```
Synthetic telemetry can trigger SNS alerts; do not use `--mode high` in an account with production notification subscribers.

### Verify a test patient's telemetry without scanning the table
```bash
aws dynamodb query --table-name VitalReadings --key-condition-expression "PatientId = :patient" --expression-attribute-values '{":patient":{"S":"SIM-TEST"}}' --region ap-south-1
```
