import pdfplumber

from app.parsers.base import Parser


class PDFParser(Parser):
    def parse(self, path: str) -> str:
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)
