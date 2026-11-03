param(
    [switch]$RunAwsChecks,
    [string]$StackName = "smart-healthcare-monitoring",
    [string]$Region = "ap-south-1"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $venvPython = ".\.venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) { throw "Run .\scripts\setup.ps1 before local tests." }
    & $venvPython -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Local tests failed." }

    if (-not $RunAwsChecks) {
        Write-Host "Local tests passed. To run read-only deployed-resource checks, add -RunAwsChecks."
        return
    }
    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw "AWS CLI is required for cloud checks." }
    $stack = & aws cloudformation describe-stacks --stack-name $StackName --region $Region --output json --no-cli-pager | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw "Could not read the CloudFormation stack. Confirm stack name, region, and AWS identity." }
    $outputs = $stack.Stacks[0].Outputs
    $apiBase = ($outputs | Where-Object OutputKey -eq "ApiBaseUrl").OutputValue
    if (-not $apiBase) { throw "Stack output ApiBaseUrl was not found." }

    $resourcesJson = & aws cloudformation list-stack-resources --stack-name $StackName --region $Region --output json --no-cli-pager
    if ($LASTEXITCODE -ne 0) { throw "Could not list stack resources." }
    $resources = ($resourcesJson | ConvertFrom-Json).StackResourceSummaries
    foreach ($logicalId in @("PatientsTable", "VitalReadingsTable", "RiskAssessmentsTable", "AlertsTable", "DocumentsTable")) {
        $resource = $resources | Where-Object LogicalResourceId -eq $logicalId | Select-Object -First 1
        if (-not $resource) { throw "Missing deployed resource: $logicalId" }
        $tableJson = & aws dynamodb describe-table --table-name $resource.PhysicalResourceId --region $Region --output json --no-cli-pager
        if ($LASTEXITCODE -ne 0 -or ($tableJson | ConvertFrom-Json).Table.TableStatus -ne "ACTIVE") {
            throw "DynamoDB table $logicalId is not ACTIVE."
        }
        Write-Host "PASS: $logicalId is ACTIVE"
    }

    foreach ($logicalId in @("PatientCrudFunction", "GetVitalsFunction", "RiskAssessmentFunction", "ProcessVitalsFunction", "DocumentManagementFunction", "AlertManagementFunction")) {
        $function = $resources | Where-Object LogicalResourceId -eq $logicalId | Select-Object -First 1
        if (-not $function) { throw "Missing deployed resource: $logicalId" }
        & aws lambda get-function-configuration --function-name $function.PhysicalResourceId --region $Region --query "State" --output text --no-cli-pager
        if ($LASTEXITCODE -ne 0) { throw "Could not inspect Lambda $logicalId." }
    }
    & aws iot get-topic-rule --rule-name SmartHealthcareProcessVitals --region $Region --query "rule.ruleDisabled" --output text --no-cli-pager
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect the IoT topic rule." }

    $tokenSecure = Read-Host "Paste a valid Cognito access token for a read-only P001 latest-vitals API check" -AsSecureString
    $tokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($tokenSecure)
    try { $accessToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPtr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPtr) }
    try {
        $result = Invoke-RestMethod -Method Get -Uri "$apiBase/patients/P001/vitals/latest" -Headers @{ Authorization = "Bearer $accessToken" }
        if ($null -eq $result.data) {
            Write-Warning "API is reachable, but no AWS-stored P001 reading exists yet."
        } else {
            Write-Host "PASS: API returned AWS-stored data for $($result.data.Timestamp)"
        }
    } finally {
        $accessToken = $null
        $tokenSecure = $null
    }
    Write-Host "Checks confirmed resource/API availability only. Verify MQTT delivery, Lambda logs, and DynamoDB data separately."
} finally {
    Pop-Location
}
