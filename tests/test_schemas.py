import re

import pytest

REGISTER = {
    "email": "schemas@example.com",
    "password": "password123",
}


@pytest.mark.asyncio
async def test_list_schemas_empty(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    r = await async_client.get("/schemas")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_schema(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    r = await async_client.post(
        "/schemas",
        json={"name": "Test Schema", "pydantic_schema": "class Test(BaseModel):\n    x: int"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["name"] == "Test Schema"


@pytest.mark.asyncio
async def test_create_schema_missing_name(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    r = await async_client.post("/schemas", json={"pydantic_schema": "class X(BaseModel): pass"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_schema_missing_code(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    r = await async_client.post("/schemas", json={"name": "X"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_schema(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    created = await async_client.post(
        "/schemas",
        json={"name": "GetTest", "pydantic_schema": "class A(BaseModel):\n    y: str"},
    )
    sid = created.json()["id"]
    r = await async_client.get(f"/schemas/{sid}")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "GetTest"
    assert "pydantic_schema" in data


@pytest.mark.asyncio
async def test_get_schema_not_found(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    r = await async_client.get("/schemas/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_schema(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    created = await async_client.post(
        "/schemas",
        json={"name": "Old", "pydantic_schema": "class O(BaseModel):\n    z: float"},
    )
    sid = created.json()["id"]
    r = await async_client.put(f"/schemas/{sid}", json={"name": "New"})
    assert r.status_code == 200
    r2 = await async_client.get(f"/schemas/{sid}")
    assert r2.json()["name"] == "New"


@pytest.mark.asyncio
async def test_delete_schema(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    created = await async_client.post(
        "/schemas",
        json={"name": "DelMe", "pydantic_schema": "class D(BaseModel):\n    v: int"},
    )
    sid = created.json()["id"]
    r = await async_client.delete(f"/schemas/{sid}")
    assert r.status_code == 200
    r2 = await async_client.get(f"/schemas/{sid}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_delete_not_found(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    r = await async_client.delete("/schemas/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_export_schema(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    created = await async_client.post(
        "/schemas",
        json={"name": "ExportTest", "pydantic_schema": "class E(BaseModel):\n    data: str"},
    )
    sid = created.json()["id"]
    r = await async_client.get(f"/schemas/{sid}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "structmydata-schema" in r.text
    assert "class E(BaseModel)" in r.text
    assert "ExportTest" in r.text


@pytest.mark.asyncio
async def test_import_schema_py(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    content = b"# name: Imported\nclass I(BaseModel):\n    val: int"
    r = await async_client.post(
        "/schemas/import",
        files={"file": ("myschema.py", content, "text/plain")},
    )
    assert r.status_code == 200
    sid = r.json()["id"]
    r2 = await async_client.get(f"/schemas/{sid}")
    assert "val: int" in r2.json()["pydantic_schema"]


@pytest.mark.asyncio
async def test_import_schema_json(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    content = b'{"name":"JSON Import","pydantic_schema":"class J(BaseModel):\\n    val: int"}'
    r = await async_client.post(
        "/schemas/import",
        files={"file": ("schema.json", content, "application/json")},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "JSON Import"


@pytest.mark.asyncio
async def test_import_schema_too_large(async_client):
    await async_client.post("/auth/register", json=REGISTER)
    content = b"x" * 10001
    r = await async_client.post(
        "/schemas/import",
        files={"file": ("big.py", content, "text/plain")},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_schema_duplicate_name_per_user(async_client):
    reg = await async_client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    body = {"name": "Dup", "pydantic_schema": "class D(BaseModel):\n    x: int"}
    first = await async_client.post("/schemas", json=body, headers=headers)
    assert first.status_code == 200
    second = await async_client.post("/schemas", json=body, headers=headers)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_create_schema_same_name_different_users(async_client):
    body = {"name": "Shared Name", "pydantic_schema": "class S(BaseModel):\n    x: int"}
    a = await async_client.post("/auth/register", json={"email": "same-a@example.com", "password": "password123"})
    b = await async_client.post("/auth/register", json={"email": "same-b@example.com", "password": "password123"})
    ra = await async_client.post("/schemas", json=body, headers={"Authorization": f"Bearer {a.json()['token']}"})
    rb = await async_client.post("/schemas", json=body, headers={"Authorization": f"Bearer {b.json()['token']}"})
    assert ra.status_code == 200
    assert rb.status_code == 200


@pytest.mark.asyncio
async def test_schema_ownership_enforced(async_client):
    body = {"name": "Private", "pydantic_schema": "class P(BaseModel):\n    x: int"}
    a = await async_client.post("/auth/register", json={"email": "own-a@example.com", "password": "password123"})
    b = await async_client.post("/auth/register", json={"email": "own-b@example.com", "password": "password123"})
    ha = {"Authorization": f"Bearer {a.json()['token']}"}
    hb = {"Authorization": f"Bearer {b.json()['token']}"}
    created = await async_client.post("/schemas", json=body, headers=ha)
    sid = created.json()["id"]
    assert (await async_client.get(f"/schemas/{sid}", headers=hb)).status_code == 404
    assert (await async_client.put(f"/schemas/{sid}", json={"name": "X"}, headers=hb)).status_code == 404
    assert (await async_client.delete(f"/schemas/{sid}", headers=hb)).status_code == 404
    assert (await async_client.get(f"/schemas/{sid}/export", headers=hb)).status_code == 404


def test_schema_ui_elements():
    with open("app/templates/index.html") as f:
        html = f.read()
    assert 'id="template-select"' in html
    assert 'id="template-save"' in html
    assert 'id="template-load"' in html
    assert 'id="template-delete"' in html
    assert 'id="template-export"' in html
    assert 'id="template-import"' in html
    assert 'id="template-import-input"' in html
    script_match = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert script_match
    assert "loadTemplateList" in script_match.group(1)
    assert "/schemas/import" in script_match.group(1)
