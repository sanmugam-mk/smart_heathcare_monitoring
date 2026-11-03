# ESP32 firmware and hardware setup

## Hardware

- ESP32 DevKit / ESP32-WROOM board.
- USB data cable.
- Windows laptop with VS Code and PlatformIO IDE.
- 2.4 GHz Wi-Fi connectivity.

No MAX30102, DS18B20, or other vital sensor is required. All measurements are generated in firmware and labeled simulated.

## Configure credentials without committing them

1. Create/activate an AWS IoT X.509 device certificate in `ap-south-1`.
2. Attach it to Thing `ESP32_SIMULATOR` and the stack-created IoT policy. The policy only grants MQTT connect as `ESP32_SIMULATOR` and publish to `smart-healthcare/P001/vitals`.
3. Obtain the Amazon Root CA 1 certificate from AWS's official IoT documentation. Verify the AWS trust chain before using it.
4. Copy `infrastructure\credentials.example.h` to `infrastructure\credentials.h`.
5. Replace the five marked placeholders with the Wi-Fi SSID/password, Root CA, device certificate, and private key. Keep PEM boundaries intact. Do not paste passwords or private keys into Serial Monitor or commit `credentials.h`.
6. If the account's ATS endpoint differs from the firmware value, update `AWS_IOT_ENDPOINT` in `infrastructure\esp32_smart_health.ino`.

The local `credentials.h`, `.pem`, `.key`, and `.crt` files are ignored by `.gitignore`. Keep a secure backup of the private key; AWS does not provide it again after download.

## Build, upload, monitor

Open the `smart-healthcare-monitoring` folder as the PlatformIO project. The project root config points PlatformIO at `infrastructure\esp32_smart_health.ino`.

```powershell
platformio run -e esp32dev
platformio run -e esp32dev -t upload --upload-port COM5
platformio device monitor -e esp32dev --port COM5 --baud 115200
```

Change simulation mode using the `simulationMode` setting near the top of the sketch (`NORMAL_MODE` default; alternatives `WARNING_MODE`, `HIGH_RISK_MODE`). Values are continuous and updated every five seconds. The firmware synchronizes UTC with NTP and does not publish until it can create a valid ISO 8601 timestamp.

Serial output never contains credentials. `MQTT Data Published Successfully!` is printed only if the MQTT client publish call succeeds.

## Troubleshooting

- Wi-Fi not connected: check 2.4 GHz availability, SSID/password, and signal.
- TLS/MQTT not connected: check active certificate, matching private key, attached policy and Thing, endpoint, time sync, and outbound port 8883.
- MQTT connects but no Lambda/DynamoDB item: inspect IoT rule status, Lambda invoke permission, Lambda CloudWatch logs, payload topic/field names, and simulation bounds.
- Dashboard is unauthorized: use a Cognito doctor/admin user and verify JWT, callback URI, API URL, and CORS origin.
- Build cannot find `credentials.h`: copy the example header and fill all placeholders before building.
