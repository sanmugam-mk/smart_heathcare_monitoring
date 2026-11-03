import json
from decimal import Decimal

from shared import api_result, groups_for


def test_api_responses_have_consistent_json_envelope_and_numeric_values():
    result = api_result(200, data={"PatientId": "P001", "HeartRate": Decimal("78")})
    payload = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert payload["success"] is True
    assert payload["data"]["HeartRate"] == 78


def test_error_response_has_message():
    result = api_result(401, message="Unauthorized")
    payload = json.loads(result["body"])
    assert payload == {"success": False, "message": "Unauthorized"}


def test_cognito_json_encoded_groups_are_parsed():
    event = {"requestContext": {"authorizer": {"jwt": {"claims": {"cognito:groups": "[\"admin\"]"}}}}}
    assert groups_for(event) == ["admin"]
