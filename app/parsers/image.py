import base64

from app.parsers.base import Parser


class ImageParser(Parser):
    def parse(self, path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
