from pathlib import Path

from app.parsers.factory import get_parser
from app.parsers.txt import TXTParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_txt_parser_output_is_string():
    text = TXTParser().parse(str(FIXTURES / "harry_potter.txt"))
    assert isinstance(text, str)
    assert len(text) > 0


def test_parser_output_shapes():
    parsers = {
        "text/plain": (FIXTURES / "harry_potter.txt", TXTParser),
    }
    for content_type, (fixture_path, parser_cls) in parsers.items():
        parser = get_parser(content_type)
        text = parser.parse(str(fixture_path))
        assert isinstance(text, str)
        assert len(text) > 0
