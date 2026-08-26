NESTED_TYPES = ("Object", "List[Object]")


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _render_default(field_type: str, default: str) -> str:
    if field_type == "str":
        return '"' + _escape(default) + '"'
    if field_type == "bool":
        return "True" if default.strip().lower() in ("true", "1") else "False"
    return default


def build_code(model_name: str, fields: list[dict]) -> str:
    used = {"List": False, "Optional": False, "date": False, "datetime": False, "Field": False}

    def scan(flds):
        for f in flds:
            t = f.get("type", "str")
            if f.get("description"):
                used["Field"] = True
            if f.get("optional"):
                used["Optional"] = True
            if "List[" in t:
                used["List"] = True
            if t in ("date", "List[date]"):
                used["date"] = True
            if t in ("datetime", "List[datetime]"):
                used["datetime"] = True
            if t in NESTED_TYPES:
                scan(f.get("children", []))

    defs: list[str] = []
    counter = [0]

    def gen(cls_name: str, flds: list[dict]):
        lines = [f"class {cls_name}(BaseModel):"]
        if not flds:
            lines.append("    pass")
        for f in flds:
            t = f.get("type", "str")
            optional = f.get("optional", False)
            default = f.get("default", "")
            desc = f.get("description", "")
            if t in NESTED_TYPES:
                counter[0] += 1
                nested_name = f"NestedModel{counter[0]}"
                gen(nested_name, f.get("children", []))
                ann = nested_name if t == "Object" else f"List[{nested_name}]"
            else:
                ann = t
            if optional:
                ann = f"Optional[{ann}]"
            line = f"    {f['name']}: {ann}"
            has_default = default != ""
            if has_default and desc:
                rhs = f'Field(default={_render_default(t, default)}, description="{_escape(desc)}")'
            elif has_default:
                rhs = _render_default(t, default)
            elif optional:
                rhs = f'Field(default=None, description="{_escape(desc)}")' if desc else "None"
            elif desc:
                rhs = f'Field(description="{_escape(desc)}")'
            else:
                rhs = None
            if rhs is not None:
                line += f" = {rhs}"
            lines.append(line)
        defs.append("\n".join(lines))

    scan(fields)
    gen(model_name, fields)

    imports = ["from pydantic import BaseModel" + (", Field" if used["Field"] else "")]
    typing_parts = [p for p, on in (("List", used["List"]), ("Optional", used["Optional"])) if on]
    if typing_parts:
        imports.append("from typing import " + ", ".join(typing_parts))
    dt_parts = [p for p, on in (("date", used["date"]), ("datetime", used["datetime"])) if on]
    if dt_parts:
        imports.append("from datetime import " + ", ".join(dt_parts))

    return "\n".join(imports) + "\n\n" + "\n\n".join(defs)
