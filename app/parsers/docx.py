from docx import Document

from app.parsers.base import Parser


class DOCXParser(Parser):
    def parse(self, path: str) -> str:
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
