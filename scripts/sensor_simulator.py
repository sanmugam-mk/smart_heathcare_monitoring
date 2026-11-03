#!/usr/bin/env python3
"""
Synthetic Health Data Sensor Simulator
Simulates lightweight ESP32 telemetry (Heart Rate, SpO2, Temperature) for Smart Healthcare Ingestion testing.
Uses AWS CLI subprocess for seamless cross-platform execution without extra dependencies.
"""

import json
import time
import random
import argparse
import subprocess
from datetime import datetime, timezone


def generate_vitals(mode):
    """
    Generates synthetic vitals based on simulation mode:
    - normal: Healthy baseline (Heart Rate 65-82, SpO2 96-99%, Temp 36.5-37.1°C)
    - warning: Mild elevation (Heart Rate 102-112, SpO2 93-95%, Temp 37.6-38.0°C)
    - high: Critical condition (Heart Rate 121-135, SpO2 88-91%, Temp 38.4-39.2°C)
    """
    if mode == "normal":
        heart_rate = random.uniform(65, 82)
        spo2 = random.uniform(96, 99)
        temperature = random.uniform(36.5, 37.1)
    elif mode == "warning":
        heart_rate = random.uniform(102, 112)
        spo2 = random.uniform(93, 95)
        temperature = random.uniform(37.6, 38.0)
    elif mode == "high":
        heart_rate = random.uniform(121, 135)
        spo2 = random.uniform(88, 91)
        temperature = random.uniform(38.4, 39.2)
    else:
        mode_choice = random.choice(["normal", "warning", "high"])
        return generate_vitals(mode_choice)

    return {
        "HeartRate": round(heart_rate, 1),
        "SpO2": round(spo2, 1),
        "Temperature": round(temperature, 1)
    }


def publish_telemetry(patient_id, mode, count, interval):
    print(f"\n--- Starting Synthetic Health Data Simulator ---")
    print(f"Patient ID: {patient_id} | Mode: [{mode.upper()}] | Count: {count} | Interval: {interval}s")
    print("-" * 75)

    for i in range(1, count + 1):
        vitals = generate_vitals(mode)
        payload = {
            "PatientId": patient_id,
            "Timestamp": datetime.now(timezone.utc).isoformat(),
            "HeartRate": vitals["HeartRate"],
            "SpO2": vitals["SpO2"],
            "Temperature": vitals["Temperature"],
            "DeviceID": "SIMULATOR_ESP32_P001",
            "Source": "SIMULATOR"
        }

        # Save temporary payload file
        payload_file = "lambda/temp_sim_payload.json"
        out_file = "lambda/temp_sim_out.json"
        with open(payload_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        try:
            cmd = [
                "aws", "lambda", "invoke",
                "--function-name", "EHR-IoTIngest",
                out_file,
                "--payload", f"file://{payload_file}",
                "--cli-binary-format", "raw-in-base64-out",
                "--region", "ap-south-1"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)

            if res.returncode == 0:
                with open(out_file, "r", encoding="utf-8") as f:
                    out_data = json.load(f)
                body_data = json.loads(out_data.get("body", "{}"))
                risk_level = body_data.get("risk_level", "UNKNOWN")
                print(f"[{i}/{count}] Telemetry Sent -> HR: {vitals['HeartRate']} BPM | SpO2: {vitals['SpO2']}% | Temp: {vitals['Temperature']} C ==> Risk Level: [{risk_level}]")
            else:
                print(f"[{i}/{count}] Error: {res.stderr.strip()}")
        except Exception as e:
            print(f"[{i}/{count}] Execution error: {str(e)}")

        if i < count:
            time.sleep(interval)

    print("\nSimulation stream completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic Sensor Telemetry Simulator")
    parser.add_argument("--patient", default="SIM-TEST", help="Test-only patient ID; must start with SIM-")
    parser.add_argument("--mode", choices=["normal", "warning", "high", "random"], default="normal", help="Simulation mode")
    parser.add_argument("--count", type=int, default=5, help="Number of messages to transmit")
    parser.add_argument("--interval", type=float, default=1.5, help="Interval in seconds between messages")
    parser.add_argument(
        "--confirm-cloud-write",
        action="store_true",
        help="Required to write synthetic readings to the configured AWS account"
    )

    args = parser.parse_args()
    if not args.patient.startswith("SIM-"):
        parser.error("Synthetic telemetry is restricted to patient IDs beginning with SIM-.")
    if not args.confirm_cloud_write:
        parser.error("Refusing to write cloud data without --confirm-cloud-write.")
    publish_telemetry(args.patient, args.mode, args.count, args.interval)
