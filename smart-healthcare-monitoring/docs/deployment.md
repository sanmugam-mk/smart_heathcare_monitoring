# Deployment guide

1. Install Python 3.12, AWS CLI v2, AWS SAM CLI, and PlatformIO.
2. Run `.\scripts\setup.ps1`; fix any missing tool before continuing.
3. Run local tests with `.\.venv\Scripts\python.exe -m pytest`.
4. Validate infrastructure with `sam validate --lint --template-file infrastructure\template.yaml`.
5. Review [aws-setup.md](aws-setup.md), select stack name/domain prefix/frontend origin, and review current AWS costs.
6. Deploy only after explicit approval: `.\scripts\deploy.ps1`. It asks for the exact word `DEPLOY`.
7. Create the first Cognito doctor and admin users and confirm any SNS subscription.
8. Copy stack outputs into `frontend\js\config.js`.
9. Create/attach the device certificate and configure `infrastructure\credentials.h`.
10. Build/flash the ESP32, check IoT MQTT Test Client receipt, then verify Lambda/DynamoDB/API/dashboard in order.

To host the frontend locally: `python -m http.server 8000 --directory frontend`. Keep the server running and browse to `http://localhost:8000/`. The AWS Cognito callback must be exactly the URI configured in the stack.

No deployment or cleanup is performed merely by reading this document. Deployment is an AWS cost-incurring action; cleanup can permanently remove stack resources.
