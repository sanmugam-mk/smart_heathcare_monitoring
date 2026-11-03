import copy
from decimal import Decimal

import pytest

from process_vitals.handler import validate
from risk_assessment.handler import assess


@pytest.fixture
def normal_payload():
    return {
        "PatientId": "P001",
        "HeartRate": 78,
        "SpO2": 98,
        "Temperature": 36.8,
        "DeviceID": "ESP32_SIMULATOR",
        "Source": "ESP32_SIMULATED",
        "Timestamp": "2026-11-02T10:30:00Z",
        "SimulationMode": "NORMAL",
    }


def test_valid_normal_vitals_are_stored_as_numeric_values(normal_payload):
    item = validate(normal_payload, "smart-healthcare/P001/vitals")
    assert item["HeartRate"] == 78
    assert item["SpO2"] == 98
    assert item["Temperature"] == Decimal("36.8")
    assert isinstance(item["HeartRate"], int)


@pytest.mark.parametrize(
    ("mode", "heart_rate", "spo2", "temperature"),
    [
        ("NORMAL", 78, 98, 36.8),
        ("WARNING", 110, 94, 38.0),
        ("HIGH_RISK", 125, 88, 39.1),
    ],
)
def test_each_simulation_mode_validates(mode, heart_rate, spo2, temperature, normal_payload):
    payload = {**normal_payload, "SimulationMode": mode, "HeartRate": heart_rate,
               "SpO2": spo2, "Temperature": temperature}
    assert validate(payload, f"smart-healthcare/P001/vitals")["SimulationMode"] == mode


def test_rejects_wrong_topic_patient(normal_payload):
    with pytest.raises(ValueError, match="topic does not match"):
        validate(normal_payload, "smart-healthcare/P002/vitals")


def test_rejects_mode_out_of_range_value(normal_payload):
    payload = {**normal_payload, "HeartRate": 150}
    with pytest.raises(ValueError, match="outside the allowed"):
        validate(payload, "smart-healthcare/P001/vitals")


def test_rejects_string_measurements(normal_payload):
    payload = {**normal_payload, "SpO2": "98"}
    with pytest.raises(ValueError, match="numeric JSON"):
        validate(payload, "smart-healthcare/P001/vitals")


def test_normalizes_timestamp_to_utc(normal_payload):
    payload = {**normal_payload, "Timestamp": "2026-11-02T15:00:00+05:30"}
    assert validate(payload, "smart-healthcare/P001/vitals")["Timestamp"] == "2026-11-02T09:30:00Z"


def test_risk_uses_vitals_not_simulation_mode(normal_payload):
    first = assess(normal_payload)
    changed_mode = copy.deepcopy(normal_payload)
    changed_mode["SimulationMode"] = "HIGH_RISK"
    second = assess(changed_mode)
    assert first["RiskScore"] == second["RiskScore"] == 0
    assert first["Category"] == second["Category"] == "NORMAL"


def test_warning_and_high_values_map_to_expected_categories(normal_payload):
    warning = {**normal_payload, "HeartRate": 110, "SpO2": 94, "Temperature": 38.0}
    high = {**normal_payload, "HeartRate": 125, "SpO2": 88, "Temperature": 39.1}
    assert assess(warning)["Category"] == "WARNING"
    assert assess(high)["Category"] == "HIGH"
    assert 0 <= assess(high)["RiskScore"] <= 10
