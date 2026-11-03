#!/usr/bin/env python3
import subprocess
import urllib.request
import json
import os

if os.environ.get("ALLOW_AWS_TEST_WRITES") != "1":
    raise SystemExit(
        "This script writes synthetic telemetry to AWS. "
        "Set ALLOW_AWS_TEST_WRITES=1 only in a non-production test account."
    )

TEST_PATIENT_ID = os.environ.get("TEST_PATIENT_ID", "SIM-TEST")
if not TEST_PATIENT_ID.startswith("SIM-"):
    raise SystemExit("Synthetic telemetry is restricted to patient IDs beginning with SIM-.")

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
print("Cognito Auth Success!")

API_BASE = "https://sf4pw8iev0.execute-api.ap-south-1.amazonaws.com/dev"

def test_vitals_post(mode, hr, spo2, temp):
    print(f"\n--- Testing POST /vitals Mode: [{mode}] ---")
    payload = {
        "PatientId": TEST_PATIENT_ID,
        "HeartRate": hr,
        "SpO2": spo2,
        "Temperature": temp,
        "DeviceID": "SIMULATOR_DASHBOARD",
        "Source": "SIMULATOR"
    }
    json_bytes = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        f"{API_BASE}/vitals",
        data=json_bytes,
        headers={"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        out = json.loads(resp.read().decode('utf-8'))
        print(f"Status Code: {resp.status}")
        print("Response:", json.dumps(out, indent=2))

test_vitals_post("NORMAL", 72.0, 98.0, 36.6)
test_vitals_post("WARNING", 106.0, 94.0, 37.8)
test_vitals_post("HIGH", 128.0, 89.0, 38.8)
