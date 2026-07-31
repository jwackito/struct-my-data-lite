from types import SimpleNamespace

from app.i18n import resolve_lang, t


def test_t_unknown_key_returns_key():
    assert t("This key does not exist", "es") == "This key does not exist"


def test_t_es_translation():
    assert t("Hello", "es") == "Hola"
