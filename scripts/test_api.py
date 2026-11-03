#!/usr/bin/env python3
import subprocess
import urllib.request
import json

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
print("Cognito Auth Success! Token Length:", len(id_token))

API_BASE = "https://sf4pw8iev0.execute-api.ap-south-1.amazonaws.com/dev"

def make_request(path):
    url = f"{API_BASE}{path}"
    print(f"\n--- Requesting GET {url} ---")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {id_token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode('utf-8')
            print(f"Status Code: {resp.status}")
            print(f"Response Body: {data}")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.read().decode('utf-8')}")

print("\n1. Testing Patients List:")
make_request("/patients")

print("\n2. Testing Vitals Latest for P001:")
make_request("/vitals/latest?PatientId=P001")

print("\n3. Testing Vitals History for P001:")
make_request("/vitals/history?PatientId=P001")

print("\n4. Testing Documents List for P001:")
make_request("/documents?action=list&PatientId=P001")
