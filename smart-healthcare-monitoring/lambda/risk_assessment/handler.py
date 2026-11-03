import os

from boto3.dynamodb.conditions import Key

from shared import api_result, table_from_env


def assess(reading):
    heart_rate = float(reading["HeartRate"])
    spo2 = float(reading["SpO2"])
    temperature = float(reading["Temperature"])
    reasons = []
    score = 0

    hr_elevated = float(os.environ.get("THRESHOLD_HR_ELEVATED", "100"))
    hr_high = float(os.environ.get("THRESHOLD_HR_HIGH", "116"))
    spo2_low = float(os.environ.get("THRESHOLD_SPO2_LOW", "96"))
    spo2_high = float(os.environ.get("THRESHOLD_SPO2_HIGH", "92"))
    temp_elevated = float(os.environ.get("THRESHOLD_TEMP_ELEVATED", "37.5"))
    temp_high = float(os.environ.get("THRESHOLD_TEMP_HIGH", "38.3"))

    if heart_rate >= hr_high:
        score += 3
        reasons.append(f"Heart rate is high ({heart_rate:g} BPM).")
    elif heart_rate >= hr_elevated:
        score += 1
        reasons.append(f"Heart rate is above the configured baseline ({heart_rate:g} BPM).")
    elif heart_rate < 50:
        score += 2
        reasons.append(f"Heart rate is below the configured baseline ({heart_rate:g} BPM).")

    if spo2 < 88:
        score += 4
        reasons.append(f"SpO2 is critically low ({spo2:g}%).")
    elif spo2 < spo2_high:
        score += 3
        reasons.append(f"SpO2 is low ({spo2:g}%).")
    elif spo2 < spo2_low:
        score += 1
        reasons.append(f"SpO2 is below the configured baseline ({spo2:g}%).")

    if temperature >= 39:
        score += 5
        reasons.append(f"Temperature is very high ({temperature:.1f} C).")
    elif temperature >= temp_high:
        score += 4
        reasons.append(f"Temperature is high ({temperature:.1f} C).")
    elif temperature >= temp_elevated:
        score += 1
        reasons.append(f"Temperature is above the configured baseline ({temperature:.1f} C).")

    score = min(score, 10)
    risk_level = "NORMAL" if score == 0 else "LOW" if score <= 2 else "MODERATE" if score <= 5 else "HIGH"
    display_category = "NORMAL" if score == 0 else "WARNING" if score <= 5 else "HIGH"
    if not reasons:
        reasons.append("All received values are within configured demonstration thresholds.")

    return {
        "PatientId": reading["PatientId"],
        "Timestamp": reading["Timestamp"],
        "RiskScore": score,
        "RiskLevel": risk_level,
        "Category": display_category,
        "Reasons": reasons,
        "CreatedAt": reading["Timestamp"],
        "Disclaimer": "Illustrative demonstration only; not a medically validated diagnostic system.",
    }


def lambda_handler(event, context):
    if "reading" in event:
        assessment = assess(event["reading"])
        table_from_env("RISK_TABLE").put_item(Item=assessment)
        return {"risk_assessment": assessment}

    patient_id = event.get("pathParameters", {}).get("patientId")
    if not patient_id:
        return api_result(400, message="patientId is required")
    if event.get("rawPath", "").endswith("/risk/history"):
        query = event.get("queryStringParameters") or {}
        try:
            limit = int(query.get("limit", "100"))
        except ValueError:
            return api_result(400, message="limit must be a whole number")
        if not 1 <= limit <= 500:
            return api_result(400, message="limit must be between 1 and 500")
        result = table_from_env("RISK_TABLE").query(
            KeyConditionExpression=Key("PatientId").eq(patient_id),
            ScanIndexForward=False,
            Limit=limit,
        )
        return api_result(200, data=result.get("Items", []))

    vitals = table_from_env("VITALS_TABLE")
    result = vitals.query(
        KeyConditionExpression="PatientId = :patient",
        ExpressionAttributeValues={":patient": patient_id},
        ScanIndexForward=False,
        Limit=1,
    )
    latest = result.get("Items", [])
    if not latest:
        return api_result(200, data=None, message="No readings are available yet")
    reading = latest[0]
    risk = table_from_env("RISK_TABLE").get_item(
        Key={"PatientId": patient_id, "Timestamp": reading["Timestamp"]}
    ).get("Item")
    if risk is None:
        risk = assess(reading)
        table_from_env("RISK_TABLE").put_item(Item=risk)
    return api_result(200, data=risk)
