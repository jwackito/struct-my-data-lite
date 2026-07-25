import ast
from typing import Any

SIMPLE_TYPES = {"str", "int", "float", "bool"}
LIST_SIMPLE_TYPES = {"List[str]", "List[int]", "List[float]"}
TYPE_MAP = {
    "str": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "date": "date",
    "List[str]": "List[str]",
    "List[float]": "List[float]",
    "List[int]": "List[int]",
}


def parse_schema(code: str) -> dict[str, Any]:
    tree = ast.parse(code)
    classes = _collect_base_model_classes(tree)
    if not classes:
        raise ValueError("No BaseModel subclass found")

    root_cls = classes[-1]
    class_map = {c.name: c for c in classes}

    fields = _parse_class_fields(root_cls, class_map)
    return {"model_name": root_cls.name, "fields": fields}


def _collect_base_model_classes(tree: ast.Module) -> list[ast.ClassDef]:
    classes = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and _is_base_model_subclass(node):
            classes.append(node)
    return classes


def _is_base_model_subclass(node: ast.ClassDef) -> bool:
    for base in node.bases:
        name = _get_name(base)
        if name == "BaseModel":
            return True
    return False


def _get_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _get_name(node.value)
    return ""


def _parse_class_fields(cls: ast.ClassDef, class_map: dict[str, ast.ClassDef]) -> list[dict]:
    fields = []
    for node in cls.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        field = _parse_field(node, class_map)
        if field:
            fields.append(field)
    return fields


def _parse_field(node: ast.AnnAssign, class_map: dict[str, ast.ClassDef]) -> dict | None:
    name = node.target.id
    annotation = node.annotation
    builder_type, children = _resolve_type(annotation, class_map)
    if builder_type is None:
        return None

    description = _extract_description(node.value)
    result = {"name": name, "type": builder_type, "description": description}
    if children:
        result["children"] = children
    return result


def _resolve_type(annotation: ast.AST | None, class_map: dict[str, ast.ClassDef]) -> tuple[str | None, list | None]:
    if annotation is None:
        return "str", None

    ann_str = _ast_to_type_str(annotation)

    if ann_str in SIMPLE_TYPES:
        return ann_str, None

    if ann_str in LIST_SIMPLE_TYPES:
        return ann_str, None

    if ann_str.startswith("Optional[") and ann_str.endswith("]"):
        inner = ann_str[9:-1]
        if inner in SIMPLE_TYPES:
            return inner, None
        if inner in LIST_SIMPLE_TYPES:
            return inner, None

    if ann_str == "Any" or ann_str == "dict" or ann_str == "Dict":
        return "str", None

    if ann_str.startswith("List["):
        inner = ann_str[5:-1]
        if inner in class_map:
            children = _parse_class_fields(class_map[inner], class_map)
            return "List[Object]", children
        return "List[str]", None

    if ann_str in class_map:
        children = _parse_class_fields(class_map[ann_str], class_map)
        return "Object", children

    return "str", None


def _extract_description(value: ast.AST | None) -> str:
    if value is None:
        return ""
    if isinstance(value, ast.Call) and _get_name(value.func) == "Field":
        for kw in value.keywords:
            if kw.arg == "description":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    return kw.value.value
    return ""


def _ast_to_type_str(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_ast_to_type_str(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        value = _ast_to_type_str(node.value)
        slice_str = _ast_to_type_str(node.slice)
        return f"{value}[{slice_str}]"
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Tuple):
        return ", ".join(_ast_to_type_str(e) for e in node.elts)
    return ""
