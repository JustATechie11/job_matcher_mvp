import fitz  # PyMuPDF
import pdfplumber


def extract_resume_text(uploaded_file) -> str:
    """
    Extract text from uploaded PDF resume.
    Uses PyMuPDF first, then pdfplumber fallback.
    """
    if uploaded_file is None:
        return ""

    file_bytes = uploaded_file.read()
    text = ""

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
    except Exception:
        text = ""

    if not text.strip():
        try:
            uploaded_file.seek(0)
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
        except Exception:
            text = ""

    return clean_resume_text(text)


def clean_resume_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = " ".join(text.split())
    return text.strip()