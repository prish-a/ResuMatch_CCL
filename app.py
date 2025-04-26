import streamlit as st
import boto3
from io import BytesIO
import os
import re
import json
import time
import nltk
from PyPDF2 import PdfReader
from docx import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.corpus import stopwords

# Initialize NLTK resources
nltk.download("punkt", quiet=True)
nltk.download("stopwords", quiet=True)

# --- Streamlit Config MUST BE FIRST ---
st.set_page_config(page_title="ResuMatch Pro", layout="wide")

# --- AWS Configuration ---
s3 = boto3.client("s3")
textract = boto3.client("textract")
lambda_client = boto3.client("lambda")
dynamodb = boto3.resource("dynamodb")

# --- Free Tier Configuration ---
MAX_TEXTRACT_PAGES = 1000  # Free Tier: 1000 pages/month
MAX_LAMBDA_INVOCATIONS = 1000000  # Free Tier: 1M requests/month
MAX_S3_SIZE_GB = 5  # Free Tier: 5GB storage
MAX_DYNAMODB_RCU = 25  # Free Tier: 25 Read Capacity Units

BUCKET_NAME = "resumatch-bucket"
TABLE_NAME = "ResuMatch-Resumes"
LAMBDA_FUNCTION_NAME = "ResuMatch-Processor"

# --- Initialize Services with Free Tier Protections ---
try:
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "filename", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "filename", "AttributeType": "S"}],
        BillingMode="PROVISIONED",
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    table.meta.client.get_waiter("table_exists").wait(TableName=TABLE_NAME)
except dynamodb.meta.client.exceptions.ResourceInUseException:
    table = dynamodb.Table(TABLE_NAME)

# --- Global State for Free Tier Tracking ---
if "textract_usage" not in st.session_state:
    st.session_state.textract_usage = 0
if "lambda_usage" not in st.session_state:
    st.session_state.lambda_usage = 0
if "s3_usage" not in st.session_state:
    st.session_state.s3_usage = 0.0

# --- Common Skills List ---
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


# --- Text Processing Functions ---
def preprocess_text(text):
    text = text.lower()
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_skills(text):
    return [
        skill
        for skill in COMMON_SKILLS
        if re.search(r"\b" + re.escape(skill) + r"\b", text.lower())
    ]


def extract_sections(text):
    sections = {"education": "", "experience": "", "skills": ""}
    current_section = None
    for line in text.split("\n"):
        line = line.strip().lower()
        if "education" in line:
            current_section = "education"
        elif "experience" in line:
            current_section = "experience"
        elif "skill" in line:
            current_section = "skills"
        elif current_section:
            sections[current_section] += line + " "
    return sections


# Using Textract
def extract_text(file_content, file_type):
    file_type = file_type.lower()
    if file_type in ["pdf", "jpg", "jpeg", "png"]:
        response = textract.detect_document_text(Document={"Bytes": file_content})
        return " ".join(
            [item["Text"] for item in response["Blocks"] if item["BlockType"] == "LINE"]
        )
    elif file_type == "docx":
        doc = Document(BytesIO(file_content))
        return " ".join([p.text for p in doc.paragraphs if p.text.strip()])
    elif file_type == "txt":
        return file_content.decode("utf-8")
    else:
        return ""


# --- Free Tier Protected Processing ---
def trigger_lambda_processing(file_name):
    if st.session_state.lambda_usage >= MAX_LAMBDA_INVOCATIONS:
        st.error("Lambda free tier limit reached!")
        return False

    try:
        lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps({"bucket": BUCKET_NAME, "key": file_name}),
        )
        st.session_state.lambda_usage += 1
        return True
    except Exception as e:
        st.error(f"Lambda error: {str(e)}")
        return False


# --- Enhanced Matching Engine ---
def match_resumes(job_desc):
    try:
        job_clean = preprocess_text(job_desc)
        resumes = []

        # Get from DynamoDB first
        db_items = table.scan(Limit=MAX_DYNAMODB_RCU).get("Items", [])
        for item in db_items:
            if text := item.get("text"):
                resumes.append(
                    (
                        item["filename"],
                        text,
                        item.get("skills", []),
                        item.get("sections", {}),
                    )
                )

        # Fallback to S3 if DynamoDB empty
        if not resumes:
            s3_objects = s3.list_objects_v2(Bucket=BUCKET_NAME).get("Contents", [])
            for obj in s3_objects[:25]:  # Limit to Free Tier reads
                file_type = obj["Key"].split(".")[-1]
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj["Key"])
                text = extract_text(response["Body"].read(), file_type)
                if text:
                    resumes.append(
                        (obj["Key"], text, extract_skills(text), extract_sections(text))
                    )

        # Calculate matches
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform([job_clean] + [t for _, t, _, _ in resumes])
        content_sim = cosine_similarity(matrix[0:1], matrix[1:])[0]

        results = []
        for i, (name, text, skills, sections) in enumerate(resumes):
            skill_score = len(set(skills) & set(extract_skills(job_desc))) / len(
                COMMON_SKILLS
            )
            section_score = (
                sum(1 for k in sections if sections[k] and k in job_desc.lower()) / 3
            )
            final_score = (
                (content_sim[i] * 0.6) + (skill_score * 0.3) + (section_score * 0.1)
            )
            results.append((name, final_score))

        return sorted(results, key=lambda x: x[1], reverse=True)
    except Exception as e:
        st.error(f"Matching error: {str(e)}")
        return []


