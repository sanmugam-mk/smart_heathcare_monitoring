# Test and verification checklist

Run local tests and SAM validation before provisioning. End-to-end tests require user-provided AWS setup and hardware; do not report an unobserved step as passed.

## Requested ordered demonstration

1. **ESP32 boots** — connect serial monitor at COM5/115200; confirm startup output and simulated-only notice.
2. **Wi-Fi connects** — confirm `WiFi Connected!`.
3. **AWS IoT connects** — confirm `AWS IoT Core Connected!`.
4. **Normal values generated** — confirm values remain in NORMAL ranges.
5. **Publish succeeds** — confirm success line only after publish call returns true.
6. **MQTT received** — subscribe using AWS IoT MQTT Test Client to `smart-healthcare/+/vitals`; inspect numeric JSON values and ISO timestamp.
7. **IoT rule invokes Lambda** — inspect Lambda CloudWatch logs after a message.
8. **DynamoDB stores readings** — query the stack VitalReadings table for P001.
9. **Risk calculated** — confirm RiskAssessments item matches its received vital values and includes reasons.
10. **API returns readings** — use authenticated API/`test.ps1 -RunAwsChecks`; latest endpoint must return stored data.
11. **Doctor login** — sign in using a Cognito doctor user, never a hard-coded password.
12. **P001 directory** — register P001 once if absent; confirm it appears from API response.
13. **Dashboard values** — compare visible values and timestamp with API/DynamoDB.
14. **Charts update** — verify chart series use the returned vital/risk histories and change after new data.
15. **Modes and risk** — change firmware mode; verify received values are in the correct allowed ranges and risk is calculated from values, not the mode label.
16. **History persists** — refresh the page; verify stored historical values remain visible.
17. **WARNING/HIGH alerts** — verify abnormal values produce DynamoDB Alerts and HIGH publishes to SNS (if a recipient confirmed its subscription).

Also test patient create/read/update and admin-only delete; document upload/download with private S3 URLs; and alert status updates. Use synthetic data only.

## Local tests

```powershell
.\.venv\Scripts\python.exe -m pytest
sam validate --lint --template-file infrastructure\template.yaml
platformio run -e esp32dev
```

ESP32 compilation requires a local `infrastructure\credentials.h`; never insert real credentials into the repository.

## Read-only AWS checks

```powershell
.\scripts\test.ps1 -RunAwsChecks -StackName smart-healthcare-monitoring
```

The script checks stack resources, Lambda configuration, IoT rule presence, DynamoDB tables, and an authenticated latest-vitals endpoint. It does not publish telemetry or alter AWS resources. Verify actual message delivery in the AWS IoT MQTT Test Client and CloudWatch; resource existence alone is not proof of end-to-end operation.
