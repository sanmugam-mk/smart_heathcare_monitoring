import json
import logging
import boto3
from decimal import Decimal
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
table = dynamodb.Table("Patients")


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def get_user_groups(event):
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    groups_raw = claims.get("cognito:groups", "")
    if not groups_raw:
        return []
    if isinstance(groups_raw, list):
        return [str(group).casefold() for group in groups_raw]
    try:
        parsed = json.loads(groups_raw)
        if isinstance(parsed, list):
            return [str(group).casefold() for group in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return [g.strip().casefold() for g in groups_raw.strip("[]").replace('"', "").split(",") if g.strip()]


def lambda_handler(event, context):
    http_method = event.get("httpMethod", "") or event.get("requestContext", {}).get("http", {}).get("method", "")
    try:
        body = json.loads(event["body"]) if event.get("body") else {}
    except json.JSONDecodeError:
        return response(400, {"error": "Request body must be valid JSON"})
    if not isinstance(body, dict):
        return response(400, {"error": "Request body must be a JSON object"})
    query_params = event.get("queryStringParameters") or {}
    path_params = event.get("pathParameters") or {}
    patient_id = path_params.get("PatientId") or body.get("PatientId") or query_params.get("PatientId")

    try:
        if http_method == "POST":
            return create_patient(body)
        elif http_method == "GET" and patient_id:
            return get_patient(patient_id)
        elif http_method == "GET":
            return list_patients(query_params.get("search"))
        elif http_method == "PUT":
            return update_patient({**body, "PatientId": patient_id} if patient_id else body)
        elif http_method == "DELETE":
            if not {"doctor", "admin"}.intersection(get_user_groups(event)):
                return response(403, {"error": "Only doctors and admins can delete patient records"})
            return delete_patient(patient_id)
        else:
            return response(400, {"error": "Unsupported method or missing parameters"})
    except Exception:
        logger.exception("Error processing patient request")
        return response(500, {"error": "Patient request could not be processed"})


def create_patient(data):
    patient_id = data.get("PatientId")
    name = data.get("Name")
    if not isinstance(patient_id, str) or not patient_id.strip() or not isinstance(name, str) or not name.strip():
        return response(400, {"error": "PatientId and Name are required"})
    if "Age" in data and (
        isinstance(data["Age"], bool)
        or not isinstance(data["Age"], (int, float))
        or not 0 <= data["Age"] <= 130
        or not float(data["Age"]).is_integer()
    ):
        return response(400, {"error": "Age must be a whole number between 0 and 130"})
    try:
        table.put_item(
            Item={**data, "PatientId": patient_id.strip(), "Name": name.strip()},
            ConditionExpression="attribute_not_exists(PatientId)"
        )
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return response(409, {"error": "A patient with this PatientId already exists"})
        raise
    logger.info(f"Patient created: {patient_id}")
    return response(201, {"message": "Patient created", "PatientId": patient_id.strip()})


def get_patient(patient_id):
    result = table.get_item(Key={"PatientId": patient_id})
    item = result.get("Item")
    if not item:
        return response(404, {"error": "Patient not found"})
    return response(200, item)


def list_patients(search_term):
    if search_term:
        result = table.scan(FilterExpression=Attr("Name").contains(search_term))
    else:
        result = table.scan()
    return response(200, {"patients": result.get("Items", [])})


def update_patient(data):
    patient_id = data.get("PatientId")
    if not patient_id:
        return response(400, {"error": "PatientId is required"})
    if "Age" in data and not isinstance(data["Age"], (int, float)):
        return response(400, {"error": "Age must be a number"})
    updates = {key: value for key, value in data.items() if key != "PatientId"}
    if not updates:
        return response(400, {"error": "At least one patient field must be provided"})
    existing = table.get_item(Key={"PatientId": patient_id}).get("Item")
    if not existing:
        return response(404, {"error": "Patient not found"})
    table.put_item(Item={**existing, **updates})
    logger.info(f"Patient updated: {patient_id}")
    return response(200, {"message": "Patient updated", "PatientId": patient_id})


def delete_patient(patient_id):
    if not patient_id:
        return response(400, {"error": "PatientId is required"})
    table.delete_item(Key={"PatientId": patient_id})
    logger.info(f"Patient deleted: {patient_id}")
    return response(200, {"message": "Patient deleted", "PatientId": patient_id})


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalEncoder)
    }