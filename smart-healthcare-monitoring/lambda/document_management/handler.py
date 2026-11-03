import logging
import os
import re
import uuid

import boto3
from boto3.dynamodb.conditions import Key

from shared import api_result, parse_body, table_from_env, utc_now


_s3 = boto3.client("s3")
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_FILE_BYTES = 10 * 1024 * 1024


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")
    query = event.get("queryStringParameters") or {}
    docs_table = table_from_env("DOCUMENTS_TABLE")
    bucket = os.environ["DOCUMENTS_BUCKET"]
    try:
        if method == "POST" and path.endswith("/complete"):
            body = parse_body(event)
            patient_id = body.get("patientId")
            document_id = event.get("pathParameters", {}).get("documentId")
            if not patient_id or not document_id:
                return api_result(400, message="patientId is required")
            key = {"PatientId": patient_id, "DocumentId": document_id}
            result = docs_table.get_item(Key=key)
            metadata = result.get("Item")
            if not metadata:
                return api_result(404, message="Document not found")
            _s3.head_object(Bucket=bucket, Key=metadata["S3Key"])
            docs_table.update_item(
                Key=key,
                UpdateExpression="SET #status = :available",
                ExpressionAttributeNames={"#status": "Status"},
                ExpressionAttributeValues={":available": "AVAILABLE"},
            )
            return api_result(200, data={"DocumentId": document_id, "Status": "AVAILABLE"})

        if method == "POST":
            body = parse_body(event)
            patient_id = body.get("patientId")
            filename = body.get("fileName")
            content_type = body.get("contentType")
            if not isinstance(patient_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", patient_id):
                return api_result(400, message="A valid patientId is required")
            if not isinstance(filename, str) or not filename.strip() or len(filename) > 180:
                return api_result(400, message="fileName must contain 1-180 characters")
            if content_type not in ALLOWED_CONTENT_TYPES:
                return api_result(400, message="Only PDF, JPEG, and PNG documents are allowed")
            size = body.get("sizeBytes")
            if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= MAX_FILE_BYTES:
                return api_result(400, message="Document size must be between 1 byte and 10 MB")
            document_id = str(uuid.uuid4())
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename.strip())
            key = f"patients/{patient_id}/{document_id}/{safe_name}"
            signed_post = _s3.generate_presigned_post(
                Bucket=bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, MAX_FILE_BYTES + 65536],
                ],
                ExpiresIn=300,
            )
            metadata = {
                "PatientId": patient_id,
                "DocumentId": document_id,
                "FileName": filename.strip(),
                "ContentType": content_type,
                "SizeBytes": size,
                "S3Key": key,
                "CreatedAt": utc_now(),
                "Status": "UPLOADING",
            }
            docs_table.put_item(Item=metadata)
            return api_result(201, data={"upload": signed_post, "document": metadata},
                              message="Upload URL created; upload before the URL expires")

        if method == "GET" and path.endswith("/download-url"):
            patient_id = query.get("patientId")
            document_id = event.get("pathParameters", {}).get("documentId")
            if not patient_id or not document_id:
                return api_result(400, message="patientId is required")
            result = docs_table.get_item(Key={"PatientId": patient_id, "DocumentId": document_id})
            doc = result.get("Item")
            if not doc or doc.get("Status") != "AVAILABLE":
                return api_result(404, message="Document not found")
            url = _s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": doc["S3Key"]},
                ExpiresIn=300,
            )
            return api_result(200, data={"downloadUrl": url, "expiresInSeconds": 300})

        if method == "GET":
            patient_id = query.get("patientId")
            if not patient_id:
                return api_result(400, message="patientId query parameter is required")
            result = docs_table.query(
                KeyConditionExpression=Key("PatientId").eq(patient_id),
                ScanIndexForward=False,
            )
            return api_result(200, data=[
                item for item in result.get("Items", []) if item.get("Status") == "AVAILABLE"
            ])
        return api_result(405, message="Unsupported document operation")
    except Exception:
        logging.getLogger().exception("Document management request failed")
        raise
