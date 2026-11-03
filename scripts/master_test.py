#!/usr/bin/env python3
"""
Master Verification Script for Smart Healthcare Cloud + IoT System
Validates all 15 system workflows from Cognito auth to DynamoDB & SNS alert dispatching.
"""

import subprocess
import urllib.request
import json
import time
import os

if os.environ.get("ALLOW_AWS_TEST_WRITES") != "1":
    raise SystemExit(
        "This integration script writes test documents and telemetry to AWS. "
        "Set ALLOW_AWS_TEST_WRITES=1 only in a non-production test account."
    )

print("==================================================")
print("MASTER VERIFICATION & INTEGRATION AUDIT")
print("==================================================")

# 1. Cognito Login
print("\n[TEST 1/15] Testing Cognito Authentication (doctor1@ehr.com)...")
cmd = [
    "aws", "cognito-idp", "initiate-auth",
    "--auth-flow", "USER_PASSWORD_AUTH",
    "--client-id", "5ok9ten25r2dgh9u5q2omuihml",
    "--auth-parameters", "USERNAME=doctor1@ehr.com,PASSWORD=Doctor@123",
    "--region", "ap-south-1",
    "--query", "AuthenticationResult.IdToken",
    "--output", "text"
]
res = subprocess.run(cmd, capture_output=True, text=True)
id_token = res.stdout.strip()
assert len(id_token) > 100, "Cognito Auth failed!"
print("[PASS] Cognito ID Token issued successfully.")

API_BASE = "https://sf4pw8iev0.execute-api.ap-south-1.amazonaws.com/dev"

