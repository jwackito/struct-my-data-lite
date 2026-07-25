import pytest

from app.schema_parser import parse_schema


def test_parse_simple_fields():
    code = """
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int
    height: float
    active: bool
"""
    result = parse_schema(code)
    assert result["model_name"] == "User"
    names = [f["name"] for f in result["fields"]]
    types = {f["name"]: f["type"] for f in result["fields"]}
    assert names == ["name", "age", "height", "active"]
    assert types["name"] == "str"
    assert types["age"] == "int"
    assert types["height"] == "float"
    assert types["active"] == "bool"


def test_parse_list_fields():
    code = """
from pydantic import BaseModel
from typing import List

class Item(BaseModel):
    tags: List[str]
    scores: List[float]
    counts: List[int]
"""
    result = parse_schema(code)
    types = {f["name"]: f["type"] for f in result["fields"]}
    assert types["tags"] == "List[str]"
    assert types["scores"] == "List[float]"
    assert types["counts"] == "List[int]"


def test_parse_field_description():
    code = """
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str = Field(description="Full name of the user")
    age: int = Field(description="Age in years")
"""
    result = parse_schema(code)
    descs = {f["name"]: f["description"] for f in result["fields"]}
    assert descs["name"] == "Full name of the user"
    assert descs["age"] == "Age in years"


def test_parse_nested_model():
    code = """
from pydantic import BaseModel
from typing import List

class Address(BaseModel):
    street: str
    city: str

class User(BaseModel):
    name: str
    address: Address
"""
    result = parse_schema(code)
    types = {f["name"]: f["type"] for f in result["fields"]}
    assert types["name"] == "str"
    assert types["address"] == "Object"
    addr = [f for f in result["fields"] if f["name"] == "address"][0]
    assert "children" in addr
    child_names = [c["name"] for c in addr["children"]]
    assert child_names == ["street", "city"]


def test_parse_list_of_nested():
    code = """
from pydantic import BaseModel
from typing import List

class Item(BaseModel):
    sku: str

class Order(BaseModel):
    order_id: str
    items: List[Item]
"""
    result = parse_schema(code)
    types = {f["name"]: f["type"] for f in result["fields"]}
    assert types["items"] == "List[Object]"
    items = [f for f in result["fields"] if f["name"] == "items"][0]
    assert "children" in items
    assert items["children"][0]["name"] == "sku"


def test_parse_optional_field():
    code = """
from pydantic import BaseModel
from typing import Optional

class User(BaseModel):
    name: str
    nickname: Optional[str] = None
"""
    result = parse_schema(code)
    types = {f["name"]: f["type"] for f in result["fields"]}
    assert types["nickname"] == "str"


def test_parse_no_models():
    with pytest.raises(ValueError, match="No BaseModel subclass found"):
        parse_schema("x = 1")


def test_parse_invalid_syntax():
    with pytest.raises(SyntaxError):
        parse_schema("class {:}")


def test_parse_any_and_dict_fallback():
    code = """
from pydantic import BaseModel
from typing import Any, Dict

class Data(BaseModel):
    metadata: Any
    extra: Dict
"""
    result = parse_schema(code)
    types = {f["name"]: f["type"] for f in result["fields"]}
    assert types["metadata"] == "str"
    assert types["extra"] == "str"


def test_last_class_is_root():
    code = """
from pydantic import BaseModel

class Inner(BaseModel):
    x: str

class Root(BaseModel):
    inner: Inner
"""
    result = parse_schema(code)
    assert result["model_name"] == "Root"
    assert len(result["fields"]) == 1
    assert result["fields"][0]["name"] == "inner"


def test_field_without_description():
    code = """
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str = Field(description="Name")
    age: int = Field()
"""
    result = parse_schema(code)
    descs = {f["name"]: f["description"] for f in result["fields"]}
    assert descs["name"] == "Name"
    assert descs["age"] == ""
