from app.parsers.base import Parser
from app.parsers.csv_ import CSVParser
from app.parsers.docx import DOCXParser
from app.parsers.image import ImageParser
from app.parsers.pdf import PDFParser
from app.parsers.txt import TXTParser


def get_parser(content_type: str) -> Parser:
    if content_type == "application/pdf":
        return PDFParser()
    if content_type in ("text/csv", "application/csv"):
        return CSVParser()
    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return DOCXParser()
    if content_type.startswith("image/"):
        return ImageParser()
    if content_type.startswith("text/"):
        return TXTParser()
    raise ValueError(f"Unsupported content type: {content_type}")
