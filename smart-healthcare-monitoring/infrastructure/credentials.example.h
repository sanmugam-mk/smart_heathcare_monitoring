#pragma once

// Copy this file to credentials.h and replace the placeholders.
// Never commit credentials.h or print secrets to Serial.
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

static const char AWS_ROOT_CA[] PROGMEM = R"PEM(
-----BEGIN CERTIFICATE-----
PASTE_AMAZON_ROOT_CA_1_HERE
-----END CERTIFICATE-----
)PEM";

static const char AWS_DEVICE_CERT[] PROGMEM = R"PEM(
-----BEGIN CERTIFICATE-----
PASTE_DEVICE_CERTIFICATE_HERE
-----END CERTIFICATE-----
)PEM";

static const char AWS_DEVICE_PRIVATE_KEY[] PROGMEM = R"PEM(
-----BEGIN RSA PRIVATE KEY-----
PASTE_DEVICE_PRIVATE_KEY_HERE
-----END RSA PRIVATE KEY-----
)PEM";
