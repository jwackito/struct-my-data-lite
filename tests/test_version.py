import pytest

from app.version import get_version


def test_get_version_parses_first_heading(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## v1.2.3-lite (2026-01-01)\n\n### Added\n- x\n\n## v1.1.0-lite\n"
    )
    assert get_version(changelog) == "v1.2.3-lite"


def test_get_version_missing_file(tmp_path):
    assert get_version(tmp_path / "nope.md") == "dev"


def test_get_version_no_heading(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\nno versions yet\n")
    assert get_version(changelog) == "dev"


def test_get_version_matches_changelog_heading():
    import re
    from pathlib import Path

    text = Path("CHANGELOG.md").read_text(encoding="utf-8")
    expected = re.search(r"^## (v\S+)", text, re.MULTILINE).group(1)
    assert get_version() == expected


@pytest.mark.asyncio
async def test_api_version(client):
    response = await client.get("/api/version")
    assert response.status_code == 200
    assert response.json() == {"version": get_version()}


@pytest.mark.asyncio
async def test_license_route(client):
    response = await client.get("/LICENSE")
    assert response.status_code == 200
    assert "MIT License" in response.text
    assert "Purrfect AI" in response.text
