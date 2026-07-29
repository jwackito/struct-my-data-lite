import io

import pdfplumber
from PIL import Image

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


def is_image_pdf(path: str) -> bool:
    with pdfplumber.open(path) as pdf:
        return all(not page.extract_text() for page in pdf.pages)


def extract_page_images(path: str, resolution: int = 150) -> list[dict]:
    images = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pil_img = page.to_image(resolution=resolution).original
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            images.append({"data": buf.getvalue(), "format": "png"})
    return images
