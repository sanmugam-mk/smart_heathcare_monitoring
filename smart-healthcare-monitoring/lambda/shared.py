import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3


_dynamodb = boto3.resource("dynamodb")


def table_from_env(name):
    table_name = os.environ.get(name)
    if not table_name:
        raise RuntimeError(f"Required environment variable {name} is not configured")
    return _dynamodb.Table(table_name)


def json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, default=json_default),
    }


def api_result(status_code, data=None, message=None):
    body = {"success": 200 <= status_code < 300}
    if data is not None:
        body["data"] = data
    if message:
        body["message"] = message
    return response(status_code, body)


def parse_body(event):
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raise ValueError("Base64-encoded JSON request bodies are not supported")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("Request body must be a JSON object")
    return parsed


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def claims(event):
    return (event.get("requestContext", {}).get("authorizer", {})
            .get("jwt", {}).get("claims", {}))


def groups_for(event):
    groups = claims(event).get("cognito:groups", [])
    if isinstance(groups, str):
        try:
            decoded = json.loads(groups)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            return decoded
        return [part.strip().strip("\"'") for part in groups.strip("[]").split(",") if part.strip()]
    return groups if isinstance(groups, list) else []
