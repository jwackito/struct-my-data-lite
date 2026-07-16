import re


def test_builder_nested_add_field_direct_child_only():
    with open("app/templates/index.html") as f:
        html = f.read()
    script_match = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert script_match, "No inline <script> block found"
    script = script_match.group(1)

    bad = re.findall(r'querySelector\(["\']\.nested-add-field["\']\)', script)
    assert not bad, (
        f"Found {len(bad)} unscoped querySelector('.nested-add-field'). "
        "Must scope to direct children only (use :scope > or iterate container.children)."
    )
