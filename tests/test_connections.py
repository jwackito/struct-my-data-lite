from unittest.mock import MagicMock, patch

import pytest

from app.connections import test_connection


@pytest.mark.asyncio
@patch("app.connections.urllib.request.urlopen")
async def test_openai_connection_invalid_key(mock_urlopen, db_session):
    from urllib.error import HTTPError

    mock_urlopen.side_effect = HTTPError(
        "https://api.openai.com/v1/models", 401, "Unauthorized", {}, None
    )

    result = await test_connection(
        "my-openai",
        {"api_key": "sk-invalid", "base_url": ""},
        "openai",
        db_session,
    )

    assert result["ok"] is False
    assert "401" in str(result.get("error", ""))


@pytest.mark.asyncio
@patch("app.providers.openai.urllib.request.urlopen")
@patch("app.connections.urllib.request.urlopen")
async def test_openai_connection_valid_key(
    mock_conn_urlopen, mock_openai_urlopen, db_session
):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"data":[{"id":"gpt-4o-mini"},{"id":"gpt-4o"}]}'
    mock_conn_urlopen.return_value.__enter__.return_value = mock_resp
    mock_openai_urlopen.return_value.__enter__.return_value = mock_resp

    result = await test_connection(
        "my-openai",
        {"api_key": "sk-valid", "base_url": ""},
        "openai",
        db_session,
    )

    assert result["ok"] is True
    assert "openai/gpt-4o-mini" in result["models"]
    assert "openai/gpt-4o" in result["models"]


@pytest.mark.asyncio
@patch("app.connections.urllib.request.urlopen")
async def test_openai_connection_missing_key(mock_urlopen, db_session):
    result = await test_connection(
        "my-openai",
        {"base_url": ""},
        "openai",
        db_session,
    )

    assert result["ok"] is False
    assert "API key is required" in str(result.get("error", ""))


@pytest.mark.asyncio
@patch("app.connections.urllib.request.urlopen")
async def test_gemini_connection_invalid_key(mock_urlopen, db_session):
    from urllib.error import HTTPError

    mock_urlopen.side_effect = HTTPError(
        "https://generativelanguage.googleapis.com/v1/models",
        403,
        "Forbidden",
        {},
        None,
    )

    result = await test_connection(
        "my-gemini",
        {"api_key": "bad-key"},
        "gemini",
        db_session,
    )

    assert result["ok"] is False
    assert "403" in str(result.get("error", ""))
