# AWS setup, deployment, and cost review

## Resources created by the SAM stack

Running the approved deployment creates five DynamoDB tables, one private encrypted S3 bucket, one SNS topic, one Cognito user pool/app client/domain/two groups, one API Gateway HTTP API, six Lambda functions and execution roles/log groups, one IoT Thing, one IoT policy, and one IoT topic rule plus Lambda invoke permission. Tables use on-demand billing. The S3 bucket blocks public access.

It does not create a device certificate/private key, send telemetry, create a public website, or delete existing resources. The IoT Thing name and IoT rule name are fixed; check for account/region collisions before deployment. Stack deletion is not automated.

## Before deployment

1. Review current pricing for `ap-south-1`, set an AWS Budget, and decide a stack name and unique Cognito domain prefix.
2. Configure AWS CLI with a non-root IAM identity that has enough permission to create the listed services, IAM roles, and CloudFormation resources.
3. Confirm the AWS identity and region:

   ```powershell
   aws sts get-caller-identity
   aws configure get region
   ```

4. Run `sam validate --lint --template-file infrastructure\template.yaml`.
5. Review the `FrontendOrigin`/`FrontendRedirectUri` values and desired risk thresholds in `infrastructure\template.yaml`.
6. Only then run `.\scripts\deploy.ps1`; inspect the cost/resource notice and type `DEPLOY`. SAM may also ask to confirm the CloudFormation change set.

Deployment can incur AWS charges; no specific estimate or free-tier eligibility is guaranteed.

## Outputs and frontend config

```powershell
aws cloudformation describe-stacks --stack-name smart-healthcare-monitoring --region ap-south-1 --query "Stacks[0].Outputs" --output table
```

Copy `ApiBaseUrl`, `UserPoolId`, `AppClientId`, and `CognitoHostedUi` into `frontend\js\config.js`. The redirect and logout URI must exactly match `FrontendRedirectUri`; the default is `http://localhost:8000/`. If hosting at a different origin, supply matching `FrontendOrigin` and `FrontendRedirectUri` values during stack deployment. `FrontendOrigin` must be an origin (no path) for CORS.

## Create doctor/admin accounts

The user pool is admin-created-only. Use a unique doctor email and a temporary password supplied interactively by the AWS CLI; never put a real password in a command file or source. Example placeholders:

```powershell
$poolId = "REGION_POOL_ID_FROM_STACK_OUTPUT"
aws cognito-idp admin-create-user --user-pool-id $poolId --username doctor@example.invalid --user-attributes Name=email,Value=doctor@example.invalid Name=email_verified,Value=true --region ap-south-1
aws cognito-idp admin-add-user-to-group --user-pool-id $poolId --username doctor@example.invalid --group-name doctor --region ap-south-1
```

Cognito creates a temporary password and prompts the user to set a permanent password on first login. Repeat with a separate administrator address and add that user to `admin`. Do not reuse the AWS account root user for application sign-in.

To subscribe to alerts, create a subscription for the `AlertsTopicArn` stack output using an approved email address and confirm the email:

```powershell
aws sns subscribe --topic-arn "SNS_TOPIC_ARN_FROM_STACK_OUTPUT" --protocol email --notification-endpoint "alerts@example.invalid" --region ap-south-1
```

SNS email notifications are emitted only for high-category demo scores. No recipient is subscribed automatically.

## IoT certificate and policy attachment

The stack creates the `ESP32_SIMULATOR` Thing, an IoT policy named `<stack-name>-esp32-publish`, and the processing rule. Create an active X.509 certificate in the AWS IoT console in `ap-south-1`, download its certificate and private key exactly once to a protected local folder, attach the certificate to the `ESP32_SIMULATOR` Thing, and attach the stack IoT policy. Keep the private key local and private.

Obtain this account's ATS data endpoint rather than assuming an endpoint:

```powershell
aws iot describe-endpoint --endpoint-type iot:Data-ATS --region ap-south-1 --query endpointAddress --output text
```

Compare it with `AWS_IOT_ENDPOINT` in the firmware and update it if the account endpoint differs. Create the local firmware secret header as described in [hardware-setup.md](hardware-setup.md).

## Verifying AWS components

The deployment script does not publish test messages. Use `.\scripts\test.ps1 -RunAwsChecks` for read-only stack/resource/API checks, then use the AWS IoT MQTT Test Client to subscribe to `smart-healthcare/+/vitals` and start the ESP32. Verify each distinct stage before claiming end-to-end success: MQTT client receipt, Lambda invocation/log, DynamoDB item, API response, and browser display. Detailed steps are in [testing.md](testing.md).

## Cleanup

`.\scripts\cleanup.ps1` intentionally does not delete anything. If you decide to retire the stack, first archive any data you need, consider the user pool and bucket contents, and review the exact CloudFormation deletion change set. Remove or empty retained data only after explicit human approval. CloudFormation stack deletion is irreversible for resources it owns.
