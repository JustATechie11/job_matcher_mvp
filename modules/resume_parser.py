import io
import pdfplumber

# Try importing fitz, but it's optional (for Windows compatibility)
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


def extract_resume_text(uploaded_file) -> str:
    """
    Extract text from uploaded PDF resume.
    Uses pdfplumber primarily, with optional PyMuPDF fallback.
    """
    if uploaded_file is None:
        return ""

    file_bytes = uploaded_file.read()
    if not file_bytes:
        return ""

    text = ""

    # Try pdfplumber first (more compatible on Windows)
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except Exception:
        pass

    # Fallback to PyMuPDF if pdfplumber didn't work
    if not text.strip() and HAS_FITZ:
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                text += page.get_text("text") + "\n"
            doc.close()
        except Exception:
            pass

    return clean_resume_text(text)


def clean_resume_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = " ".join(text.split())
    return text.strip()