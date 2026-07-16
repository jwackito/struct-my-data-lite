from unittest.mock import MagicMock, patch

import pydantic
import pytest

from app.extraction import ExtractionService, _find_model


def test_find_model():
    ns = {"T": pydantic.BaseModel, "Person": type("Person", (pydantic.BaseModel,), {"name": (str, ...)})}
    model = _find_model(ns)
    assert model.__name__ == "Person"


def test_find_model_no_model():
    with pytest.raises(ValueError, match="No Pydantic model"):
        _find_model({"foo": 42})


def test_find_model_ignores_base():
    ns = {"Base": pydantic.BaseModel}
    with pytest.raises(ValueError):
        _find_model(ns)


@patch("app.extraction.Instructor")
def test_extract_success(mock_instructor_class):
    mock_client = MagicMock()
    mock_instructor_class.return_value = mock_client

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"name": "Harry", "age": 11}
    mock_client.chat.completions.create.return_value = mock_result

    service = ExtractionService(mock_client)
    schema = """
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int
"""
    result = service.extract("Harry is 11 years old", schema, "test-model")
    assert result == {"name": "Harry", "age": 11}
    mock_client.chat.completions.create.assert_called_once()


@patch("app.extraction.Instructor")
def test_extract_invalid_schema(mock_instructor_class):
    service = ExtractionService(MagicMock())
    with pytest.raises(ValueError, match="Invalid schema"):
        service.extract("hello", "import not_a_module", "test-model")


@patch("app.extraction.Instructor")
def test_extract_runtime_error(mock_instructor_class):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("LLM down")

    service = ExtractionService(mock_client)
    schema = """
from pydantic import BaseModel

class X(BaseModel):
    y: str
"""
    with pytest.raises(RuntimeError, match="Extraction failed"):
        service.extract("hello", schema, "test-model")


@patch("app.extraction.Instructor")
def test_extract_multimodal_image(mock_instructor_class):
    mock_client = MagicMock()
    mock_instructor_class.return_value = mock_client

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"name": "Harry", "age": 11}
    mock_client.chat.completions.create.return_value = mock_result

    service = ExtractionService(mock_client)
    schema = """
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int
"""
    image_content = {"type": "image", "data": "abc123", "format": "jpeg"}
    result = service.extract(image_content, schema, "vision-model")

    assert result == {"name": "Harry", "age": 11}
    _, kwargs = mock_client.chat.completions.create.call_args
    msgs = kwargs["messages"]
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert isinstance(msgs[0]["content"], list)
    assert msgs[0]["content"][0]["type"] == "text"
    assert msgs[0]["content"][1]["type"] == "image_url"
    assert msgs[0]["content"][1]["image_url"]["url"] == "data:image/jpeg;base64,abc123"
