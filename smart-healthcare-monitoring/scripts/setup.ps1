$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    Write-Host "Checking local tools. This script does not contact AWS or create cloud resources."
    $python = Get-Command py -ErrorAction SilentlyContinue
    if ($python) {
        & py -3.12 --version
        if ($LASTEXITCODE -ne 0) { throw "Python 3.12 was not found through the Windows py launcher." }
        $pythonCommand = "py"
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { throw "Install Python 3.12 and ensure python.exe is on PATH." }
        & python --version
        if ($LASTEXITCODE -ne 0) { throw "Python could not be started." }
        $pythonCommand = "python"
    }

    foreach ($tool in @("aws", "sam", "platformio")) {
        if (Get-Command $tool -ErrorAction SilentlyContinue) {
            Write-Host "$tool is available."
        } else {
            Write-Warning "$tool was not found on PATH."
        }
    }
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        if ($pythonCommand -eq "py") { & py -3.12 -m venv .venv } else { & python -m venv .venv }
        if ($LASTEXITCODE -ne 0) { throw "Could not create the local Python virtual environment." }
    }
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Installing local test requirements failed." }

    if (Get-Command sam -ErrorAction SilentlyContinue) {
        & sam validate --lint --template-file infrastructure\template.yaml
        if ($LASTEXITCODE -ne 0) { throw "SAM template validation failed." }
    } else {
        Write-Warning "Install AWS SAM CLI before deployment; SAM validation was skipped."
    }
    if (Get-Command aws -ErrorAction SilentlyContinue) {
        $configuredRegion = & aws configure get region
        if ($configuredRegion -ne "ap-south-1") {
            Write-Warning "AWS CLI default region is '$configuredRegion'; this project deploys to ap-south-1. Set --region or configure the intended profile."
        } else {
            Write-Host "AWS CLI default region is ap-south-1."
        }
        & aws sts get-caller-identity --no-cli-pager
        if ($LASTEXITCODE -ne 0) { Write-Warning "AWS CLI is installed but no usable AWS identity was confirmed." }
    }
    Write-Host "Setup checks complete. No AWS resources were created."
} finally {
    Pop-Location
}
