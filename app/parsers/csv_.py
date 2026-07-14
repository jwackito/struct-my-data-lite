import csv
import io

from app.parsers.base import Parser


class CSVParser(Parser):
    def parse(self, path: str) -> str:
        with open(path, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return ""
        widths = [max(len(cell) for cell in col) for col in zip(*rows)]
        lines = []
        for row in rows:
            lines.append("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))
        return "\n".join(lines)
