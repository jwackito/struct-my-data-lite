from types import SimpleNamespace

from app.i18n import resolve_lang, t


def test_t_unknown_key_returns_key():
    assert t("This key does not exist", "es") == "This key does not exist"


def test_t_es_translation():
    assert t("Hello", "es") == "Hola"


def test_t_en_fallback_for_missing_es_key(monkeypatch):
    from app import i18n

    monkeypatch.setitem(i18n.DICTS["es"], "Hello", None)
    assert t("Hello", "es") == "Hello"


def test_t_interpolation():
    assert t("Hello {name}", "es", name="Mundo") == "Hola Mundo"


def test_es_covers_all_en_keys():
    from app.i18n import DICTS

    assert set(DICTS["es"].keys()) == set(DICTS["en"].keys())


def test_translations_have_no_empty_values():
    from app.i18n import DICTS

    for lang in ("en", "es"):
        for key, value in DICTS[lang].items():
            assert value.strip(), f"empty translation for {key!r} in {lang}"


def test_resolve_lang_cookie_wins():
    request = SimpleNamespace(
        cookies={"lang": "es"},
        headers={"accept-language": "en-US,en;q=0.9"},
    )
    assert resolve_lang(request) == "es"
