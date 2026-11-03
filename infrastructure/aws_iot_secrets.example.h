#pragma once

// Copy this file to aws_iot_secrets.h and replace the placeholders using a
// newly issued AWS IoT device certificate and private key. Never commit that file.
const char AWS_CERT_CA[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
REPLACE_WITH_AMAZON_ROOT_CA
-----END CERTIFICATE-----
)EOF";

const char AWS_CERT_CRT[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
REPLACE_WITH_DEVICE_CERTIFICATE
-----END CERTIFICATE-----
)EOF";

const char AWS_CERT_PRIVATE[] PROGMEM = R"EOF(
-----BEGIN PRIVATE KEY-----
REPLACE_WITH_DEVICE_PRIVATE_KEY
-----END PRIVATE KEY-----
)EOF";
