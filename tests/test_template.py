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


def _html():
    with open("app/templates/index.html") as f:
        return f.read()


def _script():
    match = re.search(r"<script>(.*?)</script>", _html(), re.DOTALL)
    assert match, "No inline <script> block found"
    return match.group(1)


def test_code_tab_and_generate_button_removed():
    html = _html()
    assert 'data-tab="code"' not in html, "Code tab must be removed from the tab bar"
    assert 'id="generate-code"' not in html, "Generate Code button must be removed"


def test_schema_field_still_submitted():
    assert 'name="pydantic_schema"' in _html(), "pydantic_schema input must remain in the form"


def test_advanced_debug_panel_present():
    html = _html()
    for marker in ('id="advanced-toggle"', 'id="advanced-panel"', 'id="advanced-status"',
                   'id="code-from-builder"', 'id="code-to-builder"'):
        assert marker in html, f"Missing {marker} in Advanced debug panel"


def test_submit_generates_schema_from_builder():
    script = _script()
    assert "manualCode" in script, "manualCode source-of-truth flag missing"
    assert "buildSchemaCode" in script, "client-side codegen buildSchemaCode missing"
    assert "htmx:configRequest" in script, "submit hook must regenerate schema before request"
    assert re.search(r"parameters\.pydantic_schema", script), "submit must set pydantic_schema parameter"


def test_js_codegen_emits_parity_constructs():
    script = _script()
    assert "Optional[" in script, "codegen must emit Optional[...] for optional fields"
    assert "from datetime import" in script, "codegen must import date/datetime"
    assert "Field(default=" in script, "codegen must emit Field(default=...) for default+description"
    assert '"date"' in script and '"datetime"' in script, "type set must include date and datetime"


def test_logged_in_user_name_injected():
    with open("app/static/i18n.js") as f:
        js = f.read()
    assert "buildUserBadge" in js, "user badge builder missing from i18n.js"
    assert 'fetch("/auth/me")' in js, "user badge must fetch /auth/me"
    assert "u.display_name || u.email" in js, "user badge must fall back to email"
    assert "/auth/logout" in js, "user badge must target the logout link"
