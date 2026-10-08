import pytest

from app.models import ModelRegistry, User
from app.providers.factory import authorize_model


@pytest.mark.asyncio
async def test_authorize_model_allows_valid_global_model(db_session):
    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    db_session.add(ModelRegistry(connection_id=None, model_name="qwen-test", enabled=True))
    await db_session.commit()

    result = await authorize_model(db_session, user, "ollama/ollama/qwen-test")
    assert result == ("ollama", "ollama", "qwen-test")
