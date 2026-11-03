import json
import boto3
import uuid

s3 = boto3.client("s3", region_name="ap-south-1")
dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
documents_table = dynamodb.Table("Documents")
BUCKET_NAME = "sanmugam-ehr-docs-2026"


def get_user_groups(event):
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    groups_raw = claims.get("cognito:groups", "")
    if not groups_raw:
        return []
    try:
        parsed = json.loads(groups_raw)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return [g.strip() for g in groups_raw.strip("[]").replace('"', "").split(",") if g.strip()]


def lambda_handler(event, context):
    http_method = event.get("requestContext", {}).get("http", {}).get("method") \
        or event.get("httpMethod", "")
    query_params = event.get("queryStringParameters") or {}

    try:
        action = query_params.get("action")
        if http_method == "GET" and action == "upload-url":
            return get_upload_url(query_params)
        elif http_method == "GET" and action == "download-url":
            return get_download_url(query_params)
        elif http_method == "GET" and action == "list":
            return list_documents(query_params)
        elif http_method == "DELETE":
            return delete_document(query_params, event)
        else:
            return response(400, {"error": "Provide action=upload-url, download-url, or list"})
    except Exception as e:
        return response(500, {"error": str(e)})


def get_upload_url(params):
    patient_id = params.get("PatientId")
    filename = params.get("filename")
    content_type = params.get("contentType") or "application/octet-stream"
    if not patient_id or not filename:
        return response(400, {"error": "PatientId and filename are required"})

    document_id = str(uuid.uuid4())
    key = f"{patient_id}/{document_id}_{filename}"

    upload = s3.generate_presigned_post(
        Bucket=BUCKET_NAME,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[{"Content-Type": content_type}],
        ExpiresIn=300
    )

    documents_table.put_item(Item={
        "DocumentId": document_id,
        "PatientId": patient_id,
        "Filename": filename,
        "S3Key": key
    })

    return response(200, {
        "upload_url": upload["url"],
        "fields": upload["fields"],
        "key": key,
        "document_id": document_id
    })


def get_download_url(params):
    key = params.get("key")
    if not key:
        return response(400, {"error": "key is required"})

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=300
    )
    return response(200, {"download_url": url})


def list_documents(params):
    patient_id = params.get("PatientId")
    if not patient_id:
        return response(400, {"error": "PatientId is required"})

    result = documents_table.query(
        IndexName="PatientIdIndex",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("PatientId").eq(patient_id)
    )
    return response(200, {"documents": result.get("Items", [])})


def delete_document(params, event):
    if "admin" not in get_user_groups(event):
        return response(403, {"error": "Only admins can delete documents"})

    document_id = params.get("DocumentId")
    key = params.get("key")
    if not document_id or not key:
        return response(400, {"error": "DocumentId and key are required"})

    s3.delete_object(Bucket=BUCKET_NAME, Key=key)
    documents_table.delete_item(Key={"DocumentId": document_id})

    return response(200, {"message": "Document deleted", "DocumentId": document_id})


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body)
    }