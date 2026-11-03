import re

from shared import api_result, groups_for, parse_body, table_from_env, utc_now


def _validate_patient(patient, create):
    allowed = {"FullName", "Age", "Gender", "Status"}
    unknown = set(patient) - allowed - ({"PatientId"} if create else set())
    if unknown:
        raise ValueError(f"Unsupported patient fields: {', '.join(sorted(unknown))}")
    if create:
        patient_id = patient.get("PatientId")
        if not isinstance(patient_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", patient_id):
            raise ValueError("PatientId must contain 1-64 letters, numbers, underscores, or hyphens")
    if "FullName" in patient and (not isinstance(patient["FullName"], str) or not patient["FullName"].strip()):
        raise ValueError("FullName must be a non-empty string")
    if "Age" in patient and (isinstance(patient["Age"], bool) or not isinstance(patient["Age"], int)
                             or not 0 <= patient["Age"] <= 125):
        raise ValueError("Age must be a whole number between 0 and 125")
    if "Gender" in patient and patient["Gender"] not in ("Female", "Male", "Other", "Prefer not to say"):
        raise ValueError("Gender must be Female, Male, Other, or Prefer not to say")
    if "Status" in patient and patient["Status"] not in ("ACTIVE", "INACTIVE"):
        raise ValueError("Status must be ACTIVE or INACTIVE")


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    patient_id = event.get("pathParameters", {}).get("patientId")
    table = table_from_env("PATIENTS_TABLE")
    try:
        if method == "GET" and not patient_id:
            result = table.scan()
            patients = result.get("Items", [])
            while result.get("LastEvaluatedKey"):
                result = table.scan(ExclusiveStartKey=result["LastEvaluatedKey"])
                patients.extend(result.get("Items", []))
            patients.sort(key=lambda item: item.get("PatientId", ""))
            return api_result(200, data=patients)
        if method == "POST":
            patient = parse_body(event)
            _validate_patient(patient, True)
            patient.update({"CreatedAt": utc_now(), "Status": patient.get("Status", "ACTIVE")})
            table.put_item(
                Item=patient,
                ConditionExpression="attribute_not_exists(PatientId)",
            )
            return api_result(201, data=patient, message="Patient registered")
        if method == "GET" and patient_id:
            result = table.get_item(Key={"PatientId": patient_id})
            if "Item" not in result:
                return api_result(404, message="Patient not found")
            return api_result(200, data=result["Item"])
        if method == "PUT" and patient_id:
            patient = parse_body(event)
            _validate_patient(patient, False)
            if not patient:
                return api_result(400, message="At least one patient field is required")
            update_parts = []
            names = {}
            values = {}
            for index, (field, value) in enumerate(patient.items()):
                name_key = f"#f{index}"
                value_key = f":v{index}"
                update_parts.append(f"{name_key} = {value_key}")
                names[name_key] = field
                values[value_key] = value
            result = table.update_item(
                Key={"PatientId": patient_id},
                UpdateExpression="SET " + ", ".join(update_parts),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ConditionExpression="attribute_exists(PatientId)",
                ReturnValues="ALL_NEW",
            )
            return api_result(200, data=result["Attributes"], message="Patient updated")
        if method == "DELETE" and patient_id:
            if "admin" not in groups_for(event):
                return api_result(403, message="Only administrators can delete patient records")
            result = table.delete_item(
                Key={"PatientId": patient_id},
                ConditionExpression="attribute_exists(PatientId)",
                ReturnValues="ALL_OLD",
            )
            return api_result(200, data=result.get("Attributes"), message="Patient deleted")
        return api_result(405, message="Unsupported patient operation")
    except ValueError as exc:
        return api_result(400, message=str(exc))
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        if method == "POST":
            return api_result(409, message="PatientId already exists")
        if method == "DELETE":
            return api_result(404, message="Patient not found")
        return api_result(404, message="Patient not found")
