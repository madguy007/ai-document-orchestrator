import streamlit as st
import pdfplumber
import fitz  # PyMuPDF
import google.generativeai as genai
import json
import requests

# Configure Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])


# ------------------ JSON CLEANING FUNCTION ------------------
def clean_json_response(response_text):
    try:
        if "```" in response_text:
            response_text = response_text.split("```")[1]

        response_text = response_text.replace("json", "").strip()
        return json.loads(response_text)

    except Exception:
        return {"error": "Invalid JSON", "raw_output": response_text}


# ------------------ GEMINI FUNCTION ------------------
def extract_structured_data(text, query):
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
    You are an intelligent document analyst.

    Understand the user question:
    "{query}"

    Extract ONLY the relevant data needed.

    Return ONLY valid JSON.

    Document:
    {text[:12000]}
    """

    response = model.generate_content(prompt)
    return response.text


# ------------------ TEXT EXTRACTION ------------------
def extract_text(file):
    file.seek(0)

    if file.type == "text/plain":
        return file.read().decode("utf-8")

    elif file.type == "application/pdf":
        text = ""

        try:
            file.seek(0)
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
        except:
            pass

        if not text.strip():
            file.seek(0)
            doc = fitz.open(stream=file.read(), filetype="pdf")
            for page in doc:
                text += page.get_text()

        return text

    return ""


# ------------------ STREAMLIT UI ------------------
st.title("AI Document Orchestrator")

uploaded_file = st.file_uploader("Upload a document", type=["pdf", "txt"])
query = st.text_input("Ask a question about the document")


# ------------------ MAIN FLOW ------------------
if uploaded_file:

    if "document_text" not in st.session_state:
        st.session_state.document_text = extract_text(uploaded_file)

    document_text = st.session_state.document_text

    st.success("Text extracted successfully ✅")
    st.text_area("Extracted Text Preview", document_text[:1000], height=200)

    if query:
        with st.spinner("Analyzing document with AI..."):
            raw_output = extract_structured_data(document_text, query)
            structured_data = clean_json_response(raw_output)

        st.subheader("📊 Extracted Structured Data")

        if "error" not in structured_data:
            st.json(structured_data)

            # ---------------- EMAIL SECTION ----------------
            st.subheader("📧 Send Alert Email")

            recipient_email = st.text_input("Enter Recipient Email")
            send_button = st.button("Send Alert Mail")

            if send_button and recipient_email:
                payload = {
                    "document_text": document_text,
                    "query": query,
                    "structured_data": structured_data,
                    "email": recipient_email
                }

                try:
                    response = requests.post(
                        st.secrets["N8N_WEBHOOK_URL"],
                        json=payload
                    )

                    st.success("Request sent to n8n ✅")

                    try:
                        result = response.json()

                        # ✅ Final Output Sections
                        st.subheader("🧠 Final Analytical Answer")
                        st.write(result.get("final_answer", "No answer"))

                        st.subheader("📧 Generated Email Body")
                        st.markdown(result.get("email_body", "No email content"), unsafe_allow_html=True)

                        st.subheader("📊 Email Automation Status")
                        st.success(result.get("status", "Unknown"))

                    except:
                        st.write(response.text)

                except Exception as e:
                    st.error(f"Error: {str(e)}")

        else:
            st.warning("⚠️ Could not parse JSON properly")
            st.code(structured_data["raw_output"], language="json")