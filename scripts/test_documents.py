#!/usr/bin/env python3
import subprocess
import urllib.parse
import urllib.request
import json
import uuid

cmd = [
    "aws", "cognito-idp", "initiate-auth",
    "--auth-flow", "USER_PASSWORD_AUTH",
    "--client-id", "5ok9ten25r2dgh9u5q2omuihml",
    "--auth-parameters", "USERNAME=admin1@ehr.com,PASSWORD=Admin@123",
    "--region", "ap-south-1",
    "--query", "AuthenticationResult.IdToken",
    "--output", "text"
]

res = subprocess.run(cmd, capture_output=True, text=True)
id_token = res.stdout.strip()
print("Cognito Admin Auth Success!")

API_BASE = "https://sf4pw8iev0.execute-api.ap-south-1.amazonaws.com/dev"

# 1. Request upload URL
url = (
    f"{API_BASE}/documents?action=upload-url"
    "&PatientId=P001&filename=Lab_Report_P001.pdf&contentType=application%2Fpdf"
)
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {id_token}"})
with urllib.request.urlopen(req) as resp:
    upload_data = json.loads(resp.read().decode('utf-8'))
print("1. Upload URL generated:", upload_data["upload_url"][:80] + "...")

# 2. Upload dummy file using the presigned S3 POST fields
pdf_content = b"%PDF-1.4 Dummy PDF Content for Testing S3 Presigned URL Upload"
boundary = f"----EHRUpload{uuid.uuid4().hex}"
parts = []
for name, value in upload_data["fields"].items():
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode("utf-8")
    )
parts.append(
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="file"; filename="Lab_Report_P001.pdf"\r\n'
    "Content-Type: application/pdf\r\n\r\n".encode("utf-8")
    + pdf_content
    + f"\r\n--{boundary}--\r\n".encode("utf-8")
)
post_req = urllib.request.Request(
    upload_data["upload_url"],
    data=b"".join(parts),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST"
)
with urllib.request.urlopen(post_req) as resp:
    print("2. Upload to S3 Status:", resp.status)

# 3. List documents for P001
list_url = f"{API_BASE}/documents?action=list&PatientId=P001"
req = urllib.request.Request(list_url, headers={"Authorization": f"Bearer {id_token}"})
with urllib.request.urlopen(req) as resp:
    docs_list = json.loads(resp.read().decode('utf-8'))
print("3. Documents List:", json.dumps(docs_list, indent=2))

# 4. Request download URL
s3_key = upload_data["key"]
dl_url = f"{API_BASE}/documents?action=download-url&key={urllib.parse.quote(s3_key)}"
req = urllib.request.Request(dl_url, headers={"Authorization": f"Bearer {id_token}"})
with urllib.request.urlopen(req) as resp:
    dl_data = json.loads(resp.read().decode('utf-8'))
print("4. Download URL generated:", dl_data["download_url"][:80] + "...")

# 5. Fetch content from presigned download URL
with urllib.request.urlopen(dl_data["download_url"]) as resp:
    downloaded_content = resp.read()
print("5. Downloaded Content length:", len(downloaded_content))
