import json
import logging
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
vitals_table = dynamodb.Table("VitalReadings")
risk_table = dynamodb.Table("RiskAssessments")
alerts_table = dynamodb.Table("Alerts")


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def lambda_handler(event, context):
    raw_path = event.get("rawPath", "")
    query_params = event.get("queryStringParameters") or {}
    path_params = event.get("pathParameters") or {}
    patient_id = path_params.get("PatientId") or query_params.get("PatientId")

    if not patient_id:
        return response(400, {"error": "PatientId path or query parameter is required"})

    try:
        if raw_path.endswith("/vitals") and "/patients/" in raw_path:
            return get_patient_monitoring(patient_id)
        elif raw_path.endswith("/alerts") and "/patients/" in raw_path:
            return get_patient_alerts(patient_id)
        elif "/vitals/latest" in raw_path:
            return get_latest_vitals_and_risk(patient_id)
        elif "/vitals/history" in raw_path:
            return get_vital_history(patient_id)
        elif "/vitals/alerts" in raw_path:
            return get_patient_alerts(patient_id)
        elif raw_path.endswith("/risk"):
            return get_patient_latest_risk(patient_id)
        else:
            action = query_params.get("action", "latest")
            if action == "history":
                return get_vital_history(patient_id)
            elif action == "alerts":
                return get_patient_alerts(patient_id)
            else:
                return get_latest_vitals_and_risk(patient_id)
    except Exception:
        logger.exception("Error serving patient monitoring request")
        return response(500, {"error": "Patient monitoring data could not be loaded"})


def get_patient_monitoring(patient_id):
    vitals_res = vitals_table.query(
        KeyConditionExpression=Key("PatientId").eq(patient_id),
        ScanIndexForward=False,
        Limit=30
    )
    history = vitals_res.get("Items", [])
    history.reverse()

    risk_res = risk_table.query(
        KeyConditionExpression=Key("PatientId").eq(patient_id),
        ScanIndexForward=False,
        Limit=1
    )

    return response(200, {
        "PatientId": patient_id,
        "Latest": history[-1] if history else None,
        "History": history,
        "LatestRisk": risk_res["Items"][0] if risk_res.get("Items") else None
    })


def get_patient_latest_risk(patient_id):
    risk_res = risk_table.query(
        KeyConditionExpression=Key("PatientId").eq(patient_id),
        ScanIndexForward=False,
        Limit=1
    )
    latest_risk = risk_res["Items"][0] if risk_res.get("Items") else None
    return response(200, {"PatientId": patient_id, "LatestRisk": latest_risk})


def get_latest_vitals_and_risk(patient_id):
    # Fetch latest vital reading
    vitals_res = vitals_table.query(
        KeyConditionExpression=Key("PatientId").eq(patient_id),
        ScanIndexForward=False,
        Limit=1
    )
    latest_vital = vitals_res["Items"][0] if vitals_res.get("Items") else None

    # Fetch latest risk assessment
    risk_res = risk_table.query(
        KeyConditionExpression=Key("PatientId").eq(patient_id),
        ScanIndexForward=False,
        Limit=1
    )
    latest_risk = risk_res["Items"][0] if risk_res.get("Items") else None

    return response(200, {
        "PatientId": patient_id,
        "LatestVital": latest_vital,
        "LatestRiskAssessment": latest_risk
    })


def get_vital_history(patient_id):
    # Fetch last 30 readings for trend graphs (ascending order for charts)
    vitals_res = vitals_table.query(
        KeyConditionExpression=Key("PatientId").eq(patient_id),
        ScanIndexForward=False,
        Limit=30
    )
    items = vitals_res.get("Items", [])
    items.reverse()  # Chronological order for line charts

    return response(200, {
        "PatientId": patient_id,
        "History": items,
        "Count": len(items)
    })


def get_patient_alerts(patient_id):
    # Fetch alert history for patient
    alerts_res = alerts_table.query(
        KeyConditionExpression=Key("PatientId").eq(patient_id),
        ScanIndexForward=False,
        Limit=20
    )
    return response(200, {
        "PatientId": patient_id,
        "Alerts": alerts_res.get("Items", []),
        "Count": len(alerts_res.get("Items", []))
    })


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
        },
        "body": json.dumps(body, cls=DecimalEncoder)
    }
