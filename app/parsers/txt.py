from app.parsers.base import Parser


class TXTParser(Parser):
    def parse(self, path: str) -> str:
        with open(path, "r") as f:
            return f.read()