# --- UI Components ---
def free_tier_sidebar():
    st.sidebar.subheader("Free Tier Usage")
    st.sidebar.progress(
        st.session_state.textract_usage / MAX_TEXTRACT_PAGES,
        text=f"Textract: {st.session_state.textract_usage}/{MAX_TEXTRACT_PAGES}",
    )
    st.sidebar.progress(
        st.session_state.lambda_usage / MAX_LAMBDA_INVOCATIONS,
        text=f"Lambda: {st.session_state.lambda_usage}/{MAX_LAMBDA_INVOCATIONS}",
    )
    st.sidebar.progress(
        st.session_state.s3_usage / MAX_S3_SIZE_GB,
        text=f"S3: {st.session_state.s3_usage:.2f}GB/{MAX_S3_SIZE_GB}GB",
    )


def main():
    # Authentication
    if "auth" not in st.session_state:
        st.session_state.auth = {"logged_in": False, "role": None}

    if not st.session_state.auth["logged_in"]:
        render_login()
    else:
        free_tier_sidebar()
        render_dashboard()


def render_login():
    st.markdown(
        """
    <div class='login-wrapper'>
        <div class='login-box'>
            <h1>🔐 ResuMatch</h1>
            <div class='stTextInput>input {border-radius: 5px !important;}</style>
    """,
        unsafe_allow_html=True,
    )

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Sign In"):
        if username == "recruiter" and password == "recruiter123":
            st.session_state.auth = {"logged_in": True, "role": "recruiter"}
            st.rerun()
        elif username.startswith("candidate") and password == "candidate123":
            st.session_state.auth = {"logged_in": True, "role": "candidate"}
            st.rerun()
        else:
            st.error("Invalid credentials")


def render_dashboard():
    st.sidebar.title(f"Welcome, {st.session_state.auth['role'].title()}!")
    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False, "role": None}
        st.rerun()

    if st.session_state.auth["role"] == "candidate":
        candidate_view()
    else:
        recruiter_view()


def candidate_view():
    st.title("📄 Upload Resume")
    file = st.file_uploader("Choose file", type=["pdf", "docx", "txt"])

    if file and st.button("Upload"):
        try:
            # Check storage
            new_size = file.size / (1024**3)
            if st.session_state.s3_usage + new_size > MAX_S3_SIZE_GB:
                st.error("Storage limit reached!")
                return

            # Extract text BEFORE uploading (read file first)
            file_content = file.read()
            text = extract_text(file_content, file.name.split(".")[-1])

            # Reset file pointer for upload
            file.seek(0)

            # Upload file
            s3.upload_fileobj(file, BUCKET_NAME, file.name)
            st.session_state.s3_usage += new_size

            # Now trigger Lambda processing (requires Lambda permissions)
            try:
                trigger_lambda_processing(file.name)
            except Exception as lambda_error:
                st.warning(
                    f"Resume uploaded but processing will be limited: {str(lambda_error)}"
                )

            # Show preview
            st.success("Upload successful!")
            st.write("**Preview:**", text[:300] + "..." if len(text) > 300 else text)
        except Exception as e:
            st.error(f"Upload failed: {str(e)}")


def recruiter_view():
    st.title("👔 Recruiter Dashboard")
    jd = st.text_area("Job Description", height=200)

    if jd and st.button("Analyze Resumes"):
        results = match_resumes(jd)

        if not results:
            st.warning("No matches found")
            return

        st.subheader("Top Matches")
        cols = st.columns(3)
        for i, (name, score) in enumerate(results[:6]):
            with cols[i % 3]:
                st.markdown(
                    f"""
            <div class="card-custom">
                <h4>{name}</h4>
                <div style='background:#4CAF50; color:white; padding:0.2rem; border-radius:4px; width:{score*100}%; display:inline-block;'>
                    {score*100:.1f}%
                </div>
            </div>
            """,
                    unsafe_allow_html=True,
                )


if __name__ == "__main__":
    main()
