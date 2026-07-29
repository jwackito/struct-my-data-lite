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
        get_parser("application/zip")


def test_factory_routes_image():
    for ct in ("image/png", "image/jpeg", "image/webp"):
        parser = get_parser(ct)
        assert isinstance(parser, ImageParser)


def test_pdf_is_image_pdf_true():
    from app.parsers.pdf import is_image_pdf
    from unittest.mock import patch, MagicMock

    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""
    mock_pdf = MagicMock()
    mock_pdf.__enter__.return_value.pages = [mock_page, mock_page]

    with patch("app.parsers.pdf.pdfplumber.open", return_value=mock_pdf):
        assert is_image_pdf("/fake/path") is True


def test_pdf_is_image_pdf_false():
    from app.parsers.pdf import is_image_pdf
    from unittest.mock import patch, MagicMock

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "some text"
    mock_pdf = MagicMock()
    mock_pdf.__enter__.return_value.pages = [mock_page]

    with patch("app.parsers.pdf.pdfplumber.open", return_value=mock_pdf):
        assert is_image_pdf("/fake/path") is False


def test_pdf_extract_page_images():
    from app.parsers.pdf import extract_page_images
    from unittest.mock import patch, MagicMock
    import io

    mock_pil = MagicMock()
    mock_pil.save.return_value = None

    mock_pageimg = MagicMock()
    mock_pageimg.original = mock_pil

    mock_page = MagicMock()
    mock_page.to_image.return_value = mock_pageimg
    mock_page.images = [{"width": 612, "height": 792}]

    mock_pdf = MagicMock()
    mock_pdf.__enter__.return_value.pages = [mock_page, mock_page]

    with patch("app.parsers.pdf.pdfplumber.open", return_value=mock_pdf):
        with patch("app.parsers.pdf.Image.new", return_value=mock_pil):
            result = extract_page_images("/fake/path", resolution=72)

    assert len(result) == 2
    assert all(r["format"] == "png" for r in result)
    assert all(isinstance(r["data"], bytes) for r in result)


def test_parser_abc():
    class BadParser(Parser):
        pass

    with pytest.raises(TypeError):
        BadParser()  # abstract method not implemented
