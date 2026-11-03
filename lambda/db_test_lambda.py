import json
import boto3

dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
table = dynamodb.Table("Patients")

def lambda_handler(event, context):
    # Write a test item
    table.put_item(
        Item={
            "PatientId": "TEST001",
            "Name": "Test Patient",
            "Age": 30
        }
    )

    # Read it back
    response = table.get_item(Key={"PatientId": "TEST001"})
    item = response.get("Item")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"retrieved_item": item}, default = str)
    }