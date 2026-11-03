param(
    [string]$StackName = "smart-healthcare-monitoring",
    [string]$Region = "ap-south-1",
    [string]$FrontendOrigin = "http://localhost:8000",
    [string]$FrontendRedirectUri = "http://localhost:8000/",
    [string]$CognitoDomainPrefix = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw "AWS CLI v2 is required." }
    if (-not (Get-Command sam -ErrorAction SilentlyContinue)) { throw "AWS SAM CLI is required." }
    if (-not $CognitoDomainPrefix) {
        $CognitoDomainPrefix = Read-Host "Enter a globally unique Cognito hosted UI domain prefix"
    }
    if ($CognitoDomainPrefix -notmatch "^[a-z0-9][a-z0-9-]{0,62}$") {
        throw "Cognito domain prefix must be 1-63 lowercase letters, numbers, or hyphens."
    }
    if ($FrontendRedirectUri -notlike "$FrontendOrigin/*" -and $FrontendRedirectUri -ne "$FrontendOrigin/") {
        throw "FrontendRedirectUri must use the exact FrontendOrigin."
    }
    & aws sts get-caller-identity --region $Region --no-cli-pager
    if ($LASTEXITCODE -ne 0) { throw "AWS identity check failed; configure a deployment identity first." }

    Write-Host ""
    Write-Host "APPROVAL REQUIRED. This deploys or updates stack '$StackName' in $Region."
    Write-Host "Resources: five on-demand DynamoDB tables; private encrypted S3 bucket; SNS topic;"
    Write-Host "Cognito pool/client/domain/groups; HTTP API; six Lambda functions and IAM roles;"
    Write-Host "IoT Thing, restricted IoT policy, IoT rule, and logging."
    Write-Host "AWS charges may apply for requests, storage, data transfer, logs, and IoT traffic."
    Write-Host "This script does NOT create device certificates, publish readings, or delete resources."
    Write-Host "Existing fixed-name IoT rules/Things may cause a deployment conflict; inspect first."
    $approval = Read-Host "Type DEPLOY exactly to continue"
    if ($approval -cne "DEPLOY") {
        Write-Host "Deployment cancelled. No AWS resources were created."
        return
    }

    & sam validate --lint --template-file infrastructure\template.yaml
    if ($LASTEXITCODE -ne 0) { throw "SAM validation failed; deployment stopped." }
    & sam build --template-file infrastructure\template.yaml
    if ($LASTEXITCODE -ne 0) { throw "SAM build failed; deployment stopped." }
    & sam deploy `
        --stack-name $StackName `
        --region $Region `
        --capabilities CAPABILITY_IAM `
        --resolve-s3 `
        --parameter-overrides `
            "FrontendOrigin=$FrontendOrigin" `
            "FrontendRedirectUri=$FrontendRedirectUri" `
            "CognitoDomainPrefix=$CognitoDomainPrefix"
    if ($LASTEXITCODE -ne 0) { throw "SAM deployment failed. Review the CloudFormation stack events." }
    Write-Host "Deployment command completed. Verify stack outputs and health before using the app."
} finally {
    Pop-Location
}
