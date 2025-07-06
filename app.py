import streamlit as st
import fitz  # PyMuPDF
import openai
import os
import json
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_pdf_text(uploaded_file):
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        return "\n".join([page.get_text() for page in doc])

def extract_fields_with_gpt(text):
    prompt = f"""
You are a legal document assistant.
1. First, classify the document type. Return options like: "NF-10 doc", "Invoice", "Purchase Order", or "Invalid Document".
2. Extract the following fields if available:

### Basic Case Information
- Policyholder
- Policy Number
- Date of Accident
- Injured Person
- Claim Number
- Applicant Name and Address
- As Assignee (Yes/No)
- Denial Reason
- Provider Name
- Service Date
- Bill Amount

### Health Service Info
- Provider of Health Service
- Type of Service Rendered
- Period of bill
- Date of bill
- Date bill received
- Final verification requested
- Final verification received
- Amount of bill
- Amount paid by insurer
- Amount in dispute
- Reason for denial

### Loss of Earnings Section
- Date claim made
- Gross earnings per month
- Period of dispute
- Amount claimed

### Health Services Dispute Table
[List of dicts with: Provider, Date of Service, Amount of Bill, Amount in Dispute, Date Claim Mailed]

### Other Necessary Expenses
[List of dicts with: Type of Expense, Amount, Date Incurred, Date Claim Mailed, Amount in Dispute]

### Request Info
- Last Name
- First Name
- Law Firm
- Telephone
- Fax
- Email
- Address
- Attorney? (Yes/No)
- Date
- Signature (text or "to be added")

3. Also provide a **brief summary** of this document (50–75 words).
4. If user upload wrong document **Invalid Document** of this document

Respond strictly in the following JSON structure:

{{
  "document_type": "...",
  "summary": "...",
  "Invalid": "..."
  "fields": {{
    "basic_info": {{ ... }},
    "health_service_info": {{ ... }},
    "loss_of_earnings": {{ ... }},
    "health_services_disputes": [...],
    "other_expenses": [...],
    "arbitration_info": {{ ... }}
  }}
}}

Here is the document text:
\"\"\"{text}\"\"\"
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()

st.set_page_config(page_title="Legal Document AI", layout="wide")
st.title("📄Legal Document Automation")

uploaded_file = st.file_uploader("📤 Upload NF-10 PDF or similar claim document", type=["pdf"])

if uploaded_file:
    with st.spinner("Reading and analyzing..."):
        text = extract_pdf_text(uploaded_file)
        gpt_response = extract_fields_with_gpt(text)

    try:
        result = json.loads(gpt_response)

        if "document_type" in result:
            st.success(f"Document Classification: {result['document_type']}")
        else:
            st.warning("Unable to determine document type.")

        st.subheader("📝 Summary")
        st.write(result.get("summary", "Summary not available."))

        fields = result.get("fields", {})

        st.subheader("Basic Case Information")
        st.json(fields.get("basic_info", {}))

        st.subheader("Health Service Info")
        st.json(fields.get("health_service_info", {}))

        st.subheader("Loss of Earnings Section")
        st.json(fields.get("loss_of_earnings", {}))

        st.subheader("Health Services Disputes")
        st.json(fields.get("health_services_disputes", []))

        st.subheader("Other Necessary Expenses")
        st.json(fields.get("other_expenses", []))

        st.subheader("User Requester Info")
        st.json(fields.get("arbitration_info", {}))

        st.download_button(
            label="📥 Download Extracted JSON",
            data=json.dumps(result, indent=2),
            file_name="nf10_extracted_output.json",
            mime="application/json"
        )

    except json.JSONDecodeError:
        st.error("Failed to parse GPT response as JSON.")
        st.code(gpt_response)
else:
    st.info("👆 Upload a valid legal document to begin.")