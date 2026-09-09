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


def test_parse_optional_flag():
    code = """
from pydantic import BaseModel
from typing import Optional

class User(BaseModel):
    name: str
    nickname: Optional[str] = None
"""
    result = parse_schema(code)
    fields = {f["name"]: f for f in result["fields"]}
    assert fields["name"]["optional"] is False
    assert fields["nickname"]["optional"] is True
    assert fields["nickname"]["default"] == ""


def test_parse_scalar_defaults():
    code = """
from pydantic import BaseModel

class Config(BaseModel):
    role: str = "member"
    count: int = 3
    rate: float = 1.5
    flag: bool = True
    off: bool = False
"""
    result = parse_schema(code)
    fields = {f["name"]: f for f in result["fields"]}
    assert fields["role"]["default"] == "member"
    assert fields["count"]["default"] == "3"
    assert fields["rate"]["default"] == "1.5"
    assert fields["flag"]["default"] == "true"
    assert fields["off"]["default"] == "false"


def test_parse_default_with_description_field():
    code = """
from pydantic import BaseModel, Field

class Config(BaseModel):
    role: str = Field(default="member", description="User role")
"""
    result = parse_schema(code)
    f = result["fields"][0]
    assert f["default"] == "member"
    assert f["description"] == "User role"


def test_parse_date_datetime_types():
    code = """
from pydantic import BaseModel
from datetime import date, datetime

class Rec(BaseModel):
    born: date
    seen: datetime
"""
    result = parse_schema(code)
    types = {f["name"]: f["type"] for f in result["fields"]}
    assert types["born"] == "date"
    assert types["seen"] == "datetime"


def test_parse_new_list_variants():
    code = """
from pydantic import BaseModel
from typing import List

class Rec(BaseModel):
    flags: List[bool]
    dates: List[date]
    stamps: List[datetime]
"""
    result = parse_schema(code)
    types = {f["name"]: f["type"] for f in result["fields"]}
    assert types["flags"] == "List[bool]"
    assert types["dates"] == "List[date]"
    assert types["stamps"] == "List[datetime]"


def test_parse_optional_list():
    code = """
from pydantic import BaseModel
from typing import List, Optional

class M(BaseModel):
    xs: Optional[List[int]] = None
"""
    result = parse_schema(code)
    f = result["fields"][0]
    assert f["type"] == "List[int]"
    assert f["optional"] is True
    assert f["default"] == ""
