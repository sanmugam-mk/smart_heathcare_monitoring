import json
from unittest.mock import patch

from patient_crud.handler import lambda_handler


class MockTable:
    def __init__(self):
        self.item = None

    def put_item(self, **kwargs):
        self.item = kwargs["Item"]


def event(method, body=None, groups=None):
    return {
        "requestContext": {
            "http": {"method": method},
            "authorizer": {"jwt": {"claims": {"cognito:groups": groups or []}}},
        },
        "pathParameters": {},
        "body": json.dumps(body or {}),
    }


def test_register_patient_stores_required_fields():
    table = MockTable()
    request = event("POST", {"PatientId": "P001", "FullName": "Demo Patient", "Age": 42, "Gender": "Other"})
    with patch("patient_crud.handler.table_from_env", return_value=table):
        result = lambda_handler(request, None)
    assert result["statusCode"] == 201
    assert table.item["PatientId"] == "P001"
    assert table.item["Status"] == "ACTIVE"
    assert table.item["CreatedAt"].endswith("Z")


def test_delete_requires_admin_group():
    table = MockTable()
    request = event("DELETE", groups=["doctor"])
    request["pathParameters"] = {"patientId": "P001"}
    with patch("patient_crud.handler.table_from_env", return_value=table):
        result = lambda_handler(request, None)
    assert result["statusCode"] == 403
