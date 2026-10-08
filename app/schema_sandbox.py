import ast
import builtins as _builtins

_ALLOWED_MODULES = {"pydantic", "typing", "datetime", "enum", "uuid", "decimal"}
_ALLOWED_CALLS = {"Field"}

_SAFE_BUILTIN_NAMES = (
    "__build_class__",
    "object",
    "super",
    "type",
    "staticmethod",
    "classmethod",
    "property",
    "isinstance",
    "issubclass",
    "list",
    "dict",
    "set",
    "frozenset",
    "tuple",
    "str",
    "int",
    "float",
    "bool",
    "bytes",
    "len",
    "min",
    "max",
    "sum",
    "abs",
    "round",
    "sorted",
    "range",
    "enumerate",
    "zip",
    "any",
    "all",
    "reversed",
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "AttributeError",
    "Exception",
)


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root not in _ALLOWED_MODULES:
        raise ImportError(f"Import of '{name}' is not allowed")
    return _builtins.__import__(name, globals, locals, fromlist, level)


def _restricted_builtins() -> dict:
    builtins = {name: getattr(_builtins, name) for name in _SAFE_BUILTIN_NAMES}
    builtins["__import__"] = _safe_import
    return builtins


def _check_identifier(name: str) -> None:
    if name.startswith("__"):
        raise ValueError(f"Name '{name}' is not allowed")


def _validate_import(node: ast.AST) -> None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root not in _ALLOWED_MODULES:
                raise ValueError(f"Import of '{alias.name}' is not allowed")
        return
    if node.level:
        raise ValueError("Relative imports are not allowed")
    root = (node.module or "").split(".")[0]
    if root not in _ALLOWED_MODULES:
        raise ValueError(f"Import from '{node.module}' is not allowed")
    for alias in node.names:
        if alias.name == "*":
            raise ValueError("Wildcard imports are not allowed")
        _check_identifier(alias.name)


def _validate_type_expr(node: ast.AST) -> None:
    if isinstance(node, ast.Name):
        _check_identifier(node.id)
        return
    if isinstance(node, ast.Attribute):
        _check_identifier(node.attr)
        _validate_type_expr(node.value)
        return
    if isinstance(node, ast.Subscript):
        _validate_type_expr(node.value)
        _validate_type_expr(node.slice)
        return
    if isinstance(node, ast.Tuple):
        for elt in node.elts:
            _validate_type_expr(elt)
        return
    if isinstance(node, ast.Constant):
        return
    raise ValueError(f"Unsupported type expression: {type(node).__name__}")


def _validate_value(node: ast.AST) -> None:
    if isinstance(node, ast.Constant):
        return
    if isinstance(node, ast.Name):
        _check_identifier(node.id)
        return
    if isinstance(node, ast.Attribute):
        _check_identifier(node.attr)
        _validate_value(node.value)
        return
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for elt in node.elts:
            _validate_value(elt)
        return
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if key is not None:
                _validate_value(key)
            _validate_value(value)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        _validate_value(node.operand)
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_CALLS:
            raise ValueError("Only Field(...) calls are allowed as values")
        for arg in node.args:
            _validate_value(arg)
        for kw in node.keywords:
            if kw.arg is not None:
                _check_identifier(kw.arg)
            _validate_value(kw.value)
        return
    raise ValueError(f"Unsupported value: {type(node).__name__}")


def _validate_targets(targets: list[ast.AST]) -> None:
    for target in targets:
        if not isinstance(target, ast.Name):
            raise ValueError("Only simple names may be assigned")
        _check_identifier(target.id)


def _validate_ann_assign(node: ast.AnnAssign) -> None:
    if not isinstance(node.target, ast.Name):
        raise ValueError("Only simple names may be annotated")
    _check_identifier(node.target.id)
    _validate_type_expr(node.annotation)
    if node.value is not None:
        _validate_value(node.value)


def _validate_class_body(stmt: ast.AST) -> None:
    if isinstance(stmt, ast.Pass):
        return
    if isinstance(stmt, ast.Expr):
        if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            return
        raise ValueError("Only docstrings are allowed as model expressions")
    if isinstance(stmt, ast.AnnAssign):
        _validate_ann_assign(stmt)
        return
    if isinstance(stmt, ast.Assign):
        _validate_targets(stmt.targets)
        _validate_value(stmt.value)
        return
    raise ValueError(f"Unsupported statement in model: {type(stmt).__name__}")


def _validate_class(node: ast.ClassDef) -> None:
    if node.decorator_list:
        raise ValueError("Decorators are not allowed")
    if not node.bases:
        raise ValueError("Models must subclass BaseModel")
    for base in node.bases:
        if not (isinstance(base, ast.Name) and base.id == "BaseModel"):
            raise ValueError("Only BaseModel subclasses are allowed")
    for stmt in node.body:
        _validate_class_body(stmt)


def validate_schema(code: str) -> None:
    tree = ast.parse(code)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _validate_import(node)
        elif isinstance(node, ast.ClassDef):
            _validate_class(node)
        elif isinstance(node, ast.Assign):
            _validate_targets(node.targets)
            _validate_value(node.value)
        elif isinstance(node, ast.AnnAssign):
            _validate_ann_assign(node)
        elif isinstance(node, ast.Pass):
            continue
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        else:
            raise ValueError(f"Unsupported statement: {type(node).__name__}")


def safe_exec(code: str, namespace: dict | None = None) -> dict:
    validate_schema(code)
    ns = namespace if namespace is not None else {}
    ns.setdefault("__name__", "<schema>")
    ns["__builtins__"] = _restricted_builtins()
    exec(compile(code, "<schema>", "exec"), ns)
    return ns
