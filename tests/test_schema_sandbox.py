import pytest

from app.schema_sandbox import safe_exec, validate_schema


def test_valid_model_is_accepted():
    code = (
        "from pydantic import BaseModel, Field\n"
        "from typing import List, Optional\n"
        "from datetime import date\n\n"
        "class Person(BaseModel):\n"
        '    name: str = Field(description="Full name")\n'
        "    age: int = 0\n"
        "    nickname: Optional[str] = None\n"
        "    born: date\n"
        "    tags: List[str]\n"
    )
    validate_schema(code)
    ns = safe_exec(code)
    assert "Person" in ns


def test_import_dunder_call_is_rejected():
    code = "x = __import__('os')\n"
    with pytest.raises(ValueError):
        validate_schema(code)
    with pytest.raises(ValueError):
        safe_exec(code)


def test_open_call_is_rejected():
    code = "x = open('/etc/passwd')\n"
    with pytest.raises(ValueError):
        validate_schema(code)
    with pytest.raises(ValueError):
        safe_exec(code)


def test_dunder_traversal_is_rejected():
    code = "x = ().__class__.__bases__\n"
    with pytest.raises(ValueError):
        validate_schema(code)
    with pytest.raises(ValueError):
        safe_exec(code)
