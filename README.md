# ResuMatch Pro

**ResuMatch Pro** is a serverless, AWS-powered resume-job matching platform built with Streamlit and Python.
It enables candidates to upload resumes and recruiters to find the best matches for job descriptions using NLP and cloud services-all while staying within the AWS Free Tier.

---

## Features

- **Candidate Portal:** Upload resumes (PDF, DOCX, or TXT) and preview extracted content.
- **Recruiter Dashboard:** Enter a job description and instantly see the top-matching resumes.
- **AI-Powered Matching:** Uses TF-IDF cosine similarity, skill overlap, and section analysis for robust matching.
- **AWS Integration:** Stores resumes in S3, processes them with Lambda and Textract, and tracks metadata in DynamoDB.
- **Free Tier Safe:** Monitors AWS usage (S3, Lambda, Textract) to prevent exceeding the Free Tier.
- **Modern UI:** Streamlit dashboard with login, cards, and progress bars for an intuitive experience.

---

## How It Works

### 1. **Authentication**

- Recruiter: `recruiter` / `recruiter123`
- Candidate: `candidateX` / `candidate123` (where X is any number)

### 2. **Resume Upload (Candidate)**

- Upload a resume file (`pdf`, `docx`, or `txt`).
- The app extracts text using AWS Textract (for PDFs/images) or python-docx (for DOCX), and previews the content.
- The file is uploaded to S3 and processed asynchronously by a Lambda function.

### 3. **Resume Processing**

- Lambda extracts text (Textract for PDFs/images, python-docx for DOCX, decode for TXT).
- Extracted data and metadata are stored in DynamoDB.

### 4. **Job Matching (Recruiter)**

- Recruiter pastes a job description.
- The app fetches all processed resumes and computes a match score for each:
  - **60%**: TF-IDF cosine similarity (textual relevance)
  - **30%**: Skill overlap (from a common skills list)
  - **10%**: Section match (education, experience, skills)
- Top matches are displayed as cards with percentage bars.

### 5. **Free Tier Monitoring**

- The sidebar shows current AWS usage for Textract, Lambda, and S3.
- Uploads and processing are blocked if limits are reached.

---

## AWS Services Used

| Service  | Purpose                 | Free Tier Limit Enforced |
| :------- | :---------------------- | :----------------------- |
| S3       | Resume file storage     | 5GB                      |
| DynamoDB | Resume metadata storage | 25 read/write units      |
| Lambda   | Resume processing       | 1M invocations/month     |
| Textract | OCR for PDFs/images     | 1,000 pages/month        |

---

## Setup Instructions

### 1. **AWS Prerequisites**

- Create an S3 bucket: `resumatch-bucket`
- Create a DynamoDB table: `ResuMatch-Resumes` (partition key: `filename`)
- Create a Lambda function: `ResuMatch-Processor` (with access to S3, DynamoDB, Textract)
- Ensure your IAM user has permissions for S3, DynamoDB, Lambda, and Textract

### 2. **Install Python Dependencies**

```bash
pip install streamlit boto3 PyPDF2 python-docx scikit-learn nltk
```

### 3. **Run the App**

```bash
streamlit run app.py
```

### 4. **(First Run Only) Download NLTK Data**

The app will auto-download NLTK resources (`punkt`, `stopwords`) on first launch.

---

## Matching Logic

- **TF-IDF Cosine Similarity:** Measures overall textual similarity between resume and job description.
- **Skill Overlap:** Compares extracted skills from both documents (using a curated skills list).
- **Section Matching:** Checks for presence of key sections (education, experience, skills).
- **Final Score:**

```
final_score = (content_similarity * 0.6) + (skill_score * 0.3) + (section_score * 0.1)
```

---

## Security Notes

- IAM users should have only the minimum permissions needed.
- No sensitive data is stored in code; all credentials are managed via AWS/IAM.

---

## Customization

- **Skills List:** Update the `COMMON_SKILLS` list in the code to reflect your domain.
- **UI Theme:** Customize via Streamlit’s `.streamlit/config.toml` or CSS in the app.
- **Authentication:** For production, replace the simple username/password with a secure method.

---

## License

This project is for educational and prototype use.
**No warranties; use at your own risk.**

---

## Acknowledgments

- [Streamlit](https://streamlit.io/)
- [AWS Free Tier](https://aws.amazon.com/free/)
- [scikit-learn](https://scikit-learn.org/)
- [NLTK](https://www.nltk.org/)


