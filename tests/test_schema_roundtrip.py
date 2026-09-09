from app.schema_codegen import build_code
from app.schema_parser import parse_schema


def _normalize(field: dict) -> dict:
    out = {
        "name": field["name"],
        "type": field["type"],
        "description": field.get("description", ""),
        "optional": field.get("optional", False),
        "default": field.get("default", ""),
    }
    if field.get("children"):
        out["children"] = [_normalize(c) for c in field["children"]]
    return out


def test_builder_to_code_to_builder_identity():
    fields = [
        {"name": "name", "type": "str", "description": "Full name"},
        {"name": "age", "type": "int", "default": "0"},
        {"name": "nickname", "type": "str", "optional": True},
        {"name": "born", "type": "date"},
        {"name": "seen", "type": "datetime"},
        {"name": "tags", "type": "List[str]"},
        {"name": "flags", "type": "List[bool]"},
        {"name": "active", "type": "bool", "default": "true"},
        {"name": "role", "type": "str", "default": "member", "description": "User role"},
        {"name": "addr", "type": "Object", "children": [
            {"name": "street", "type": "str"},
            {"name": "zip", "type": "str", "optional": True},
        ]},
        {"name": "items", "type": "List[Object]", "children": [
            {"name": "sku", "type": "str"},
            {"name": "qty", "type": "int", "default": "1"},
        ]},
    ]
    code = build_code("Root", fields)
    parsed = parse_schema(code)
    assert parsed["model_name"] == "Root"
    assert parsed["fields"] == [_normalize(f) for f in fields]


def test_code_to_builder_to_code_stability():
    code = """
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class Person(BaseModel):
    name: str = Field(description="Full name")
    age: int = 0
    nickname: Optional[str] = None
    born: date
    tags: List[str]
    active: bool = True
"""
    first = parse_schema(code)
    regenerated = build_code(first["model_name"], first["fields"])
    second = parse_schema(regenerated)
    assert second["model_name"] == first["model_name"]
    assert second["fields"] == first["fields"]


def test_generated_code_is_valid_python():
    fields = [
        {"name": "x", "type": "int", "default": "5"},
        {"name": "y", "type": "str", "optional": True, "description": "why"},
        {"name": "kids", "type": "List[Object]", "children": [{"name": "n", "type": "str"}]},
    ]
    code = build_code("Model", fields)
    compile(code, "<schema>", "exec")


def test_generated_code_imports_and_executes_as_pydantic():
    import pydantic

    fields = [
        {"name": "count", "type": "int", "default": "3"},
        {"name": "when", "type": "datetime"},
        {"name": "label", "type": "str", "optional": True},
    ]
    code = build_code("ExecModel", fields)
    namespace = {}
    exec(code, namespace)
    model = namespace["ExecModel"]
    assert issubclass(model, pydantic.BaseModel)
    instance = model(when="2024-01-15T10:30:00")
    assert instance.count == 3
    assert instance.label is None
