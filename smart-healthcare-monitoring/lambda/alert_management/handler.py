from boto3.dynamodb.conditions import Key

from shared import api_result, groups_for, parse_body, table_from_env


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    patient_id = event.get("pathParameters", {}).get("patientId")
    alert_id = event.get("pathParameters", {}).get("alertId")
    table = table_from_env("ALERTS_TABLE")
    try:
        if method == "GET" and patient_id:
            result = table.query(
                IndexName="PatientAlertsIndex",
                KeyConditionExpression=Key("PatientId").eq(patient_id),
                ScanIndexForward=False,
            )
            return api_result(200, data=result.get("Items", []))
        if method == "PATCH" and alert_id:
            body = parse_body(event)
            status = body.get("status")
            if status not in ("OPEN", "ACKNOWLEDGED", "RESOLVED"):
                return api_result(400, message="status must be OPEN, ACKNOWLEDGED, or RESOLVED")
            if status == "RESOLVED" and "admin" not in groups_for(event):
                return api_result(403, message="Only administrators can resolve alerts")
            result = table.update_item(
                Key={"AlertId": alert_id},
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "Status"},
                ExpressionAttributeValues={":status": status},
                ConditionExpression="attribute_exists(AlertId)",
                ReturnValues="ALL_NEW",
            )
            return api_result(200, data=result["Attributes"], message="Alert status updated")
        return api_result(405, message="Unsupported alert operation")
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return api_result(404, message="Alert not found")
