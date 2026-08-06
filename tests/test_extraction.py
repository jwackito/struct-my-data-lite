import uuid
from unittest.mock import MagicMock, patch

import pydantic
import pytest

from app.config import settings
from app.extraction import ExtractionService, _find_model
from app.models import Document, ExtractionJob


def test_extract_on_response_callback():
    service = ExtractionService(MagicMock())
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"name": "Harry", "age": 11}
    service.client.chat.completions.create.return_value = mock_result

    callback = MagicMock()
    schema = """
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int
"""
    result = service.extract("Harry is 11", schema, "test-model", on_response=callback)
    assert result == {"name": "Harry", "age": 11}
    callback.assert_called_once_with(mock_result)


def test_extract_on_response_not_called_on_failure():
    service = ExtractionService(MagicMock())
    service.client.chat.completions.create.side_effect = Exception("LLM down")

    callback = MagicMock()
    schema = """
from pydantic import BaseModel

class X(BaseModel):
    y: str
"""
    with pytest.raises(RuntimeError):
        service.extract("hello", schema, "test-model", on_response=callback)
    callback.assert_not_called()


def test_find_model():
    ns = {}
    exec("""
from pydantic import BaseModel

class Helper(BaseModel):
    x: int

class Root(BaseModel):
    name: str
""", ns)
    model = _find_model(ns)
    assert model.__name__ == "Root"


def test_find_model_no_model():
    with pytest.raises(ValueError, match="No Pydantic model"):
        _find_model({"foo": 42})


def test_find_model_ignores_base():
    ns = {"Base": pydantic.BaseModel}
    with pytest.raises(ValueError):
        _find_model(ns)


def test_find_model_picks_last_class():
    ns = {}
    exec("""
from pydantic import BaseModel

class TitularDominio(BaseModel):
    nombre: str

class Interviniente(BaseModel):
    cuit: str

class Escritura(BaseModel):
    titulares_dominio: list
""", ns)
    model = _find_model(ns)
    assert model.__name__ == "Escritura"


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


@pytest.mark.asyncio
async def test_extract_without_model_id_uses_default(async_client, db_session, patch_async_session):
    await async_client.post("/auth/register", json={
        "email": "extract-default@example.com",
        "password": "password123",
    })
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()

    with patch("app.main.process_job"):
        resp = await async_client.post("/extract", json={
            "document_id": str(doc.id),
            "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n  y: str",
        })
    assert resp.status_code == 200
    job_id = resp.json()["id"]

    job = await db_session.get(ExtractionJob, uuid.UUID(job_id))
    assert job.model_name == settings.ollama_model
