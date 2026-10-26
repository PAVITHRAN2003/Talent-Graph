import io
from pypdf import PdfReader


def extract_text(filename: str, data: bytes, max_pages: int = 60) -> str:
    """PDF or TXT bytes -> clean text. Raises ValueError with a user-friendly message."""
    if filename.lower().endswith(".txt"):
        return data.decode("utf-8", errors="ignore").strip()
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = [(p.extract_text() or "") for p in reader.pages[:max_pages]]
    except Exception as e:
        raise ValueError(f"Could not read PDF: {type(e).__name__}") from e
    text = "\n".join(pages).strip()
    if len(text) < 80:
        raise ValueError("No extractable text (scanned/image PDF). Upload a text-based PDF.")
    return text
