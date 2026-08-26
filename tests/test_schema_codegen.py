import textwrap

from app.schema_codegen import build_code


def _dedent(s: str) -> str:
    return textwrap.dedent(s).strip("\n")


def test_simple_required_fields():
    fields = [
        {"name": "name", "type": "str"},
        {"name": "age", "type": "int"},
        {"name": "height", "type": "float"},
        {"name": "active", "type": "bool"},
    ]
    expected = _dedent(
        """
        from pydantic import BaseModel

        class User(BaseModel):
            name: str
            age: int
            height: float
            active: bool
        """
    )
    assert build_code("User", fields) == expected


def test_description_uses_field():
    fields = [{"name": "name", "type": "str", "description": "Full name"}]
    expected = _dedent(
        """
        from pydantic import BaseModel, Field

        class User(BaseModel):
            name: str = Field(description="Full name")
        """
    )
    assert build_code("User", fields) == expected


def test_optional_field_defaults_to_none():
    fields = [{"name": "nickname", "type": "str", "optional": True}]
    expected = _dedent(
        """
        from pydantic import BaseModel
        from typing import Optional

        class User(BaseModel):
            nickname: Optional[str] = None
        """
    )
    assert build_code("User", fields) == expected


def test_scalar_defaults():
    fields = [
        {"name": "role", "type": "str", "default": "member"},
        {"name": "count", "type": "int", "default": "3"},
        {"name": "rate", "type": "float", "default": "1.5"},
        {"name": "flag", "type": "bool", "default": "true"},
    ]
    expected = _dedent(
        """
        from pydantic import BaseModel

        class Config(BaseModel):
            role: str = "member"
            count: int = 3
            rate: float = 1.5
            flag: bool = True
        """
    )
    assert build_code("Config", fields) == expected


def test_default_with_description():
    fields = [{"name": "role", "type": "str", "default": "member", "description": "User role"}]
    expected = _dedent(
        """
        from pydantic import BaseModel, Field

        class Config(BaseModel):
            role: str = Field(default="member", description="User role")
        """
    )
    assert build_code("Config", fields) == expected


def test_date_datetime_and_new_lists():
    fields = [
        {"name": "born", "type": "date"},
        {"name": "seen", "type": "datetime"},
        {"name": "tags", "type": "List[str]"},
        {"name": "flags", "type": "List[bool]"},
        {"name": "dates", "type": "List[date]"},
    ]
    expected = _dedent(
        """
        from pydantic import BaseModel
        from typing import List
        from datetime import date, datetime

        class Rec(BaseModel):
            born: date
            seen: datetime
            tags: List[str]
            flags: List[bool]
            dates: List[date]
        """
    )
    assert build_code("Rec", fields) == expected


def test_nested_object_and_list_of_objects():
    fields = [
        {"name": "addr", "type": "Object", "children": [{"name": "street", "type": "str"}]},
        {"name": "items", "type": "List[Object]", "children": [{"name": "sku", "type": "str"}]},
    ]
    expected = _dedent(
        """
        from pydantic import BaseModel
        from typing import List

        class NestedModel1(BaseModel):
            street: str

        class NestedModel2(BaseModel):
            sku: str

        class Order(BaseModel):
            addr: NestedModel1
            items: List[NestedModel2]
        """
    )
    assert build_code("Order", fields) == expected


def test_optional_list():
    fields = [{"name": "xs", "type": "List[int]", "optional": True}]
    expected = _dedent(
        """
        from pydantic import BaseModel
        from typing import List, Optional

        class M(BaseModel):
            xs: Optional[List[int]] = None
        """
    )
    assert build_code("M", fields) == expected


def test_optional_with_description_uses_field_default_none():
    fields = [{"name": "note", "type": "str", "optional": True, "description": "Optional note"}]
    expected = _dedent(
        """
        from pydantic import BaseModel, Field
        from typing import Optional

        class M(BaseModel):
            note: Optional[str] = Field(default=None, description="Optional note")
        """
    )
    assert build_code("M", fields) == expected


def test_empty_model_uses_pass():
    expected = _dedent(
        """
        from pydantic import BaseModel

        class Empty(BaseModel):
            pass
        """
    )
    assert build_code("Empty", []) == expected


def test_bool_default_is_case_insensitive():
    fields = [
        {"name": "a", "type": "bool", "default": "true"},
        {"name": "b", "type": "bool", "default": "True"},
        {"name": "c", "type": "bool", "default": "false"},
        {"name": "d", "type": "bool", "default": "FALSE"},
    ]
    code = build_code("M", fields)
    assert "a: bool = True" in code
    assert "b: bool = True" in code
    assert "c: bool = False" in code
    assert "d: bool = False" in code
