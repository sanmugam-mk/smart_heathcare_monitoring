import json
import logging
import boto3
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
sns = boto3.client("sns", region_name="ap-south-1")

vitals_table = dynamodb.Table("VitalReadings")
risk_table = dynamodb.Table("RiskAssessments")
alerts_table = dynamodb.Table("Alerts")

SNS_TOPIC_ARN = "arn:aws:sns:ap-south-1:798645002694:EHR-HighRiskAlerts"


def lambda_handler(event, context):
    logger.info("Received telemetry ingestion request")

    if isinstance(event.get("body"), str):
        try:
            payload = json.loads(event["body"])
        except json.JSONDecodeError:
            return http_response(400, {"error": "Request body must be valid JSON"})
    elif isinstance(event.get("body"), dict):
        payload = event["body"]
    else:
        payload = event

    patient_id = payload.get("PatientId") or payload.get("patient_id")
    if not patient_id:
        return http_response(400, {"error": "Missing PatientId"})

    finger_detected = payload.get("FingerDetected")
    if finger_detected is not None and not isinstance(finger_detected, bool):
        return http_response(400, {"error": "FingerDetected must be a boolean"})
    sensor_ready = payload.get("SensorReady")
    if sensor_ready is not None and not isinstance(sensor_ready, bool):
        return http_response(400, {"error": "SensorReady must be a boolean"})

    metrics = {}
    for metric in ("HeartRate", "SpO2", "Temperature"):
        if metric not in payload or payload[metric] is None:
            continue
        if isinstance(payload[metric], bool):
            return http_response(400, {"error": f"{metric} must be a finite number"})
        try:
            value = Decimal(str(payload[metric]))
        except (ValueError, TypeError, ArithmeticError):
            return http_response(400, {"error": f"{metric} must be a finite number"})
        if not value.is_finite():
            return http_response(400, {"error": f"{metric} must be a finite number"})
        metrics[metric] = value

    if not metrics and finger_detected is None:
        return http_response(400, {"error": "At least one measured vital or finger-detection status is required"})

    timestamp = payload.get("Timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not isinstance(timestamp, str) or not timestamp.strip():
        return http_response(400, {"error": "Timestamp must be a non-empty string"})
    try:
        datetime.fromisoformat(timestamp.strip().replace("Z", "+00:00"))
    except ValueError:
        return http_response(400, {"error": "Timestamp must be an ISO-8601 date-time"})
    timestamp = timestamp.strip()

    vital_item = {
        "PatientId": str(patient_id),
        "Timestamp": timestamp,
        **metrics,
        "DeviceID": str(payload.get("DeviceID", "unknown")),
        "Source": str(payload.get("Source", "unknown"))
    }
    if finger_detected is not None:
        vital_item["FingerDetected"] = finger_detected
    if sensor_ready is not None:
        vital_item["SensorReady"] = sensor_ready

    try:
        vitals_table.put_item(Item=vital_item)
        assessment = None
        if metrics:
            assessment = evaluate_risk(
                patient_id,
                timestamp,
                metrics.get("HeartRate"),
                metrics.get("SpO2"),
                metrics.get("Temperature")
            )
            risk_table.put_item(Item={
                "PatientId": str(patient_id),
                "Timestamp": timestamp,
                "RiskLevel": assessment["RiskLevel"],
                "RiskScore": Decimal(str(assessment["RiskScore"])),
                "DetectedAbnormalities": assessment["DetectedAbnormalities"],
                "Explanation": assessment["Explanation"]
            })
            if assessment["RiskLevel"] == "HIGH":
                trigger_high_risk_alert(str(patient_id), timestamp, vital_item, assessment)
    except Exception:
        logger.exception("Failed to persist or assess telemetry")
        return http_response(500, {"error": "Telemetry could not be processed"})

    logger.info("Telemetry stored and risk assessment completed")
    result = {
        "message": "Telemetry processed successfully",
        "patient_id": str(patient_id),
        "finger_detected": finger_detected
    }
    if assessment:
        result.update({
            "risk_level": assessment["RiskLevel"],
            "risk_score": assessment["RiskScore"],
            "abnormalities": assessment["DetectedAbnormalities"],
            "explanation": assessment["Explanation"]
        })
    return http_response(200, result)


def evaluate_risk(patient_id, timestamp, heart_rate, spo2, temperature):
    """
    Clinical Decision Rule Engine:
    Evaluates vital metrics against medical baseline thresholds.
    - Heart Rate (BPM): Normal 60-100, Warning 50-59 or 101-120, Critical <50 or >120
    - SpO2 (%): Normal >=95, Warning 92-94, Critical <92
    - Temperature (°C): Normal 36.5-37.5, Warning 37.6-38.2 or 35.5-36.4, Critical >38.2 or <35.5
    """
    score = 0
    abnormalities = []
    explanations = []

    # --- Heart Rate Assessment ---
    if heart_rate is not None and heart_rate > 120:
        score += 4
        abnormalities.append("CRITICAL_HIGH_HEART_RATE")
        explanations.append(f"Severe tachycardia detected: Heart Rate ({heart_rate:.1f} BPM) > 120 BPM.")
    elif heart_rate is not None and heart_rate > 100:
        score += 2
        abnormalities.append("ELEVATED_HEART_RATE")
        explanations.append(f"Elevated heart rate detected: Heart Rate ({heart_rate:.1f} BPM) > 100 BPM.")
    elif heart_rate is not None and heart_rate < 50:
        score += 4
        abnormalities.append("CRITICAL_LOW_HEART_RATE")
        explanations.append(f"Severe bradycardia detected: Heart Rate ({heart_rate:.1f} BPM) < 50 BPM.")
    elif heart_rate is not None and heart_rate < 60:
        score += 2
        abnormalities.append("LOW_HEART_RATE")
        explanations.append(f"Low heart rate detected: Heart Rate ({heart_rate:.1f} BPM) < 60 BPM.")

    # --- SpO2 Oxygen Saturation Assessment ---
    if spo2 is not None and spo2 < 92:
        score += 4
        abnormalities.append("CRITICAL_HYPOXIA")
        explanations.append(f"Severe hypoxemia detected: Oxygen Saturation SpO2 ({spo2:.1f}%) < 92%.")
    elif spo2 is not None and spo2 < 95:
        score += 2
        abnormalities.append("MILD_HYPOXIA")
        explanations.append(f"Mild oxygen desaturation detected: Oxygen Saturation SpO2 ({spo2:.1f}%) < 95%.")

    # --- Body Temperature Assessment ---
    if temperature is not None and temperature > 38.2:
        score += 3
        abnormalities.append("CRITICAL_HIGH_FEVER")
        explanations.append(f"High fever detected: Body Temperature ({temperature:.1f}°C) > 38.2°C.")
    elif temperature is not None and temperature > 37.5:
        score += 1
        abnormalities.append("ELEVATED_TEMPERATURE")
        explanations.append(f"Elevated temperature detected: Body Temperature ({temperature:.1f}°C) > 37.5°C.")
    elif temperature is not None and temperature < 35.5:
        score += 3
        abnormalities.append("CRITICAL_HYPOTHERMIA")
        explanations.append(f"Hypothermia risk detected: Body Temperature ({temperature:.1f}°C) < 35.5°C.")

    # --- Overall Risk Level Classification ---
    if score >= 5 or "CRITICAL_HYPOXIA" in abnormalities or "CRITICAL_HIGH_HEART_RATE" in abnormalities:
        level = "HIGH"
    elif score >= 2:
        level = "WARNING"
    else:
        level = "NORMAL"

    if not explanations:
        measured = []
        if heart_rate is not None:
            measured.append("heart rate")
        if spo2 is not None:
            measured.append("SpO2")
        if temperature is not None:
            measured.append("temperature")
        explanations.append(
            "Measured vital signs (" + ", ".join(measured) +
            ") are within configured ranges; unavailable measurements were not assessed."
        )

    return {
        "RiskLevel": level,
        "RiskScore": score,
        "DetectedAbnormalities": abnormalities,
        "Explanation": explanations
    }


def trigger_high_risk_alert(patient_id, timestamp, vital_item, assessment):
    """
    Dispatches urgent alert via Amazon SNS and logs alert to DynamoDB.
    """
    measured_values = []
    if "HeartRate" in vital_item:
        measured_values.append(f"  - Heart Rate: {vital_item['HeartRate']} BPM")
    if "SpO2" in vital_item:
        measured_values.append(f"  - SpO2: {vital_item['SpO2']}%")
    if "Temperature" in vital_item:
        measured_values.append(f"  - Temperature: {vital_item['Temperature']}°C")

    message_text = (
        f"EMERGENCY HEALTHCARE ALERT - HIGH RISK DETECTED\n"
        f"Patient ID: {patient_id}\n"
        f"Timestamp: {timestamp}\n"
        f"Risk Level: HIGH (Score: {assessment['RiskScore']})\n\n"
        f"Measured Vitals:\n" + "\n".join(measured_values) + "\n\n"
        f"Clinical Rationale:\n" + "\n".join(assessment['Explanation']) + "\n\n"
        f"Action Required: Immediate clinical evaluation recommended."
    )

    sns_message_id = "N/A"
    try:
        sns_res = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"HIGH RISK ALERT: Patient {patient_id}",
            Message=message_text
        )
        sns_message_id = sns_res.get("MessageId", "N/A")
        logger.info(f"Published SNS High-Risk alert for {patient_id}, MessageId={sns_message_id}")
    except Exception as e:
        logger.error(f"Failed to publish SNS alert: {str(e)}")

    # Log to DynamoDB Alerts table
    alerts_table.put_item(Item={
        "PatientId": patient_id,
        "Timestamp": timestamp,
        "RiskLevel": "HIGH",
        "VitalsSnapshot": {
            key: vital_item[key]
            for key in ("HeartRate", "SpO2", "Temperature")
            if key in vital_item
        },
        "Message": message_text,
        "SNSMessageId": sns_message_id,
        "Status": "SENT"
    })


def http_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS"
        },
        "body": json.dumps(body)
    }
