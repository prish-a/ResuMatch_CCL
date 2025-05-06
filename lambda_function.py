import boto3
import time

s3 = boto3.client("s3")
textract = boto3.client("textract")
dynamodb = boto3.resource("dynamodb").Table("ResuMatch-Resumes")

COMMON_SKILLS = [
    "python",
    "java",
    "javascript",
    "html",
    "css",
    "react",
    "angular",
    "vue",
    "node.js",
    "express",
    "django",
    "flask",
    "spring",
    "hibernate",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "terraform",
    "jenkins",
    "git",
    "sql",
    "mysql",
    "postgresql",
    "mongodb",
    "redis",
    "elasticsearch",
    "machine learning",
    "deep learning",
    "nlp",
    "computer vision",
    "data analysis",
    "data visualization",
    "tableau",
    "power bi",
    "excel",
    "project management",
    "agile",
    "scrum",
    "product management",
    "ui/ux",
    "figma",
    "sketch",
]


def lambda_handler(event, context):
    try:
        obj = s3.get_object(Bucket=event["bucket"], Key=event["key"])
        content = obj["Body"].read()

        response = textract.detect_document_text(Document={"Bytes": content})
        text = " ".join(
            [item["Text"] for item in response["Blocks"] if item["BlockType"] == "LINE"]
        )

        text_lower = text.lower()
        extracted_skills = [skill for skill in COMMON_SKILLS if skill in text_lower]

        dynamodb.put_item(
            Item={
                "resume_id": event["key"],
                "text": text,
                "skills": extracted_skills,
                "timestamp": int(time.time()),
            }
        )

        return {"statusCode": 200}
    except Exception as e:
        print(f"Error: {str(e)}")
        return {"statusCode": 500}
