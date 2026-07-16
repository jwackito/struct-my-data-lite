import base64
from pathlib import Path

import pytest

from app.parsers.base import Parser
from app.parsers.csv_ import CSVParser
from app.parsers.factory import get_parser
from app.parsers.image import ImageParser
from app.parsers.txt import TXTParser

FIXTURES = Path(__file__).parent / "fixtures"


def test_image_parser_returns_base64(tmp_path):
    img = tmp_path / "test.png"
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    img.write_bytes(raw)
    result = ImageParser().parse(str(img))
    assert base64.b64decode(result) == raw


def test_txt_parser():
    text = TXTParser().parse(str(FIXTURES / "harry_potter.txt"))
    assert "Dursley" in text
    assert text.startswith("Mr. and Mrs. Dursley")


def test_csv_parser():
    text = CSVParser().parse(str(FIXTURES / "sample.csv"))
    assert "Harry" in text
    assert "Hermione" in text
    assert "Ron" in text


def test_factory_txt():
    parser = get_parser("text/plain")
    assert isinstance(parser, TXTParser)


def test_factory_unsupported():
    with pytest.raises(ValueError, match="Unsupported"):
        get_parser("image/png")


def test_parser_abc():
    class BadParser(Parser):
        pass

    with pytest.raises(TypeError):
        BadParser()  # abstract method not implemented
