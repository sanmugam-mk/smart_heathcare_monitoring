param([string]$StackName = "smart-healthcare-monitoring", [string]$Region = "ap-south-1")

Write-Warning "No resources will be deleted by this script."
Write-Host "Before any future cleanup, export needed patient/document data and inspect the CloudFormation deletion change set."
Write-Host "Deleting the stack can permanently remove Cognito users, DynamoDB records, SNS configuration, IoT resources, and API/Lambda resources."
Write-Host "The S3 bucket may need to be emptied deliberately before CloudFormation can delete it."
Write-Host "After a separate human review and approval, the manual command would be:"
Write-Host "  sam delete --stack-name $StackName --region $Region"
Write-Host "This script will not run that command."
