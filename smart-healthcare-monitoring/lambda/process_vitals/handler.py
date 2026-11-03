import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3

from shared import json_default, table_from_env, utc_now

logger = logging.getLogger()
logger.setLevel(logging.INFO)
_lambda = boto3.client("lambda")
_sns = boto3.client("sns")

RANGES = {
    "NORMAL": {"HeartRate": (65, 95), "SpO2": (96, 100), "Temperature": (36.3, 37.4)},
    "WARNING": {"HeartRate": (100, 115), "SpO2": (92, 95), "Temperature": (37.6, 38.2)},
    "HIGH_RISK": {"HeartRate": (120, 140), "SpO2": (85, 91), "Temperature": (38.5, 39.5)},
}
ISO_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$")


def validate(payload, topic):
    required = ("PatientId", "HeartRate", "SpO2", "Temperature", "DeviceID", "Source", "Timestamp", "SimulationMode")
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    patient_id = payload["PatientId"]
    if not isinstance(patient_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", patient_id):
        raise ValueError("PatientId has an invalid format")
    if topic and topic != f"smart-healthcare/{patient_id}/vitals":
        raise ValueError("MQTT topic does not match PatientId")
    if payload["Source"] != "ESP32_SIMULATED" or payload["DeviceID"] != "ESP32_SIMULATOR":
        raise ValueError("Unexpected device identity or data source")
    timestamp = payload["Timestamp"]
    if not isinstance(timestamp, str) or not ISO_TIMESTAMP.fullmatch(timestamp):
        raise ValueError("Timestamp must be an ISO 8601 timestamp with timezone")
    parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    timestamp = parsed_timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    mode = payload["SimulationMode"]
    if mode not in RANGES:
        raise ValueError("SimulationMode must be NORMAL, WARNING, or HIGH_RISK")

    item = {
        "PatientId": patient_id,
        "Timestamp": timestamp,
        "DeviceID": payload["DeviceID"],
        "Source": payload["Source"],
        "SimulationMode": mode,
    }
    for field in ("HeartRate", "SpO2", "Temperature"):
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be a numeric JSON value")
        low, high = RANGES[mode][field]
        numeric_value = float(value)
        if not low <= numeric_value <= high:
            raise ValueError(f"{field} is outside the allowed {mode} simulation range")
        item[field] = value if isinstance(value, int) else Decimal(str(value))
    return item


def lambda_handler(event, context):
    try:
        payload = event
        if isinstance(event, dict) and isinstance(event.get("payload"), str):
            payload = json.loads(event["payload"])
        topic = event.get("topic") if isinstance(event, dict) else None
        item = validate(payload, topic)
        table_from_env("VITALS_TABLE").put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PatientId) AND attribute_not_exists(#ts)",
            ExpressionAttributeNames={"#ts": "Timestamp"},
        )
        invocation = _lambda.invoke(
            FunctionName=os.environ["RISK_FUNCTION_NAME"],
            InvocationType="RequestResponse",
            Payload=json.dumps({"reading": item}, default=json_default).encode(),
        )
        if invocation.get("FunctionError"):
            raise RuntimeError(f"RiskAssessment invocation failed: {invocation['FunctionError']}")
        risk_result = json.loads(invocation["Payload"].read())
        risk = risk_result.get("risk_assessment")
        if not risk:
            raise RuntimeError("RiskAssessment returned no assessment")

        if risk["Category"] in ("WARNING", "HIGH"):
            alert = {
                "AlertId": str(uuid.uuid4()),
                "PatientId": item["PatientId"],
                "AlertType": risk["Category"],
                "Message": "; ".join(risk["Reasons"]),
                "Severity": risk["RiskLevel"],
                "Timestamp": utc_now(),
                "Status": "OPEN",
            }
            table_from_env("ALERTS_TABLE").put_item(Item=alert)
            if risk["Category"] == "HIGH":
                topic_arn = os.environ.get("ALERTS_TOPIC_ARN")
                if topic_arn:
                    _sns.publish(
                        TopicArn=topic_arn,
                        Subject=f"High demonstration risk: {item['PatientId']}",
                        Message=json.dumps(alert),
                    )

        logger.info("Processed patient=%s timestamp=%s category=%s",
                    item["PatientId"], item["Timestamp"], risk["Category"])
        return {"statusCode": 200, "message": "Reading processed", "risk": risk}
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Rejected IoT message: %s", exc)
        raise
    except Exception:
        logger.exception("Failed to process IoT message")
        raise
