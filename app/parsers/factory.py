from app.parsers.base import Parser
from app.parsers.csv_ import CSVParser
from app.parsers.image import ImageParser
from app.parsers.pdf import PDFParser
from app.parsers.txt import TXTParser
from app.parsers.word import WordParser

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

WORD_CONTENT_TYPES = {
    "application/msword",
    "application/vnd.ms-word",
    "application/x-msword",
    DOCX_CONTENT_TYPE,
}

WORD_EXTENSIONS = (".doc", ".docx")


def get_parser(content_type: str, filename: str | None = None) -> Parser:
    if content_type in WORD_CONTENT_TYPES:
        return WordParser()
    if content_type == "application/pdf":
        return PDFParser()
    if content_type in ("text/csv", "application/csv"):
        return CSVParser()
    if content_type.startswith("image/"):
        return ImageParser()
    if content_type.startswith("text/"):
        return TXTParser()
    if content_type in ("application/octet-stream", "") and filename:
        lowered = filename.lower()
        if lowered.endswith(".pdf"):
            return PDFParser()
        if lowered.endswith(WORD_EXTENSIONS):
            return WordParser()
    raise ValueError(f"Unsupported content type: {content_type}")