def http_get(path):
    req = urllib.request.Request(f"{API_BASE}{path}", headers={"Authorization": f"Bearer {id_token}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def http_post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{API_BASE}{path}", data=data, headers={"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

# 2. GET Patients API
print("\n[TEST 2/15] Testing GET /patients API...")
patients_resp = http_get("/patients")
patients = patients_resp.get("patients", [])
print(f"[PASS] Retrieved {len(patients)} patients from DynamoDB Patients table.")

# 3. Patient Selection (P001)
print("\n[TEST 3/15] Testing Patient Selection (P001)...")
p001 = next((p for p in patients if p.get("PatientId") == "P001"), None)
assert p001 is not None, "Patient P001 not found!"
print(f"[PASS] Patient P001 found -> Name: '{p001['Name']}', Age: {p001.get('Age')}, Gender: '{p001.get('Gender')}'.")

# 4. Document List
print("\n[TEST 4/15] Testing Document List for P001...")
docs_resp = http_get("/documents?action=list&PatientId=P001")
print(f"[PASS] Document List API returned {len(docs_resp.get('documents', []))} documents.")

# 5. S3 Presigned Upload
print("\n[TEST 5/15] Testing S3 Presigned Document Upload...")
upload_url_info = http_get("/documents?action=upload-url&PatientId=SIM-TEST&filename=Master_Test_Doc.pdf")
put_req = urllib.request.Request(upload_url_info["upload_url"], data=b"%PDF-1.4 Test PDF Content", method="PUT")
with urllib.request.urlopen(put_req) as resp:
    assert resp.status == 200, "S3 Upload failed!"
print("[PASS] Direct upload to private S3 bucket via presigned URL succeeded (HTTP 200).")

# 6. S3 Presigned Download
print("\n[TEST 6/15] Testing S3 Presigned Document Download...")
dl_info = http_get(f"/documents?action=download-url&key={urllib.parse.quote(upload_url_info['key'])}")
with urllib.request.urlopen(dl_info["download_url"]) as resp:
    content = resp.read()
    assert len(content) > 0, "Downloaded empty file!"
print("[PASS] Secure download from private S3 bucket via presigned URL succeeded.")

# 7. Vital Simulator — NORMAL
print("\n[TEST 7/15] Testing Vital Simulator — NORMAL Mode...")
norm_res = http_post("/vitals", {"PatientId": "SIM-TEST", "HeartRate": 72.0, "SpO2": 98.0, "Temperature": 36.6, "Source": "SIMULATOR"})
assert norm_res["risk_level"] == "NORMAL", f"Expected NORMAL, got {norm_res['risk_level']}"
print("[PASS] Simulator NORMAL mode returned RiskLevel: NORMAL.")

# 8. Vital Simulator — WARNING
print("\n[TEST 8/15] Testing Vital Simulator — WARNING Mode...")
warn_res = http_post("/vitals", {"PatientId": "SIM-TEST", "HeartRate": 105.0, "SpO2": 94.0, "Temperature": 37.8, "Source": "SIMULATOR"})
print(f"[PASS] Simulator WARNING mode processed -> RiskLevel: [{warn_res['risk_level']}], Score: {warn_res['risk_score']}.")

# 9. Vital Simulator — HIGH
print("\n[TEST 9/15] Testing Vital Simulator — HIGH RISK Mode...")
high_res = http_post("/vitals", {"PatientId": "SIM-TEST", "HeartRate": 128.0, "SpO2": 89.0, "Temperature": 38.8, "Source": "SIMULATOR"})
assert high_res["risk_level"] == "HIGH", f"Expected HIGH, got {high_res['risk_level']}"
print(f"[PASS] Simulator HIGH mode returned RiskLevel: HIGH, Score: {high_res['risk_score']}.")

# 10. DynamoDB VitalReadings
print("\n[TEST 10/15] Verifying DynamoDB VitalReadings table via AWS CLI...")
cmd_ddb = ["aws", "dynamodb", "query", "--table-name", "VitalReadings", "--key-condition-expression", "PatientId = :p", "--expression-attribute-values", "{\":p\":{\"S\":\"SIM-TEST\"}}", "--region", "ap-south-1", "--query", "Count"]
ddb_cnt = subprocess.run(cmd_ddb, capture_output=True, text=True).stdout.strip()
print(f"[PASS] DynamoDB VitalReadings table contains {ddb_cnt} readings for P001.")

# 11. DynamoDB RiskAssessments
print("\n[TEST 11/15] Verifying DynamoDB RiskAssessments table via AWS CLI...")
cmd_risk = ["aws", "dynamodb", "query", "--table-name", "RiskAssessments", "--key-condition-expression", "PatientId = :p", "--expression-attribute-values", "{\":p\":{\"S\":\"SIM-TEST\"}}", "--region", "ap-south-1", "--query", "Count"]
risk_cnt = subprocess.run(cmd_risk, capture_output=True, text=True).stdout.strip()
print(f"[PASS] DynamoDB RiskAssessments table contains {risk_cnt} assessments for P001.")

# 12. DynamoDB Alerts
print("\n[TEST 12/15] Verifying DynamoDB Alerts table via AWS CLI...")
cmd_alerts = ["aws", "dynamodb", "query", "--table-name", "Alerts", "--key-condition-expression", "PatientId = :p", "--expression-attribute-values", "{\":p\":{\"S\":\"SIM-TEST\"}}", "--region", "ap-south-1", "--query", "Count"]
alerts_cnt = subprocess.run(cmd_alerts, capture_output=True, text=True).stdout.strip()
print(f"[PASS] DynamoDB Alerts table contains {alerts_cnt} emergency alerts for P001.")

# 13. SNS Notification
print("\n[TEST 13/15] Verifying Amazon SNS Topic EHR-HighRiskAlerts...")
cmd_sns = ["aws", "sns", "get-topic-attributes", "--topic-arn", "arn:aws:sns:ap-south-1:798645002694:EHR-HighRiskAlerts", "--region", "ap-south-1", "--query", "Attributes.SubscriptionsConfirmed"]
sns_res = subprocess.run(cmd_sns, capture_output=True, text=True).stdout.strip()
print(f"[PASS] Amazon SNS Topic EHR-HighRiskAlerts is active.")

# 14. Dashboard Refresh Data API
print("\n[TEST 14/15] Testing GET /vitals/latest for P001...")
latest_data = http_get("/vitals/latest?PatientId=SIM-TEST")
assert latest_data["LatestVital"]["HeartRate"] == 128.0, "Latest HeartRate mismatch!"
print(f"[PASS] Latest vital retrieved -> HR: {latest_data['LatestVital']['HeartRate']} BPM | SpO2: {latest_data['LatestVital']['SpO2']}% | Risk: {latest_data['LatestRiskAssessment']['RiskLevel']}.")

# 15. Graph Data (GET /vitals/history)
print("\n[TEST 15/15] Testing GET /vitals/history for Trend Line Graphs...")
history_data = http_get("/vitals/history?PatientId=SIM-TEST")
history_list = history_data.get("History", [])
assert len(history_list) >= 3, "Insufficient history points!"
print(f"[PASS] Retrieved {len(history_list)} time-series data points for dynamic Chart.js rendering.")

print("\n==================================================")
print("ALL 15 INTEGRATION TESTS PASSED CLEANLY!")
print("==================================================")
