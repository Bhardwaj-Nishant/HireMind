"""
Loads your resume text once, from a plain-text file you provide.

For now this expects a plain .txt file (simplest to get matching working
end-to-end). If your resume is a PDF/DOCX, extract its text once and save
it as resume.txt here — a proper PDF/DOCX ingestion step can be added
later without changing matcher.py, since everything downstream just
consumes this module's plain string.
"""
import os

RESUME_PATH = os.environ.get(
    "RESUME_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "intelligence-service", "resume.txt")
)

_resume_cache: str | None = None


def get_resume_text() -> str:
    global _resume_cache
    if _resume_cache is None:
        if not os.path.exists(RESUME_PATH):
            raise FileNotFoundError(
                f"Resume file not found at {RESUME_PATH}. "
                f"Set RESUME_PATH env var, or place resume.txt in intelligence-service/."
            )
        with open(RESUME_PATH, "r", encoding="utf-8") as f:
            _resume_cache = f.read()
    return _resume_cache