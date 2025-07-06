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
1. Classify the document type. Possible values: "AR1", "NF3", or "Invalid Document".
2. Extract fields as structured JSON for comparison.

AR1 format includes:
- Claim Number
- Total Billed Amount
- Line Items: [{{"Date of Service": "...", "Procedure Code": "...", "Amount": ...}}]

NF3 format includes:
- Claim Number
- CPT Codes: [{{"Date of Service": "...", "Procedure Code": "...", "Amount": ...}}]

Respond in JSON:
{{
  "document_type": "...",
  "summary": "...",
  "fields": {{
    "claim_number": "...",
    "total_billed": "...",
    "line_items": [{{"Date of Service": "...", "Procedure Code": "...", "Amount": ...}}]
  }}
}}

Document:
\"\"\"{text}\"\"\"
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()


def compare_documents(ar1_data, nf3_data):
    mismatches = []

    ar1_items = ar1_data.get("fields", {}).get("line_items", [])
    nf3_items = nf3_data.get("fields", {}).get("line_items", [])

    matched_indices = set()
    for ar1_item in ar1_items:
        found = False
        for idx, nf3_item in enumerate(nf3_items):
            if idx in matched_indices:
                continue
            if (
                ar1_item["Date of Service"] == nf3_item["Date of Service"]
                and ar1_item["Procedure Code"] == nf3_item["Procedure Code"]
            ):
                if ar1_item["Amount"] != nf3_item["Amount"]:
                    mismatches.append({
                        "type": "Amount Mismatch",
                        "date": ar1_item["Date of Service"],
                        "code": ar1_item["Procedure Code"],
                        "ar1_amount": ar1_item["Amount"],
                        "nf3_amount": nf3_item["Amount"]
                    })
                matched_indices.add(idx)
                found = True
                break
        if not found:
            mismatches.append({
                "type": "Missing in NF3",
                "date": ar1_item["Date of Service"],
                "code": ar1_item["Procedure Code"],
                "ar1_amount": ar1_item["Amount"]
            })

    # for items in NF3 not in AR1
    for idx, nf3_item in enumerate(nf3_items):
        if idx not in matched_indices:
            mismatches.append({
                "type": "Extra in NF3",
                "date": nf3_item["Date of Service"],
                "code": nf3_item["Procedure Code"],
                "nf3_amount": nf3_item["Amount"]
            })

    return mismatches

st.set_page_config(page_title="📑 AR1 vs NF3 Comparison Tool", layout="wide")
st.title("📑 Compare AR1 & NF3 Medical Claim Forms")

col1, col2 = st.columns(2)
with col1:
    ar1_file = st.file_uploader("Upload AR1 (Arbitration Request Form)", type=["pdf"], key="ar1")
with col2:
    nf3_file = st.file_uploader("Upload NF3 (No Fault Form)", type=["pdf"], key="nf3")

if ar1_file and nf3_file:
    with st.spinner("Extracting data from both documents..."):
        ar1_text = extract_pdf_text(ar1_file)
        nf3_text = extract_pdf_text(nf3_file)

        ar1_response = extract_fields_with_gpt(ar1_text)
        nf3_response = extract_fields_with_gpt(nf3_text)

    try:
        ar1_data = json.loads(ar1_response)
        nf3_data = json.loads(nf3_response)

        st.subheader("📄 Document Summaries")
        st.write("**AR1 Summary**:", ar1_data.get("summary", "N/A"))
        st.write("**NF3 Summary**:", nf3_data.get("summary", "N/A"))

        st.subheader("📋 Extracted Fields")
        st.json({"AR1": ar1_data, "NF3": nf3_data})

        st.subheader("Comparison Result")
        mismatches = compare_documents(ar1_data, nf3_data)
        if mismatches:
            st.error("Mismatches Found")
            for mismatch in mismatches:
                st.json(mismatch)
        else:
            st.success("All billed items match correctly!")

    except json.JSONDecodeError:
        st.error("Failed to parse GPT response as JSON.")
        st.code(ar1_response + "\n\n" + nf3_response)
else:
    st.info("👆 Please upload both AR1 and NF3 documents to continue.")
