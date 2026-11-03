from boto3.dynamodb.conditions import Key

from shared import api_result, table_from_env


def lambda_handler(event, context):
    patient_id = event.get("pathParameters", {}).get("patientId")
    if not patient_id:
        return api_result(400, message="patientId is required")
    path = event.get("rawPath", "")
    query = event.get("queryStringParameters") or {}
    table = table_from_env("VITALS_TABLE")
    try:
        if path.endswith("/latest"):
            result = table.query(
                KeyConditionExpression=Key("PatientId").eq(patient_id),
                ScanIndexForward=False,
                Limit=1,
            )
            reading = result.get("Items", [])
            return api_result(200, data=reading[0] if reading else None,
                              message=None if reading else "Waiting for incoming readings...")

        limit = int(query.get("limit", "100"))
        if not 1 <= limit <= 500:
            return api_result(400, message="limit must be between 1 and 500")
        key_condition = Key("PatientId").eq(patient_id)
        start = query.get("from")
        end = query.get("to")
        if start and end:
            key_condition = key_condition & Key("Timestamp").between(start, end)
        elif start:
            key_condition = key_condition & Key("Timestamp").gte(start)
        elif end:
            key_condition = key_condition & Key("Timestamp").lte(end)
        result = table.query(
            KeyConditionExpression=key_condition,
            ScanIndexForward=False,
            Limit=limit,
        )
        return api_result(200, data=result.get("Items", []))
    except ValueError:
        return api_result(400, message="limit must be a whole number")
