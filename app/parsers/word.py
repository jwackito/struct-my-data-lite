import subprocess

from app.parsers.base import Parser
from app.parsers.docx import DOCXParser

_ZIP_MAGIC = b"PK\x03\x04"
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class WordParser(Parser):
    def parse(self, path: str) -> str:
        with open(path, "rb") as f:
            head = f.read(8)
        if head.startswith(_ZIP_MAGIC):
            return DOCXParser().parse(path)
        if head.startswith(_OLE2_MAGIC):
            return self._antiword(path)
        raise ValueError("Unsupported Word document (expected .doc or .docx)")

    def _antiword(self, path: str) -> str:
        try:
            proc = subprocess.run(
                ["antiword", "-m", "UTF-8.txt", "-w", "0", path],
                capture_output=True,
                timeout=60,
            )
        except FileNotFoundError:
            raise ValueError("antiword is not installed")
        except subprocess.TimeoutExpired:
            raise ValueError("antiword timed out")
        if proc.returncode != 0:
            detail = proc.stderr.decode("utf-8", "replace")[:200].strip()
            raise ValueError(f"antiword failed: {detail}")
        return proc.stdout.decode("utf-8", "replace")
