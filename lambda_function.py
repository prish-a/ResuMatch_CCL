import boto3
import time

s3 = boto3.client("s3")
textract = boto3.client("textract")
dynamodb = boto3.resource("dynamodb").Table("ResuMatch-Resumes")


def lambda_handler(event, context):
    try:
        obj = s3.get_object(Bucket=event["bucket"], Key=event["key"])
        content = obj["Body"].read()

        # Textract extraction
        response = textract.detect_document_text(Document={"Bytes": content})
        text = " ".join(
            [item["Text"] for item in response["Blocks"] if item["BlockType"] == "LINE"]
        )

        # Store in DynamoDB
        dynamodb.put_item(
            Item={
                "filename": event["key"],
                "text": text,
                "skills": [],  # Add skill extraction if needed
                "timestamp": int(time.time()),
            }
        )

        return {"statusCode": 200}
    except Exception as e:
        print(f"Error: {str(e)}")
        return {"statusCode": 500}
